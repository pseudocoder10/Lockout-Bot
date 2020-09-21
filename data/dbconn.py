import random

import discord
import psycopg2
from utils import cf_api
import time
from datetime import datetime
from humanfriendly import format_timespan as timeez
from utils import elo
import asyncio
import json
from functools import cmp_to_key


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


def author_list():
    with open('./data/authors.json') as f:
        data = json.load(f)
    return data


TOTAL_TIME = 45*60 + 120


class DbConn:
    def __init__(self):
        self.cf = cf_api.CodeforcesAPI()
        self.authors = author_list()
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
                            channel BIGINT,
                            duration BIGINT
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
                            status TEXT,
                            duration BIGINT
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
                        result INT, 
                        duration BIGINT
                    ) 
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS rating(
                        idx SERIAL,
                        guild BIGINT,
                        id BIGINT,
                        rating BIGINT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS ongoing_rounds(
                            guild BIGINT,
                            users TEXT,
                            rating TEXT,
                            points TEXT,
                            time INT,
                            channel BIGINT,
                            problems TEXT,
                            status TEXT,
                            duration BIGINT,
                            repeat BIGINT,
                            times TEXT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS ongoing_round_alts(
                            guild BIGINT,
                            users TEXT,
                            alys TEXT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS finished_rounds(
                            guild BIGINT,
                            users TEXT,
                            rating TEXT,
                            points TEXT,
                            time INT,
                            channel BIGINT,
                            problems TEXT,
                            status TEXT,
                            duration BIGINT,
                            repeat BIGINT,
                            times TEXT,
                            end_time INT
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
        curr.close()
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
                curr.close()
                continue

            if is_nonstandard(self.get_name(x['contestId'])):
                curr.close()
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
        curr.close()
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
        curr.close()
        return data[2]

    def add_to_challenge(self, guild, p1, p2, rating, time, channel, duration):
        query = """
                    INSERT INTO challenge
                    (guild, p1_id, p2_id, rating, time, channel, duration)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, p1, p2, rating, time, channel, duration))
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

    def is_an_author(self, id, handles):
        if str(id) not in self.authors:
            return True
        for x in handles:
            if x in self.authors[str(id)]:
                return True
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
        curr.close()

        problems = self.get_problems()

        handle1, handle2 = self.get_handle(guild, data[1]), self.get_handle(guild, data[2])

        problems_1 = await self.cf.get_user_problems(handle1)
        if not problems_1[0]:
            return [False, "Codeforces API Error"]

        problems_1_filt = []
        for x in problems_1[1]:
            problems_1_filt.append(x[2])

        problems_2 = await self.cf.get_user_problems(handle2)
        if not problems_2[0]:
            return [False, "Codeforces API Error"]

        problems_2_filt = []
        for x in problems_2[1]:
            problems_2_filt.append(x[2])

        fset = []
        for x in problems:
            if (x[2] not in problems_1_filt) and (x[2] not in problems_2_filt) and not self.is_an_author(x[0], [handle1, handle2]):
                fset.append(x)

        print(len(fset))

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
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time())+5, data[5], probs, "00000", data[6]))
        self.conn.commit()
        curr.close()

        print(final_questions)
        await ctx.send(f"Starting match between <@{data[1]}> and <@{data[2]}>. The match will contain 5 tasks and "
                       f"you have {data[6]} minutes to solve them. The first person to solve a problem gets the points for it."
                       "The scores will update automatically every 1 minute but You can manually update them by typing"
                       "`.match update`. Note that this command can be used atmost once in a minute in a server.")
        return [True, final_questions, data[6]]

    def get_opponent(self, guild, id):
        query = """
                    SELECT p1_id, p2_id FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)                     
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchone()
        curr.close()
        if data[0] == id:
            return data[1]
        else:
            return data[0]

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
        curr.close()
        for x in data:
            
            try:
                done = 0
                judging = False
                handle1 = self.get_handle(x[0], x[1])
                handle2 = self.get_handle(x[0], x[2])
                sub1 = await self.cf.get_submissions(handle1)
                sub2 = await self.cf.get_submissions(handle2)
                status=""
                guild = client.get_guild(x[0])
                channel = client.get_channel(x[5])
                mem1 = guild.get_member(x[1])
                mem2 = guild.get_member(x[2])
                problems = x[6].split()
                for i in range(0, 5):
                    if x[7][i] != '0':
                        status = status + x[7][i]
                        continue
                    time1 = get_solve_time(problems[i], sub1)
                    time2 = get_solve_time(problems[i], sub2)
                    judging1 = False
                    judging1 = judging1 | is_pending(problems[i], sub1) | is_pending(problems[i], sub2)
                    if judging1:
                        judging = True
                        status = status + '0'
                        continue
                    if time1 > x[4] + x[8]*60 and time2 > x[4] + x[8]*60:
                        status = status + '0'
                        continue
                    if time1 < time2 and time1 <= x[4] + x[8]*60:
                        done = 1
                        status = status + '1'
                        await channel.send(embed=discord.Embed(description=f"{mem1.mention} has solved the problem worth {(i+1)*100} points", color=discord.Color.blue()))

                    elif time1 > time2 and time2 <= x[4] + x[8]*60:
                        done = 1
                        status = status + '2'
                        await channel.send(embed=discord.Embed(description=f"{mem2.mention} has solved the problem worth {(i+1)*100} points", color=discord.Color.blue()))

                    elif time1 == time2 and time1 <= x[4] + x[8]*60:
                        done = 1
                        status = status + '3'
                        await channel.send(embed=discord.Embed(
                            description=f"Both {mem1.mention} and {mem2.mention} have solved the problem worth {(i + 1) * 100} points at the same time",
                            color=discord.Color.blue()))
                query = """
                            UPDATE ongoing
                            SET
                            status = %s
                            WHERE
                            guild = %s and p1_id = %s
                        """
                curr = self.conn.cursor()
                curr.execute(query, (status, x[0], x[1]))
                self.conn.commit()
                curr.close()
                if (match_over(status)[0] or time.time() - x[4] > x[8]*60 or all_done(status)) and not judging:
                    await self.print_results(client, x[5], x)
                else:
                    if done == 0:
                        continue
                    await channel.send(f"{mem1.mention} {mem2.mention}, there is an update in standings")
                    a = match_over(status)[1]
                    b = match_over(status)[2]
                    pname = ""
                    prating = ""
                    ppts = ""
                    problems = x[6].split()
                    tme = x[8]*60 - (int(time.time())-x[4])
                    for i in range(0, 5):
                        if status[i] != '0':
                            continue

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

        query = """
                    DELETE FROM ongoing
                    WHERE
                    guild = %s AND p1_id = %s
                """
        curr.execute(query, (x[0], x[1]))
        self.conn.commit()
        curr.close()

        x = data
        a = 0
        b = 0
        result = 0
        for i in range(0, 5):
            if x[7][i] == '1':
                a += (i+1)*100
            if x[7][i] == '2':
                b += (i+1)*100
            if x[7][i] == '3':
                a += (i+1)*50
                b += (i+1)*50
        message = ""
        try:
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
        except Exception:
            pass
        curr = self.conn.cursor()
        query = """
                    INSERT INTO finished
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time()), data[7], result, int(time.time())-data[4]))
        self.conn.commit()
        curr.close()

        pp = result
        if pp == 2:
            pp = 0
        elif pp== 0:
            pp = 0.5
        elif pp>2:
            return
        rating1 = self.get_match_rating(data[0], data[1])[-1]
        rating2 = self.get_match_rating(data[0], data[2])[-1]
        data1 = calc_rating(self.get_match_rating(data[0], data[1])[-1], self.get_match_rating(x[0], data[2])[-1], pp, 1 - pp)
        self.add_rating_update(data[0], data[1], data1[0])
        self.add_rating_update(data[0], data[2], data1[1])
        embed = discord.Embed(description=f"<@{data[1]}> {rating1} -> {data1[0]}\n<@{data[2]}> {rating2} -> {data1[1]}", color=discord.Color.blurple())
        embed.set_author(name="Rating changes")
        await channel.send(embed=embed)

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
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time()), data[7], result, int(time.time())-data[4]))
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
        curr.close()
        resp = []
        c = 0
        for x in data:
            try:
                a = 0
                b = 0
                for i in range(0, 5):
                    if x[7][i] == '1':
                        a += (i+1)*100
                    if x[7][i] == '2':
                        b += (i+1)*100
                    if x[7][i] == '3':
                        a += (i + 1) * 50
                        b += (i + 1) * 50
                tme = int(time.time())-x[4]
                m = int(tme/60)
                s = tme%60
                resp.append([str(c), self.get_handle(guild, x[1]), self.get_handle(guild, x[2]), str(x[3]), f"{m}m {s}s", f"{a}-{b}"])
                c += 1
            except Exception as e:
                print(e)
        return resp

    def get_finished(self, guild):
        query = """
                    SELECT * FROM finished
                    WHERE
                    guild = %s
                    ORDER BY time ASC
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild,))
        data = curr.fetchall()
        curr.close()
        resp = []
        c = 1
        for x in data:
            try:
                handle1 = self.get_handle(guild, x[1])
                handle2 = self.get_handle(guild, x[2])
            except Exception as e:
                print(e)
                continue
            tme = x[7]
            m = int(tme / 60)
            s = tme % 60
            a = 0
            b = 0
            for i in range(0, 5):
                if x[5][i] == '1':
                    a += (i + 1) * 100
                if x[5][i] == '2':
                    b += (i + 1) * 100
                if x[5][i] == '3':
                    a += (i + 1) * 50
                    b += (i + 1) * 50
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

    def get_user_finished(self, guild, user):
        query = """
                    SELECT * FROM finished
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                    ORDER BY time ASC
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, user, user))
        data = curr.fetchall()
        curr.close()
        resp = []
        c = 1
        for x in data:
            try:
                handle1 = self.get_handle(guild, x[1])
                handle2 = self.get_handle(guild, x[2])
            except Exception as e:
                print(e)
                continue
            tme = x[7]
            m = int(tme / 60)
            s = tme % 60
            a = 0
            b = 0
            for i in range(0, 5):
                if x[5][i] == '1':
                    a += (i + 1) * 100
                if x[5][i] == '2':
                    b += (i + 1) * 100
                if x[5][i] == '3':
                    a += (i + 1) * 50
                    b += (i + 1) * 50
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

    def get_match_rating(self, guild, id):
        query = """
                    SELECT rating FROM rating
                    WHERE
                    guild = %s AND id = %s
                    ORDER BY
                    idx ASC
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id))
        data = curr.fetchall()
        curr.close()
        data1 = [x[0] for x in data]
        return data1

    def add_rating_update(self, guild, id, rating):
        query = """
                    INSERT INTO rating
                    VALUES
                    (DEFAULT, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, rating))
        self.conn.commit()
        curr.close()

    def add_rated_user(self, guild, id):
        query = """
                    SELECT * FROM rating
                    WHERE
                    guild = %s AND id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id))
        data = curr.fetchall()
        if len(data) > 0:
            return
        query = """
                    INSERT INTO rating
                    VALUES
                    (DEFAULT, %s, %s, %s)
                """
        curr.execute(query, (guild, id, 1500))
        self.conn.commit()
        curr.close()

    def get_ranklist(self, ctx):
        data = []
        query = """
                    SELECT guild, id, rating FROM rating
                    WHERE
                    guild = %s
                    ORDER BY
                    idx ASC
                """
        curr = self.conn.cursor()
        curr.execute(query, (ctx.guild.id, ))
        resp = curr.fetchall()
        curr.close()
        resp.reverse()
        done = []
        for x in resp:
            try:
                if x[1] in done:
                    continue
                data1 = self.get_match_rating(ctx.guild.id, x[1])
                if len(data1) <= 1:
                    continue
                done.append(x[1])
                data.append([ctx.guild.get_member(x[1]).name, x[2]])
            except Exception:
                print("User not in server <printing ranklist>")
        return data

    def get_count(self, table):
        query = f"""
                    SELECT COUNT(*) FROM {table}
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchone()
        curr.close()
        return data[0]

    def add_to_alt_table(self, ctx ,users ,handles):
        if handles is None:
            return
        query = f"""
                    INSERT INTO ongoing_round_alts
                    VALUES
                    (%s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (ctx.guild.id, ' '.join([f"{x.id}" for x in users]), ' '.join([f"{x}" for x in handles])))
        temp = self.conn.commit()
        curr.close()        

    def add_to_ongoing_round(self, ctx, users, rating, points, problems, duration, repeat, handles=None):
        query = f"""
                    INSERT INTO ongoing_rounds
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        times = ' '.join(['0']*len(users))
        curr.execute(query, (ctx.guild.id, ' '.join([f"{x.id}" for x in users]), ' '.join([f"{x}" for x in rating]),
                             ' '.join([f"{x}" for x in points]), int(time.time()), ctx.channel.id,
                             ' '.join([f"{x[0]}/{x[1]}" for x in problems]), ' '.join('0' for i in range(len(users))),
                             duration, repeat, times))
        self.add_to_alt_table(ctx,users,handles)
        self.conn.commit()
        curr.close()

    async def get_subs(self, handles):
        data = []
        try:
            for i in range(len(handles)):
                subs = await self.cf.get_submissions(handles[i])
                if subs == False:
                    return [False]
                data.append(subs)
        except Exception:
            return [False]
        return [True, data]

    def in_a_round(self, guild, user):
        query = f"""
                    SELECT * FROM ongoing_rounds
                    WHERE
                    users LIKE %s AND guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (f"%{user}%", guild))
        data = curr.fetchall()
        curr.close()
        if len(data) > 0:
            return True
        return False

    def get_ongoing_rounds(self, guild):
        query = f"""
                    SELECT * FROM ongoing_rounds
                    WHERE
                    guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ))
        data = curr.fetchall()
        curr.close()
        return data

    def update_round_status(self, guild, users, status, problems, timestamp):
        query = f"""
                    UPDATE ongoing_rounds 
                    SET
                    status = %s, 
                    problems = %s,
                    times = %s
                    WHERE
                    guild = %s AND users = %s 
                """
        curr = self.conn.cursor()
        curr.execute(query, (' '.join([str(x) for x in status]), ' '.join(problems), ' '.join([str(x) for x in timestamp]),
                             guild.id, ' '.join([str(x.id) for x in users])))
        self.conn.commit()
        curr.close()

    async def get_user_problems(self, handles):
        data = []
        try:
            for i in range(len(handles)):
                subs = await self.cf.get_user_problems(handles[i])
                if not subs[0]:
                    return [False]
                data.extend(subs[1])
                if i % 2 == 0 and i > 0:
                    await asyncio.sleep(1)
        except Exception:
            return [False]
        return [True, data]

    def get_unsolved_problem(self, solved, total, handles, rating):
        fset = []
        for x in total:
            if x[2] not in [name[2] for name in solved] and not self.is_an_author(x[0], handles) and x[4] == rating:
                fset.append(x)
        return random.choice(fset) if len(fset) > 0 else None

    def fetch_handles(self,guild,users):
        try:
            query = f"""
                    SELECT * FROM ongoing_round_alts
                    WHERE
                    guild = %s AND USERS LIKE %s
                """
            curr = self.conn.cursor()
            curr.execute(query, (guild, ' '.join([f"{x.id}" for x in users])))
            data = curr.fetchone()
            data = data[-1]
            data = [x for x in data.split(' ')]
            curr.close()
            return data
        except Exception as e:
            print(f"Failed update of rounds {e}")
            return None


    async def update_rounds(self, client, guild=None):
        if not guild:
            query = """SELECT * FROM ongoing_rounds"""
        else:
            query = f"""
                        SELECT * FROM ongoing_rounds
                        WHERE
                        guild = {guild}
                    """
        print(f"round updating {guild}")
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        for x in data:
            try:
                guild = client.get_guild(x[0])
                users = [guild.get_member(int(x1)) for x1 in x[1].split()]
                handles = [self.get_handle(guild.id, user.id) for user in users]
                rating = [int(x1) for x1 in x[2].split()]
                points = [int(x1) for x1 in x[3].split()]
                channel = guild.get_channel(x[5])
                problems = x[6].split()
                status = [int(x1) for x1 in x[7].split()]
                duration = x[8]
                start = x[4]
                repeat = x[9]
                timestamp = [int(x1) for x1 in x[10].split()]
                enter_time = int(time.time())
                judging = False

                subs = await self.get_subs(handles)
                if not subs[0]:      
                
                    continue
                subs = subs[1]
                result = []

                # judging .............................

                for i in range(0, len(problems)):
                    if problems[i] == '0':
                        result.append([])
                        continue

                    times = []
                    judging1 = False
                    for sub in subs:
                        times.append(get_solve_time(problems[i], sub))
                        judging1 = judging1 | is_pending(problems[i], sub)
                    if judging1:
                        judging = True
                        result.append([])
                        continue
                    if min(times) > start + duration*60:
                        result.append([])
                        continue

                    result.append([ii for ii in range(len(users)) if times[ii] == min(times)])
                    for j in range(len(users)):
                        if times[j] == min(times):
                            timestamp[j] = max(timestamp[j], min(times))

                # checking if solved ...................

                done = False
                for i in range(len(problems)):
                    if len(result[i]) == 0:
                        continue
                    done = True
                    problems[i] = '0'
                    for j in range(len(result[i])):
                        status[result[i][j]] += points[i]
                    await channel.send(embed=discord.Embed(description=f"{' '.join([f'{users[j].mention}' for j in result[i]])} has solved the problem worth {points[i]} points (problem number {i+1})",
                                                           color=discord.Color.blue()))

                # adding new problem ............................

                temp = self.fetch_handles(guild.id,users)
                if temp is not None:
                    for handle in temp:
                        if handle not in handles:
                            handles.append(handle)
                
                if done and repeat > 0:
                    all_subs = await self.get_user_problems(handles)
                    if not all_subs[0]:
                        continue
                    all_subs = all_subs[1]
                    for prob in problems:
                        if prob != '0':
                            all_subs.append([prob.split('/')[0], prob.split('/')[1], self.get_problem_name(prob.split('/')[0], prob.split('/')[1])])
                    all_prob = self.get_problems()
                    for i in range(len(problems)):
                        if problems[i] == '0':
                            newProb = self.get_unsolved_problem(all_subs, all_prob, handles, rating[i])
                            if not newProb:
                                problems[i] = '0'
                            else:
                                problems[i] = f"{newProb[0]}/{newProb[1]}"

                self.update_round_status(guild, users, status, problems, timestamp)
                x = list(x)
                x[6] = ' '.join([str(pp) for pp in problems])
                x[7] = ' '.join([str(pp) for pp in status])
                x = tuple(x)

                # printing ................................

                if (enter_time > start + duration*60 or (repeat == 0 and self.no_change_possible(status[:], points, problems))) and not judging:
                    await channel.send(f"{' '.join([f'{user.mention}'for user in users])} match over, here are the final standings:")
                    await channel.send(embed=self.print_round_score(users, status, timestamp, guild.id, 1))
                    if len(users) > 1:
                        self.finish_round(x)
                    self.delete_round(guild.id, users[0].id)
                elif done:
                    await channel.send(f"{' '.join([f'{user.mention}' for user in users])} there is an update in standings")

                    pname = []
                    for prob in problems:
                        if prob == '0':
                            pname.append('No unsolved problems of this rating left' if repeat == 1 else "This problem has been solved")
                        else:
                            id = prob.split('/')[0]
                            idx = prob.split('/')[1]
                            pname.append(f"[{self.get_problem_name(id, idx)}](https://codeforces.com/problemset/problem/{prob})")

                    embed = discord.Embed(color=discord.Color.magenta())
                    embed.set_author(name=f"Problems left")
                    embed.add_field(name="Points", value='\n'.join(x[3].split()), inline=True)
                    embed.add_field(name="Problem", value='\n'.join(pname), inline=True)
                    embed.add_field(name="Rating", value='\n'.join(x[2].split()), inline=True)
                    embed.set_footer(text=f"Time left: {timeez(start+60*duration-int(time.time()))}")
                    await channel.send(embed=embed)
                    await channel.send(embed=self.print_round_score(users, status, timestamp, guild.id, 0))
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Failed update of rounds {e}")
            await asyncio.sleep(1)

    def finish_round(self, data):
        query = f"""
                    INSERT INTO finished_rounds
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9],
                             data[10], int(time.time())))
        self.conn.commit()
        curr.close()

    def delete_round(self, guild, user):
        query = f"""
                    DELETE FROM ongoing_rounds
                    WHERE
                    guild = %s AND USERS LIKE %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, f"%{user}%"))
        self.conn.commit()
        curr.close()

        query = f"""
                    DELETE FROM ongoing_round_alts
                    WHERE
                    guild = %s AND USERS LIKE %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, f"%{user}%"))
        self.conn.commit()
        curr.close()

    def get_recent_rounds(self, guild, user=""):
        query = f"""
                    SELECT * FROM finished_rounds
                    WHERE guild = %s AND users LIKE %s
                    ORDER BY end_time DESC
                """
        curr =self.conn.cursor()
        curr.execute(query, (guild, f"%{user}%"))
        data = curr.fetchall()
        curr.close()
        return data

    def get_round_info(self, guild, user):
        query = f"""
                            SELECT * FROM ongoing_rounds
                            WHERE 
                            guild = %s AND users LIKE %s
                        """
        curr = self.conn.cursor()
        curr.execute(query, (guild, f"%{user}%"))
        data = curr.fetchone()
        curr.close()
        return data

    def print_round_score(self, users, status, timestamp, guild, over):
        def comp(a, b):
            if a[0] > b[0]:
                return -1
            if a[0] < b[0]:
                return 1
            if a[1] == b[1]:
                return 0
            return -1 if a[1] < b[1] else 1

        ranks = [[status[i], timestamp[i], users[i]] for i in range(len(status))]
        ELO = elo.ELOMatch()
        ranks.sort(key=cmp_to_key(comp))
        for i in range(len(users)):
            ELO.addPlayer(users[i].id, [[x[0], x[1]] for x in ranks].index([status[i], timestamp[i]])+1, self.get_match_rating(guild, users[i].id)[-1])
        ELO.calculateELOs()

        embed = discord.Embed(color=discord.Color.dark_blue())
        embed.set_author(name="Standings")
        for x in ranks:
            pos = [[i[0], i[1]] for i in ranks].index([x[0], x[1]]) + 1
            user = x[2]
            desc = f"{user.mention}\n"
            desc += f"**Points: {x[0]}**\n"
            desc += f"**{'Predicted rating changes' if over == 0 else 'Rating changes'}: "
            new_ = ELO.getELO(x[2].id)
            old_ = new_ - ELO.getELOChange(x[2].id)
            if over == 1:
                self.add_rating_update(guild, x[2].id, new_)
            desc += f"{old_} --> {new_} ({'+' if new_>=old_ else ''}{new_-old_})**\n\n"
            embed.add_field(name=f"Rank {pos}", value=desc, inline=False)

        return embed


    def no_change_possible(self, status, points, problems):
        status.sort()
        sum = 0
        for i in range(len(points)):
            if problems[i] != '0':
                sum = sum + points[i]
        for i in range(len(status)-1):
            if status[i] + sum >= status[i+1]:
                return False
        if len(status) == 1 and sum > 0:
            return False
        return True

def match_over(status):
    a = 0
    b = 0
    for i in range(0, 5):
        if status[i] == '1':
            a += (i+1)*100
        if status[i] == '2':
            b += (i+1)*100
        if status[i] == '3':
            a += (i+1)*50
            b += (i+1)*50
    if a >= 800 or b >= 800:
        return [True, a, b]
    else:
        return [False, a, b]


def get_solve_time(problem, sub):
    c_id = int(problem.split('/')[0])
    idx = problem.split('/')[1]
    sub.reverse()
    ans = 10000000000
    for x in sub:
        try:
            if x['problem']['contestId'] == c_id and x['problem']['index'] == idx and x['verdict'] == "OK":
                ans = min(ans, x['creationTimeSeconds'])
        except Exception:
            pass
    return ans


def is_pending(problem, sub):
    c_id = int(problem.split('/')[0])
    idx = problem.split('/')[1]
    sub.reverse()
    for x in sub:
        try:
            if x['problem']['contestId'] == c_id and x['problem']['index'] == idx:
                if 'verdict' not in x or x['verdict'] == "TESTING":
                    return True
        except Exception:
            pass
    return False


def all_done(status):
    for i in status:
        if i == '0':
            return False
    return True


def calc_rating(rate1, rate2, c1, c2):
    p1 = 1/(1+10**((rate2-rate1)/400))
    p2 = 1/(1+10**((rate1-rate2)/400))

    delt = int(80*(c1 - p1))
    return [int(rate1 + delt), int(rate2 - delt)]
