import os.path
from environment import database


class Account:
    id: int
    username: str
    password: str
    email: str
    osu_id: int
    about: str
    pfp: str
    status: str
    exists: bool

    def __init__(self, identifier):
        print(f"Loading account {identifier}")
        try:
            identifier = int(identifier)
            from_query_string = "id = %s"
        except ValueError:
            from_query_string = "username = %s"

        result = database.fetch_one(
            f"""
            SELECT 
                id,                                                                                             -- 0
                username,                                                                                       -- 1
                password,                                                                                       -- 2
                email,                                                                                          -- 3
                osu_id,                                                                                         -- 4
                about,                                                                                          -- 5
                status,                                                                                         -- 6
                EXISTS (
                    SELECT 1 
                    FROM gq_data 
                    WHERE gq_data.id = accounts.id
                ) AS has_gq                                                                                     -- 7
            FROM accounts 
            WHERE {from_query_string}
            """,
            params=(identifier,)
        )

        try:
            self.id = result[0]
            self.username = result[1]
            self.password = result[2]
            self.email = result[3]
            self.has_osu = result[4] != 0
            self.has_gq = result[7]
            self.osu_id = result[4]
            self.about = result[5]
            if self.has_osu:
                self.pfp = f"https://a.ppy.sh/{self.osu_id}"
            else:
                self.pfp = f"static/pfps/huh.png"
            self.status = result[6]
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
            self.pfp = f"static/pfps/huh.png"
            self.status = "restricted"
            self.exists = False

    # <editor-fold desc="Modifiers">
    @staticmethod
    def create(username: str, password: str, email: str, osu_id: int, about: str):
        query = """
        INSERT INTO accounts (username, password, email, osu_id, about)
        VALUES (%s, %s, %s, %s, %s)
        """

        params = (
            username,
            password,
            email,
            osu_id,
            about
        )

        database.execute(query, params)

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
        Check if username exists
        """

        result = database.fetch_all(f"select username from accounts where username = %s;", params=(name,))
        return len(result) > 0

    # </editor-fold>

    def jsonify(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "osuid": self.osu_id,
            "about": self.about,
            "pfp": self.pfp,
            "status": self.status
        }
