import discord
import asyncio
import os
import math
import traceback

from discord.ext import commands
from discord.ext.commands import cooldown, BucketType

from data import dbconn
from utils import cf_api, discord_, codeforces, updation, elo, tournament_helper, challonge_api
from constants import AUTO_UPDATE_TIME, ADMIN_PRIVILEGE_ROLES


MAX_ROUND_USERS = 5
LOWER_RATING = 800
UPPER_RATING = 3600
MATCH_DURATION = [5, 180]
MAX_PROBLEMS = 6
MAX_ALTS = 5
ROUNDS_PER_PAGE = 5


class Round(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.cf = cf_api.CodeforcesAPI()
        self.api = challonge_api.ChallongeAPI(self.client)

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

    @round.command(name="challenge", brief="Challenge multiple users to a round")
    async def challenge(self, ctx, *users: discord.Member):
        users = list(set(users))
        if len(users) == 0:
            await discord_.send_message(ctx, f"The correct usage is `.round challenge @user1 @user2...`")
            return
        if ctx.author not in users:
            users.append(ctx.author)
        if len(users) > MAX_ROUND_USERS:
            await ctx.send(f"{ctx.author.mention} atmost {MAX_ROUND_USERS} users can compete at a time")
            return
        for i in users:
            if not self.db.get_handle(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"Handle for {i.mention} not set! Use `.handle identify` to register")
                return
            if self.db.in_a_round(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"{i.mention} is already in a round!")
                return

        embed = discord.Embed(description=f"{' '.join(x.mention for x in users)} react on the message with ✅ within 30 seconds to join the round. {'Since you are the only participant, this will be a practice round and there will be no rating changes' if len(users) == 1 else ''}",
            color=discord.Color.purple())
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")

        all_reacted = False
        reacted = []

        def check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji == "✅" and user in users

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=30, check=check)
                reacted.append(user)
                if all(item in reacted for item in users):
                    all_reacted = True
                    break
            except asyncio.TimeoutError:
                break

        if not all_reacted:
            await discord_.send_message(ctx, f"Unable to start round, some participant(s) did not react in time!")
            return

        problem_cnt = await discord_.get_time_response(self.client, ctx, f"{ctx.author.mention} enter the number of problems between [1, {MAX_PROBLEMS}]", 30, ctx.author, [1, MAX_PROBLEMS])
        if not problem_cnt[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        problem_cnt = problem_cnt[1]

        duration = await discord_.get_time_response(self.client, ctx, f"{ctx.author.mention} enter the duration of match in minutes between {MATCH_DURATION}", 30, ctx.author, MATCH_DURATION)
        if not duration[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        duration = duration[1]

        rating = await discord_.get_seq_response(self.client, ctx, f"{ctx.author.mention} enter {problem_cnt} space seperated integers denoting the ratings of problems (between {LOWER_RATING} and {UPPER_RATING})", 60, problem_cnt, ctx.author, [LOWER_RATING, UPPER_RATING])
        if not rating[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        rating = rating[1]

        points = await discord_.get_seq_response(self.client, ctx, f"{ctx.author.mention} enter {problem_cnt} space seperated integer denoting the points of problems (between 100 and 10,000)", 60, problem_cnt, ctx.author, [100, 10000])
        if not points[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        points = points[1]

        repeat = await discord_.get_time_response(self.client, ctx, f"{ctx.author.mention} do you want a new problem to appear when someone solves a problem (type 1 for yes and 0 for no)", 30, ctx.author, [0, 1])
        if not repeat[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        repeat = repeat[1]

        for i in users:
            if self.db.in_a_round(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"{i.name} is already in a round!")
                return

        alts = await discord_.get_alt_response(self.client, ctx, f"{ctx.author.mention} Do you want to add any alts? Type none if not applicable else type `alts: handle_1 handle_2 ...` You can add upto **{MAX_ALTS}** alt(s)", MAX_ALTS, 60, ctx.author)

        if not alts:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return

        alts = alts[1]

        tournament = 0
        if len(users) == 2 and (await tournament_helper.is_a_match(ctx.guild.id, users[0].id, users[1].id, self.api, self.db)):
            tournament = await discord_.get_time_response(self.client, ctx,
                                                      f"{ctx.author.mention} this round is a part of the tournament. Do you want the result of this round to be counted in the tournament. Type `1` for yes and `0` for no",
                                                      30, ctx.author, [0, 1])
            if not tournament[0]:
                await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
                return
            tournament = tournament[1]

        await ctx.send(embed=discord.Embed(description="Starting the round...", color=discord.Color.green()))

        problems = await codeforces.find_problems([self.db.get_handle(ctx.guild.id, x.id) for x in users]+alts, rating)
        if not problems[0]:
            await discord_.send_message(ctx, problems[1])
            return

        problems = problems[1]

        self.db.add_to_ongoing_round(ctx, users, rating, points, problems, duration, repeat, alts, tournament)
        round_info = self.db.get_round_info(ctx.guild.id, users[0].id)

        await ctx.send(embed=discord_.round_problems_embed(round_info))

    @round.command(name="ongoing", brief="View ongoing rounds")
    async def ongoing(self, ctx):
        data = self.db.get_all_rounds(ctx.guild.id)

        content = discord_.ongoing_rounds_embed(data)

        if len(content) == 0:
            await discord_.send_message(ctx, f"No ongoing rounds")
            return

        currPage = 0
        totPage = math.ceil(len(content) / ROUNDS_PER_PAGE)
        text = '\n'.join(content[currPage * ROUNDS_PER_PAGE: min(len(content), (currPage + 1) * ROUNDS_PER_PAGE)])
        embed = discord.Embed(description=text, color=discord.Color.blurple())
        embed.set_author(name="Ongoing Rounds")
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
                    content[currPage * ROUNDS_PER_PAGE: min(len(content), (currPage + 1) * ROUNDS_PER_PAGE)])
                embed = discord.Embed(description=text, color=discord.Color.blurple())
                embed.set_author(name="Ongoing rounds")
                embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
                await message.edit(embed=embed)

            except asyncio.TimeoutError:
                break

    @round.command(brief="Invalidate a round (Admin/Mod/Lockout Manager only)")
    async def _invalidate(self, ctx, member: discord.Member):
        if not discord_.has_admin_privilege(ctx):
            await discord_.send_message(ctx, f"{ctx.author.mention} you require 'manage server' permission or one of the "
                                    f"following roles: {', '.join(ADMIN_PRIVILEGE_ROLES)} to use this command")
            return
        if not self.db.in_a_round(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"{member.mention} is not in a round")
            return
        self.db.delete_round(ctx.guild.id, member.id)
        await discord_.send_message(ctx, f"Round deleted")

    @round.command(name="recent", brief="Show recent rounds")
    async def recent(self, ctx, user: discord.Member=None):
        data = self.db.get_recent_rounds(ctx.guild.id, str(user.id) if user else None)

        content = discord_.recent_rounds_embed(data)

        if len(content) == 0:
            await discord_.send_message(ctx, f"No recent rounds")
            return

        currPage = 0
        totPage = math.ceil(len(content) / ROUNDS_PER_PAGE)
        text = '\n'.join(content[currPage * ROUNDS_PER_PAGE: min(len(content), (currPage + 1) * ROUNDS_PER_PAGE)])
        embed = discord.Embed(description=text, color=discord.Color.blurple())
        embed.set_author(name="Recent Rounds")
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
                    content[currPage * ROUNDS_PER_PAGE: min(len(content), (currPage + 1) * ROUNDS_PER_PAGE)])
                embed = discord.Embed(description=text, color=discord.Color.blurple())
                embed.set_author(name="Recent rounds")
                embed.set_footer(text=f"Page {currPage + 1} of {totPage}")
                await message.edit(embed=embed)

            except asyncio.TimeoutError:
                break

#     @round.command(name="invalidate", brief="Invalidate your round")
#     async def invalidate(self, ctx):
#         if not self.db.in_a_round(ctx.guild.id, ctx.author.id):
#             await ctx.send(f"{ctx.author.mention} you are not in a round")
#             return
#
#         data = self.db.get_round_info(ctx.guild.id, ctx.author.id)
#         try:
#             users = [await ctx.guild.fetch_member(int(x)) for x in data[1].split()]
#         except Exception:
#             await ctx.send(f"{ctx.author.mention} some error occurred! Maybe one of the participants left the server")
#             return
#
#         msg = await ctx.send(f"{' '.join([x.mention for x in users])} react within 30 seconds to invalidate the match")
#         await msg.add_reaction("✅")
#
#         await asyncio.sleep(30)
#         message = await ctx.channel.fetch_message(msg.id)
#
#         reaction = None
#         for x in message.reactions:
#             if x.emoji == "✅":
#                 reaction = x
#
#         reacted = await reaction.users().flatten()
#         for i in users:
#             if i not in reacted:
#                 await ctx.send(f"Unable to invalidate round, {i.name} did not react in time!")
#                 return
#
#         self.db.delete_round(ctx.guild.id, ctx.author.id)
#         await ctx.send(f"Match has been invalidated")
#
    @round.command(brief="Update matches status for the server")
    @cooldown(1, AUTO_UPDATE_TIME, BucketType.guild)
    async def update(self, ctx):
        await ctx.send(embed=discord.Embed(description="Updating rounds for this server", color=discord.Color.green()))
        rounds = self.db.get_all_rounds(ctx.guild.id)

        for round in rounds:
            try:
                resp = await updation.update_round(round)
                if not resp[0]:
                    logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                    await logging_channel.send(f"Error while updating rounds: {resp[1]}")
                    continue
                resp = resp[1]
                channel = self.client.get_channel(round.channel)

                if resp[2] or resp[1]:
                    await channel.send(f"{' '.join([(await ctx.guild.fetch_member(int(m))).mention for m in round.users.split()])} there is an update in standings")

                for i in range(len(resp[0])):
                    if len(resp[0][i]):
                        await channel.send(embed=discord.Embed(
                            description=f"{' '.join([(await ctx.guild.fetch_member(m)).mention for m in resp[0][i]])} has solved problem worth **{round.points.split()[i]}** points",
                            color=discord.Color.blue()))

                if not resp[1] and resp[2]:
                    new_info = self.db.get_round_info(round.guild, round.users)
                    await channel.send(embed=discord_.round_problems_embed(new_info))

                if resp[1]:
                    round_info = self.db.get_round_info(round.guild, round.users)
                    ranklist = updation.round_score(list(map(int, round_info.users.split())),
                                           list(map(int, round_info.status.split())),
                                           list(map(int, round_info.times.split())))
                    eloChanges = elo.calculateChanges([[(await ctx.guild.fetch_member(user.id)), user.rank, self.db.get_match_rating(round_info.guild, user.id)[-1]] for user in ranklist])

                    for id in list(map(int, round_info.users.split())):
                        self.db.add_rating_update(round_info.guild, id, eloChanges[id][0])

                    self.db.delete_round(round_info.guild, round_info.users)
                    self.db.add_to_finished_rounds(round_info)

                    embed = discord.Embed(color=discord.Color.dark_magenta())
                    pos, name, ratingChange = '', '', ''
                    for user in ranklist:
                        handle = self.db.get_handle(round_info.guild, user.id)
                        emojis = [":first_place:", ":second_place:", ":third_place:"]
                        pos += f"{emojis[user.rank-1] if user.rank <= len(emojis) else str(user.rank)} **{user.points}**\n"
                        name += f"[{handle}](https://codeforces.com/profile/{handle})\n"
                        ratingChange += f"{eloChanges[user.id][0]} (**{'+' if eloChanges[user.id][1] >= 0 else ''}{eloChanges[user.id][1]}**)\n"
                    embed.add_field(name="Position", value=pos)
                    embed.add_field(name="User", value=name)
                    embed.add_field(name="Rating changes", value=ratingChange)
                    embed.set_author(name=f"Round over! Final standings")
                    await channel.send(embed=embed)

                    if round_info.tournament == 1:
                        tournament_info = self.db.get_tournament_info(round_info.guild)
                        if not tournament_info or tournament_info.status != 2:
                            continue
                        if ranklist[1].rank == 1 and tournament_info.type != 2:
                            await discord_.send_message(channel, "Since the round ended in a draw, you will have to compete again for it to be counted in the tournament")
                        else:
                            res = await tournament_helper.validate_match(round_info.guild, ranklist[0].id, ranklist[1].id, self.api, self.db)
                            if not res[0]:
                                await discord_.send_message(channel, res[1] + "\n\nIf you think this is a mistake, type `.tournament forcewin <handle>` to grant victory to a user")
                            else:
                                draw = True if ranklist[1].rank == 1 else False
                                scores = f"{ranklist[0].points}-{ranklist[1].points}" if res[1]['player1'] == res[1][
                                    ranklist[0].id] else f"{ranklist[1].points}-{ranklist[0].points}"
                                match_resp = await self.api.post_match_results(res[1]['tournament_id'], res[1]['match_id'], scores, res[1][ranklist[0].id] if not draw else "tie")
                                if not match_resp or 'errors' in match_resp:
                                    await discord_.send_message(channel, "Some error occurred while validating tournament match. \n\nType `.tournament forcewin <handle>` to grant victory to a user manually")
                                    if match_resp and 'errors' in match_resp:
                                        logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                                        await logging_channel.send(f"Error while validating tournament rounds: {match_resp['errors']}")
                                    continue
                                winner_handle = self.db.get_handle(round_info.guild, ranklist[0].id)
                                await discord_.send_message(channel, f"{f'Congrats **{winner_handle}** for qualifying to the next round. :tada:' if not draw else 'The round ended in a draw!'}\n\nTo view the list of future tournament rounds, type `.tournament matches`")
                                if await tournament_helper.validate_tournament_completion(round_info.guild, self.api, self.db):
                                    await self.api.finish_tournament(res[1]['tournament_id'])
                                    await asyncio.sleep(3)
                                    winner_handle = await tournament_helper.get_winner(res[1]['tournament_id'], self.api)
                                    await channel.send(embed=tournament_helper.tournament_over_embed(round_info.guild, winner_handle, self.db))
                                    self.db.add_to_finished_tournaments(self.db.get_tournament_info(round_info.guild), winner_handle)
                                    self.db.delete_tournament(round_info.guild)

            except Exception as e:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(f"Error while updating rounds: {str(traceback.format_exc())}")

    @round.command(name="problems", brief="View problems of a round")
    async def problems(self, ctx, member: discord.Member=None):
        if not member:
            member = ctx.author
        if not self.db.in_a_round(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"{member.mention} is not in a round")
            return

        round_info = self.db.get_round_info(ctx.guild.id, member.id)
        await ctx.send(embed=discord_.round_problems_embed(round_info))

    @round.command(name="custom", brief="Challenge to a round with custom problemset")
    async def custom(self, ctx, *users: discord.Member):
        users = list(set(users))
        if len(users) == 0:
            await discord_.send_message(ctx, f"The correct usage is `.round custom @user1 @user2...`")
            return
        if ctx.author not in users:
            users.append(ctx.author)
        if len(users) > MAX_ROUND_USERS:
            await ctx.send(f"{ctx.author.mention} atmost {MAX_ROUND_USERS} users can compete at a time")
            return
        for i in users:
            if not self.db.get_handle(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"Handle for {i.mention} not set! Use `.handle identify` to register")
                return
            if self.db.in_a_round(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"{i.mention} is already in a round!")
                return

        embed = discord.Embed(
            description=f"{' '.join(x.mention for x in users)} react on the message with ✅ within 30 seconds to join the round. {'Since you are the only participant, this will be a practice round and there will be no rating changes' if len(users) == 1 else ''}",
            color=discord.Color.purple())
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")

        all_reacted = False
        reacted = []

        def check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji == "✅" and user in users

        while True:
            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=30, check=check)
                reacted.append(user)
                if all(item in reacted for item in users):
                    all_reacted = True
                    break
            except asyncio.TimeoutError:
                break

        if not all_reacted:
            await discord_.send_message(ctx, f"Unable to start round, some participant(s) did not react in time!")
            return

        problem_cnt = await discord_.get_time_response(self.client, ctx,
                                                       f"{ctx.author.mention} enter the number of problems between [1, {MAX_PROBLEMS}]",
                                                       30, ctx.author, [1, MAX_PROBLEMS])
        if not problem_cnt[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        problem_cnt = problem_cnt[1]

        duration = await discord_.get_time_response(self.client, ctx,
                                                    f"{ctx.author.mention} enter the duration of match in minutes between {MATCH_DURATION}",
                                                    30, ctx.author, MATCH_DURATION)
        if not duration[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        duration = duration[1]

        problems = await discord_.get_problems_response(self.client, ctx,
                                                 f"{ctx.author.mention} enter {problem_cnt} space seperated problem ids denoting the problems. Eg: `123/A 455/B 242/C ...`",
                                                 60, problem_cnt, ctx.author)
        if not problems[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        problems = problems[1]

        points = await discord_.get_seq_response(self.client, ctx,
                                                 f"{ctx.author.mention} enter {problem_cnt} space seperated integer denoting the points of problems (between 100 and 10,000)",
                                                 60, problem_cnt, ctx.author, [100, 10000])
        if not points[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        points = points[1]

        for i in users:
            if self.db.in_a_round(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"{i.name} is already in a round!")
                return
        rating = [problem.rating for problem in problems]

        tournament = 0
        if len(users) == 2 and (await tournament_helper.is_a_match(ctx.guild.id, users[0].id, users[1].id, self.api, self.db)):
            tournament = await discord_.get_time_response(self.client, ctx,
                                                          f"{ctx.author.mention} this round is a part of the tournament. Do you want the result of this round to be counted in the tournament. Type `1` for yes and `0` for no",
                                                          30, ctx.author, [0, 1])
            if not tournament[0]:
                await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
                return
            tournament = tournament[1]

        await ctx.send(embed=discord.Embed(description="Starting the round...", color=discord.Color.green()))
        self.db.add_to_ongoing_round(ctx, users, rating, points, problems, duration, 0, [], tournament)
        round_info = self.db.get_round_info(ctx.guild.id, users[0].id)

        await ctx.send(embed=discord_.round_problems_embed(round_info))


def setup(client):
    client.add_cog(Round(client))