import hashlib
import json
import secrets
import urllib.parse

from datetime import datetime, timedelta, timezone

import environment

database = environment.database
from api.osu_api import fetch_osu_data
from api.gentrys_quest.user_api import get_ranking
from objects.EmailManager import EmailManager


class Account:
    id: int
    username: str
    password: str
    email: str
    links: list
    about: str
    pfp: str
    status: str
    tags: list
    gq_scores: list
    osu_data: dict
    osu_matches: list
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

        self.pfp = "https://storage.cloud.google.com/gdcheerioscombucket/profile-pictures/huh.png"

        try:
            self.id = result["id"]
            self.username = result["username"]
            self.password = result["password"]
            self.email = result["email"]
            self.has_gqc = False
            self.has_gq = result["has_gq"] != 0
            self.links = database.fetch_all_to_dict("SELECT * FROM auth_identities WHERE user_id = %s",
                                                    params=(self.id,)) or []
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
                    database.execute(f"UPDATE accounts SET is_supporter = FALSE WHERE {from_query_string}",
                                     params=(identifier,))
                    self.supporter = False
                else:
                    self.supporter = True
            else:
                self.supporter = result["is_supporter"]
            self.osu_matches = database.fetch_all_to_dict(
                """
                SELECT
                    id,
                    name,
                    open,
                    pinned,
                    ended,
                    started,
                    opener,
                    (
                        SELECT count(*) FROM osu_match_users where match = osu_matches.id
                    ) as users
                FROM osu_matches
                WHERE opener = %s
                """, params=(self.id,))

        except TypeError:
            self.id = 0
            self.username = "User not found"
            self.password = ""
            self.email = ""
            self.links = []
            self.has_gqc = False
            self.has_gq = False
            self.about = "This user does not exist"
            self.status = "offline"
            self.created = datetime.now()
            self.supporter = False
            self.last_support = None
            self.supporter_lasts = None
            self.tags = []
            self.exists = False
            self.is_admin = False
            self.osu_matches = []

        self.osu_data = {}
        self.gq_data = {}

        if self.get_link("osu"):
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

            stats = environment.database.fetch_all_to_dict(
                """
                SELECT
                    "type",
                    COALESCE(SUM(amount), 0) AS total
                FROM gq_statistics
                WHERE "user" = %s
                GROUP BY "type"
                """,
                params=(self.id,)
            ) or []

            self.gq_data = {
                "scores": leaderboards,
                "stats": stats,
                "metrics": environment.database.fetch_all_to_dict(
                    """SELECT *
                       FROM gq_metrics
                       WHERE user_id = %s
                       ORDER BY recorded_at desc""",
                    params=(self.id,)),
                "metadata": environment.database.fetch_to_dict(
                    """SELECT *
                       FROM gq_data
                       WHERE id = %s""",
                    params=(self.id,)),
                "ranking": get_ranking(self.id),
                "items": environment.database.fetch_all_to_dict(
                    """SELECT *
                       FROM gq_items
                       WHERE owner = %s""",
                    params=(self.id,))
            }

            level = 0
            for i, threshold in enumerate(environment.gq_levels):
                if self.gq_data["metadata"]["score"] >= threshold:
                    level = i + 1
                else:
                    break
            self.gq_data["metadata"]["level"] = level
            self.gq_data["metadata"]["required"] = environment.gq_levels[level]

    @staticmethod
    def from_session(session):
        id = database.fetch_one("SELECT \"user\" FROM sessions WHERE id = %s", params=(session,))
        if id:
            return Account(id[0])
        return None

    @staticmethod
    def id_from_session(session):
        id = database.fetch_one("SELECT \"user\" FROM sessions WHERE id = %s", params=(session,))
        if id:
            return id[0]
        return None

    @staticmethod
    def create_session(id: int):
        session_id = database.fetch_one("INSERT INTO sessions (\"user\") VALUES (%s) RETURNING id", params=(id,))
        return session_id[0]

    @staticmethod
    def revoke_session(session_id):
        if session_id is None:
            return

        database.execute("DELETE FROM sessions WHERE id = %s", params=(session_id,))

    @staticmethod
    def search(query: str):
        return database.fetch_all_to_dict(
            f"SELECT id, username FROM accounts WHERE username ILIKE %s OR about ILIKE %s LIMIT 5;",
            params=(f"%{query}%", f"%{query}%"))

    # <editor-fold desc="Modifiers">
    @staticmethod
    def create(username: str, password: str, email: str, about: str) -> "Account":
        query = """
                INSERT INTO accounts (username, password, email, about)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """

        params = (
            username,
            password,
            email,
            about
        )

        id = database.fetch_one(query, params)[0]
        return Account(id)

    @staticmethod
    def queue(username: str, password: str, email: str, about: str, supporter_id=None, osu_id=None, google_info=None):

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
        password = Account.get_password_hash(str(password))
        pending_id = database.fetch_one(
            """
            INSERT INTO pending_accounts (username, password, email, about, token)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            params=(username, password, email, about, token_hash)
        )[0]

        try:
            url_parts = [
                f"{environment.domain}/api/account/verify?",
                f"sid={pending_id}",
                f"&token={raw_token}"
            ]

            if supporter_id is not None:
                url_parts.append(f"&supporter_id={supporter_id}")
            if osu_id is not None:
                url_parts.append(f"&osu_id={osu_id}")
            if google_info is not None:
                url_parts.append(f"&google_info={urllib.parse.quote(json.dumps(google_info))}")

            verification_url = "".join(url_parts)
            EmailManager.send_verification_email(email, username, verification_url)
        except ValueError as e:
            return {
                "success": False,
                "message": f"{e}"
            }

        return {
            "success": True,
            "message": "Verification email sent. Please check your inbox."
        }

    @staticmethod
    def get_password_hash(password: str):
        return str(environment.bcrypt.generate_password_hash(password))[2:-1]  # remove the byte chars

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

    @staticmethod
    def claim_supporter(supporter_id, id: int):
        weeks = database.fetch_one(
            """
            UPDATE supports
            SET \"user\" = %s
            WHERE id = %s
            RETURNING weeks
            """,
            params=(id, supporter_id)
        )
        if weeks:
            Account.make_supporter(id, weeks[0])

    @staticmethod
    def insert_supporter(id: int, weeks: int = 1):
        database.execute(
            """
            INSERT INTO supports (\"user\", weeks)
            VALUES (%s, %s)
            """,
            params=(id, weeks)
        )

    @staticmethod
    def buy_supporter(id: int, weeks: int = 1):
        """
        Method specific for after purchase
        """
        Account.make_supporter(id, weeks)
        Account.insert_supporter(id, weeks)

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
            database.execute(
                """
                INSERT INTO auth_identities (user_id, provider, provider_subject)
                VALUES (%s, %s, %s)
                """,
                params=(self.id, "osu", osu_id)
            )

            return data
        return None

    def get_osu_data(self):
        link = self.get_link("osu")
        if link:
            data = database.fetch_to_dict("SELECT * FROM osu_users WHERE id = %s;", params=(link["provider_subject"],))
            if data:
                return data

        return None

    # </editor-fold>

    def get_link(self, provider):
        """
        Retrieves the provider link for the account.

        :param provider: Provider name
        :return: provider subject
        """

        for link in self.links:
            if link["provider"] == provider:
                return link

        return None

    def jsonify(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "osu data": self.osu_data,
            "matches": self.osu_matches,
            "gq data": self.gq_data,
            "about": self.about,
            "pfp": self.pfp,
            "status": self.status,
            "supporter": self.supporter,
            "last_support": self.last_support,
            "supporter_lasts": self.supporter_lasts,
            "tags": self.tags
        }
