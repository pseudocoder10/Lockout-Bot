import psycopg2
import os
import time

from collections import namedtuple
from dotenv import load_dotenv


class DbConn:
    def __init__(self):
        load_dotenv('.env')
        self.conn = psycopg2.connect(database=os.environ.get("DB_NAME"), user=os.environ.get("DB_USERNAME"),
                                     password=os.environ.get("DB_PASSWORD"), host="127.0.0.1", port="5432")
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
                            times TEXT,
                            tournament BIGINT
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
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS tournament_info(
                            guild BIGINT,
                            name TEXT,
                            type INT,
                            id BIGINT,
                            url TEXT,
                            status INT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS finished_tournaments(
                            guild BIGINT,
                            name TEXT,
                            type INT,
                            id BIGINT,
                            url TEXT,
                            winner TEXT,
                            time BIGINT
                    )
                    """)
        cmds.append("""
                        CREATE TABLE IF NOT EXISTS registrants(
                            guild BIGINT,
                            discord_id BIGINT,
                            handle TEXT,
                            rating INT,
                            challonge_id BIGINT
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

    def get_handle(self, guild, discord_id):
        query = f"""
                    SELECT cf_handle FROM handles
                    WHERE
                    guild = %s AND
                    discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        data = curr.fetchone()
        curr.close()
        if not data:
            return None
        return data[0]

    def add_handle(self, guild, discord_id, cf_handle, rating):
        query = f"""
                    INSERT INTO handles
                    (guild, discord_id, cf_handle, rating)
                    VALUES
                    (%s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id, cf_handle, rating))
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

    def remove_handle(self, guild, discord_id):
        query = f"""
                    DELETE from handles
                    WHERE
                    guild = %s AND
                    discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        self.conn.commit()
        curr.close()

    def get_handle_info(self, guild, discord_id):
        query = f"""
                    SELECT * FROM handles
                    WHERE
                    guild = %s AND
                    discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        data = curr.fetchone()
        curr.close()
        return data

    def get_all_handles(self, guild=None):
        query = f"""
                    SELECT * FROM handles
                """
        if guild is not None:
            query += f" WHERE guild = {guild}"
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
        return data

    def update_cf_rating(self, handle, rating):
        query = f"""
                    UPDATE handles
                    SET rating = %s
                    WHERE cf_handle = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (rating, handle))
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

    def get_challenge_info(self, guild, id):
        query = """
                    SELECT * FROM challenge
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchone()
        curr.close()
        Challenge = namedtuple('Challenge', 'guild p1_id p2_id rating time channel duration')
        return Challenge(data[0], data[1], data[2], data[3], data[4], data[5], data[6])

    # id = contest_id/index
    def get_problems(self, id=None):
        curr = self.conn.cursor()
        if not id:
            query = """
                        SELECT * FROM problems
                    """
            curr.execute(query)
        else:
            query = """
                        SELECT * FROM problems
                        WHERE
                        id = %s AND index = %s
                    """
            curr.execute(query, (id.split('/')[0], id.split('/')[1]))

        res = curr.fetchall()
        Problem = namedtuple('Problem', 'id index name type rating')
        curr.close()
        data = []
        for x in res:
            data.append(Problem(x[0], x[1], x[2], x[3], x[4]))
        return data

    def get_contest_name(self, contest_id):
        query = f"""
                    SELECT name FROM contests
                    WHERE
                    id = %s 
                """
        curr = self.conn.cursor()
        curr.execute(query, (contest_id,))
        data = curr.fetchone()
        curr.close()
        #  print(id)
        if len(data) == 0:
            return "69"
        return data[0]

    def add_to_ongoing(self, challenge_info, time, problems):
        query = """
                    INSERT INTO ongoing
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (challenge_info.guild, challenge_info.p1_id, challenge_info.p2_id, challenge_info.rating,
                     time, challenge_info.channel, ' '.join([f"{x.id}/{x.index}" for x in problems]), "00000",
                     challenge_info.duration))
        self.conn.commit()
        curr.close()

    def get_all_matches(self, guild=None):
        query = f"""
                    SELECT * FROM ongoing
                 """
        if guild is not None:
            query += f" WHERE guild = {guild}"
        curr = self.conn.cursor()
        curr.execute(query)
        resp = curr.fetchall()
        curr.close()
        Match = namedtuple('Match', 'guild p1_id p2_id rating time channel problems status duration')
        match_info = []
        for data in resp:
            match_info.append(Match(data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8]))
        return match_info

    def get_match_info(self, guild, id):
        query = f"""
                    SELECT * FROM ongoing
                    WHERE
                    guild = %s AND (p1_id = %s OR p2_id = %s)
                 """
        curr = self.conn.cursor()
        curr.execute(query, (guild, id, id))
        data = curr.fetchone()
        curr.close()
        Match = namedtuple('Match', 'guild p1_id p2_id rating time channel problems status duration')
        return Match(data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8])

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

    def update_match_status(self, match_info, status):
        query = f"""
                    UPDATE ongoing
                    SET
                    status = %s
                    WHERE
                    guild = %s AND p1_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (status, match_info.guild, match_info.p1_id))
        self.conn.commit()
        curr.close()

    def add_to_finished(self, match_info, status):
        query = """
                    INSERT INTO finished
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (match_info.guild, match_info.p1_id, match_info.p2_id, match_info.rating, int(time.time()),
                             status, "0", int(time.time()) - match_info.time))
        self.conn.commit()
        curr.close()

    def get_recent_matches(self, guild, user=None):
        if user:
            query = f"""
                        SELECT * FROM finished
                        WHERE
                        guild = %s AND p1_id = %s or p2_id = %s
                        ORDER BY time DESC
                    """
            curr = self.conn.cursor()
            curr.execute(query, (guild, user, user))
        else:
            query = f"""
                        SELECT * FROM finished
                        WHERE
                        guild = %s 
                        ORDER BY time DESC
                    """
            curr = self.conn.cursor()
            curr.execute(query, (guild,))
        res = curr.fetchall()
        curr.close()
        data = []
        Match = namedtuple('Match', 'guild p1_id p2_id rating time status result duration')
        for x in res:
            data.append(Match(x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7]))
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

    def get_ranklist(self, guild):
        data = []
        query = """
                    SELECT guild, id, rating FROM rating
                    WHERE
                    guild = %s
                    ORDER BY
                    idx DESC
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ))
        resp = curr.fetchall()
        curr.close()
        done = []
        for x in resp:
            try:
                if x[1] in done:
                    continue
                data1 = self.get_match_rating(guild, x[1])
                if len(data1) <= 1:
                    continue
                done.append(x[1])
                data.append([x[1], x[2]])
            except Exception:
                pass
        return data

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

    def add_to_ongoing_round(self, ctx, users, rating, points, problems, duration, repeat, alts, tournament=0):
        query = f"""
                    INSERT INTO ongoing_rounds
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (ctx.guild.id, ' '.join([f"{x.id}" for x in users]), ' '.join(map(str, rating)),
                             ' '.join(map(str, points)), int(time.time()), ctx.channel.id,
                             ' '.join([f"{x.id}/{x.index}" for x in problems]), ' '.join('0' for i in range(len(users))),
                             duration, repeat, ' '.join(['0'] * len(users)), tournament))
        self.add_to_alt_table(ctx, users, alts)
        self.conn.commit()
        curr.close()

    def add_to_alt_table(self, ctx, users, handles):
        if len(handles) == 0:
            return
        query = f"""
                    INSERT INTO ongoing_round_alts
                    VALUES
                    (%s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (ctx.guild.id, ' '.join([f"{x.id}" for x in users]), ' '.join(map(str, handles))))
        self.conn.commit()
        curr.close()

    def fetch_alts(self, guild, user):
        query = f"""
                    SELECT * FROM ongoing_round_alts
                    WHERE
                    guild = %s AND USERS LIKE %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, f"%{user}%"))
        data = curr.fetchone()
        curr.close()
        if not data:
            return []
        data = data[-1]
        return data.split()

    def get_round_info(self, guild, users):
        query = f"""
                    SELECT * FROM ongoing_rounds
                    WHERE
                    guild = %s AND users LIKE %s
                 """
        curr = self.conn.cursor()
        curr.execute(query, (guild, f"%{users}%"))
        data = curr.fetchone()
        curr.close()
        Round = namedtuple('Round', 'guild users rating points time channel problems status duration repeat times, tournament')
        return Round(data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11])

    def get_all_rounds(self, guild=None):
        query = f"""
                    SELECT * FROM ongoing_rounds
                """
        if guild is not None:
            query += f" WHERE guild = {guild}"
        curr = self.conn.cursor()
        curr.execute(query)
        res = curr.fetchall()
        curr.close()
        Round = namedtuple('Round', 'guild users rating points time channel problems status duration repeat times, tournament')
        return [Round(data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11]) for data in res]

    def update_round_status(self, guild, user, status, problems, timestamp):
        query = f"""
                    UPDATE ongoing_rounds 
                    SET
                    status = %s, 
                    problems = %s,
                    times = %s
                    WHERE
                    guild = %s AND users LIKE %s 
                """
        curr = self.conn.cursor()
        curr.execute(query,
                     (' '.join([str(x) for x in status]), ' '.join(problems), ' '.join([str(x) for x in timestamp]),
                      guild, f"%{user}%"))
        self.conn.commit()
        curr.close()

    def delete_round(self, guild, user):
        query = f"""
                    DELETE FROM ongoing_rounds
                    WHERE
                    guild = %s AND users LIKE %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, f"%{user}%"))
        self.conn.commit()

        query = f"""
                    DELETE FROM ongoing_round_alts
                    WHERE
                    guild = %s AND USERS LIKE %s
                """
        curr.execute(query, (guild, f"%{user}%"))
        self.conn.commit()
        curr.close()

    def add_to_finished_rounds(self, round_info):
        query = f"""
                    INSERT INTO finished_rounds
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (round_info.guild, round_info.users, round_info.rating, round_info.points, round_info.time,
                                round_info.channel, round_info.problems, round_info.status, round_info.duration, round_info.repeat,
                                round_info.times, int(time.time())))
        self.conn.commit()
        curr.close()

    def get_recent_rounds(self, guild, user=None):
        query = f"""
                    SELECT * FROM finished_rounds
                    WHERE guild = %s
                    ORDER BY end_time DESC
                """
        if user:
            query = f"""
                        SELECT * FROM finished_rounds
                        WHERE guild = %s AND users LIKE %s
                        ORDER BY end_time DESC
                    """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ) if user is None else (guild, f"%{user}%"))
        res = curr.fetchall()
        curr.close()
        Round = namedtuple('Round', 'guild users rating points time channel problems status duration repeat times end_time')
        data = []
        for x in res:
            data.append(Round(x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[11]))
        return data

    def add_problem(self, id, index, name, type, rating):
        query = f"""
                    INSERT INTO problems
                    (id, index, name, type, rating)
                    VALUES
                    (%s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, index, name, type, rating))
        self.conn.commit()
        curr.close()

    def add_contest(self, id, name):
        query = f"""
                    INSERT INTO contests
                    (id, name)
                    VALUES
                    (%s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, name))
        self.conn.commit()
        curr.close()

    def get_contests_id(self):
        query = f"""
                    SELECT id from contests
                """
        curr = self.conn.cursor()
        curr.execute(query)
        data = curr.fetchall()
        curr.close()
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

    def get_tournament_info(self, guild):
        query = f"""
                    SELECT * FROM tournament_info
                    WHERE guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ))
        data = curr.fetchone()
        curr.close()
        if not data:
            return None
        Tournament = namedtuple('Tournament', 'guild, name, type, id, url, status')
        return Tournament(data[0], data[1], data[2], data[3], data[4], data[5])

    def add_tournament(self, guild, name, type, id, url, status):
        query = f"""
                    INSERT INTO tournament_info
                    VALUES
                    (%s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, name, type, id, url, status))
        self.conn.commit()
        curr.close()

    def add_registrant(self, guild, discord_id, handle, rating, challonge_id):
        query = f"""
                    INSERT INTO registrants
                    VALUES
                    (%s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id, handle, rating, challonge_id))
        self.conn.commit()
        curr.close()

    def remove_registrant(self, guild, discord_id):
        query = f"""
                    DELETE FROM registrants
                    WHERE
                    guild = %s AND discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        self.conn.commit()
        curr.close()

    def remove_registrant_by_handle(self, guild, handle):
        query = f"""
                    DELETE FROM registrants
                    WHERE
                    guild = %s AND handle = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, handle))
        self.conn.commit()
        res = curr.rowcount
        curr.close()
        return res

    def get_registrants(self, guild):
        query = f"""
                    SELECT * FROM registrants
                    WHERE guild = %s
                    ORDER BY rating DESC
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ))
        data = curr.fetchall()
        curr.close()
        Registrant = namedtuple('Registrant', 'guild, discord_id, handle, rating, challonge_id')
        return [Registrant(x[0], x[1], x[2], x[3], x[4]) for x in data]

    def get_registrant_info(self, guild, challonge_id):
        query = f"""
                    SELECT * FROM registrants
                    WHERE guild = %s AND challonge_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, challonge_id))
        x = curr.fetchone()
        curr.close()
        Registrant = namedtuple('Registrant', 'guild, discord_id, handle, rating, challonge_id')
        return Registrant(x[0], x[1], x[2], x[3], x[4])

    def update_tournament_params(self, id, url, status, guild):
        query = f"""
                    UPDATE tournament_info
                    SET 
                    id = %s,
                    url = %s,
                    status = %s
                    WHERE
                    guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (id, url, status, guild))
        self.conn.commit()
        curr.close()

    def map_user_to_challongeid(self, guild, discord_id, challonge_id):
        query = f"""
                    UPDATE registrants
                    SET challonge_id = %s
                    WHERE guild = %s AND discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (challonge_id, guild, discord_id))
        self.conn.commit()
        curr.close()

    def get_challonge_id(self, guild, discord_id):
        query = f"""
                    SELECT challonge_id FROM registrants
                    WHERE
                    guild = %s AND discord_id = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, discord_id))
        data = curr.fetchone()
        curr.close()
        if not data:
            return None
        return data[0]

    def delete_tournament(self, guild):
        query = f"""
                    DELETE FROM tournament_info 
                    WHERE guild = %s
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ))
        self.conn.commit()

        query = f"""
                    DELETE FROM registrants
                    WHERE guild = %s
                """
        curr.execute(query, (guild, ))
        self.conn.commit()
        curr.close()

    def add_to_finished_tournaments(self, tournament_info, winner):
        query = f"""
                    INSERT INTO finished_tournaments
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                """
        curr = self.conn.cursor()
        curr.execute(query, (tournament_info.guild, tournament_info.name, tournament_info.type, tournament_info.id,
                             tournament_info.url, winner, int(time.time())))
        self.conn.commit()
        curr.close()

    def get_recent_tournaments(self, guild):
        query = f"""
                    SELECT * FROM finished_tournaments
                    WHERE guild = %s
                    ORDER BY time DESC
                """
        curr = self.conn.cursor()
        curr.execute(query, (guild, ))
        data = curr.fetchall()
        curr.close()
        Tournament = namedtuple("Tournament", "guild name type id url winner time")
        return [Tournament(x[0], x[1], x[2], x[3], x[4], x[5], x[6]) for x in data]


