import aiohttp
from random import randint


class CodeforcesAPI:
    def __init__(self):
        self.url = ""

    async def api_response(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as resp:
                    response = await resp.json()
                    return response
        except Exception:
            return None

    async def check_handle(self, handle):
        self.url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response()
        if not response:
            return [False, "Codeforces API Error"]
        if response["status"] != "OK":
            return [False, "Handle not found."]
        else:
            data = response["result"][0]
            return [True, data]

    async def get_contest_list(self):
        self.url = "https://codeforces.com/api/contest.list"
        response = await self.api_response()
        if not response:
            return False
        else:
            return response

    async def get_problem_list(self):
        self.url = "https://codeforces.com/api/problemset.problems"
        response = await self.api_response()
        if not response:
            return False
        else:
            return response

    async def get_user_problems(self, handle):
        self.url = f"https://codeforces.com/api/user.status?handle={handle}"
        response = await self.api_response()
        if not response:
            return False
        try:
            data = []
            for x in response['result']:
                y = x['problem']
                if 'rating' not in y:
                    continue
                data.append((y['contestId'], y['index'], y['name'], y['type'], y['rating'], None))
            return data
        except Exception:
            return False

    async def get_submissions(self, handle):
        self.url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=10"
        response = await self.api_response()
        if not response:
            return False
        else:
            return response['result']

    async def get_rating(self, handle):
        self.url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response()
        if 'rating' in response["result"][0]:
            return response["result"][0]["rating"]
        else:
            return 0

    async def get_first_name(self, handle):
        self.url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response()
        if not response or "firstName" not in response["result"][0]:
            return None
        return response["result"][0]["firstName"]