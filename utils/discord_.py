import discord
import time
import asyncio
import math

from humanfriendly import format_timespan as timeez

from constants import ADMIN_PRIVILEGE_ROLES
from utils.updation import match_score, round_score
from utils import updation, cf_api
from data import dbconn


db = dbconn.DbConn()
cf = cf_api.CodeforcesAPI()


class DummyUser:
    def __init__(self, id):
        self.id = id
        self.name = "**DummyName**"
        self.mention = "**DummyUser**"


def has_admin_privilege(ctx):
    if ctx.channel.permissions_for(ctx.author).manage_guild:
        return True
    for role in ADMIN_PRIVILEGE_ROLES:
        if role.lower() in [x.name.lower() for x in ctx.author.roles]:
            return True
    return False


async def send_message(ctx, message):
    await ctx.send(embed=discord.Embed(description=message, color=discord.Color.gold()))


async def fetch_member(guild, id):
    try:
        member = await guild.fetch_member(id)
        return member
    except Exception:
        return DummyUser(id)


async def get_time_response(client, ctx, message, time, author, range_):
    original = await ctx.send(embed=discord.Embed(description=message, color=discord.Color.green()))

    def check(m):
        if not m.content.isdigit() or not m.author == author:
            return False
        i = m.content
        if int(i) < range_[0] or int(i) > range_[1]:
            return False
        return True
    try:
        msg = await client.wait_for('message', timeout=time, check=check)
        await original.delete()
        return [True, int(msg.content)]
    except asyncio.TimeoutError:
        await original.delete()
        return [False]


async def get_seq_response(client, ctx, message, time, length, author, range_):
    original = await ctx.send(embed=discord.Embed(description=message, color=discord.Color.green()))

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
        await original.delete()
        return [True, [int(x) for x in msg.content.split()]]
    except asyncio.TimeoutError:
        await original.delete()
        return [False]


async def get_alt_response(client, ctx, message, limit, time, author):
    original = await ctx.send(embed=discord.Embed(description=message, color=discord.Color.green()))

    async def check(m):
        if m.author != author:
            return False
        if m.content.lower() == "none":
            return True, []
        data = m.content.split()
        if data[0].lower() != "alts:":
            return False
        data = data[1:]
        if len(data) > limit or len(data) <= 0:
            return False
        handles = []
        for i in data:
            resp = await cf.check_handle((i))
            if not resp[0]:
                return False
            handles.append(resp[1]['handle'])
        return True, handles

    def check1(m):
        return m.author == author and m.channel.id == ctx.channel.id

    while True:
        try:
            msg = await client.wait_for('message', timeout=time, check=check1)
            res = await check(msg)
            if not res:
                continue
            await original.delete()
            return True, res[1]
        except asyncio.TimeoutError:
            await original.delete()
            return False


async def get_problems_response(client, ctx, message, time, length, author):
    original = await ctx.send(embed=discord.Embed(description=message, color=discord.Color.green()))

    def check(m):
        if m.author != author:
            return False
        data = m.content.split()
        if len(data) != length:
            return False
        for i in data:
            problem = i.split('/')
            if len(problem) != 2:
                return False
            if not db.get_problems(i.upper()):
                return False
        return True

    try:
        msg = await client.wait_for('message', timeout=time, check=check)
        await original.delete()
        return [True, [db.get_problems(x.upper())[0] for x in msg.content.split()]]
    except asyncio.TimeoutError:
        await original.delete()
        return [False]


def match_problems_embed(match_info):
    a, b = match_score(match_info.status)
    problems = match_info.problems.split()

    points = [f"{100 * (i + 1)}" for i in range(5)]
    names = [f"[{db.get_problems(problems[i])[0].name}](https://codeforces.com/contest/{problems[i].split('/')[0]}"
             f"/problem/{problems[i].split('/')[1]})" if match_info.status[i] == '0' else "This problem has been solved"
             for i in range(5)]
    rating = [f"{match_info.rating + i * 100}" for i in range(5)]

    handle1, handle2 = db.get_handle(match_info.guild, match_info.p1_id), db.get_handle(match_info.guild,
                                                                                        match_info.p2_id)

    embed = discord.Embed(description=f"[{handle1}](https://codeforces.com/profile/{handle1}) (**{a}** points) vs "
                                      f"(**{b}** points) [{handle2}](https://codeforces.com/profile/{handle2})",
                          color=discord.Color.green())
    embed.set_author(name=f"Problems")

    embed.add_field(name="Points", value='\n'.join(points), inline=True)
    embed.add_field(name="Problem Name", value='\n'.join(names), inline=True)
    embed.add_field(name="Rating", value='\n'.join(rating), inline=True)
    embed.set_footer(text=f"Time left: {timeez((match_info.time + 60 * match_info.duration) - int(time.time()))}")

    return embed


def ongoing_matches_embed(data):
    content = []
    for match in data:
        try:
            handle1, handle2 = db.get_handle(match.guild, match.p1_id), db.get_handle(match.guild, match.p2_id)
            a, b = updation.match_score(match.status)
            profile_url = "https://codeforces.com/profile/"
            content.append(f"{len(content)+1}. [{handle1}]({profile_url+handle1})(**{a}** points) vs (**{b}** points) [{handle2}]"
                           f"({profile_url+handle2}) | {match.rating} rated | Time left: {timeez(match.time+60*match.duration-int(time.time()))}")
        except Exception:
            pass
    return content


def recent_matches_embed(data):
    content = []
    for match in data:
        try:
            handle1, handle2 = db.get_handle(match.guild, match.p1_id), db.get_handle(match.guild, match.p2_id)
            a, b = updation.match_score(match.status)
            profile_url = "https://codeforces.com/profile/"
            content.append(f"{len(content)+1}. [{handle1}]({profile_url+handle1})(**{a}** points) vs (**{b}** points) [{handle2}]"
                           f"({profile_url+handle2}) {f'was won by **{handle1 if a>b else handle2}**' if a!=b else 'ended in a **draw**!'} | {match.rating} rated | {timeez(int(time.time())-match.time)} ago")
        except Exception:
            pass
    return content


def round_problems_embed(round_info):
    ranklist = round_score(list(map(int, round_info.users.split())), list(map(int, round_info.status.split())), list(map(int, round_info.times.split())))

    problems = round_info.problems.split()
    names = [f"[{db.get_problems(problems[i])[0].name}](https://codeforces.com/contest/{problems[i].split('/')[0]}"
             f"/problem/{problems[i].split('/')[1]})" if problems[i] != '0' else "This problem has been solved" if
             round_info.repeat == 0 else "No problems of this rating left" for i in range(len(problems))]

    desc = ""
    for user in ranklist:
        emojis = [":first_place:", ":second_place:", ":third_place:"]
        handle = db.get_handle(round_info.guild, user.id)
        desc += f"{emojis[user.rank-1] if user.rank <= len(emojis) else user.rank} [{handle}](https://codeforces.com/profile/{handle}) **{user.points}** points\n"

    embed = discord.Embed(description=desc, color=discord.Color.magenta())
    embed.set_author(name=f"Problems")

    embed.add_field(name="Points", value='\n'.join(round_info.points.split()), inline=True)
    embed.add_field(name="Problem Name", value='\n'.join(names), inline=True)
    embed.add_field(name="Rating", value='\n'.join(round_info.rating.split()), inline=True)
    embed.set_footer(text=f"Time left: {timeez((round_info.time + 60 * round_info.duration) - int(time.time()))}")

    return embed


def recent_rounds_embed(data):
    content = []

    for round in data:
        try:
            ranklist = updation.round_score(list(map(int, round.users.split())), list(map(int, round.status.split())),
                                            list(map(int, round.times.split())))
            msg = ' vs '.join([f"[{db.get_handle(round.guild, user.id)}](https://codeforces.com/profile/{db.get_handle(round.guild, user.id)}) `Rank {user.rank}` `{user.points} Points`"
                               for user in ranklist])
            msg += f"\n**Problem ratings:** {round.rating}"
            msg += f"\n**Score distribution** {round.points}"
            msg += f"\n**Duration:** {timeez(min(60*round.duration, round.end_time-round.time))}\n\n"
            content.append(msg)
        except Exception:
            pass

    return content


def ongoing_rounds_embed(data):
    content = []

    for round in data:
        try:
            ranklist = updation.round_score(list(map(int, round.users.split())), list(map(int, round.status.split())),
                                            list(map(int, round.times.split())))
            msg = ' vs '.join([f"[{db.get_handle(round.guild, user.id)}](https://codeforces.com/profile/{db.get_handle(round.guild, user.id)}) `Rank {user.rank}` `{user.points} Points`"
                               for user in ranklist])
            msg += f"\n**Problem ratings:** {round.rating}"
            msg += f"\n**Score distribution** {round.points}"
            msg += f"\n**Time left:** {timeez(60*round.duration + round.time - int(time.time()))}\n\n"
            content.append(msg)
        except Exception:
            pass

    return content


async def content_pagination(content, client, PER_PAGE, heading, ctx, color, extra_text: str=""):
    currPage = 0
    totPage = math.ceil(len(content) / PER_PAGE)
    text = '\n'.join(content[currPage * PER_PAGE: min(len(content), (currPage + 1) * PER_PAGE)])
    embed = discord.Embed(description=text, color=color)
    embed.set_author(name=heading)
    embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
    message = await ctx.send(embed=embed, content=extra_text)

    await message.add_reaction("⏮")
    await message.add_reaction("◀")
    await message.add_reaction("▶")
    await message.add_reaction("⏭")

    def check(reaction, user):
        return reaction.message.id == message.id and reaction.emoji in ["⏮", "◀", "▶",
                                                                        "⏭"] and user != client.user

    while True:
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=90, check=check)
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
                content[currPage * PER_PAGE: min(len(content), (currPage + 1) * PER_PAGE)])
            embed = discord.Embed(description=text, color=color)
            embed.set_author(name=heading)
            embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
            await message.edit(embed=embed, content=extra_text)

        except asyncio.TimeoutError:
            break



