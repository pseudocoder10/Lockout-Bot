import discord
from discord.ext import commands, tasks
from discord.ext.commands import Bot, when_mentioned_or
from os import environ
from discord import Game
from data import dbconn
import time, asyncio
from datetime import datetime

from humanfriendly import format_timespan as timeez
from utils import scraper
from discord.ext.commands import CommandNotFound, CommandOnCooldown, MissingPermissions, MissingRequiredArgument, \
    BadArgument, MissingAnyRole

from utils import cf_api

client = Bot(description="A Discord bot to compete with each other using codeforces problems",
             command_prefix=when_mentioned_or("."))
uptime = 0

db = dbconn.DbConn()
api = cf_api.CodeforcesAPI()


@client.event
async def on_ready():
    await client.change_presence(activity=Game(name="in matches | .help"))
    print("Ready")
    global uptime
    uptime = int(time.time())
    update_matches.start()

root_users=[519879218402689024,515920333623263252]

@client.command(hidden=True)
async def update_db(ctx):
    if ctx.author.id not in root_users:
        return
    await db.update_db(ctx)


@client.command(hidden=True)
async def updateratings(ctx):
    if ctx.author.id not in root_users:
        return
    await ctx.send("Updating ratings")
    data = db.get_overall_handles()
    i = 0
    for x in data:
        if i%4 == 0:
            await asyncio.sleep(1)
        i += 1
        try:
            rating = await api.get_rating(x[0])
            db.update_rating(x[0], rating)
        except Exception as e:
            print(f"update error {e}")
    await ctx.send("Ratings updated")


@client.command(hidden=True)
async def scrape_(ctx):
    if ctx.author.id not in root_users:
        return
    await ctx.send("Scraping data")
    scraper.run()
    await ctx.send("Data scraped")


@client.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, CommandNotFound):
        pass

    elif isinstance(error, CommandOnCooldown):
        pass

    elif isinstance(error, BadArgument) or isinstance(error, MissingRequiredArgument):
        command = ctx.command
        usage = f".{str(command)} "
        params = []
        for key, value in command.params.items():
            if key not in ['self', 'ctx']:
                params.append(f"[{key}]" if "NoneType" in str(value) else f"<{key}>")
        usage += ' '.join(params)
        await ctx.send(f"Usage: **{usage}**")

    elif isinstance(error, MissingPermissions) or isinstance(error, MissingAnyRole):
        await ctx.send(f"{str(error)}")

    else:
        print(f"{ctx.author.id} {ctx.guild.id} {ctx.message.content}")
        print(error)


@client.command()
async def botinfo(ctx):
    handles = db.get_count('handles')
    matches = db.get_count('finished') 
    rounds = db.get_count('finished_rounds')
    guilds = len(client.guilds)
    uptime_ = int(time.time()) - uptime

    embed = discord.Embed(description="A discord bot to compete with others on codeforces in a Lockout format", color=discord.Color.magenta())
    embed.set_author(name="Bot Stats", icon_url=client.user.avatar_url)
    embed.set_thumbnail(url=client.user.avatar_url)

    embed.add_field(name="Handles Set", value=f"**{handles}**", inline=True)
    embed.add_field(name="Matches played", value=f"**{matches}**", inline=True)
    embed.add_field(name="Rounds played", value=f"**{rounds}**", inline=True)
    embed.add_field(name="Servers", value=f"**{guilds}**", inline=True)
    embed.add_field(name="Uptime", value=f"**{timeez(uptime_)}**", inline=True)
    embed.add_field(name="\u200b", value=f"\u200b", inline=True)
    embed.add_field(name="GitHub repository", value=f"[GitHub](https://github.com/pseudocoder10/Lockout-Bot)", inline=True)
    embed.add_field(name="Bot Invite link", value=f"[Invite](https://discord.com/oauth2/authorize?client_id=669978762120790045&permissions=0&scope=bot)",
                    inline=True)
    embed.add_field(name="Support Server", value=f"[Server](https://discord.gg/xP2UPUn)",
                    inline=True)

    await ctx.send(embed=embed)


@tasks.loop(seconds=60)
async def update_matches():
    print(f"Attempting to auto update matches at {datetime.fromtimestamp(int(time.time())).strftime('%A, %B %d, %Y %I:%M:%S')}")
    try:
        await db.update_matches(client)
    except Exception as e:
        print(f"Failed to auto update matches {str(e)}")

    try:
        await db.update_rounds(client)
    except Exception as e:
        print(f"Failed to auto update rounds {e}")


if __name__ == "__main__":
    client.load_extension("handles")
    client.load_extension("matches")
    client.load_extension("help")
    client.load_extension("round")

token = environ.get('BOT_TOKEN')
if not token:
    print('Bot token not found!')
else:
    client.run(token)
