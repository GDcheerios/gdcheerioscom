import hashlib
import secrets

from datetime import datetime, timedelta, timezone

import environment

database = environment.database
from api.osu_api import fetch_osu_data
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
    is_admin: bool

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
                is_admin,
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

        if result["supporter_lasts"]:
            if datetime.now(tz=timezone.utc) > result["supporter_lasts"]:
                database.execute(f"UPDATE accounts SET is_supporter = FALSE WHERE {from_query_string}", params=(identifier,))
                self.supporter = False
            else:
                self.supporter = True
        else:
            self.supporter = result["is_supporter"]

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
            self.last_support = result["last_support"]
            self.supporter_lasts = result["supporter_lasts"]
            self.tags = database.fetch_all_to_dict("SELECT * FROM account_tags WHERE account = %s",
                                                   params=(self.id,)) or []
            self.exists = True
            self.is_admin = result["is_admin"]
            if result["supporter_lasts"]:
                if datetime.now(tz=timezone.utc) > result["supporter_lasts"]:
                    database.execute(f"UPDATE accounts SET is_supporter = FALSE WHERE {from_query_string}", params=(identifier,))
                    self.supporter = False
                else:
                    self.supporter = True
            else:
                self.supporter = result["is_supporter"]
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
            self.is_admin = False

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
                "metrics": environment.database.fetch_all_to_dict(
                    "SELECT * FROM gq_metrics WHERE user_id = %s ORDER BY recorded_at desc", params=(self.id,)),
                "metadata": environment.database.fetch_to_dict("SELECT * FROM gq_data WHERE id = %s",
                                                               params=(self.id,)),
                "ranking": environment.database.fetch_to_dict("SELECT * FROM gq_rankings WHERE id = %s",
                                                              params=(self.id,)),
                "items": environment.database.fetch_all_to_dict("SELECT * FROM gq_items WHERE owner = %s",
                                                                params=(self.id,))
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
                VALUES (%s, %s, %s, %s, %s) RETURNING id
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
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
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

    @staticmethod
    def change_about(id: int, new_about: str):
        """
        Change about
        """

        database.execute(f"update accounts set about = %s where id = %s;", params=(new_about, id))

    @staticmethod
    def make_supporter(id: int, weeks: int = 1):
        """
        Grants supporter status to an account.
        If the user is already a supporter, adds time to the expiration date.
        Otherwise, sets expiration to NOW + weeks.
        """
        database.execute(
            """
            UPDATE accounts
            SET is_supporter    = TRUE,
                last_support    = NOW(),
                supporter_lasts = GREATEST(COALESCE(supporter_lasts, NOW()), NOW()) + (INTERVAL '1 week' * %s)
            WHERE id = %s
            """,
            params=(weeks, id)
        )

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

    def set_osu_id(self, osu_id):
        data = fetch_osu_data(osu_id)
        if data:
            database.execute("UPDATE accounts SET osu_id = %s where id = %s;", params=(data["id"], self.id))
            return data

        return None

    def get_osu_data(self):
        data = database.fetch_to_dict("SELECT * FROM osu_users WHERE id = %s;", params=(self.osu_id,))
        if data:
            return data

        return None

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
