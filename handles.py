import asyncio

from discord import Embed, Color, Member, utils, File
from discord.ext import commands
from data import dbconn
from utils import cf_api, paginator
import discord
import random
import string
from random import randint
from operator import itemgetter


async def send_message(ctx, message):
    await ctx.send(embed=discord.Embed(description=message, color=discord.Color.gold()))


class Handles(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.cf = cf_api.CodeforcesAPI()

    @commands.group(brief='Commands related to handles', invoke_without_command=True)
    async def handle(self, ctx):
        await ctx.send_help(ctx.command)

    @handle.command(brief="Set your handle")
    @commands.has_any_role('Admin', 'Moderator')
    async def set(self, ctx, member: discord.Member, handle: str=None):
        if handle is None:
            await send_message(ctx, "Usage: .handle set <username> <cf handle>")
            return
        data = await self.cf.check_handle(handle)
        if not data[0]:
            await send_message(ctx, data[1])
            return
        handle = data[1]['handle']
        if self.db.handle_in_db(ctx.guild.id, member.id):
            await send_message(ctx, f"Handle for user {member.mention} already set.")
            return

        # all conditions met
        data = data[1]
        rating = 0
        rank = ""
        if "rating" not in data:
            rating = 0
            rank = "unrated"
        else:
            rating = data['rating']
            rank = data['rank']
        self.db.add_handle(ctx.guild.id, member.id, handle, rating)
        embed = discord.Embed(description=f'Handle for user {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})',
                              color=Color(randint(0, 0xFFFFFF)))
        embed.add_field(name='Rank', value=f'{rank}', inline=True)
        embed.add_field(name='Rating', value=f'{rating}', inline=True)
        embed.set_thumbnail(url=f"https:{data['titlePhoto']}")
        await ctx.send(embed=embed)

    @handle.command(brief="Remove someone's handle")
    @commands.has_any_role('Admin', 'Moderator')
    async def remove(self, ctx, member: discord.Member):
        if not self.db.handle_in_db(ctx.guild.id, member.id):
            await send_message(ctx, "Handle for user not set")
            return
        self.db.remove_handle(ctx.guild.id, member.id)
        await ctx.send(embed=Embed(description=f"Handle for user {member.mention} removed successfully", color=Color.green()))

    @handle.command(brief="Set your handle yourself")
    async def identify(self, ctx, handle: str=None):
        if not handle:
            await send_message(ctx, "Usage: .handle identify <cf handle>")
            return
        if self.db.handle_in_db(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "Your handle is already set, ask an admin or mod to remove it first and try again.")
            return
        data = await self.cf.check_handle(handle)
        if not data[0]:
            await send_message(ctx, data[1])
            return
        data = data[1]
        handle = data['handle']
        res = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))
        await send_message(ctx, f"Please change your first name on this [link](https://codeforces.com/settings/social) to `{res}` within 60 seconds")
        await asyncio.sleep(60)
        if res != await self.cf.get_first_name(handle):
            await send_message(ctx, f"Unable to set handle, please try again")
            return
        rating = 0
        rank = ""
        member = ctx.author
        if "rating" not in data:
            rating = 0
            rank = "unrated"
        else:
            rating = data['rating']
            rank = data['rank']
        self.db.add_handle(ctx.guild.id, member.id, handle, rating)
        embed = discord.Embed(description=f'Handle for user {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})',
                              color=Color(randint(0, 0xFFFFFF)))
        embed.add_field(name='Rank', value=f'{rank}', inline=True)
        embed.add_field(name='Rating', value=f'{rating}', inline=True)
        embed.set_thumbnail(url=f"https:{data['titlePhoto']}")
        await ctx.send(embed=embed)

    @handle.command(brief="Get someone's handle")
    async def get(self, ctx, member: discord.Member):
        if not self.db.handle_in_db(ctx.guild.id, member.id):
            await send_message(ctx, f'Handle for user {member.mention} is not set currently')
            return
        handle = self.db.get_handle(ctx.guild.id, member.id)
        await ctx.send(embed=Embed(description=f"Handle for user {member.mention} currently set to [{handle}](https://codeforces.com/profile/{handle})",
                             color=Color.green()))

    @handle.command(brief="Get handle list")
    async def list(self, ctx):
        data = self.db.get_all_handles(ctx.guild.id)
        if len(data) == 0:
            await ctx.send("No one has set their handle yet")
            return
        data1 = []
        for x in data:
            try:
                data1.append([ctx.guild.get_member(int(x[1])).name, x[2], x[3]])
            except Exception as e:
                print(e)
        data = data1
        data = sorted(data, key=itemgetter(2), reverse=True)
        data = [[x[0], x[1], str(x[2])] for x in data]
        await paginator.Paginator(data, ["User", "Handle", "Rating"], f"Handle List", 15).paginate(ctx, self.client)


def setup(client):
    client.add_cog(Handles(client))