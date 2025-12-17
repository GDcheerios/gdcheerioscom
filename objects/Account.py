import hashlib
import secrets

from datetime import datetime, timedelta, timezone

import environment

database = environment.database
from api.osu_api import get_user_info
from objects.EmailManager import EmailManager


class Account:
    id: int
    username: str
    password: str
    email: str
    osu_id: int
    about: str
    pfp: str
    status: str
    tags: list
    gq_scores: list
    osu_data: dict
    exists: bool

    def __init__(self, identifier):
        print(f"Loading account {identifier}")
        try:
            identifier = int(identifier)
            from_query_string = "id = %s"
        except ValueError:
            from_query_string = "username = %s"

        result = database.fetch_to_dict(
            f"""
            SELECT 
                id,
                username,
                password,
                email,
                osu_id,
                about,
                status,
                created,
                is_supporter,
                last_support,
                supporter_lasts,
                EXISTS (
                    SELECT 1
                    FROM gq_data
                    WHERE gq_data.id = accounts.id
                ) AS has_gq
            FROM accounts 
            WHERE {from_query_string}
            """,
            params=(identifier,)
        )

        self.pfp = "https://storage.cloud.google.com/gdcheerioscombucket/profile-pictures/huh.png"

        try:
            self.id = result["id"]
            self.username = result["username"]
            self.password = result["password"]
            self.email = result["email"]
            self.has_osu = result["osu_id"] != 0
            self.has_gqc = False
            self.has_gq = result["has_gq"] != 0
            self.osu_id = result["osu_id"]
            self.about = result["about"]
            self.status = result["status"]
            self.created = result["created"]
            self.supporter = result["is_supporter"]
            self.last_support = result["last_support"]
            self.supporter_lasts = result["supporter_lasts"]
            self.tags = database.fetch_all_to_dict("SELECT * FROM account_tags WHERE account = %s",
                                                   params=(self.id,)) or []
            self.exists = True
        except TypeError:
            self.id = 0
            self.username = "User not found"
            self.password = ""
            self.email = ""
            self.has_osu = False
            self.has_gqc = False
            self.has_gq = False
            self.osu_id = 0
            self.about = "This user does not exist"
            self.status = "offline"
            self.created = datetime.now()
            self.supporter = False
            self.last_support = None
            self.supporter_lasts = None
            self.tags = []
            self.exists = False

        self.osu_data = {}
        self.gq_data = {}

        if self.has_osu:
            self.osu_data = self.get_osu_data()

        if self.has_gq:
            gq_scores = database.fetch_all_to_dict(
                """
                SELECT id,
                       score,
                       (SELECT gq_leaderboards.name
                        from gq_leaderboards
                        where gq_leaderboards.id = gq_scores.leaderboard) as name
                FROM gq_scores
                WHERE "user" = %s
                """,
                params=(self.id,)
            ) or []

            leaderboards = {}
            for score in gq_scores:
                if score["name"] not in leaderboards:
                    leaderboards[score["name"]] = []

            for score in gq_scores:
                leaderboards[score["name"]].append({
                    "score": score["score"],
                    "id": score["id"]
                })

            self.gq_data = {
                "scores": leaderboards,
                "metrics": environment.database.fetch_all_to_dict("SELECT * FROM gq_metrics WHERE user_id = %s ORDER BY recorded_at desc", params=(self.id,)),
                "metadata": environment.database.fetch_to_dict("SELECT * FROM gq_data WHERE id = %s", params=(self.id,)),
                "ranking": environment.database.fetch_to_dict("SELECT * FROM gq_rankings WHERE id = %s", params=(self.id,)),
                "items": environment.database.fetch_all_to_dict("SELECT * FROM gq_items WHERE owner = %s", params=(self.id,))
            }
            if self.gq_data["ranking"]:
                self.gq_data["ranking"]["placement"] = environment.database.fetch_one(
                    """
                    SELECT COUNT(*) + 1
                    FROM gq_rankings r2
                    WHERE r2.weighted > (SELECT weighted
                                         FROM gq_rankings r1
                                         WHERE r1.id = %s)
                    """,
                    params=(self.id,)
                )[0]

            level = 0
            for i, threshold in enumerate(environment.gq_levels):
                if self.gq_data["metadata"]["score"] >= threshold:
                    level = i + 1
                else:
                    break
            self.gq_data["metadata"]["level"] = level
            self.gq_data["metadata"]["required"] = environment.gq_levels[level]

    # <editor-fold desc="Modifiers">
    @staticmethod
    def create(username: str, password: str, email: str, osu_id: int, about: str) -> "Account":
        query = """
                INSERT INTO accounts (username, password, email, osu_id, about)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """

        params = (
            username,
            password,
            email,
            osu_id,
            about
        )

        id = database.fetch_one(query, params)[0]
        return Account(id)

    @staticmethod
    def queue(username: str, password: str, email: str, osu_id: int, about: str):

        now = datetime.now(tz=timezone.utc)
        database.execute(
            """
            DELETE
            FROM pending_accounts
            WHERE expires < %s;
            """,
            params=(now,)
        )
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        password = str(password)
        password = str(environment.bcrypt.generate_password_hash(password))[2:-1]  # remove the byte chars
        pending_id = database.fetch_one(
            """
            INSERT INTO pending_accounts (username, password, email, osu_id, about, token)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            params=(username, password, email, osu_id, about, token_hash)
        )[0]
        EmailManager.send_verification_email(email, username,
                                             f"{environment.domain}/api/account/verify?sid={pending_id}&token={raw_token}")

    @staticmethod
    def set_status(id: int, status: str):
        database.execute("UPDATE accounts SET status = %s where id = %s", params=(status, id))

    @staticmethod
    def change_username(id: int, new_username: str):
        """
        Change username
        """

        database.execute(f"update accounts set username = %s where id = %s;", params=(new_username, id))

    # </editor-fold>

    # <editor-fold desc="Checks">

    @staticmethod
    def name_exists(name: str) -> bool:
        """
        Check if a username exists
        :return: true or false, depending on if the username exists in the database
        """

        result = database.fetch_all(f"select username from accounts where username = %s;", params=(name,))
        return len(result) > 0

    @staticmethod
    def email_exists(email: str) -> bool:
        """
        Check if an email exists
        :return: true or false, depending on if the email exists in the database
        """

        result = database.fetch_all(f"select email from accounts where email = %s;", params=(email,))
        return len(result) > 0

    # </editor-fold>

    # <editor-fold desc="Osu">

    def fetch_osu_data(self):
        if self.has_osu:
            try:
                data = get_user_info(self.osu_id)
                return {
                    'username': data['username'],
                    'score': data['statistics']['total_score'],
                    'playcount': data['statistics']['play_count'],
                    'accuracy': data['statistics']['hit_accuracy'],
                    'performance': data['statistics']['pp'],
                    'rank': data['statistics']['global_rank'],
                }
            except KeyError:
                print("User doesn't exist on osu!")
                database.execute("UPDATE accounts SET osu_id = 0 WHERE id = %s", params=(self.id,))

        return None

    def get_osu_data(self):
        if self.has_osu:
            data = database.fetch_to_dict("SELECT * FROM osu_users WHERE id = %s", params=(self.osu_id,))
            if not data:
                if not self.update_osu_data():
                    return None
                return self.get_osu_data()
            else:
                return data

        return None

    def update_osu_data(self):
        data = None
        try:
            last_refresh = \
                database.fetch_one("SELECT last_refresh FROM osu_users WHERE id = %s", params=(self.osu_id,))[0]
            right_now = (last_refresh + timedelta(minutes=1))
            can_refresh = right_now < datetime.now()
            print(f"last refresh: {last_refresh}\n"
                  f"now: {right_now}\n"
                  f"{can_refresh}")
        except TypeError:
            can_refresh = True

        if can_refresh:
            data = self.fetch_osu_data()
            if not data:
                return False

        result = database.fetch_one("SELECT id FROM osu_users WHERE id = %s", params=(self.osu_id,))
        if result:
            database.execute(
                "UPDATE osu_users SET username = %s, score = %s, playcount = %s, accuracy = %s, performance = %s, rank = %s, last_refresh = now() WHERE id = %s",
                params=(
                    data['username'],
                    data['score'],
                    data['playcount'],
                    data['accuracy'],
                    data['performance'],
                    data['rank'],
                    self.osu_id
                )
            )
        else:
            database.execute(
                "INSERT INTO osu_users (id, username, score, playcount, accuracy, performance, rank) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                params=(
                    self.osu_id,
                    data['username'],
                    data['score'],
                    data['playcount'],
                    data['accuracy'],
                    data['performance'],
                    data['rank']
                )
            )

        return True

    # </editor-fold>

    def jsonify(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "osu data": self.osu_data,
            "gq data": self.gq_data,
            "about": self.about,
            "pfp": self.pfp,
            "status": self.status,
            "supporter": self.supporter,
            "last_support": self.last_support,
            "supporter_lasts": self.supporter_lasts,
            "tags": self.tags
        }
