import discord
from discord.ext import commands, tasks
from discord.ext.commands import Bot, when_mentioned_or
from os import environ
from discord import Game
from data import dbconn
import time, asyncio
from datetime import datetime

from utils import cf_api

client = Bot(description="A Discord bot to compete with each other using codeforces problems",
             command_prefix=when_mentioned_or("."))

db = dbconn.DbConn()
api = cf_api.CodeforcesAPI()


@client.event
async def on_ready():
    await client.change_presence(activity=Game(name="in matches | .help"))
    print("Ready")
    update_matches.start()


@client.command(hidden=True)
async def update_db(ctx):
    if ctx.author.id != 515920333623263252:
        return
    await db.update_db(ctx)


@client.command(hidden=True)
async def updateratings(ctx):
    if ctx.author.id != 515920333623263252:
        return
    await ctx.send("Updating ratings")
    data = db.get_overall_handles()
    i = 0
    for x in data:
        if i%4 == 0:
            await asyncio.sleep(1)
        i += 1
        rating = await api.get_rating(x[0])
        db.update_rating(x[0], rating)
    await ctx.send("Ratings updated")


@tasks.loop(seconds=120)
async def update_matches():
    print(f"Attempting to auto update matches at {datetime.fromtimestamp(int(time.time())).strftime('%A, %B %d, %Y %I:%M:%S')}")
    try:
        await db.update_matches(client)
    except Exception as e:
        print(f"Failed to auto update matches {str(e)}")


if __name__ == "__main__":
    client.load_extension("handles")
    client.load_extension("matches")

token = environ.get('BOT_TOKEN')
if not token:
    print('Bot token not found!')
else:
    client.run(token)