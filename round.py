import discord
import random
import asyncio
import time
import math

from functools import cmp_to_key
from humanfriendly import format_timespan as timeez

from data import dbconn
from utils import cf_api, paginator

from discord.ext import commands
from discord.ext.commands import cooldown, BucketType, CommandOnCooldown



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


async def get_seq_response(client, ctx, message, time, length, author, range_):
    await ctx.send(message)

    def check(m):
        if m.author != author:
            return False
        data = m.content.split()
        if len(data) != length:
            return False
        for i in data:
            if not i.isdigit():
                return False
            if int(i) < range_[0] or int(i) > range_[1]:
                return False
        return True

    try:
        msg = await client.wait_for('message', timeout=time, check=check)
        return [True, [int(x) for x in msg.content.split()]]
    except asyncio.TimeoutError:
        return [False]

def get_time():
    return time.time()

class Round(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.api = cf_api.CodeforcesAPI()

    async def get_user_problems(self, handles):
        data = []
        try:
            for i in range(len(handles)):
                subs = await self.api.get_user_problems(handles[i])
                if not subs[0]:
                    return [False]
                data.extend(subs[1])
        except Exception:
            return [False]
        return [True, data]

    async def get_alt_response(self, client, ctx, message, time, author):
        await ctx.send(message)

        def check(m):
            if m.author != author:
                return False
            elements = m.content.split()
            if len(elements) < 1:
                return False
            if len(elements) == 1:
                if elements[0].lower() == "none":
                    return True
            if elements[0].lower() != "alts:" :
                return False 
            return True

        try:
            msg = await client.wait_for('message', timeout=time, check=check)
            return [True, [x for x in msg.content.split()]]
        except asyncio.TimeoutError:
            return [False]

    def get_unsolved_problem(self, solved, total, handles, rating):
        fset = []
        for x in total:
            if x[2] not in [name[2] for name in solved] and not self.db.is_an_author(x[0], handles) and x[4] == rating:
                fset.append(x)
        return random.choice(fset) if len(fset) > 0 else None

    def make_result_embed(self, users, points, times, rating, problem_points, duration):
        def comp(a, b):
            if a[0] > b[0]:
                return -1
            if a[0] < b[0]:
                return 1
            if a[1] == b[1]:
                return 0
            return -1 if a[1] < b[1] else 1
        standings = []
        standings1 = []
        for i in range(len(users)):
            standings.append([points[i], times[i], users[i]])
            standings1.append([points[i], times[i]])
        standings.sort(key=cmp_to_key(comp))
        standings1.sort(key=cmp_to_key(comp))

        msg = ' vs '.join([f"{standings[i][2].mention} `Rank {standings1.index([standings[i][0], standings[i][1]])+1}` `{standings[i][0]} Points`" for i in range(len(users))])
        msg += f"\n**Problem ratings:** {rating}"
        msg += f"\n**Score distribution** {problem_points}"
        msg += f"\n**Duration:** {timeez(duration)}\n\n"
        return msg


    def make_round_embed(self, ctx):
        desc = "Information about Matches related commands! **[use .round <command>]**\n\n"
        match = self.client.get_command('round')

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

    @commands.group(brief='Commands related to rounds! Type .round for more details', invoke_without_command=True)
    async def round(self, ctx):
        await ctx.send(embed=self.make_round_embed(ctx))

    @round.command(name="challenge", aliases=['begin'], brief="Challenge someone to a round")
    async def challenge(self, ctx, *users: discord.Member):
        users = list(set(users))
        if len(users) == 0:
            await ctx.send(f"The correct usage is `.round challenge @user1 @user2...`")
            return
        if ctx.author not in users:
            users.append(ctx.author)
        if len(users) > 5:
            await ctx.send(f"{ctx.author.mention} you can't compete with more than 4 users at a time")
            return
        for i in users:
            if not self.db.handle_in_db(ctx.guild.id, i.id):
                await ctx.send(f"Handle for {i.name} not set! Use `.handle identify` to register")
                return
            if self.db.in_a_round(ctx.guild.id, i.id):
                await ctx.send(f"{i.name} is already in a round!")
                return

        embed = discord.Embed(description=f"{' '.join(x.mention for x in users)} react on the message with ✅ within 30 seconds to join the round. {'Since you are the only participant, this will be a practice round and there will be no rating changes' if len(users) == 1 else ''}",
            color=discord.Color.purple())
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")

        await asyncio.sleep(30)
        message = await ctx.channel.fetch_message(message.id)

        reaction = None
        for x in message.reactions:
            if x.emoji == "✅":
                reaction = x

        reacted = await reaction.users().flatten()
        for i in users:
            if i not in reacted:
                await ctx.send(f"Unable to start round, {i.name} did not react in time!")
                return

        problem_cnt = await get_time_response(self.client, ctx, f"{ctx.author.mention} enter the number of problems between [1, 6]", 30, ctx.author, [1, 6])
        if not problem_cnt[0]:
            await ctx.send(f"{ctx.author.mention} you took too long to decide")
            return
        problem_cnt = problem_cnt[1]

        time = await get_time_response(self.client, ctx, f"{ctx.author.mention} enter the duration of match in minutes between [5, 180]", 30, ctx.author, [5, 180])
        if not time[0]:
            await ctx.send(f"{ctx.author.mention} you took too long to decide")
            return
        time = time[1]

        rating = await get_seq_response(self.client, ctx, f"{ctx.author.mention} enter {problem_cnt} space seperated integers denoting the ratings of problems (between 700 and 4000)", 60, problem_cnt, ctx.author, [700, 4000])
        if not rating[0]:
            await ctx.send(f"{ctx.author.mention} you took too long to decide")
            return
        rating = rating[1]

        points = await get_seq_response(self.client, ctx, f"{ctx.author.mention} enter {problem_cnt} space seperated integer denoting the points of problems (between 100 and 10,000)", 60, problem_cnt, ctx.author, [100, 10000])
        if not points[0]:
            await ctx.send(f"{ctx.author.mention} you took too long to decide")
            return
        points = points[1]

        repeat = await get_time_response(self.client, ctx, f"{ctx.author.mention} do you want a new problem to appear when someone solves a problem (type 1 for yes and 0 for no)", 30, ctx.author, [0, 1])
        if not repeat[0]:
            await ctx.send(f"{ctx.author.mention} you took too long to decide")
            return
        repeat = repeat[1]

        for i in users:
            if self.db.in_a_round(ctx.guild.id, i.id):
                await ctx.send(f"{i.name} is already in a round!")
                return

        check = False 
        start_time = get_time()
        First = True
        handles = [self.db.get_handle(ctx.guild.id, user.id) for user in users]

        while get_time() - start_time < 60:
            if First:
                alts = await self.get_alt_response(self.client, ctx, f"{ctx.author.mention} add alts of users\ntype None if not applicable \nFormat \"Alts: handle_1 handle_2 .. \n\"len(handles) <= 2*len(users) must be satisfied", 60, ctx.author)
                First = False
            else:
                alts = await self.get_alt_response(self.client, ctx, f"{ctx.author.mention} add alts of users", 60, ctx.author)
            if alts[0]:
                alts = alts[1]
                if len(alts) < 1:
                    continue
                if len(alts) == 1:
                    if alts[0].lower() == "none":
                        check = True
                        alts = []
                        break
                else:
                    alts = alts[1:]
                    check = True
                    for alt in alts:
                        res = await self.api.check_handle(alt)
                        if not res[0]:
                            await ctx.send(f"{ctx.author.mention} " + alt + " is not valid codeforces handle, try again")
                            check = False 
                            break
                    alts.extend(handles)
                    alts = list(set(alts))
                    if len(alts) > 2*len(users):
                        await ctx.send(f"{ctx.author.mention} len(handles) <= 2*len(users) must be satisfied")
                        check = False
                    if check:
                        handles = alts
                        break

        if not check: 
            await ctx.send(f"{ctx.author.mention} you took too long to decide")
            return 

        await ctx.send(embed=discord.Embed(description="Starting the round...", color=discord.Color.green()))

        problems = await self.get_user_problems(handles)
        if not problems[0]:
            await ctx.send(f"Codeforces API Error!")
            return
        solved_problems = problems[1]

        tot_problems = self.db.get_problems()
        chosen = []

        for i in range(len(rating)):
            x = rating[i]
            solved_problems.extend(chosen)
            problem = self.get_unsolved_problem(solved_problems, tot_problems, handles, x)
            if not problem:
                await ctx.send(f"Not enough problems of rating {x} left")
                return
            chosen.append(problem)

        embed = discord.Embed(color=discord.Color.magenta())
        embed.set_author(name="Problems")
        embed.add_field(name="Points", value='\n'.join(str(pt) for pt in points), inline=True)
        embed.add_field(name="Problem Name", value='\n'.join([f"[{pr[2]}](https://codeforces.com/problemset/problem/{pr[0]}/{pr[1]})" for pr in chosen]), inline=True)
        embed.add_field(name="Rating", value='\n'.join([str(rt) for rt in rating]), inline=True)
        embed.set_footer(text=f"Time left: {time} minutes 0 seconds")
        await ctx.send(embed=embed)

        self.db.add_to_ongoing_round(ctx, users, rating, points, chosen, time, repeat ,handles)

    @round.command(name="ongoing", brief="View ongoing rounds")
    async def ongoing(self, ctx):
        data = self.db.get_ongoing_rounds(ctx.guild.id)

        embed = []
        for x in data:
            try:
                users = [ctx.guild.get_member(int(x1)) for x1 in x[1].split()]
                status = [int(x1) for x1 in x[7].split()]
                timestamp = [int(x1) for x1 in x[10].split()]
                embed_ = self.db.print_round_score(users, status, timestamp, ctx.guild.id, 0)
                embed_.add_field(name="Time left", value=timeez(x[4]+60*x[8]-int(time.time())), inline=False)
                embed.append(embed_)
            except Exception as e:
                pass

        if len(embed) == 0:
            await ctx.send("There are no ongoing rounds")
            return

        for i in range(len(embed)):
            embed[i].set_footer(text=f"Page {i+1} of {len(embed)}")

        currPage = 0
        totPage = len(embed)
        message = await ctx.send(embed=embed[currPage])

        await message.add_reaction("\U000025c0")
        await message.add_reaction("\U000025b6")

        def check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji in ["\U000025c0",
                                                                            "\U000025b6"] and user != self.client.user

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=180, check=check)
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                if reaction.emoji == "\U000025c0":
                    currPage = (currPage - 1 + totPage) % totPage
                    await message.edit(embed=embed[currPage])
                else:
                    currPage = (currPage + 1 + totPage) % totPage
                    await message.edit(embed=embed[currPage])
            except asyncio.TimeoutError:
                break

    @round.command(brief="Invalidate a round (Admin Only)")
    @commands.has_any_role('Admin', 'Moderator')
    async def _invalidate(self, ctx, member: discord.Member):
        if not self.db.in_a_round(ctx.guild.id, member.id):
            await ctx.send(f"{member.name} is not in a round")
            return
        self.db.delete_round(ctx.guild.id, member.id)
        await ctx.send(f"Round deleted")

    @round.command(name="recent", brief="Show recent rounds")
    async def recent(self, ctx, user: discord.Member=None):
        data = self.db.get_recent_rounds(ctx.guild.id, str(user.id) if user else "")
        content = []
        embeds = []

        for x in data:
            try:
                content.append(self.make_result_embed([ctx.guild.get_member(int(i)) for i in x[1].split()],
                                                    [int(i) for i in x[7].split()], [int(i) for i in x[10].split()],
                                                    x[2], x[3], x[11] - x[4]))
            except Exception as e:
                print(e)

        if len(content) == 0:
            await ctx.send(f"No recent rounds")
            return

        currPage = 0
        perPage = 5
        totPage = math.ceil(len(content) / perPage)

        for i in range(totPage):
            embed = discord.Embed(description='\n'.join(content[i*perPage:min((i+1)*perPage, len(content))]), color=discord.Color.purple())
            embed.set_author(name="Recent Rounds")
            embed.set_footer(text=f"Page {i+1} of {totPage}")
            embeds.append(embed)

        message = await ctx.send(embed=embeds[currPage])

        await message.add_reaction("\U000025c0")
        await message.add_reaction("\U000025b6")

        def check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji in ["\U000025c0",
                                                                            "\U000025b6"] and user != self.client.user

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=180, check=check)
                try:
                    await reaction.remove(user)
                except Exception:
                    pass
                if reaction.emoji == "\U000025c0":
                    currPage = (currPage - 1 + totPage) % totPage
                    await message.edit(embed=embeds[currPage])
                else:
                    currPage = (currPage + 1 + totPage) % totPage
                    await message.edit(embed=embeds[currPage])
            except asyncio.TimeoutError:
                break

    @round.command(name="invalidate", brief="Invalidate your round")
    async def invalidate(self, ctx):
        if not self.db.in_a_round(ctx.guild.id, ctx.author.id):
            await ctx.send(f"{ctx.author.mention} you are not in a round")
            return

        data = self.db.get_round_info(ctx.guild.id, ctx.author.id)
        try:
            users = [ctx.guild.get_member(int(x)) for x in data[1].split()]
        except Exception:
            await ctx.send(f"{ctx.author.mention} some error occurred! Maybe one of the participants left the server")
            return

        msg = await ctx.send(f"{' '.join([x.mention for x in users])} react within 30 seconds to invalidate the match")
        await msg.add_reaction("✅")

        await asyncio.sleep(30)
        message = await ctx.channel.fetch_message(msg.id)

        reaction = None
        for x in message.reactions:
            if x.emoji == "✅":
                reaction = x

        reacted = await reaction.users().flatten()
        for i in users:
            if i not in reacted:
                await ctx.send(f"Unable to invalidate round, {i.name} did not react in time!")
                return

        self.db.delete_round(ctx.guild.id, ctx.author.id)
        await ctx.send(f"Match has been invalidated")

    @round.command(brief="Update matches status for the server")
    @cooldown(1, 60, BucketType.guild)
    async def update(self, ctx):
        await ctx.send(embed=discord.Embed(description="Updating rounds for this server", color=discord.Color.green()))
        await self.db.update_rounds(self.client, ctx.guild.id)

    @update.error
    async def update_error(self, ctx, exc):
        if isinstance(exc, CommandOnCooldown):
            await ctx.send(embed=discord.Embed(
                description=f"Slow down!\nThe cooldown of command is **60s**, pls retry after **{exc.retry_after:,.2f}s**",
                color=discord.Color.red()))

    @round.command(name="problems", brief="View problems of a round")
    async def problems(self, ctx, member: discord.Member=None):
        if not member:
            member = ctx.author
        if not self.db.in_a_round(ctx.guild.id, member.id):
            await ctx.send(f"{member.name} is not in a round")
            return

        x = self.db.get_round_info(ctx.guild.id, member.id)

        problems = x[6].split()
        duration = x[8]
        start = x[4]
        repeat = x[9]

        pname = []
        for prob in problems:
            if prob == '0':
                pname.append(
                    'No unsolved problems of this rating left' if repeat == 1 else "This problem has been solved")
            else:
                id = prob.split('/')[0]
                idx = prob.split('/')[1]
                pname.append(f"[{self.db.get_problem_name(id, idx)}](https://codeforces.com/problemset/problem/{prob})")

        embed = discord.Embed(color=discord.Color.magenta())
        embed.set_author(name=f"Problems left")
        embed.add_field(name="Points", value='\n'.join(x[3].split()), inline=True)
        embed.add_field(name="Problem", value='\n'.join(pname), inline=True)
        embed.add_field(name="Rating", value='\n'.join(x[2].split()), inline=True)
        embed.set_footer(text=f"Time left: {timeez(start + 60 * duration - int(time.time()))}")
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Round(client))