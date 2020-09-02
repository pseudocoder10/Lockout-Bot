import aiohttp
import asyncio


class CodeforcesAPI:
    def __init__(self):
        pass

    async def api_response(self, url):
        try:
            tries = 0
            async with aiohttp.ClientSession() as session:
                while tries < 5:
                    tries += 1
                    async with session.get(url) as resp:
                        response = await resp.json()
                        if response['status'] == 'FAILED' and 'limit exceeded' in response['comment'].lower():
                            await asyncio.sleep(1)
                        else:
                            return response
                return response
        except Exception:
            return None

    async def check_handle(self, handle):
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if not response:
            return [False, "Codeforces API Error"]
        if response["status"] != "OK":
            return [False, "Handle not found."]
        else:
            data = response["result"][0]
            return [True, data]

    async def get_contest_list(self):
        url = "https://codeforces.com/api/contest.list"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response

    async def get_problem_list(self):
        url = "https://codeforces.com/api/problemset.problems"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response

    async def get_user_problems(self, handle):
        url = f"https://codeforces.com/api/user.status?handle={handle}"
        response = await self.api_response(url)
        if not response:
            return [False]
        try:
            data = []
            for x in response['result']:
                y = x['problem']
                if 'rating' not in y:
                    continue
                data.append((y['contestId'], y['index'], y['name'], y['type'], y['rating'], None))
            return [True, data]
        except Exception as e:
            return [False]

    async def get_submissions(self, handle):
        url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=50"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response['result']

    async def get_rating(self, handle):
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if 'rating' in response["result"][0]:
            return response["result"][0]["rating"]
        else:
            return 0

    async def get_first_name(self, handle):
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if not response or "firstName" not in response["result"][0]:
            return None
        return response["result"][0]["firstName"]
