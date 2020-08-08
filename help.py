import discord

from discord.ext import commands
from discord.ext.commands import BucketType
from humanfriendly import format_timespan as timeez

from data import dbconn


class Help(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.client.remove_command("help")

    def make_help_embed(self, ctx):
        desc = "Information about commands are given below! \n\n"
        handle = self.client.get_command('handle')
        match = self.client.get_command('match')

        desc += "Handle related commands **[use .handle <command>]**\n\n"
        for cmd in handle.commands:
            desc += f"`{cmd.name}`: **{cmd.brief}**\n"
        desc += "\n\nMatch related commands **[use .match <command>]**\n\n"
        for cmd in match.commands:
            desc += f"`{cmd.name}`: **{cmd.brief}**\n"
        embed = discord.Embed(description=desc, color=discord.Color.dark_magenta())
        embed.set_author(name="Lockout commands help", icon_url=ctx.me.avatar_url)
        embed.set_footer(text="Use the prefix . before each command. For detailed usage about a particular command, type .help <command>")
        embed.add_field(name="GitHub repository", value=f"[GitHub](https://github.com/pseudocoder10/Lockout-Bot)",
                        inline=True)
        embed.add_field(name="Bot Invite link",
                        value=f"[Invite](https://discord.com/oauth2/authorize?client_id=669978762120790045&permissions=0&scope=bot)",
                        inline=True)
        embed.add_field(name="Support Server", value=f"[Server](https://discord.gg/xP2UPUn)",
                        inline=True)
        return embed

    def make_cmd_embed(self, command):
        usage = f".{str(command)} "
        params = []
        for key, value in command.params.items():
            if key not in ['self', 'ctx']:
                params.append(f"[{key}]" if "NoneType" in str(value) else f"<{key}>")
        usage += ' '.join(params)
        aliases = [str(command), *command.aliases]
        embed = discord.Embed(title=f"Information about {str(command)}", color=discord.Color.dark_magenta())
        embed.add_field(name="Description", value=command.brief, inline=False)
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
        embed.add_field(name="Aliases", value=f"{' '.join([f'`{x}`' for x in aliases])}", inline=False)
        return embed

    @commands.command(name="help")
    @commands.cooldown(1, 5, BucketType.user)
    async def help(self, ctx, *, cmd: str=None):
        """Shows help for various commands"""
        if cmd is None:
            await ctx.send(embed=self.make_help_embed(ctx))
        else:
            command = self.client.get_command(cmd)
            if command is None or command.hidden:
                await ctx.send(f"{ctx.author.mention} that command does not exists")
                return
            await ctx.send(embed=self.make_cmd_embed(command))


def setup(client):
    client.add_cog(Help(client))