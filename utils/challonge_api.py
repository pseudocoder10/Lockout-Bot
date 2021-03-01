import aiohttp
import os
import traceback

BASE_URL = "https://api.challonge.com/v1/"


class ChallongeAPI:
    def __init__(self, client):
        self.api_key = os.environ.get("CHALLONGE_KEY")
        self.client = client

    async def api_response(self, method, url, params=None):
        try:
            headers = {'Content-Type': 'application/json'}
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, json=params, headers=headers) as resp:
                    response = await resp.json()
                    return response
        except Exception as e:
            logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
            await logging_channel.send(f"Error while updating matches: {str(traceback.format_exc())}")
            return None

    async def add_tournament(self, tournament_info):
        url = BASE_URL + "tournaments.json"
        params = {
            "api_key": self.api_key,
            "tournament": {
                "name": tournament_info.name,
                "game_name": "Competitive Programming",
                "prediction_method": 1,
                "tournament_type": ["single elimination", "double elimination", "swiss"][tournament_info.type],
                "private": "true"
            }
        }
        return await self.api_response("POST", url, params)

    async def bulk_add_participants(self, tournament_id, participants):
        url = BASE_URL + f"tournaments/{tournament_id}/participants/bulk_add.json"

        params = {
            "api_key": self.api_key,
            "participants": participants
        }
        return await self.api_response("POST", url, params)

    async def delete_tournament(self, tournament_id):
        url = BASE_URL + f"tournaments/{tournament_id}.json?api_key={self.api_key}"
        await self.api_response("DELETE", url)

    async def open_for_predictions(self, tournament_id):
        url = BASE_URL + f"tournaments/{tournament_id}/open_for_predictions.json"
        params = {
            "api_key": self.api_key
        }

        return await self.api_response("POST", url, params)

    async def start_tournament(self, tournament_id):
        url = BASE_URL + f"tournaments/{tournament_id}/start.json"
        params = {
            "api_key": self.api_key
        }

        return await self.api_response("POST", url, params)

    async def get_tournament_matches(self, tournament_id):
        url = BASE_URL + f"tournaments/{tournament_id}/matches.json?api_key={self.api_key}"
        return await self.api_response("GET", url)

    async def get_particiapnts_info(self, tournament_id):
        url = BASE_URL + f"tournaments/{tournament_id}/participants.json?api_key={self.api_key}"
        return await self.api_response("GET", url)

    async def post_match_results(self, tournament_id, match_id, scores, winner_id):
        url = BASE_URL + f"tournaments/{tournament_id}/matches/{match_id}.json"
        params = {
            "api_key": self.api_key,
            "match": {
                "scores_csv": scores,
                "winner_id": winner_id
            }
        }

        return await self.api_response("PUT", url, params)

    async def invalidate_match(self, tournament_id, match_id):
        url = BASE_URL + f"tournaments/{tournament_id}/matches/{match_id}/reopen.json"
        params = {
            "api_key": self.api_key,
        }

        return await self.api_response("POST", url, params)

    async def finish_tournament(self, tournament_id):
        url = BASE_URL + f"tournaments/{tournament_id}/finalize.json"
        params = {
            "api_key": self.api_key
        }

        return await self.api_response("POST", url, params)



