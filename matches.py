from discord import Embed, Color, File
from discord.ext import commands
from discord.ext.commands import cooldown, BucketType, CommandOnCooldown
from data import dbconn
from utils import cf_api, paginator
import discord
import time
from operator import itemgetter

from io import BytesIO
import asyncio
import matplotlib.pyplot as plt
import os


async def send_message(ctx, message):
    await ctx.send(embed=discord.Embed(description=message, color=discord.Color.gold()))


async def plot_gaph(ctx, data, handle):
    x_axis, y_axis = [], []
    for i in range(0, len(data)):
        x_axis.append(i+1)
        y_axis.append(data[i])
    ends = [-100000, 1300, 1400, 1500, 1600, 1700, 1750, 1800, 1850, 1900, 100000]
    colors = ['#CCCCCC', '#77FF77', '#77DDBB', '#AAAAFF', '#FF88FF', '#FFCC88', '#FFBB55', '#FF7777', '#FF3333',
              '#AA0000']
    plt.plot(x_axis, y_axis, linestyle='-', marker='o', markersize=3, markerfacecolor='white', markeredgewidth=0.5)
    ymin, ymax = plt.gca().get_ylim()
    bgcolor = plt.gca().get_facecolor()
    for i in range(1, 11):
        plt.axhspan(ends[i - 1], ends[i], facecolor=colors[i - 1], alpha=0.8, edgecolor=bgcolor, linewidth=0.5)
    locs, labels = plt.xticks()
    for loc in locs:
        plt.axvline(loc, color=bgcolor, linewidth=0.5)
    plt.ylim(min(1250, ymin-100), max(ymax + 100, 1650))
    plt.legend(["%s (%d)" % (handle, y_axis[-1])], loc='upper left')


    filename = "%s.png" % str(ctx.message.id)
    plt.savefig(filename)
    with open(filename, 'rb') as file:
        discord_file = File(BytesIO(file.read()), filename='plot.png')
    os.remove(filename)
    plt.clf()
    plt.close()
    embed = Embed(title="Match rating for for %s" % handle, color=Color.blue())
    embed.set_image(url="attachment://plot.png")
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.avatar_url)
    await ctx.channel.send(embed=embed, file=discord_file)


class Matches(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.cf = cf_api.CodeforcesAPI()

    def make_match_embed(self, ctx):
        desc = "Information about Matches related commands! **[use .match <command>]**\n\n"
        match = self.client.get_command('match')

        for cmd in match.commands:
            desc += f"`{cmd.name}`: **{cmd.brief}**\n"
        embed = discord.Embed(description=desc, color=discord.Color.dark_magenta())
        embed.set_author(name="Lockout commands help", icon_url=ctx.me.avatar_url)
        embed.set_footer(
            text="Use the prefix . before each command. For detailed usage about a particular command, type .help match <command>")
        embed.add_field(name="GitHub repository", value=f"[GitHub](https://github.com/pseudocoder10/Lockout-Bot)",
                        inline=True)
        embed.add_field(name="Bot Invite link",
                        value=f"[Invite](https://discord.com/oauth2/authorize?client_id=669978762120790045&permissions=0&scope=bot)",
                        inline=True)
        embed.add_field(name="Support Server", value=f"[Server](https://discord.gg/xP2UPUn)",
                        inline=True)
        return embed

    @commands.group(brief='Commands related to matches. Type .match for more details', invoke_without_command=True)
    async def match(self, ctx):
        await ctx.send(embed=self.make_match_embed(ctx))

    @match.command(brief="Challenge someone to a match")
    async def challenge(self, ctx, member:discord.Member, rating: int=None):
        if rating is None:
            await send_message(ctx, "Pls specify a rating to before challenging. Example: `.match challenge @bhavya 1800`")
            return
        if member.id == ctx.author.id:
            await send_message(ctx, "You cannot challenge yourself!!")
            return
        if not self.db.handle_in_db(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "Set your handle first before challenging someone")
            return
        if not self.db.handle_in_db(ctx.guild.id, member.id):
            await send_message(ctx, f"Handle for your opponent {member.mention} not set")
            return
        if self.db.is_challenging(ctx.guild.id, ctx.author.id) or self.db.is_challenged(ctx.guild.id, ctx.author.id) or self.db.in_a_match(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "You are already challenging someone/being challenged/in a match. Pls try again later")
            return
        if self.db.is_challenging(ctx.guild.id, member.id) or self.db.is_challenged(ctx.guild.id, member.id) or self.db.in_a_match(ctx.guild.id, member.id):
            await send_message(ctx, "Your opponent is already challenging someone/being challenged/in a match. Pls try again later")
            return
        if rating not in range(0, 4200):
            await send_message(ctx, "Invalid Rating Range")
            return
        rating = rating - rating%100

        duration = 0
        try:
            await ctx.send(f"{ctx.author.mention}, enter the duration of the match in minutes between [5, 180]")
            message = await self.client.wait_for('message', timeout=30, check=lambda message: message.author == ctx.author)
            if not message.content.isdigit():
                await ctx.send(f"That's not a valid integer! Match invalidated {ctx.author.mention}")
                return
            duration = int(message.content)
            if duration not in range(5, 181):
                await ctx.send(f"Enter an integer between **5** and **180**! Match invalidated")
                return
        except asyncio.TimeoutError:
            await ctx.send(f"You took too long to decide! Match invalidated {ctx.author.mention}")
            return

        await ctx.send(f"{ctx.author.mention} has challenged {member.mention} to a match with problem ratings from {rating} to {rating+400} and lasting {duration} minutes. Type `.match accept` within 60 seconds to accept")
        tme = int(time.time())
        self.db.add_to_challenge(ctx.guild.id, ctx.author.id, member.id, rating, tme, ctx.channel.id, duration)
        await asyncio.sleep(60)
        if self.db.is_challenging(ctx.guild.id, ctx.author.id, tme):
            await ctx.send(f"{ctx.author.mention} your time to challenge {member.mention} has expired.")
            self.db.remove_challenge(ctx.guild.id, ctx.author.id)

    @match.command(brief="Withdraw your challenge")
    async def withdraw(self, ctx):
        if not self.db.is_challenging(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "You are not challenging anyone")
            return
        self.db.remove_challenge(ctx.guild.id, ctx.author.id)
        await ctx.send(f"Challenge by {ctx.author.mention} has been removed")

    @match.command(brief="Decline a challenge")
    async def decline(self, ctx):
        if not self.db.is_challenged(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "Noone is challenging you")
            return
        self.db.remove_challenge(ctx.guild.id, ctx.author.id)
        await ctx.send(f"Challenge to {ctx.author.mention} has been removed")

    @match.command(brief="Accept a challenge")
    async def accept(self, ctx):
        if not self.db.is_challenged(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "Noone is challenging you")
            return
        await ctx.send(embed=Embed(description=f"Preparing to start the match...", color=Color.green()))
        resp = await self.db.add_to_ongoing(ctx, ctx.guild.id, ctx.author.id)
        if not resp[0]:
            await send_message(ctx, resp[1])
            return
        data = resp[1]
        await asyncio.sleep(5)
        pname = ""
        prating = ""
        for x in data:
            pname += f"[{x[2]}](https://codeforces.com/problemset/problem/{x[0]}/{x[1]})\n"
            prating += f"{x[4]}\n"
        embed = Embed(color=Color.green())
        embed.set_author(name="Problems")
        embed.add_field(name="Points", value="100\n200\n300\n400\n500", inline=True)
        embed.add_field(name="Problem Name", value=pname, inline=True)
        embed.add_field(name="Rating", value=prating, inline=True)
        embed.set_footer(text=f"Time left: {resp[2]} minutes 0 seconds")
        await ctx.send(embed=embed)

    @match.command(brief="Invalidate a match (Admin Only)")
    @commands.has_any_role('Admin', 'Moderator')
    async def _invalidate(self, ctx, member: discord.Member):
        if not self.db.in_a_match(ctx.guild.id, member.id):
            await send_message(ctx, f"User {member.mention} is not in a match.")
            return
        self.db.delete_match(ctx.guild.id, member.id)
        await ctx.send(embed=discord.Embed(description="Match has been invalidated", color=discord.Color.green()))

    @match.command(brief="Invalidate your match", aliases=["forfeit", "cancel"])
    async def invalidate(self, ctx):
        if not self.db.in_a_match(ctx.guild.id, ctx.author.id):
            await send_message(ctx, f"User {ctx.author.mention} is not in a match.")
            return
        opponent = ctx.guild.get_member(self.db.get_opponent(ctx.guild.id, ctx.author.id))
        await ctx.send(f"{opponent.mention} you opponent {ctx.author.mention} has proposed to forfeit the match, type `yes` within 30 seconds to accept")

        try:
            message = await self.client.wait_for('message', timeout=30, check=lambda message: message.author == opponent and message.content.lower() == 'yes')
            self.db.delete_match(ctx.guild.id, ctx.author.id)
            await ctx.send(embed=discord.Embed(description=f"{ctx.author.mention} {opponent.mention}, match has been invalidated", color=discord.Color.green()))
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention} your opponent didn't respond in time")

    @match.command(brief="Give victory to someone (Admin Only)")
    @commands.has_any_role('Admin', 'Moderator')
    async def forcewin(self, ctx, member: discord.Member):
        if not self.db.in_a_match(ctx.guild.id, member.id):
            await send_message(ctx, f"User {member.mention} is not in a match.")
            return
        self.db.forcewin(ctx.guild.id, member.id)
        await ctx.send(f"{member.mention} has been awarded victory")

    @match.command(brief="Display ongoing matches")
    async def ongoing(self, ctx):
        data = self.db.get_ongoing(ctx.guild.id)
        if len(data) == 0:
            await send_message(ctx, "No ongoing matches")
            return
        data.reverse()
        await paginator.Paginator(data, ["S.No", "Handle1", "Handle2", "Rating", "Time spent", "Points"], f"Ongoing matches", 10).paginate(ctx, self.client)

    @match.command(brief="Show recent matches")
    async def recent(self, ctx, member: discord.Member=None):
        if not member:
            data = self.db.get_finished(ctx.guild.id)
            if len(data) == 0:
                await send_message(ctx, "No recent matches")
                return
            data.reverse()
            await paginator.Paginator(data, ["S.No", "Handle1", "Handle2", "Rating", "Duration", "Result"],
                                      f"Recent Matches", 10).paginate(ctx, self.client)
        else:
            data = self.db.get_user_finished(ctx.guild.id, member.id)
            if len(data) == 0:
                await send_message(ctx, f"No recent matches played by {member.name}")
                return
            data.reverse()
            await paginator.Paginator(data, ["S.No", "Handle1", "Handle2", "Rating", "Duration", "Result"],
                                      f"Recent Matches played by {member.name}", 10).paginate(ctx, self.client)

    @match.command(brief="Show problems left from your ongoing match")
    async def problems(self, ctx, member: discord.Member=None):
        if member is None:
            member = ctx.author
        if not self.db.in_a_match(ctx.guild.id, member.id):
            await send_message(ctx, f"User {member.mention} is not in a match!")
            return
        await ctx.send(embed=self.db.show_problems(ctx.guild.id, member.id))

    @match.command(brief="Update matches status for the server")
    @cooldown(1, 60, BucketType.guild)
    async def update(self, ctx):
        await self.db.update_matches(self.client, ctx)

    @update.error
    async def update_error(self, ctx, exc):
        if isinstance(exc, CommandOnCooldown):
            await ctx.send(embed=discord.Embed(description=f"Slow down!\nThe cooldown of command is **60s**, pls retry after **{exc.retry_after:,.2f}s**", color=discord.Color.red()))

    @match.command(brief="View someone's profile")
    async def profile(self, ctx, member: discord.Member=None):
        if member is None:
            member = ctx.author
        if not self.db.handle_in_db(ctx.guild.id, member.id):
            await send_message(ctx, f"User {member.mention} has not set their handle")
            return
        data = self.db.get_profile(ctx.guild.id, member.id)
        wins, loss, draw = 0, 0, 0
        handle = self.db.get_handle(ctx.guild.id, member.id)
        distrib = [0, 0, 0, 0, 0]
        points = 0
        n = len(data)
        fastest, rate = 1000000000, 0

        for x in data:
            if x[1] == member.id:
                if x[6] in [1, 3]:
                    wins += 1
                    if x[4] < fastest:
                        fastest = x[4]
                        rate = x[3]
                if x[6] in [2, 4]:
                    loss += 1
                if x[6] == 0:
                    draw += 1
                for i in range(0, 5):
                    if x[5][i] == '1':
                        distrib[i] += 1
                        points += (i+1)*100
            else:
                if x[6] in [2, 4]:
                    wins += 1
                    if x[4] < fastest:
                        fastest = x[4]
                        rate = x[3]
                if x[6] in [1, 3]:
                    loss += 1
                if x[6] == 0:
                    draw += 1
                for i in range(0, 5):
                    if x[5][i] == '2':
                        distrib[i] += 1
                        points += (i+1)*100

        fast = ""
        av = 0
        if n !=0:
            av = points/n
        if fastest == 1000000000:
            fast = "NIL"
        else:
            fast = f"{int(fastest/60)}m {fastest%60}s [{rate} Rating]"

        embed = discord.Embed(description=f"Profile for user {member.mention}", color=discord.Color.dark_blue())
        embed.add_field(name="Handle", value=f"[{handle}](https://codeforces.com/profile/{handle})", inline=False)
        embed.add_field(name="Wins", value=str(wins), inline=True)
        embed.add_field(name="Draws", value=str(draw), inline=True)
        embed.add_field(name="Losses", value=str(loss), inline=True)
        embed.add_field(name="Problem Points", value="100\n200\n300\n400\n500", inline=True)
        embed.add_field(name="Times Solved", value=f"{distrib[0]}\n{distrib[1]}\n{distrib[2]}\n{distrib[3]}\n{distrib[4]}\n", inline=True)
        embed.add_field(name="Average Points", value=f"{int(av)}", inline=False)
        embed.add_field(name="Fastest Time", value=fast, inline=True)
        await ctx.send(embed=embed)

    @match.command(brief="Plot match rating")
    async def rating(self, ctx, member: discord.Member=None):
        if member is None:
            member = ctx.author
        data = self.db.get_match_rating(ctx.guild.id, member.id)
        try:
            self.db.get_handle(ctx.guild.id, member.id)
        except Exception:
            await send_message(ctx, f"Handle for user {member.mention} not set")
            return
        if len(data) <= 1:
            await ctx.send(embed=discord.Embed(description=f"User {member.mention} is unrated! Compete in matches to become rated"))
            return
        await plot_gaph(ctx, data[1:], self.db.get_handle(ctx.guild.id, member.id))

    @match.command(brief="Show match ratings of all the users")
    async def ranklist(self, ctx):
        data = self.db.get_ranklist(ctx)
        print(data)
        if len(data) == 0:
            await send_message(ctx, "No rated user in the server")
            return
        data = sorted(data, key=itemgetter(1), reverse=True)
        data = [[x[0], str(x[1])] for x in data]
        await paginator.Paginator(data, ["User", "Rating"], f"Match Ratings", 10).paginate(ctx, self.client)


def setup(client):
    client.add_cog(Matches(client))