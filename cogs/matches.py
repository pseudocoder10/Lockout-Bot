import asyncio
import matplotlib.pyplot as plt
import os
import math
import discord
import time
import traceback

from discord import Embed, Color, File
from discord.ext import commands
from discord.ext.commands import cooldown, BucketType
from operator import itemgetter
from io import BytesIO

from data import dbconn
from utils import cf_api, paginator, discord_, codeforces, updation, elo
from constants import BOT_INVITE, GITHUB_LINK, SERVER_INVITE, ADMIN_PRIVILEGE_ROLES, AUTO_UPDATE_TIME

LOWER_RATING = 800
UPPER_RATING = 3600
MATCH_DURATION = [5, 180]
RESPONSE_WAIT_TIME = 30
ONGOING_PER_PAGE = 10
RECENT_PER_PAGE = 5


async def plot_graph(ctx, data, handle):
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


async def get_time_response(client, ctx, message, time, author, range_):
    await ctx.send(message)

    def check(m):
        if not m.content.isdigit() or not m.author == author:
            return False
        i = m.content
        if int(i) < range_[0] or int(i) > range_[1]:
            return False
        return True
    try:
        msg = await client.wait_for('message', timeout=time, check=check)
        return [True, int(msg.content)]
    except asyncio.TimeoutError:
        return [False]


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
        embed.add_field(name="GitHub repository", value=f"[GitHub]({GITHUB_LINK})",
                        inline=True)
        embed.add_field(name="Bot Invite link",
                        value=f"[Invite]({BOT_INVITE})",
                        inline=True)
        embed.add_field(name="Support Server", value=f"[Server]({SERVER_INVITE})",
                        inline=True)
        return embed

    @commands.group(brief='Commands related to matches. Type .match for more details', invoke_without_command=True)
    async def match(self, ctx):
        await ctx.send(embed=self.make_match_embed(ctx))

    @match.command(brief="Challenge someone to a match")
    async def challenge(self, ctx, member:discord.Member, rating: int):
        if member.id == ctx.author.id:
            await discord_.send_message(ctx, "You cannot challenge yourself!!")
            return
        if not self.db.get_handle(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, "Set your handle first before challenging someone")
            return
        if not self.db.get_handle(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"Handle for your opponent {member.mention} not set")
            return
        if self.db.is_challenging(ctx.guild.id, ctx.author.id) or self.db.is_challenged(ctx.guild.id, ctx.author.id) or self.db.in_a_match(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, "You are already challenging someone/being challenged/in a match. Pls try again later")
            return
        if self.db.is_challenging(ctx.guild.id, member.id) or self.db.is_challenged(ctx.guild.id, member.id) or self.db.in_a_match(ctx.guild.id, member.id):
            await discord_.send_message(ctx, "Your opponent is already challenging someone/being challenged/in a match. Pls try again later")
            return
        if rating not in range(LOWER_RATING, UPPER_RATING - 400 + 1):
            await discord_.send_message(ctx, f"Invalid Rating Range, enter an integer between {LOWER_RATING}-{UPPER_RATING-400}")
            return
        rating = rating - rating % 100
        resp = await get_time_response(self.client, ctx,
                                       f"{ctx.author.mention}, enter the duration of the match in minutes between {MATCH_DURATION}",
                                       RESPONSE_WAIT_TIME, ctx.author, MATCH_DURATION)
        if not resp[0]:
            await ctx.send(f"You took too long to decide! Match invalidated {ctx.author.mention}")
            return

        duration = resp[1]

        await ctx.send(f"{ctx.author.mention} has challenged {member.mention} to a match with problem ratings from "
                       f"{rating} to {rating+400} and lasting {duration} minutes. Type `.match accept` within 60 seconds to accept")
        tme = int(time.time())
        self.db.add_to_challenge(ctx.guild.id, ctx.author.id, member.id, rating, tme, ctx.channel.id, duration)
        await asyncio.sleep(60)
        if self.db.is_challenging(ctx.guild.id, ctx.author.id, tme):
            await ctx.send(f"{ctx.author.mention} your time to challenge {member.mention} has expired.")
            self.db.remove_challenge(ctx.guild.id, ctx.author.id)

    @match.command(brief="Withdraw your challenge")
    async def withdraw(self, ctx):
        if not self.db.is_challenging(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, "You are not challenging anyone")
            return
        self.db.remove_challenge(ctx.guild.id, ctx.author.id)
        await ctx.send(f"Challenge by {ctx.author.mention} has been removed")

    @match.command(brief="Decline a challenge")
    async def decline(self, ctx):
        if not self.db.is_challenged(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, "No-one is challenging you")
            return
        self.db.remove_challenge(ctx.guild.id, ctx.author.id)
        await ctx.send(f"Challenge to {ctx.author.mention} has been removed")

    @match.command(brief="Accept a challenge")
    async def accept(self, ctx):
        if not self.db.is_challenged(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, "No-one is challenging you")
            return
        embed = Embed(description=f"Preparing to start the match...", color=Color.green())
        embed.set_footer(text=f"You can now conduct tournaments using the bot.\n"
                              f"Type .tournament faq for more info")
        await ctx.send(embed=embed)

        data = self.db.get_challenge_info(ctx.guild.id, ctx.author.id)
        self.db.remove_challenge(ctx.guild.id, ctx.author.id)

        handle1, handle2 = self.db.get_handle(ctx.guild.id, data.p1_id), self.db.get_handle(ctx.guild.id, data.p2_id)
        problems = await codeforces.find_problems([handle1, handle2], [data.rating + i*100 for i in range(0, 5)])

        if not problems[0]:
            await discord_.send_message(ctx, problems[1])
            return

        problems = problems[1]
        self.db.add_to_ongoing(data, int(time.time()), problems)

        match_info = self.db.get_match_info(ctx.guild.id, ctx.author.id)
        await ctx.send(embed=discord_.match_problems_embed(match_info))
    
    @match.command(brief="Invalidate a match (Admin/Mod/Lockout Manager only)")
    async def _invalidate(self, ctx, member: discord.Member):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx, f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                    f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return
        if not self.db.in_a_match(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"User {member.mention} is not in a match.")
            return
        self.db.delete_match(ctx.guild.id, member.id)
        await ctx.send(embed=discord.Embed(description="Match has been invalidated", color=discord.Color.green()))

    @match.command(brief="Invalidate your match", aliases=["forfeit", "cancel"])
    async def invalidate(self, ctx):
        if not self.db.in_a_match(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, f"User {ctx.author.mention} is not in a match.")
            return
        match_info = self.db.get_match_info(ctx.guild.id, ctx.author.id)
        opponent = await discord_.fetch_member(ctx.guild, match_info.p1_id if match_info.p1_id != ctx.author.id else match_info.p2_id)
        await ctx.send(f"{opponent.mention} you opponent {ctx.author.mention} has proposed to forfeit the match, type `yes` within 30 seconds to accept")

        try:
            message = await self.client.wait_for('message', timeout=30, check=lambda message: message.author == opponent and message.content.lower() == 'yes' and message.channel.id == ctx.channel.id)
            self.db.delete_match(ctx.guild.id, ctx.author.id)
            await ctx.send(embed=discord.Embed(description=f"{ctx.author.mention} {opponent.mention}, match has been invalidated", color=discord.Color.green()))
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention} your opponent didn't respond in time")

    @match.command(brief="Draw your current match")
    async def draw(self, ctx):
        if not self.db.in_a_match(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, f"User {ctx.author.mention} is not in a match.")
            return
        match = self.db.get_match_info(ctx.guild.id, ctx.author.id)
        opponent = await discord_.fetch_member(ctx.guild,
                                               match.p1_id if match.p1_id != ctx.author.id else match.p2_id)
        await ctx.send(
            f"{opponent.mention} you opponent {ctx.author.mention} has proposed to draw the match, type `yes` within 30 seconds to accept")

        try:
            message = await self.client.wait_for('message', timeout=30, check=lambda
                message: message.author == opponent and message.content.lower() == 'yes' and message.channel.id == ctx.channel.id)
            channel = self.client.get_channel(match.channel)
            a, b = updation.match_score("00000")
            p1_rank, p2_rank = 1 if a >= b else 2, 1 if b >= a else 2
            ranklist = []
            ranklist.append([await discord_.fetch_member(ctx.guild, match.p1_id), p1_rank,
                                 self.db.get_match_rating(ctx.guild.id, match.p1_id)[-1]])
            ranklist.append([await discord_.fetch_member(ctx.guild, match.p2_id), p2_rank,
                                 self.db.get_match_rating(ctx.guild.id, match.p2_id)[-1]])
            ranklist = sorted(ranklist, key=itemgetter(1))
            res = elo.calculateChanges(ranklist)

            self.db.add_rating_update(ctx.guild.id, match.p1_id, res[match.p1_id][0])
            self.db.add_rating_update(ctx.guild.id, match.p2_id, res[match.p2_id][0])
            self.db.delete_match(match.guild, match.p1_id)
            self.db.add_to_finished(match, "00000")

            embed = discord.Embed(color=discord.Color.dark_magenta())
            pos, name, ratingChange = '', '', ''
            for user in ranklist:
                pos += f"{':first_place:' if user[1] == 1 else ':second_place:'}\n"
                name += f"{user[0].mention}\n"
                ratingChange += f"{res[user[0].id][0]} (**{'+' if res[user[0].id][1] >= 0 else ''}{res[user[0].id][1]}**)\n"
            embed.add_field(name="Position", value=pos)
            embed.add_field(name="User", value=name)
            embed.add_field(name="Rating changes", value=ratingChange)
            embed.set_author(name=f"Match over! Final standings\nScore: {a}-{b}")
            await channel.send(embed=embed)
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention} your opponent didn't respond in time")

    @match.command(brief="Display ongoing matches")
    async def ongoing(self, ctx):
        data = self.db.get_all_matches(ctx.guild.id)
        if len(data) == 0:
            await discord_.send_message(ctx, "No ongoing matches")
            return
        content = discord_.ongoing_matches_embed(data)

        currPage = 0
        totPage = math.ceil(len(content) / ONGOING_PER_PAGE)
        text = '\n'.join(content[currPage * ONGOING_PER_PAGE: min(len(content), (currPage+1)*ONGOING_PER_PAGE)])
        embed = discord.Embed(description=text, color=discord.Color.gold())
        embed.set_author(name="Ongoing matches")
        embed.set_footer(text=f"Page {currPage+1} of {totPage}")
        message = await ctx.send(embed=embed)

        await message.add_reaction("⏮")
        await message.add_reaction("◀")
        await message.add_reaction("▶")
        await message.add_reaction("⏭")

        def check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji in ["⏮", "◀", "▶", "⏭"] and user != self.client.user

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=90, check=check)
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                if reaction.emoji == "⏮":
                    currPage = 0
                elif reaction.emoji == "◀":
                    currPage = max(currPage-1, 0)
                elif reaction.emoji == "▶":
                    currPage = min(currPage+1, totPage-1)
                else:
                    currPage = totPage-1
                text = '\n'.join(content[currPage * ONGOING_PER_PAGE: min(len(content), (currPage + 1) * ONGOING_PER_PAGE)])
                embed = discord.Embed(description=text, color=discord.Color.gold())
                embed.set_author(name="Ongoing matches")
                embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
                await message.edit(embed=embed)

            except asyncio.TimeoutError:
                break

    @match.command(brief="Show recent matches")
    async def recent(self, ctx, member: discord.Member=None):
        data = self.db.get_recent_matches(ctx.guild.id, member.id if member else None)
        if len(data) == 0:
            await discord_.send_message(ctx, "No recent matches")
            return

        content = discord_.recent_matches_embed(data)

        currPage = 0
        totPage = math.ceil(len(content) / RECENT_PER_PAGE)
        text = '\n'.join(content[currPage * RECENT_PER_PAGE: min(len(content), (currPage + 1) * RECENT_PER_PAGE)])
        embed = discord.Embed(description=text, color=discord.Color.gold())
        embed.set_author(name="Finished matches")
        embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
        message = await ctx.send(embed=embed)

        await message.add_reaction("⏮")
        await message.add_reaction("◀")
        await message.add_reaction("▶")
        await message.add_reaction("⏭")

        def check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji in ["⏮", "◀", "▶",
                                                                            "⏭"] and user != self.client.user

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=90, check=check)
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                if reaction.emoji == "⏮":
                    currPage = 0
                elif reaction.emoji == "◀":
                    currPage = max(currPage - 1, 0)
                elif reaction.emoji == "▶":
                    currPage = min(currPage + 1, totPage - 1)
                else:
                    currPage = totPage - 1
                text = '\n'.join(
                    content[currPage * RECENT_PER_PAGE: min(len(content), (currPage + 1) * RECENT_PER_PAGE)])
                embed = discord.Embed(description=text, color=discord.Color.gold())
                embed.set_author(name="Finished matches")
                embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
                await message.edit(embed=embed)

            except asyncio.TimeoutError:
                break

    @match.command(brief="Show problems left from someone's ongoing match")
    async def problems(self, ctx, member: discord.Member=None):
        if member is None:
            member = ctx.author
        if not self.db.in_a_match(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"User {member.mention} is not in a match!")
            return
        await ctx.send(embed=discord_.match_problems_embed(self.db.get_match_info(ctx.guild.id, member.id)))

    @match.command(brief="Update matches status for the server")
    @cooldown(1, AUTO_UPDATE_TIME, BucketType.guild)
    async def update(self, ctx):
        await ctx.send(embed=discord.Embed(description=f"Updating matches for this server", color=discord.Color.green()))

        matches = self.db.get_all_matches(ctx.guild.id)
        for match in matches:
            try:
                # updates, over, match_status
                resp = await updation.update_match(match)
                if not resp[0]:
                    logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                    await logging_channel.send(f"Error while updating matches: {resp[1]}")
                    continue
                resp = resp[1]
                channel = self.client.get_channel(match.channel)
                if resp[1] or len(resp[0]) > 0:
                    mem1, mem2 = await discord_.fetch_member(ctx.guild, match.p1_id), \
                                 await discord_.fetch_member(ctx.guild, match.p2_id)
                    await channel.send(f"{mem1.mention} {mem2.mention}, there is an update in standings!")

                for x in resp[0]:
                    await channel.send(embed=discord.Embed(
                        description=f"{' '.join([(await discord_.fetch_member(ctx.guild, m)).mention for m in x[1]])} has solved problem worth {x[0]*100} points",
                        color=discord.Color.blue()))

                if not resp[1] and len(resp[0]) > 0:
                    await channel.send(embed=discord_.match_problems_embed(self.db.get_match_info(ctx.guild.id, match.p1_id)))

                if resp[1]:
                    a, b = updation.match_score(resp[2])
                    p1_rank, p2_rank = 1 if a >= b else 2, 1 if b >= a else 2
                    ranklist = []
                    ranklist.append([await discord_.fetch_member(ctx.guild, match.p1_id), p1_rank, self.db.get_match_rating(ctx.guild.id, match.p1_id)[-1]])
                    ranklist.append([await discord_.fetch_member(ctx.guild, match.p2_id), p2_rank, self.db.get_match_rating(ctx.guild.id, match.p2_id)[-1]])
                    ranklist = sorted(ranklist, key=itemgetter(1))
                    res = elo.calculateChanges(ranklist)

                    self.db.add_rating_update(ctx.guild.id, match.p1_id, res[match.p1_id][0])
                    self.db.add_rating_update(ctx.guild.id, match.p2_id, res[match.p2_id][0])
                    self.db.delete_match(match.guild, match.p1_id)
                    self.db.add_to_finished(match, resp[2])

                    embed = discord.Embed(color=discord.Color.dark_magenta())
                    pos, name, ratingChange = '', '', ''
                    for user in ranklist:
                        pos += f"{':first_place:' if user[1] == 1 else ':second_place:'}\n"
                        name += f"{user[0].mention}\n"
                        ratingChange += f"{res[user[0].id][0]} (**{'+' if res[user[0].id][1] >= 0 else ''}{res[user[0].id][1]}**)\n"
                    embed.add_field(name="Position", value=pos)
                    embed.add_field(name="User", value=name)
                    embed.add_field(name="Rating changes", value=ratingChange)
                    embed.set_author(name=f"Match over! Final standings\nScore: {a}-{b}")
                    await channel.send(embed=embed)
            except Exception as e:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(f"Error while updating matches: {str(traceback.format_exc())}")

    # @match.command(brief="View someone's profile")
    # async def profile(self, ctx, member: discord.Member=None):
    #     if member is None:
    #         member = ctx.author
    #     if not self.db.get_handle(ctx.guild.id, member.id):
    #         await discord_.send_message(ctx, f"User {member.mention} has not set their handle")
    #         return
    #     data = self.db.get_profile(ctx.guild.id, member.id)
    #     wins, loss, draw = 0, 0, 0
    #     handle = self.db.get_handle(ctx.guild.id, member.id)
    #     distrib = [0, 0, 0, 0, 0]
    #     points = 0
    #     n = len(data)
    #     fastest, rate = 1000000000, 0
    #
    #     for x in data:
    #         if x[1] == member.id:
    #             if x[6] in [1, 3]:
    #                 wins += 1
    #                 if x[4] < fastest:
    #                     fastest = x[4]
    #                     rate = x[3]
    #             if x[6] in [2, 4]:
    #                 loss += 1
    #             if x[6] == 0:
    #                 draw += 1
    #             for i in range(0, 5):
    #                 if x[5][i] == '1':
    #                     distrib[i] += 1
    #                     points += (i+1)*100
    #         else:
    #             if x[6] in [2, 4]:
    #                 wins += 1
    #                 if x[4] < fastest:
    #                     fastest = x[4]
    #                     rate = x[3]
    #             if x[6] in [1, 3]:
    #                 loss += 1
    #             if x[6] == 0:
    #                 draw += 1
    #             for i in range(0, 5):
    #                 if x[5][i] == '2':
    #                     distrib[i] += 1
    #                     points += (i+1)*100
    #
    #     fast = ""
    #     av = 0
    #     if n !=0:
    #         av = points/n
    #     if fastest == 1000000000:
    #         fast = "NIL"
    #     else:
    #         fast = f"{int(fastest/60)}m {fastest%60}s [{rate} Rating]"
    #
    #     embed = discord.Embed(description=f"Profile for user {member.mention}", color=discord.Color.dark_blue())
    #     embed.add_field(name="Handle", value=f"[{handle}](https://codeforces.com/profile/{handle})", inline=False)
    #     embed.add_field(name="Wins", value=str(wins), inline=True)
    #     embed.add_field(name="Draws", value=str(draw), inline=True)
    #     embed.add_field(name="Losses", value=str(loss), inline=True)
    #     embed.add_field(name="Problem Points", value="100\n200\n300\n400\n500", inline=True)
    #     embed.add_field(name="Times Solved", value=f"{distrib[0]}\n{distrib[1]}\n{distrib[2]}\n{distrib[3]}\n{distrib[4]}\n", inline=True)
    #     embed.add_field(name="Average Points", value=f"{int(av)}", inline=False)
    #     embed.add_field(name="Fastest Time", value=fast, inline=True)
    #     await ctx.send(embed=embed)

    @match.command(brief="Plot match rating")
    async def rating(self, ctx, member: discord.Member=None):
        if member is None:
            member = ctx.author
        data = self.db.get_match_rating(ctx.guild.id, member.id)
        if not self.db.get_handle(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"Handle for user {member.mention} not set")
            return
        if len(data) <= 1:
            await ctx.send(embed=discord.Embed(description=f"User {member.mention} is unrated! Compete in matches to become rated"))
            return
        await plot_graph(ctx, data[1:], self.db.get_handle(ctx.guild.id, member.id))

    @match.command(brief="Show match ratings of all the users")
    async def ranklist(self, ctx):
        res = self.db.get_ranklist(ctx.guild.id)
        if len(res) == 0:
            await discord_.send_message(ctx, "No user has played a match so far")
            return
        res = sorted(res, key=itemgetter(1), reverse=True)
        data = []
        for x in res:
            try:
                data.append([(await discord_.fetch_member(ctx.guild, x[0])).name, str(x[1])])
            except Exception:
                pass
        await paginator.Paginator(data, ["User", "Rating"], f"Match Ratings", 10).paginate(ctx, self.client)


def setup(client):
    client.add_cog(Matches(client))