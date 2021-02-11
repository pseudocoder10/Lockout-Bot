import discord
import time

from discord.ext import commands
from humanfriendly import format_timespan as timeez
from psutil import Process, virtual_memory

from utils import tasks
from data import dbconn
from constants import OWNERS, SERVER_INVITE, BOT_INVITE, GITHUB_LINK


class Misc(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.uptime = int(time.time())

    @commands.command(name="updateratings", hidden=True)
    async def updateratings(self, ctx):
        if ctx.author.id not in OWNERS:
            return
        await ctx.send(embed=discord.Embed(description="Updating ratings", color=discord.Color.green()))
        await tasks.update_ratings(self.client)
        await ctx.send(embed=discord.Embed(description="Ratings updated", color=discord.Color.green()))

    @commands.command(name="update_db", hidden=True)
    async def updatedb(self, ctx):
        if ctx.author.id not in OWNERS:
            return
        await ctx.send(embed=discord.Embed(description="Updating problemset", color=discord.Color.green()))
        await tasks.update_problemset(self.client)
        await ctx.send(embed=discord.Embed(description="Problemset updated", color=discord.Color.green()))

    @commands.command(name="backup", hidden=True)
    async def backup(self, ctx):
        if ctx.author.id not in OWNERS:
            return
        await ctx.send(embed=discord.Embed(description="Taking backup", color=discord.Color.green()))
        await tasks.create_backup(self.client)
        await ctx.send(embed=discord.Embed(description="Backup taken", color=discord.Color.green()))

    @commands.command(name="scrape_", hidden=True)
    async def scrape_(self, ctx):
        if ctx.author.id not in OWNERS:
            return
        await ctx.send(embed=discord.Embed(description="Scraping problem author list", color=discord.Color.green()))
        await tasks.scrape_authors(self.client)
        await ctx.send(embed=discord.Embed(description="Done", color=discord.Color.green()))

    @commands.command()
    async def botinfo(self, ctx):
        handles = self.db.get_count('handles')
        matches = self.db.get_count('finished') 
        rounds = self.db.get_count('finished_rounds')
        guilds = len(self.client.guilds)
        uptime_ = int(time.time()) - self.uptime

        proc = Process()
        with proc.oneshot():
            mem_total = virtual_memory().total / (1024 ** 3)
            mem_of_total = proc.memory_percent()
            mem_usage = mem_total * (mem_of_total / 100)

        embed = discord.Embed(description="A discord bot to compete with others on codeforces in a Lockout format",
                              color=discord.Color.magenta())
        embed.set_author(name="Bot Stats", icon_url=self.client.user.avatar_url)
        embed.set_thumbnail(url=self.client.user.avatar_url)

        embed.add_field(name="Handles Set", value=f"**{handles}**", inline=True)
        embed.add_field(name="Matches played", value=f"**{matches}**", inline=True)
        embed.add_field(name="Rounds played", value=f"**{rounds}**", inline=True)
        embed.add_field(name="Servers", value=f"**{guilds}**", inline=True)
        embed.add_field(name="Uptime", value=f"**{timeez(uptime_)}**", inline=True)
        embed.add_field(name="Memory usage", value=f"{int(mem_usage * 1024)} MB / {mem_total:,.0f} GB ({mem_of_total:.0f}%)",
                        inline=True)
        embed.add_field(name="GitHub repository", value=f"[GitHub]({GITHUB_LINK})", inline=True)
        embed.add_field(name="Bot Invite link", value=f"[Invite]({BOT_INVITE})", inline=True)
        embed.add_field(name="Support Server", value=f"[Server]({SERVER_INVITE})", inline=True)

        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Misc(client))
