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
from discord.ext.commands import cooldown, BucketType, CommandOnCooldown


async def send_message(ctx, message):
    await ctx.send(embed=discord.Embed(description=message, color=discord.Color.gold()))


class Handles(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.cf = cf_api.CodeforcesAPI()

    def make_handle_embed(self, ctx):
        desc = "Information about Handle related commands! **[use .handle <command>]**\n\n"
        handle = self.client.get_command('handle')
        for cmd in handle.commands:
            desc += f"`{cmd.name}`: **{cmd.brief}**\n"
        embed = discord.Embed(description=desc, color=discord.Color.dark_magenta())
        embed.set_author(name="Lockout commands help", icon_url=ctx.me.avatar_url)
        embed.set_footer(
            text="Use the prefix . before each command. For detailed usage about a particular command, type .help <command>")
        embed.add_field(name="GitHub repository", value=f"[GitHub](https://github.com/pseudocoder10/Lockout-Bot)",
                        inline=True)
        embed.add_field(name="Bot Invite link",
                        value=f"[Invite](https://discord.com/oauth2/authorize?client_id=669978762120790045&permissions=0&scope=bot)",
                        inline=True)
        embed.add_field(name="Support Server", value=f"[Server](https://discord.gg/xP2UPUn)",
                        inline=True)
        return embed

    @commands.group(brief='Commands related to handles! Type .handle for more details', invoke_without_command=True)
    async def handle(self, ctx):
        await ctx.send(embed=self.make_handle_embed(ctx))

    @handle.command(brief="Set someone's handle (Admin only)")
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
        self.db.add_rated_user(ctx.guild.id, member.id)
        embed = discord.Embed(description=f'Handle for user {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})',
                              color=Color(randint(0, 0xFFFFFF)))
        embed.add_field(name='Rank', value=f'{rank}', inline=True)
        embed.add_field(name='Rating', value=f'{rating}', inline=True)
        embed.set_thumbnail(url=f"https:{data['titlePhoto']}")
        await ctx.send(embed=embed)

    @handle.command(brief="Remove someone's handle (Admin only)")
    @commands.has_any_role('Admin', 'Moderator')
    async def remove(self, ctx, member: discord.Member):
        if not self.db.handle_in_db(ctx.guild.id, member.id):
            await send_message(ctx, "Handle for user not set")
            return
        self.db.remove_handle(ctx.guild.id, member.id)
        await ctx.send(embed=Embed(description=f"Handle for user {member.mention} removed successfully", color=Color.green()))

    @handle.command(brief="Set your handle yourself")
    @cooldown(1, 60, BucketType.user)
    async def identify(self, ctx, handle: str=None):
        if not handle:
            await send_message(ctx, "Usage: .handle identify <cf handle>")
            ctx.command.reset_cooldown(ctx)
            return
        if self.db.handle_in_db(ctx.guild.id, ctx.author.id):
            await send_message(ctx, "Your handle is already set, ask an admin or mod to remove it first and try again.")
            ctx.command.reset_cooldown(ctx)
            return
        data = await self.cf.check_handle(handle)
        if not data[0]:
            await send_message(ctx, data[1])
            return
        data = data[1]
        handle = data['handle']
        res = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))
        await send_message(ctx, f"Please change your first name on this [link](https://codeforces.com/settings/social) to `{res}` within 60 seconds {ctx.author.mention}")
        await asyncio.sleep(60)
        if res != await self.cf.get_first_name(handle):
            await send_message(ctx, f"Unable to set handle, please try again {ctx.author.mention}")
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
        self.db.add_rated_user(ctx.guild.id, member.id)
        embed = discord.Embed(description=f'Handle for user {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})',
                              color=Color(randint(0, 0xFFFFFF)))
        embed.add_field(name='Rank', value=f'{rank}', inline=True)
        embed.add_field(name='Rating', value=f'{rating}', inline=True)
        embed.set_thumbnail(url=f"https:{data['titlePhoto']}")
        await ctx.send(embed=embed)
    
    @identify.error
    async def identify_error(self, ctx, exc):
        if isinstance(exc, CommandOnCooldown):
            await ctx.send(embed=discord.Embed(description=f"Slow down!\nThe cooldown of command is **60s**, pls retry after **{exc.retry_after:,.2f}s**", color=discord.Color.red()))

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
                data1.append([(await ctx.guild.fetch_member(int(x[1]))).name, x[2], x[3]])
            except Exception as e:
                print(e)
        data = data1
        data = sorted(data, key=itemgetter(2), reverse=True)
        data = [[x[0], x[1], str(x[2])] for x in data]
        await paginator.Paginator(data, ["User", "Handle", "Rating"], f"Handle List", 15).paginate(ctx, self.client)


def setup(client):
    client.add_cog(Handles(client))