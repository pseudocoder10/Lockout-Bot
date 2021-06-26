import aiohttp
import asyncio

from collections import namedtuple


class CodeforcesAPI:
    def __init__(self):
        pass

    async def api_response(self, url, params=None):
        try:
            tries = 0
            async with aiohttp.ClientSession() as session:
                while tries < 5:
                    tries += 1
                    async with session.get(url, params=params) as resp:
                        response = {}
                        if resp.status == 503:
                            response['status'] = "FAILED"
                            response['comment'] = "limit exceeded"
                        else:
                            response = await resp.json()

                        if response['status'] == 'FAILED' and 'limit exceeded' in response['comment'].lower():
                            await asyncio.sleep(1)
                        else:
                            return response
                return response
        except Exception as e:
            return None

    async def check_handle(self, handle):
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if not response:
            return [False, "Codeforces API Error"]
        if response["status"] != "OK":
            return [False, response["comment"]]
        else:
            return [True, response["result"][0]]

    async def get_contest_list(self):
        url = "https://codeforces.com/api/contest.list"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response['result']

    async def get_problem_list(self):
        url = "https://codeforces.com/api/problemset.problems"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response['result']['problems']

    async def get_user_problems(self, handle, count=None):
        url = f"https://codeforces.com/api/user.status?handle={handle}"
        if count:
            url += f"&from=1&count={count}"
        response = await self.api_response(url)
        if not response:
            return [False, "CF API Error"]
        if response['status'] != 'OK':
            return [False, response['comment']]
        try:
            data = []
            Problem = namedtuple('Problem', 'id index name type rating, sub_time, verdict')
            for x in response['result']:
                y = x['problem']
                if 'rating' not in y:
                    continue
                if 'verdict' not in x:
                    x['verdict'] = None
                data.append(Problem(y['contestId'], y['index'], y['name'], y['type'], y['rating'],
                                    x['creationTimeSeconds'], x['verdict']))
            return [True, data]
        except Exception as e:
            return [False, str(e)]

    async def get_rating(self, handle):
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if response is None:
            return None
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

    async def get_user_info(self, handles):
        url = f"https://codeforces.com/api/user.info"
        response = await self.api_response(url, handles)
        return response['result']
