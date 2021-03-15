import discord

from utils import challonge_api
from data import dbconn


async def is_a_match(guild, p1_id, p2_id, api: challonge_api.ChallongeAPI, db: dbconn.DbConn):
    tournament_info = db.get_tournament_info(guild)
    if not tournament_info or tournament_info.status != 2:
        return False

    matches = await api.get_tournament_matches(tournament_info.id)
    if not matches or 'error' in matches:
        return False
    p1_id, p2_id = db.get_challonge_id(guild, p1_id), db.get_challonge_id(guild, p2_id)
    if not p1_id or not p2_id:
        return False
    for match in matches:
        data = match['match']
        if data['state'] == 'open' and ((data['player1_id'] == p1_id and data['player2_id'] == p2_id) or (data['player1_id'] == p2_id and data['player2_id'] == p1_id)):
            return True

    return False


async def validate_match(guild, p1_id, p2_id, api: challonge_api.ChallongeAPI, db: dbconn.DbConn):
    tournament_info = db.get_tournament_info(guild)
    if not tournament_info or tournament_info.status != 2:
        return [False, "Couldn't validate tournament match: Tournament not found"]

    matches = await api.get_tournament_matches(tournament_info.id)
    if not matches:
        return [False, "Couldn't validate tournament match: API Error"]
    p1_cid, p2_cid = db.get_challonge_id(guild, p1_id), db.get_challonge_id(guild, p2_id)
    if not p1_cid or not p2_cid:
        return [False, "Couldn't validate tournament match: User not found"]

    for match in matches:
        data = match['match']
        if data['state'] == 'open' and ((data['player1_id'] == p1_cid and data['player2_id'] == p2_cid) or (data['player1_id'] == p2_cid and data['player2_id'] == p1_cid)):
            res = {p1_id: p1_cid, p2_id: p2_cid, 'match_id': data['id'], 'tournament_id': data['tournament_id'],
                   'player1': data['player1_id']}
            return [True, res]

    return [False, "Couldn't validate tournament match: Unable to find the match"]


async def validate_tournament_completion(guild, api: challonge_api.ChallongeAPI, db: dbconn.DbConn):
    tournament_info = db.get_tournament_info(guild)
    if not tournament_info or tournament_info.status != 2:
        return False

    matches = await api.get_tournament_matches(tournament_info.id)
    if not matches:
        return False
    for match in matches:
        if match['match']['state'] == 'open':
            return False
        if match['match']['state'] == 'pending':
            return False
    return True


async def get_winner(tournament_id, api:challonge_api.ChallongeAPI):
    participants = await api.get_particiapnts_info(tournament_id)
    for user in participants:
        if user['participant']['final_rank'] == 1:
            return user['participant']['name'].split()[0]
    return None


def tournament_over_embed(guild, winner, db: dbconn.DbConn):
    tournament_info = db.get_tournament_info(guild)

    desc = f"The tournament has successfully completed! Congrats to **{winner}** for winning the tournament :tada:\n\n"
    desc += f"Number of participants: **{len(db.get_registrants(guild))}**\n"
    desc += f"Tournament type: **{['Single Elimination', 'Double Elimination', 'Swiss'][tournament_info.type]}**\n"
    desc += f"View complete results [here](https://challonge.com/{tournament_info.url})"

    embed = discord.Embed(description=desc, color=discord.Color.green())
    embed.set_author(name=tournament_info.name)
    return embed
