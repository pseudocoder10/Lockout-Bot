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
        if not problems_1[0]:
            return [False, "Codeforces API Error"]

        problems_1_filt = []
        for x in problems_1[1]:
            problems_1_filt.append(x[2])

        problems_2 = await self.cf.get_user_problems(self.get_handle(guild, data[2]))
        if not problems_2[0]:
            return [False, "Codeforces API Error"]

        problems_2_filt = []
        for x in problems_2[1]:
            problems_2_filt.append(x[2])

        fset = []
        for x in problems:
            if (x[2] not in problems_1_filt) and (x[2] not in problems_2_filt):
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
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time()), data[5], probs, "00000", data[6]))
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
                    judging = judging | is_pending(problems[i], sub1) | is_pending(problems[i], sub2)
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
                curr.execute(query, (status, x[0], x[1]))
                self.conn.commit()
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

        query = """
                    DELETE FROM ongoing
                    WHERE
                    guild = %s AND p1_id = %s
                """
        curr.execute(query, (x[0], x[1]))
        self.conn.commit()

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
        query = """
                    INSERT INTO finished
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr.execute(query, (data[0], data[1], data[2], data[3], int(time.time()) - data[4], data[7], result, data[8]))
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
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild,))
        data = curr.fetchall()
        resp = []
        c = 1
        for x in data:
            try:
                handle1 = self.get_handle(guild, x[1])
                handle2 = self.get_handle(guild, x[2])
            except Exception as e:
                print(e)
                continue
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
        if x['problem']['contestId'] == c_id and x['problem']['index'] == idx and x['verdict'] == "OK":
            ans = min(ans, x['creationTimeSeconds'])
    return ans

def is_pending(problem, sub):
    c_id = int(problem.split('/')[0])
    idx = problem.split('/')[1]
    sub.reverse()
    for x in sub:
        if x['problem']['contestId'] == c_id and x['problem']['index'] == idx and x['verdict'] == "TESTING":
            return True
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
