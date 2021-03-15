import asyncio
import discord
import os
import time

from discord.ext import commands
from discord.ext.commands import BucketType
from humanfriendly import format_timespan as timeez

from data import dbconn
from utils import challonge_api, paginator, discord_, tournament_helper
from constants import BOT_INVITE, GITHUB_LINK, SERVER_INVITE, ADMIN_PRIVILEGE_ROLES

MAX_REGISTRANTS = 256


class Tournament(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.api = challonge_api.ChallongeAPI(self.client)

    def make_tournament_embed(self, ctx):
        desc = "Information about Tournament related commands! **[use .tournament <command>]**\n\n"
        handle = self.client.get_command('tournament')
        for cmd in handle.commands:
            desc += f"`{cmd.name}`: **{cmd.brief}**\n"
        embed = discord.Embed(description=desc, color=discord.Color.dark_magenta())
        embed.set_author(name="Lockout commands help", icon_url=ctx.me.avatar_url)
        embed.set_footer(
            text="Use the prefix . before each command. For detailed usage about a particular command, type .help <command>")
        embed.add_field(name="GitHub repository", value=f"[GitHub]({GITHUB_LINK})",
                        inline=True)
        embed.add_field(name="Bot Invite link",
                        value=f"[Invite]({BOT_INVITE})",
                        inline=True)
        embed.add_field(name="Support Server", value=f"[Server]({SERVER_INVITE})",
                        inline=True)
        return embed

    @commands.group(brief='Commands related to tournaments! Type .tournament for more details', invoke_without_command=True, aliases=['tourney'])
    async def tournament(self, ctx):
        await ctx.send(embed=self.make_tournament_embed(ctx))

    @tournament.command(name="faq", brief="FAQ")
    async def faq(self, ctx):
        data = [["What formats are supported?",
                 "The bot currently supports 3 types of formats: Single Elimination, Double Elimination and Swiss"],
                ["Where will the tournament be held?",
                 "The tournament will be held on [Challonge](https://challonge.com). The bot will automatically setup the tournament and update brackets."],
                ["How to setup a tournament?",
                 "To setup a tournament type `.tournament setup x y` where x is an integer in the range 0 to 2 (Single Elim, Double Elim, Swiss) denoting tournament type and y is the name of the tournament."],
                ["How to register/unregister for the tournament?",
                 "To register type `.tournament register` and to unregister type `.tournament unregister`. Admins can forcefully unregister a user by typing `.tournament _unregister <handle>`."],
                ["How to start the tournament?",
                 "To start the tournament, type `.tournament begin`"],
                ["How to compete once the tournament has started?",
                 "To compete, use the `.round` command and challenge your opponent. The bot will automatically ask you if you want the result of the round to be counted in the tournament and update the tournament bracket once the round is complete."],
                ["What if my opponent doesn't show up or leaves the server without completing the matches?",
                 "You can ask an admin to use the command `.tournament forcewin <handle>` where handle is the winners codeforces handle."],
                ["What if the bot accidentally gives victory to the wrong user?",
                 "You can ask an admin to invalidate the match results by typing `.tournament match_invalidate x` where x is match number (can be accessed from challonge page of the tournament). This will also reset the subsequent matches whose result depends on this match"]]

        embed = discord.Embed(description='\n\n'.join([f':small_red_triangle_down: **{x[0]}**\n:white_small_square: {x[1]}' for x in data]), color=discord.Color.dark_green())
        embed.set_author(name="Frequently Asked Questions about tournaments")
        await ctx.send(embed=embed)

    @tournament.command(name="setup", brief="Setup a tournament.")
    async def setup(self, ctx, tournament_type: int, *, tournament_name: str):
        """
        **tournament_name:** Alpha-numeric string (Max 50 characters)
        **tournament_type:** Integer (0: single elimination, 1: double elimination, 2: swiss)
        """
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx, f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                    f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return
        if len(tournament_name) not in range(1, 51):
            await discord_.send_message(ctx, "The tournament name should be 50 character max")
            return
        if any([not ch.isalnum() and ch != ' ' for ch in tournament_name]):
            await discord_.send_message(ctx, "The tournament name should contain only alpha-numeric characters")
            return
        if tournament_type not in range(0, 3):
            await discord_.send_message(ctx, "Tournament type should be either 0, 1 or 2. (0: single elimination, 1: double elimination, 2: swiss)")
            return
        if self.db.get_tournament_info(ctx.guild.id):
            await discord_.send_message(ctx, "A tournament is already in progress in this server!")
            return

        self.db.add_tournament(ctx.guild.id, tournament_name, tournament_type, 0, "-", 0)
        types = ["Single Elimination", "Double Elimination", "Swiss"]

        desc = f"""
               Initialised a {types[tournament_type]} tournament. 
               To register, type `.tournament register` (Max registrations: **{MAX_REGISTRANTS}**)
               To unregister, type `.tournament unregister`
               To start the tournament, type `.tournament begin` 
               """
        embed = discord.Embed(description=desc, color=discord.Color.green())
        embed.set_author(name=tournament_name)
        await ctx.send(embed=embed)

    @tournament.command(name="register", brief="Register for the tournament")
    async def register(self, ctx):
        tournament_info = self.db.get_tournament_info(ctx.guild.id)
        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 0:
            await discord_.send_message(ctx, "The tournament has already begun")
            return
        if not self.db.get_handle(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, "Your handle is not set, set your handle first and try again")
            return
        handle_info = self.db.get_handle_info(ctx.guild.id, ctx.author.id)
        registrants = self.db.get_registrants(ctx.guild.id)
        if ctx.author.id in [x.discord_id for x in registrants]:
            await discord_.send_message(ctx, "You have already registered for the tournament")
            return
        if handle_info[2] in [x.handle for x in registrants]:
            await discord_.send_message(ctx, f"Someone has already registered for the tournament with handle `{handle_info[2]}`")
            return
        if len(registrants) == MAX_REGISTRANTS:
            await discord_.send_message(ctx, "The tournament has already reached its max registrants limit!")
            return

        self.db.add_registrant(ctx.guild.id, ctx.author.id, handle_info[2], handle_info[3], 0)

        await ctx.send(embed=discord.Embed(description=f"Successfully registered for the tournament. `{MAX_REGISTRANTS-len(registrants)-1}` slots left.",
                                           color=discord.Color.green()))

    @tournament.command(name="unregister", brief="Unregister from the tournament")
    async def unregister(self, ctx):
        tournament_info = self.db.get_tournament_info(ctx.guild.id)
        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 0:
            await discord_.send_message(ctx, "The tournament has already begun")
            return
        registrants = self.db.get_registrants(ctx.guild.id)
        if ctx.author.id not in [x.discord_id for x in registrants]:
            await discord_.send_message(ctx, "You have not registered for the tournament")
            return

        self.db.remove_registrant(ctx.guild.id, ctx.author.id)
        await ctx.send(embed=discord.Embed(
            description=f"Successfully unregistered from the tournament. `{MAX_REGISTRANTS - len(registrants) + 1}` slots left.",
            color=discord.Color.green()))

    @tournament.command(name="_unregister", brief="Forcefully unregister someone from the tournament")
    async def _unregister(self, ctx, *, handle: str):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx, f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                    f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return
        tournament_info = self.db.get_tournament_info(ctx.guild.id)
        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 0:
            await discord_.send_message(ctx, "The tournament has already begun")
            return
        registrants = self.db.get_registrants(ctx.guild.id)

        res = self.db.remove_registrant_by_handle(ctx.guild.id, handle)
        if not res:
            await discord_.send_message(ctx, f"The user with handle `{handle}` has not registered for the tournament")
            return
        await ctx.send(embed=discord.Embed(
            description=f"Successfully unregistered from the tournament. `{MAX_REGISTRANTS - len(registrants) + 1}` slots left.",
            color=discord.Color.green()))

    @tournament.command(name="registrants", brief="View the list of users who have registered the tournament")
    async def registrants(self, ctx):
        registrants = self.db.get_registrants(ctx.guild.id)
        if not registrants:
            await discord_.send_message(ctx, "No registrations yet")
            return

        await paginator.Paginator([[str(i+1), registrants[i].handle, str(registrants[i].rating)] for i in range(len(registrants))], ["S No.", "Handle", "Rating"], "Registrants for the Lockout tournament", 15).paginate(ctx, self.client)

    @tournament.command(name="info", brief="Get basic information about the tournament")
    async def info(self, ctx):
        tournament_info = self.db.get_tournament_info(ctx.guild.id)
        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return

        desc = ""
        desc += f"**Tournament name**: {tournament_info.name}\n"
        desc += f"**Tournament type**: {['Single Elimination', 'Double Elimination', 'Swiss'][tournament_info.type]}\n"
        desc += f"**Registrations**: {len(self.db.get_registrants(ctx.guild.id))}\n"
        desc += f"**Challonge link**: {'Tournament not started yet' if tournament_info.status == 0 else f'[link](https://challonge.com/{tournament_info.url})'}"

        embed = discord.Embed(description=desc, color=discord.Color.dark_orange())
        embed.set_author(name="Lockout tournament details")
        await ctx.send(embed=embed)

    @tournament.command(name="begin", brief="Begin the tournament", aliases=['start'])
    @commands.cooldown(1, 120, BucketType.guild)
    async def begin(self, ctx):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx, f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                    f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return
        tournament_info = self.db.get_tournament_info(ctx.guild.id)
        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return

        if tournament_info.status == 2:
            await discord_.send_message(ctx, f"The tournament has already begun! Type `.tournament matches` or `.tournament info` to view details about the tournament")
            return

        registrants = self.db.get_registrants(ctx.guild.id)
        if not registrants or len(registrants) < 2:
            await discord_.send_message(ctx, "Not enough registrants for the tournament yet")
            return

        logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))

        if tournament_info.status == 0:
            resp = await discord_.get_time_response(self.client, ctx, "Are you sure you want to start the tournament? No new registrations will be allowed once the tournament has started. Type `1` for yes and `0` for no", 30, ctx.author, [0, 1])
            if not resp[0] or resp[1] == 0:
                ctx.command.reset_cooldown(ctx)
                return
            await ctx.send(f"Setting up tournament...")
            tournament_resp = await self.api.add_tournament(tournament_info)
            if not tournament_resp or 'errors' in tournament_resp:
                ctx.command.reset_cooldown(ctx)
                await discord_.send_message(ctx, "Some error occurred, try again later")
                if tournament_resp and 'errors' in tournament_resp:
                    await logging_channel.send(f"Error in tournament setup: {ctx.guild.id} {tournament_resp['errors']}")
                return

            # api takes some time to register tournament id
            await asyncio.sleep(5)
            await ctx.send(f"Adding participants...")
            participants_resp = await self.api.bulk_add_participants(tournament_resp['tournament']['id'], [{"name": f"{registrants[i].handle} ({registrants[i].rating})", "seed": i+1} for i in range(len(registrants))])

            if not participants_resp or 'errors' in participants_resp:
                ctx.command.reset_cooldown(ctx)
                await discord_.send_message(ctx, "Some error occurred, try again later")
                if participants_resp and 'errors' in participants_resp:
                    await logging_channel.send(f"Error in bulk adding participants: {ctx.guild.id} {participants_resp['errors']}")
                await self.api.delete_tournament(tournament_resp['tournament']['id'])
                return

            await asyncio.sleep(5)
            await ctx.send("Enabling brackets predictions...")
            predictions_resp = await self.api.open_for_predictions(tournament_resp['tournament']['id'])

            if not predictions_resp or 'errors' in predictions_resp:
                ctx.command.reset_cooldown(ctx)
                await discord_.send_message(ctx, "Some error occurred, try again later")
                if predictions_resp and 'errors' in predictions_resp:
                    await logging_channel.send(f"Error in enabling predictions: {ctx.guild.id} {predictions_resp['errors']}")
                await self.api.delete_tournament(tournament_resp['tournament']['id'])
                return

            self.db.update_tournament_params(tournament_resp['tournament']['id'], tournament_resp['tournament']['url'], 1, ctx.guild.id)
            for data in participants_resp:
                self.db.map_user_to_challongeid(ctx.guild.id, registrants[data['participant']['seed']-1].discord_id, data['participant']['id'])

            desc = ""
            desc += f"The tournament has been setup. You can find the brackets [here](https://challonge.com/{tournament_resp['tournament']['url']})\n"
            desc += f"You can now make predictions on each of the brackets and climb up the predictions leaderboard. Make new predictions [here](https://challonge.com/tournaments/{tournament_resp['tournament']['id']}/predictions/new)\n\n"
            desc += f"Note that the tournament has **not** started yet. Once everyone has made their predictions, type `.tournament begin` for the tournament to officially begin\n\n"

            desc += f"**Tournament type**: {['Single Elimination', 'Double Elimination', 'Swiss'][tournament_info.type]}\n"
            desc += f"**Number of registrations**: {len(registrants)}"

            embed = discord.Embed(description=desc, color=discord.Color.green())
            embed.set_author(name=tournament_info.name)
            await ctx.send(embed=embed)
            ctx.command.reset_cooldown(ctx)
        else:
            await ctx.send(f"Starting the tournament...")
            tournament_resp = await self.api.start_tournament(tournament_info.id)
            if not tournament_resp or 'errors' in tournament_resp:
                ctx.command.reset_cooldown(ctx)
                await discord_.send_message(ctx, "Some error occurred, try again later")
                if tournament_resp and 'errors' in tournament_resp:
                    await logging_channel.send(f"Error in tournament setup: {ctx.guild.id} {tournament_resp['errors']}")
                return

            self.db.update_tournament_params(tournament_info.id, tournament_info.url, 2, ctx.guild.id)

            desc = f"The tournament has officially begun! View brackets on this [link](https://challonge.com/{tournament_info.url})\n\n"
            desc += f"To play tournament matches just use the `.round` command of the bot and challenge someone to a round. \n" \
                   f"If the round is part of the tournament, then the bot will ask whether you want the result of the round " \
                   f"to be counted in the tournament. \nIn case of a draw, you will have to play the round again. GLHF!\n\n"
            desc += f"**Some useful commands**:\n\n"
            desc += f"`.tournament matches`: View a list of future matches of the tournament\n"
            desc += f"`.tournament info`: View general info about the tournament\n"
            desc += f"`.tournament forcewin <handle>`: Grant victory to a user without conducting the match\n"
            desc += f"`.tournament invalidate`: Invalidate the tournament\n"

            embed = discord.Embed(description=desc, color=discord.Color.green())
            embed.set_author(name=tournament_info.name)
            await ctx.send(embed=embed)

    @tournament.command(name="delete", brief="Delete the tournament")
    async def delete_(self, ctx):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx,
                                        f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                        f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return
        tournament_info = self.db.get_tournament_info(ctx.guild.id)
        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return

        resp = await discord_.get_time_response(self.client, ctx, "Are you sure you want to delete the tournament? This action is irreversable. Type `1` for yes and `0` for no", 30, ctx.author, [0, 1])
        if resp[0] and resp[1] == 1:
            if tournament_info.status != 0:
                await self.api.delete_tournament(tournament_info.id)
            self.db.delete_tournament(ctx.guild.id)
            await discord_.send_message(ctx, "Tournament has been deleted")

    @tournament.command(name="matches", brief="View the tournament matches")
    @commands.cooldown(1, 10, BucketType.user)
    async def matches(self, ctx):
        tournament_info = self.db.get_tournament_info(ctx.guild.id)

        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 2:
            await discord_.send_message(ctx, "The tournament has not begun yet, type `.tournament begin` to start the tournament")
            return

        matches_resp = await self.api.get_tournament_matches(tournament_info.id)

        if not matches_resp or 'errors' in matches_resp:
            await discord_.send_message(ctx, "Some error occurred, try again later")
            if matches_resp and 'errors' in matches_resp:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(
                    f"Error in displaying matches list: {ctx.guild.id} {matches_resp['errors']}")
            return

        content = []
        for match in matches_resp:
            data = match['match']
            if data['state'] == 'open':
                desc = f"**Round {abs(data['round'])}** {'(Losers bracket)' if data['round'] < 0 else ''}\n"
                user1 = self.db.get_registrant_info(ctx.guild.id, data['player1_id'])
                user2 = self.db.get_registrant_info(ctx.guild.id, data['player2_id'])
                desc += f"{user1.handle} ({user1.rating}) vs ({user2.rating}) {user2.handle}\n"
                content.append(desc)

        await discord_.content_pagination(content, self.client, 10, "Upcoming tournament matches", ctx,
                                          discord.Color.gold(), f"View all matches at https://challonge.com/{tournament_info.url}")

    @tournament.command(name="forcewin", brief="Grant victory to a user without them competing")
    @commands.cooldown(1, 10, BucketType.user)
    async def forcewin(self, ctx, *, handle: str):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx, f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                    f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return

        tournament_info = self.db.get_tournament_info(ctx.guild.id)

        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 2:
            await discord_.send_message(ctx, "The tournament has not begun yet, type `.tournament begin` to start the tournament")
            return

        registrants = self.db.get_registrants(ctx.guild.id)
        challonge_id = None

        for user in registrants:
            if user.handle.lower() == handle.lower():
                challonge_id = user.challonge_id

        if not challonge_id:
            await discord_.send_message(ctx, f"User with handle `{handle}` has not registered for the tournament")
            return

        matches_resp = await self.api.get_tournament_matches(tournament_info.id)

        if not matches_resp or 'errors' in matches_resp:
            await discord_.send_message(ctx, "Some error occurred, try again later")
            if matches_resp and 'errors' in matches_resp:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(
                    f"Error in forcewin match fetching: {ctx.guild.id} {matches_resp['errors']}")
            return

        match_id = None
        player1_id = None
        for match in matches_resp:
            if match['match']['state'] != 'open':
                continue
            if match['match']['player1_id'] == challonge_id or match['match']['player2_id'] == challonge_id:
                match_id = match['match']['id']
                player1_id = match['match']['player1_id']
                break

        if not match_id:
            await discord_.send_message(ctx, f"Couldn't find a match for handle `{handle}`")
            return

        scores = await discord_.get_seq_response(self.client, ctx, f"{ctx.author.mention} enter 2 space seperated integers denoting the scores of winner and loser respectively", 30, 2, ctx.author, [0, 10000])
        if not scores[0]:
            return

        if challonge_id != player1_id:
            scores[1][0], scores[1][1] = scores[1][1], scores[1][0]

        resp = await self.api.post_match_results(tournament_info.id, match_id, f"{scores[1][0]}-{scores[1][1]}", challonge_id)
        if not resp or 'errors' in resp:
            await discord_.send_message(ctx, "Some error occurred, try again later")
            if resp and 'errors' in resp:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(
                    f"Error in forcewin match score reporting: {ctx.guild.id} {resp['errors']}")
        else:
            await discord_.send_message(ctx, f"Granted victory to user with handle `{handle}`")

            if await tournament_helper.validate_tournament_completion(tournament_info.guild, self.api, self.db):
                await self.api.finish_tournament(tournament_info.id)
                winner_handle = await tournament_helper.get_winner(tournament_info.id, self.api)
                await ctx.send(embed=tournament_helper.tournament_over_embed(tournament_info.guild, winner_handle, self.db))
                self.db.delete_tournament(tournament_info.guild)
                self.db.add_to_finished_tournaments(tournament_info, winner_handle)

    @tournament.command(name="forcedraw", brief="Force draw a match (Swiss only)")
    @commands.cooldown(1, 10, BucketType.user)
    async def forcedraw(self, ctx, *, handle: str):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx,
                                        f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                        f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return

        tournament_info = self.db.get_tournament_info(ctx.guild.id)

        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 2:
            await discord_.send_message(ctx, "The tournament has not begun yet, type `.tournament begin` to start the tournament")
            return

        if tournament_info.type != 2:
            await discord_.send_message(ctx, "This command can only be used for swiss tournaments")
            return

        registrants = self.db.get_registrants(ctx.guild.id)
        challonge_id = None

        for user in registrants:
            if user.handle.lower() == handle.lower():
                challonge_id = user.challonge_id

        if not challonge_id:
            await discord_.send_message(ctx, f"User with handle `{handle}` has not registered for the tournament")
            return

        matches_resp = await self.api.get_tournament_matches(tournament_info.id)

        if not matches_resp or 'errors' in matches_resp:
            await discord_.send_message(ctx, "Some error occurred, try again later")
            if matches_resp and 'errors' in matches_resp:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(
                    f"Error in forcewin match fetching: {ctx.guild.id} {matches_resp['errors']}")
            return

        match_id = None
        player1_id = None
        for match in matches_resp:
            if match['match']['state'] != 'open':
                continue
            if match['match']['player1_id'] == challonge_id or match['match']['player2_id'] == challonge_id:
                match_id = match['match']['id']
                player1_id = match['match']['player1_id']
                break

        if not match_id:
            await discord_.send_message(ctx, f"Couldn't find a match for handle `{handle}`")
            return

        scores = await discord_.get_seq_response(self.client, ctx,
                                                 f"{ctx.author.mention} enter 2 space seperated integers denoting the scores of the players",
                                                 30, 2, ctx.author, [0, 10000])
        if not scores[0]:
            return

        if challonge_id != player1_id:
            scores[1][0], scores[1][1] = scores[1][1], scores[1][0]

        resp = await self.api.post_match_results(tournament_info.id, match_id, f"{scores[1][0]}-{scores[1][1]}", "tie")
        if not resp or 'errors' in resp:
            await discord_.send_message(ctx, "Some error occurred, try again later")
            if resp and 'errors' in resp:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(
                    f"Error in forcedraw match score reporting: {ctx.guild.id} {resp['errors']}")
        else:
            await discord_.send_message(ctx, f"Match involving `{handle}` has been drawn")

            if await tournament_helper.validate_tournament_completion(tournament_info.guild, self.api, self.db):
                await self.api.finish_tournament(tournament_info.id)
                winner_handle = await tournament_helper.get_winner(tournament_info.id, self.api)
                await ctx.send(
                    embed=tournament_helper.tournament_over_embed(tournament_info.guild, winner_handle, self.db))
                self.db.delete_tournament(tournament_info.guild)
                self.db.add_to_finished_tournaments(tournament_info, winner_handle)

    @tournament.command(name="match_invalidate", brief="Invalidate the results of a match", aliases=['invalidate_match'])
    @commands.cooldown(1, 10, BucketType.user)
    async def match_invalidate(self, ctx, idx: int):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx,
                                        f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                        f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return

        tournament_info = self.db.get_tournament_info(ctx.guild.id)

        if not tournament_info:
            await discord_.send_message(ctx, "There is no ongoing tournament in the server currently")
            return
        if tournament_info.status != 2:
            await discord_.send_message(ctx,
                                        "The tournament has not begun yet, type `.tournament begin` to start the tournament")
            return

        matches_resp = await self.api.get_tournament_matches(tournament_info.id)

        if not matches_resp or 'errors' in matches_resp:
            await discord_.send_message(ctx, "Some error occurred, try again later")
            if matches_resp and 'errors' in matches_resp:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(
                    f"Error in match_invalidate: {ctx.guild.id} {matches_resp['errors']}")
            return

        match_id = None

        for match in matches_resp:
            if match['match']['state'] == 'complete' and match['match']['suggested_play_order'] == idx:
                match_id = match['match']['id']

        if match_id:
            await self.api.invalidate_match(tournament_info.id, match_id)
            await discord_.send_message(ctx, f"Invalidated match number `{idx}`. All future matches whose results was dependent on this match have also been reset")
        else:
            await discord_.send_message(ctx, f"Couldn't find match number `{idx}`")

    @tournament.command(name="recent", brief="View list of recent tournaments")
    async def recent(self, ctx):
        data = self.db.get_recent_tournaments(ctx.guild.id)

        if not data:
            await discord_.send_message(ctx, "No tournaments have been played so far")
            return

        content = []
        for i in range(len(data)):
            content.append(f"`{len(data)-i}.` [{data[i].name}](https://challonge.com/{data[i].url}) was won by [{data[i].winner}](https://codeforces.com/profile/{data[i].winner}) "
                           f"| {['Single Elimination', 'Double Elimination', 'Swiss'][data[i].type]} | {timeez(int(time.time()) - data[i].time)}")

        await discord_.content_pagination(content, self.client, 10, "Recent tournaments", ctx, discord.Color.dark_purple())


def setup(client):
    client.add_cog(Tournament(client))
