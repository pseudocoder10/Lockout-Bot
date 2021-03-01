import os
import discord
import time
import traceback
import asyncio

from datetime import date
from operator import itemgetter

from data import dbconn
from constants import BACKUP_DIR
from utils import updation, discord_, elo, cf_api, scraper, tournament_helper, challonge_api


db = dbconn.DbConn()
cf = cf_api.CodeforcesAPI()
api = None


async def update_matches(client):
    matches = db.get_all_matches()
    for match in matches:
        try:
            # updates, over, match_status
            guild = client.get_guild(match.guild)
            resp = await updation.update_match(match)
            if not resp[0]:
                logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(f"Error while updating matches: {resp[1]}")
                continue
            resp = resp[1]
            channel = client.get_channel(match.channel)
            if resp[1] or len(resp[0]) > 0:
                mem1, mem2 = await guild.fetch_member(match.p1_id), await guild.fetch_member(match.p2_id)
                await channel.send(
                    f"{mem1.mention} {mem2.mention}, there is an update in standings!")

            for x in resp[0]:
                await channel.send(embed=discord.Embed(
                    description=f"{' '.join([(await guild.fetch_member(m)).mention for m in x[1]])} has solved problem worth {x[0] * 100} points",
                    color=discord.Color.blue()))

            if not resp[1] and len(resp[0]) > 0:
                await channel.send(
                    embed=discord_.match_problems_embed(db.get_match_info(guild.id, match.p1_id)))

            if resp[1]:
                a, b = updation.match_score(resp[2])
                p1_rank, p2_rank = 1 if a >= b else 2, 1 if b >= a else 2
                ranklist = []
                ranklist.append([await guild.fetch_member(match.p1_id), p1_rank,
                                 db.get_match_rating(guild.id, match.p1_id)[-1]])
                ranklist.append([await guild.fetch_member(match.p2_id), p2_rank,
                                 db.get_match_rating(guild.id, match.p2_id)[-1]])
                ranklist = sorted(ranklist, key=itemgetter(1))
                res = elo.calculateChanges(ranklist)

                db.add_rating_update(guild.id, match.p1_id, res[match.p1_id][0])
                db.add_rating_update(guild.id, match.p2_id, res[match.p2_id][0])
                db.delete_match(match.guild, match.p1_id)
                db.add_to_finished(match, resp[2])

                embed = discord.Embed(color=discord.Color.dark_magenta())
                pos, name, ratingChange = '', '', ''
                for user in ranklist:
                    pos += f"{':first_place:' if user[1] == 1 else ':second_place:'}\n"
                    name += f"{user[0].mention}\n"
                    ratingChange += f"{res[user[0].id][0]} (**{'+' if res[user[0].id][1] >= 0 else ''}{res[user[0].id][1]}**)\n"
                embed.add_field(name="Position", value=pos)
                embed.add_field(name="User", value=name)
                embed.add_field(name="Rating changes", value=ratingChange)
                embed.set_author(name=f"Match over! Final standings\nScore: {a}-{b}")
                await channel.send(embed=embed)
        except Exception as e:
            logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
            await logging_channel.send(f"Error while updating matches: {str(traceback.format_exc())}")


async def update_rounds(client):
    rounds = db.get_all_rounds()
    global api
    if api is None:
        api = challonge_api.ChallongeAPI(client)
    for round in rounds:
        try:
            guild = client.get_guild(round.guild)
            resp = await updation.update_round(round)
            if not resp[0]:
                logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(f"Error while updating rounds: {resp[1]}")
                continue
            resp = resp[1]
            channel = client.get_channel(round.channel)

            if resp[2] or resp[1]:
                await channel.send(
                    f"{' '.join([(await guild.fetch_member(int(m))).mention for m in round.users.split()])} there is an update in standings")

            for i in range(len(resp[0])):
                if len(resp[0][i]):
                    await channel.send(embed=discord.Embed(
                        description=f"{' '.join([(await guild.fetch_member(m)).mention for m in resp[0][i]])} has solved problem worth **{round.points.split()[i]}** points",
                        color=discord.Color.blue()))

            if not resp[1] and resp[2]:
                new_info = db.get_round_info(round.guild, round.users)
                await channel.send(embed=discord_.round_problems_embed(new_info))

            if resp[1]:
                round_info = db.get_round_info(round.guild, round.users)
                ranklist = updation.round_score(list(map(int, round_info.users.split())),
                                                list(map(int, round_info.status.split())),
                                                list(map(int, round_info.times.split())))
                eloChanges = elo.calculateChanges([[(await guild.fetch_member(user.id)), user.rank,
                                                    db.get_match_rating(round_info.guild, user.id)[-1]] for user in
                                                   ranklist])

                for id in list(map(int, round_info.users.split())):
                    db.add_rating_update(round_info.guild, id, eloChanges[id][0])

                db.delete_round(round_info.guild, round_info.users)
                db.add_to_finished_rounds(round_info)

                embed = discord.Embed(color=discord.Color.dark_magenta())
                pos, name, ratingChange = '', '', ''
                for user in ranklist:
                    handle = db.get_handle(round_info.guild, user.id)
                    emojis = [":first_place:", ":second_place:", ":third_place:"]
                    pos += f"{emojis[user.rank - 1] if user.rank <= len(emojis) else str(user.rank)} **{user.points}**\n"
                    name += f"[{handle}](https://codeforces.com/profile/{handle})\n"
                    ratingChange += f"{eloChanges[user.id][0]} (**{'+' if eloChanges[user.id][1] >= 0 else ''}{eloChanges[user.id][1]}**)\n"
                embed.add_field(name="Position", value=pos)
                embed.add_field(name="User", value=name)
                embed.add_field(name="Rating changes", value=ratingChange)
                embed.set_author(name=f"Round over! Final standings")
                await channel.send(embed=embed)

                if round_info.tournament == 1:
                    if ranklist[1].rank == 1:
                        await discord_.send_message(channel, "Since the round ended in a draw, you will have to compete again for it to be counted in the tournament")
                    else:
                        res = await tournament_helper.validate_match(round_info.guild, ranklist[0].id, ranklist[1].id, api, db)
                        if not res[0]:
                            await discord_.send_message(channel, res[1] + "\n\nIf you think this is a mistake, type `.tournament forcewin <handle>` to grant victory to a user")
                        else:
                            scores = f"{ranklist[0].points}-{ranklist[1].points}" if res[1]['player1'] == res[1][ranklist[0].id] else f"{ranklist[1].points}-{ranklist[0].points}"
                            match_resp = await api.post_match_results(res[1]['tournament_id'], res[1]['match_id'], scores, res[1][ranklist[0].id])
                            if not match_resp or 'errors' in match_resp:
                                await discord_.send_message(channel, "Some error occurred while validating tournament match. \n\nType `.tournament forcewin <handle>` to grant victory to a user manually")
                                if match_resp and 'errors' in match_resp:
                                    logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                                    await logging_channel.send(f"Error while validating tournament rounds: {match_resp['errors']}")
                                continue
                            winner_handle = db.get_handle(round_info.guild, ranklist[0].id)
                            await discord_.send_message(channel, f"Congrats **{winner_handle}** for qualifying to the next round.\n\nTo view the list of future tournament rounds, type `.tournament matches`")
                            if await tournament_helper.validate_tournament_completion(round_info.guild, api, db):
                                await api.finish_tournament(res[1]['tournament_id'])
                                await asyncio.sleep(3)
                                winner_handle = await tournament_helper.get_winner(res[1]['tournament_id'], api)
                                await channel.send(embed=tournament_helper.tournament_over_embed(round_info.guild, winner_handle, db))
                                db.add_to_finished_tournaments(db.get_tournament_info(round_info.guild), winner_handle)
                                db.delete_tournament(round_info.guild)

        except Exception as e:
            logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
            await logging_channel.send(f"Error while updating rounds: {str(traceback.format_exc())}")


async def create_backup(client):
    logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
    await logging_channel.send("Attempting to take backup...")
    try:
        if not os.path.isdir(BACKUP_DIR):
            os.mkdir(BACKUP_DIR)
        filename = f"lockout_backup_{date.today().strftime('%d_%m_%y')}_{int(time.time())}"
        command = f"pg_dump --dbname=postgresql://{os.environ.get('DB_USERNAME')}:{os.environ.get('DB_PASSWORD')}@127.0.0.1:5432/{os.environ.get('DB_NAME')} > {BACKUP_DIR+filename}.bak"
        os.system(command)
        await logging_channel.send("Backup taken successfully")
    except Exception as e:
        await logging_channel.send(f"Failed to take backup: {str(traceback.format_exc())}")


async def update_ratings(client):
    logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
    await logging_channel.send("Attempting to update ratings...")
    try:
        handles = [x[2] for x in db.get_all_handles()]
        handles = list(set(handles))

        CHAR_LIMIT = 3000

        segments = []
        curr = []
        c = 0

        for handle in handles:
            if len(handle) + c > CHAR_LIMIT:
                segments.append(curr)
                curr = []
                c = 0
            curr.append(handle)
            c += len(handle)

        segments.append(curr)

        for segment in segments:
            data = await cf.get_user_info({'handles': ';'.join(segment)})
            for user in data:
                db.update_cf_rating(user['handle'], user['rating'] if 'rating' in user else 0)

        await logging_channel.send("Ratings updated successfully")
    except Exception as e:
        await logging_channel.send(f"Error while updating ratings: {str(traceback.format_exc())}")


def isNonStandard(contest_name):
    names = [
        'wild', 'fools', 'unrated', 'surprise', 'unknown', 'friday', 'q#', 'testing',
        'marathon', 'kotlin', 'onsite', 'experimental', 'abbyy']
    for x in names:
        if x in contest_name.lower():
            return True
    return False


async def update_problemset(client):
    logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
    await logging_channel.send("Attempting to update problemset...")

    contest_id = [x[0] for x in db.get_contests_id()]
    problem_id = [x.id for x in db.get_problems()]
    contest_list = await cf.get_contest_list()
    problem_list = await cf.get_problem_list()

    mapping = {}

    con_cnt, prob_cnt = 0, 0

    try:
        for contest in contest_list:
            mapping[contest['id']] = contest['name']
            if contest['id'] not in contest_id and contest['phase'] == "FINISHED" and not isNonStandard(contest['name']):
                con_cnt += 1
                db.add_contest(contest['id'], contest['name'])

        for problem in problem_list:
            if problem['contestId'] in mapping and not isNonStandard(mapping[problem['contestId']]) and 'rating' in problem and problem['contestId'] not in problem_id:
                prob_cnt += 1
                db.add_problem(problem['contestId'], problem['index'], problem['name'], problem['type'], problem['rating'])
        await logging_channel.send(f"Problemset Updated, added {con_cnt} new contests and {prob_cnt} new problems")
    except Exception as e:
        await logging_channel.send(f"Error while updating problemset: {str(traceback.format_exc())}")


async def scrape_authors(client):
    logging_channel = await client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
    await logging_channel.send("Scraping contest author list...")
    try:
        scraper.run()
        await logging_channel.send("Done")
    except Exception as e:
        await logging_channel.send(f"Error while scraping {str(traceback.format_exc())}")




