import time

from functools import cmp_to_key
from collections import namedtuple

from data import dbconn
from utils import cf_api, codeforces

db = dbconn.DbConn()
cf = cf_api.CodeforcesAPI()

RECENT_SUBS_LIMIT = 50


def match_score(status):
    a, b = 0, 0

    for i in range(5):
        if status[i] == '1':
            a += 100 * (i + 1)
        if status[i] == '2':
            b += 100 * (i + 1)
        if status[i] == '3':
            a += 50 * (i + 1)
            b += 50 * (i + 1)

    return a, b


def no_change_possible(match_status):
    a, b = match_score(match_status)
    left = 0
    for i in range(5):
        if match_status[i] == '0':
            left += (i + 1) * 100

    if abs(a - b) > left or left == 0:
        return True
    return False


async def update_match(match_info):
    handle1, handle2 = db.get_handle(match_info.guild, match_info.p1_id), db.get_handle(match_info.guild,
                                                                                        match_info.p2_id)
    enter_time = time.time()
    sub1, sub2 = await cf.get_user_problems(handle1, RECENT_SUBS_LIMIT), await cf.get_user_problems(handle2,
                                                                                                    RECENT_SUBS_LIMIT)
    if not sub1[0]:
        return sub1
    if not sub2[0]:
        return sub2
    sub1, sub2 = sub1[1], sub2[1]

    judging, over = False, False
    problems = match_info.problems.split()

    updates = []
    new_status = ''

    for i in range(5):
        if match_info.status[i] != '0':
            new_status += match_info.status[i]
            continue

        time1, time2 = codeforces.get_solve_time(sub1, int(problems[i].split('/')[0]), problems[i].split('/')[1]), \
                       codeforces.get_solve_time(sub2, int(problems[i].split('/')[0]), problems[i].split('/')[1])

        if time1 == -1 or time2 == -1:
            judging = True
            new_status += match_info.status[i]
            continue

        if time1 < time2 and time1 <= match_info.time + 60 * match_info.duration:
            updates.append([i + 1, [match_info.p1_id]])
            new_status += '1'
        elif time2 < time1 and time2 <= match_info.time + 60 * match_info.duration:
            updates.append([i + 1, [match_info.p2_id]])
            new_status += '2'
        elif time1 == time2 and time1 <= match_info.time + 60 * match_info.duration:
            updates.append([i + 1, [match_info.p1_id, match_info.p2_id]])
            new_status += '3'
        else:
            new_status += '0'

    if len(updates):
        db.update_match_status(match_info, new_status)
    if not judging and (enter_time > match_info.time + 60 * match_info.duration or no_change_possible(new_status)):
        over = True

    return [True, [updates, over, new_status]]


def round_score(users, status, times):
    def comp(a, b):
        if a[0] > b[0]:
            return -1
        if a[0] < b[0]:
            return 1
        if a[1] == b[1]:
            return 0
        return -1 if a[1] < b[1] else 1

    ranks = [[status[i], times[i], users[i]] for i in range(len(status))]
    ranks.sort(key=cmp_to_key(comp))
    res = []

    for user in ranks:
        User = namedtuple("User", "id points rank")
        # user points rank
        res.append(User(user[2], user[0], [[x[0], x[1]] for x in ranks].index([user[0], user[1]]) + 1))
    return res


def no_round_change_possible(status, points, problems):
    status.sort()
    sum = 0
    for i in range(len(points)):
        if problems[i] != '0':
            sum = sum + points[i]
    for i in range(len(status) - 1):
        if status[i] + sum > status[i + 1]:
            return False
    if len(status) == 1 and sum > 0:
        return False
    return True


async def update_round(round_info):
    users = list(map(int, round_info.users.split()))
    handles = [db.get_handle(round_info.guild, user) for user in users]
    rating = list(map(int, round_info.rating.split()))
    enter_time = time.time()
    points = list(map(int, round_info.points.split()))
    status = list(map(int, round_info.status.split()))
    timestamp = list(map(int, round_info.times.split()))
    subs = [await cf.get_user_problems(handle, RECENT_SUBS_LIMIT) for handle in handles]
    for sub in subs:
        if not sub[0]:
            return sub

    subs = [sub[1] for sub in subs]
    judging, over, updated = False, False, False
    problems = round_info.problems.split()

    updates = []

    for i in range(len(problems)):
        if problems[i] == '0':
            updates.append([])
            continue

        times = [codeforces.get_solve_time(sub, int(problems[i].split('/')[0]), problems[i].split('/')[1]) for sub in subs]

        if any([_ == -1 for _ in times]):
            judging = True
            updates.append([])
            continue

        solved = []
        for j in range(len(users)):
            if times[j] == min(times) and times[j] <= round_info.time + 60 * round_info.duration:
                solved.append(users[j])
                status[j] += points[i]
                problems[i] = '0'
                timestamp[j] = max(timestamp[j], min(times))
                updated = True

        updates.append((solved))

        if len(solved) > 0 and round_info.repeat == 1:
            res = await codeforces.find_problems(handles+db.fetch_alts(round_info.guild, users[0]), [rating[i]])
            if not res[0]:
                new_problem = '0'
            else:
                new_problem = f"{res[1][0].id}/{res[1][0].index}"
            problems[i] = new_problem

    if updated:
        db.update_round_status(round_info.guild, users[0], status, problems, timestamp)

    if not judging and (enter_time > round_info.time + 60 * round_info.duration or (round_info.repeat == 0 and no_round_change_possible(status[:], points, problems))):
        over = True
    return [True, [updates, over, updated]]