import random

import discord
import psycopg2
from utils import cf_api
import time
from datetime import datetime
import asyncio
import string


async def send_message(ctx, message, color):
    await ctx.send(embed=discord.Embed(description=message, color=color))


def is_nonstandard(name):
    useless = [
    'wild', 'fools', 'unrated', 'surprise', 'unknown', 'friday', 'q#', 'testing',
    'marathon', 'kotlin', 'onsite', 'experimental', 'abbyy']
    for x in useless:
        if x in name.lower():
            return True
    return False


TOTAL_TIME = 45*60 + 120


class DbConn:
    def __init__(self):
        self.cf = cf_api.CodeforcesAPI()
        self.conn = psycopg2.connect(database="", user="", password="", host="127.0.0.1", port="5432")
        print("Opened database successfully")
        self.make_tables()

    def make_tables(self):
        cmds = []
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS handles(
                           guild BIGINT,
                           discord_id BIGINT,
                           cf_handle TEXT,
                           rating INT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS problems(
                            id INT,
                            index TEXT,
                            name TEXT,
                            type TEXT,
                            rating INT,
                            tags TEXT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS contests(
                            id INT, 
                            name TEXT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS challenge(
                            guild BIGINT,
                            p1_id BIGINT,
                            p2_id BIGINT,
                            rating INT,
                            time INT, 
                            channel BIGINT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS ongoing(
                            guild BIGINT,
                            p1_id BIGINT,
                            p2_id BIGINT,
                            rating INT,
                            time INT,
                            channel BIGINT,
                            problems TEXT,
                            status TEXT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS finished(
                        guild BIGINT,
                        p1_id BIGINT,
                        p2_id BIGINT,
                        rating INT,
                        time INT,
                        status TEXT,
                        result INT
                    ) 
                    """)

        try:
            curr = self.conn.cursor()
            for x in cmds:
                curr.execute(x)
            curr.close()
            self.conn.commit()
        except Exception:
            print("Error while making tables")

    def add_handle(self, guild, discord_id, cf_handle, rating):
        query = f"""
                    INSERT INTO handles
                    (guild, discord_id, cf_handle, rating)
                    VALUES
                    ({guild}, {discord_id}, \'{cf_handle}\', {rating})
                """
        curr = self.conn.cursor()
        curr.execute(query)
        self.conn.commit()
        curr.close()

    def remove_handle(self, guild, discord_id):
        query = f"""
                    DELETE from handles
                    WHERE
                    guild = {guild} AND
                    discord_id = {discord_id}
                """
        curr = self.conn.cursor()
        curr.execute(query)
        self.conn.commit()
        curr.close()

    def handle_in_db(self, guild, discord_id):
        query = f"""
                    SELECT * FROM handles
                    WHERE
                    guild = {guild} AND
                    discord_id = {discord_id}
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        if len(data) == 0:
            return False
        else:
            return True

    def get_handle(self, guild, discord_id):
        query = f"""
                    SELECT cf_handle FROM handles
                    WHERE
                    guild = {guild} AND
                    discord_id = {discord_id}
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchone()
        curr.close()
        return data[0]

    def get_all_handles(self, guild):
        query = f"""
                    SELECT * FROM handles
                    WHERE
                    guild = {guild}
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        return data

    def get_overall_handles(self):
        query = """
                    SELECT cf_handle FROM handles
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        return data

    def update_rating(self, handle, rating):
        query = f"""
                    UPDATE handles
                    SET
                    rating = %s
                    WHERE
                    cf_handle = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (rating, handle))
        self.conn.commit()
        curr.close()

    async def update_db(self, ctx):
        resp = await self.update_contests()
        if not resp:
            await send_message(ctx, "API Error! Could'nt update contest list", discord.Color.red())
        else:
            await send_message(ctx, "Updated contest list successfully", discord.Color.green())
        resp = await self.update_problems()
        if not resp:
            await send_message(ctx, "API Error! Could'nt update problems list", discord.Color.red())
        else:
            await send_message(ctx, "Updated problems list successfully", discord.Color.green())

    async def update_contests(self):
        data = await self.cf.get_contest_list()
        if not data:
            return False
        i = 0
        lim = 30
        query = f"""
                    SELECT * FROM contests
                """
        curr = self.conn.cursor()
        curr.execute(query)
        temp = curr.fetchall()
        print(len(temp))
        if not temp:
            lim = len(data['result'])
        print(lim)
        for x in data['result']:
            if i == lim:
                break
            i += 1
            query = f"""
                        SELECT * FROM contests
                        WHERE
                        id = {x['id']}
                    """
            curr = self.conn.cursor()
            curr.execute(query)
            temp = curr.fetchall()
            if len(temp) != 0:
                continue
            query = f"""
                        INSERT INTO contests
                        (id, name)
                        VALUES
                        ({x['id']}, \'{x['name']}\')
                    """
            curr.execute(query)
            self.conn.commit()
            curr.close()
        return True

    async def update_problems(self):
        data = await self.cf.get_problem_list()
        if not data:
            return False
        i = 0
        lim = 30
        query = f"""
                    SELECT * FROM problems
                """
        curr = self.conn.cursor()
        curr.execute(query)
        temp = curr.fetchall()
        print(len(temp))
        if not temp:
            lim = len(data['result']['problems'])
        print(lim)

        for x in data['result']['problems']:
            if i == lim:
                break
            i += 1
            query = f"""
                        SELECT * FROM problems
                        WHERE
                        id = %s AND index = %s
                    """
            curr = self.conn.cursor()
            curr.execute(query, (x['contestId'], x['index']))
            temp = curr.fetchall()
            if len(temp) != 0:
                continue

            if is_nonstandard(self.get_name(x['contestId'])):
                continue

            rating = 0
            if 'rating' in x:
                rating = x['rating']
            query = f"""
                        INSERT INTO problems
                        (id, index, name, type, rating)
                        VALUES
                        (%s, %s, %s, %s, %s)
                    """
            curr.execute(query, (x['contestId'], x['index'], x['name'], x['type'], rating))
            self.conn.commit()
            curr.close()
        return True

    def get_problems(self):
        query = """
                    SELECT * FROM problems
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        return data

    def get_name(self, id):
        query = f"""
                    SELECT name FROM contests
                    WHERE
                    id = %s 
                """
        curr = self.conn.cursor()
        curr.execute(query, (id,))
        data = curr.fetchone()
      #  print(id)
        if len(data) == 0:
            return "69"
        return data[0]

    def get_problem_name(self, id, index):
        query = f"""
                    SELECT * from problems
                    WHERE
                    id = %s AND index = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, index))
        data = curr.fetchone()
        return data[2]

    def add_to_challenge(self, guild, p1, p2, rating, time, channel):
        query = """
                    INSERT INTO challenge
                    (guild, p1_id, p2_id, rating, time, channel)
                    VALUES
                    (%s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, p1, p2, rating, time, channel))
        self.conn.commit()
        curr.close()

    def remove_challenge(self, guild, id):
        query = """
                    DELETE FROM challenge
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        self.conn.commit()
        curr.close()

    def is_challenging(self, guild, id, tme=None):
        if tme is not None:
            query = """
                        SELECT * FROM challenge
                        WHERE
                        guild = %s AND time = %s AND p1_id = %s 
                    """
            curr = self.conn.cursor()
            curr.execute(query, (guild, tme, id))
            data = curr.fetchall()
            curr.close()
            if len(data) > 0:
                return True
            else:
                return False
        else:
            query = """
                        SELECT * FROM challenge
                        WHERE
                        guild = %s AND p1_id = %s 
                    """
            curr = self.conn.cursor()
            curr.execute(query, (guild, id))
            data = curr.fetchall()
            curr.close()
            if len(data) > 0:
                return True
            else:
                return False

    def is_challenged(self, guild, id):
        query = """
                    SELECT * FROM challenge
                    WHERE
                    guild = %s AND p2_id = %s 
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id))
        data = curr.fetchall()
        curr.close()
        if len(data) > 0:
            return True
        else:
            return False

    def in_a_match(self, guild, id):
        query = """
                    SELECT * FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchall()
        curr.close()
        if len(data) > 0:
            return True
        else:
            return False

    async def add_to_ongoing(self, ctx, guild, id):
        query = """
                    SELECT * FROM challenge
                    WHERE
                    guild = %s AND p2_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id))
        data = curr.fetchone()
        query = """
                    DELETE FROM challenge
                    WHERE
                    guild = %s AND p2_id = %s
                """
        curr.execute(query, (guild, id))
        self.conn.commit()

        problems = self.get_problems()

        problems_1 = await self.cf.get_user_problems(self.get_handle(guild, data[1]))
        if not problems_1:
            return [False, "Codeforces API Error"]

        problems_2 = await self.cf.get_user_problems(self.get_handle(guild, data[2]))
        if not problems_2:
            return [False, "Codeforces API Error"]

        fset = []
        for x in problems:
            if (x not in problems_1) and (x not in problems_2):
                fset.append(x)

        final_questions = []
        for i in range(0, 5):
            rate = data[3]+i*100
            selected = []
            for x in fset:
                if x[4] == rate:
                    selected.append(x)
            if len(selected) == 0:
                return [False, f"No problems with rating {rate} left for the users"]
            final_questions.append(random.choice(selected))

        probs=""
        for x in final_questions:
            probs += f"{x[0]}/{x[1]} "
        query = """
                    INSERT INTO ongoing
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time()), data[5], probs, "00000"))
        self.conn.commit()
        curr.close()

        print(final_questions)
        await ctx.send(f"Starting match between <@{data[1]}> and <@{data[2]}>. The match will contain 5 questions and"
                       "you have around 45-49 minutes to solve them. The first person to solve a problem gets the points for it."
                       "The scores will update automatically every 2 minutes but You can manually update them by typing"
                       "`.match update`. Note that this command can be used atmost once in a minute in a server.")
        return [True, final_questions]

    async def update_matches(self, client, ctx=None):
        query = ""
        if ctx is None:
            query = """
                        SELECT * FROM ongoing
                    """
        else:
            print(f"Manual update called by {ctx.author.id}|{ctx.author.name} server: {ctx.guild.id}|{ctx.guild.name} time: {datetime.fromtimestamp(int(time.time())).strftime('%A, %B %d, %Y %I:%M:%S')}")
            await ctx.send(embed=discord.Embed(description=f"Updating matches for this server", color=discord.Color.green()))
            query = f"""
                        SELECT * FROM ongoing
                        WHERE
                        guild = {ctx.guild.id} 
                    """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        for x in data:
            try:
                if time.time() - x[4] > TOTAL_TIME:
                    await self.print_results(client, x[5], x)
                    continue
                done = 0
                handle1 = self.get_handle(x[0], x[1])
                handle2 = self.get_handle(x[0], x[2])
                sub1 = await self.cf.get_submissions(handle1)
                sub2 = await self.cf.get_submissions(handle2)
                status=""
                problems = x[6].split()
                for i in range(0, 5):
                    if x[7][i] != '0':
                        status = status + x[7][i]
                        continue
                    time1 = get_solve_time(problems[i], sub1)
                    time2 = get_solve_time(problems[i], sub2)
                    if time1 == 10000000000 and time2 == 10000000000:
                        status = status + '0'
                        continue
                    if time1 <= time2:
                        done = 1
                        status = status + '1'
                    else:
                        done = 1
                        status = status + '2'
                query = """
                            UPDATE ongoing
                            SET
                            status = %s
                            WHERE
                            guild = %s and p1_id = %s
                        """
                curr.execute(query, (status, x[0], x[1]))
                self.conn.commit()
                if match_over(status)[0]:
                    await self.print_results(client, x[5], x)
                else:
                    if done == 0:
                        continue
                    a = match_over(status)[1]
                    b = match_over(status)[2]
                    pname = ""
                    prating = ""
                    ppts = ""
                    problems = x[6].split()
                    tme = TOTAL_TIME - 120 - (int(time.time())-x[4])
                    for i in range(0, 5):
                        if status[i] != '0':
                            continue
                        for x in data:
                            ppts += f"{(i+1)*100}\n"
                            pname += f"[{self.get_problem_name(problems[i].split('/')[0], problems[i].split('/')[1])}](https://codeforces.com/problemset/problem/{problems[i]})\n"
                            prating += f"{(i*100)+x[3]}\n"
                    embed = discord.Embed(color=discord.Color.green())
                    embed.set_author(name=f"Current standings \n{handle1} ({a} points) vs ({b} points) {handle2}")
                    embed.add_field(name="Points", value=ppts, inline=True)
                    embed.add_field(name="Problem", value=pname, inline=True)
                    embed.add_field(name="Rating", value=prating, inline=True)
                    embed.set_footer(text=f"Time left: {int(tme/60)} minutes {tme%60} seconds")
                    channel = client.get_channel(x[5])
                    await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed manual update {str(e)}")
            await asyncio.sleep(1)
        curr.close()

    async def print_results(self, client, channel_id, x):
        channel = client.get_channel(channel_id)
        guild = client.get_guild(x[0])

        query = """
                    SELECT * FROM ongoing
                    WHERE
                    guild = %s AND p1_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (x[0], x[1]))
        data = curr.fetchone()
        x = data
        a = 0
        b = 0
        result = 0
        for i in range(0, 5):
            if x[7][i] == '1':
                a += (i+1)*100
            if x[7][i] == '2':
                b += (i+1)*100
        message = ""
        if a > b:
            message = f"Match over, {guild.get_member(x[1]).mention} has defeated {guild.get_member(x[2]).mention}\n"
            message = message + f"Final score {a} - {b}"
            result = 1
        elif a < b:
            message = f"Match over, {guild.get_member(x[2]).mention} has defeated {guild.get_member(x[1]).mention}\n"
            message = message + f"Final score {a} - {b}"
            result = 2
        else:
            message = f"Match over, its a draw between {guild.get_member(x[1]).mention} and {guild.get_member(x[2]).mention}!\n"
            message = message + f"Final score {a} - {b}"
            result = 0

        await channel.send(message)

        query = """
                    DELETE FROM ongoing
                    WHERE
                    guild = %s AND p1_id = %s
                """
        curr.execute(query, (x[0], x[1]))
        self.conn.commit()

        query = """
                    INSERT INTO finished
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                """
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time())-data[4], data[7], result))
        self.conn.commit()
        curr.close()

    def show_problems(self, guild, id):
        query = """
                    SELECT * FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchone()
        curr.close()
        rating = data[3]
        problems = data[6].split()
        status = data[7]
        pts = ""
        name = ""
        rate = ""
        for i in range(0, 5):
            if status[i] != '0':
                continue
            pts += f"{(i+1)*100}\n"
            name += f"[{self.get_problem_name(problems[i].split('/')[0], problems[i].split('/')[1])}](https://codeforces.com/problemset/problem/{problems[i]})\n"
            rate += f"{(i * 100) + rating}\n"
        embed = discord.Embed(color=discord.Color.green())
        embed.set_author(name=f"Problems left")
        embed.add_field(name="Points", value=pts, inline=True)
        embed.add_field(name="Problem", value=name, inline=True)
        embed.add_field(name="Rating", value=rate, inline=True)
        return embed

    def delete_match(self, guild, id):
        query = """
                    DELETE FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        self.conn.commit()
        curr.close()

    def forcewin(self, guild, id):
        query = """
                    SELECT * FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchone()
        query = """
                    DELETE FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr.execute(query, (guild, id, id))
        self.conn.commit()
        result = 3
        if data[2] == id:
            result = 4
        query = """
                    INSERT INTO finished
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                """
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time()) - data[4], data[7], result))
        self.conn.commit()
        curr.close()

    def get_ongoing(self, guild):
        query = """
                    SELECT * FROM ongoing
                    WHERE
                    guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild,))
        data = curr.fetchall()
        resp = []
        c = 0
        for x in data:
            a = 0
            b = 0
            for i in range(0, 5):
                if x[7][i] == '1':
                    a += (i+1)*100
                if x[7][i] == '2':
                    b += (i+1)*100
            tme = int(time.time())-x[4]
            m = int(tme/60)
            s = tme%60
            resp.append([str(c), self.get_handle(guild, x[1]), self.get_handle(guild, x[2]), str(x[3]), f"{m}m {s}s", f"{a}-{b}"])
            c += 1
        return resp

    def get_finished(self, guild):
        query = """
                    SELECT * FROM finished
                    WHERE
                    guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild,))
        data = curr.fetchall()
        resp = []
        c = 1
        for x in data:
            handle1 = self.get_handle(guild, x[1])
            handle2 = self.get_handle(guild, x[2])
            tme = x[4]
            m = int(tme / 60)
            s = tme % 60
            a = 0
            b = 0
            for i in range(0, 5):
                if x[5][i] == '1':
                    a += (i + 1) * 100
                if x[5][i] == '2':
                    b += (i + 1) * 100
            result = ""
            if x[6] == 0:
                result = f"Draw {a}-{b}"
            if x[6] == 1:
                result = f"{handle1} won {a}-{b}"
            if x[6] == 2:
                result = f"{handle2} won {b}-{a}"
            if x[6] == 3:
                result = f"{handle1} (ForceWin)"
            if x[6] == 4:
                result = f"{handle2} (ForceWin)"
            resp.append([str(c), handle1, handle2, str(x[3]), f"{m}m {s}s", result])
            c += 1
        return resp

    def get_profile(self, guild, id):
        query = """
                    SELECT * FROM finished
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchall()
        curr.close()
        return data

def match_over(status):
    a = 0
    b = 0
    for i in range(0, 5):
        if status[i] == '1':
            a += (i+1)*100
        if status[i] == '2':
            b += (i+1)*100
    if a >= 800 or b >= 800:
        return [True, a, b]
    else:
        return [False, a, b]


def get_solve_time(problem, sub):
    c_id = int(problem.split('/')[0])
    idx = problem.split('/')[1]
    sub.reverse()
    for x in sub:
        if x['problem']['contestId'] == c_id and x['problem']['index'] == idx and x['verdict'] == "OK":
            return x['creationTimeSeconds']
    return 10000000000