from environment import database
from api.osu_api import get_user_info
from api.gentrys_quest.user_api import get_xp


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

        self.pfp = "https://storage.cloud.google.com/gdcheerioscombucket/profile-pictures/huh.png"

        try:
            self.id = result[0]
            self.username = result[1]
            self.password = result[2]
            self.email = result[3]
            self.has_osu = result[4] != 0
            self.has_gq = result[7]
            self.osu_id = result[4]
            self.about = result[5]
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
            self.status = "restricted"
            self.exists = False

    # <editor-fold desc="Modifiers">
    @staticmethod
    def create(username: str, password: str, email: str, osu_id: int, about: str):
        query = """
                INSERT INTO accounts (username, password, email, osu_id, about)
                VALUES (%s, %s, %s, %s, %s) \
                """

        params = (
            username,
            password,
            email,
            osu_id,
            about
        )

        database.execute(query, params)
        Account(username).update_osu_data()  # attempt to initialize osu data

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
        """

        result = database.fetch_all(f"select username from accounts where username = %s;", params=(name,))
        return len(result) > 0

    def get_osu_data(self):
        if self.has_osu:
            data = get_user_info(self.osu_id)
            return {
                'username': data['username'],
                'score': data['statistics']['total_score'],
                'playcount': data['statistics']['play_count'],
                'accuracy': data['statistics']['hit_accuracy'],
                'performance': data['statistics']['pp'],
                'rank': data['statistics']['global_rank']
            }
        else:
            return None

    def update_osu_data(self):
        data = self.get_osu_data()
        if data is not None:
            result = database.fetch_one("SELECT id FROM osu_users WHERE id = %s", params=(self.osu_id,))
            if result:
                database.execute(
                    "UPDATE osu_users SET username = %s, score = %s, playcount = %s, accuracy = %s, performance = %s, rank = %s WHERE id = %s",
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

    # </editor-fold>

    def jsonify(self) -> dict:

        gq_data = None
        items = {
            "characters": [],
            "artifacts": [],
            "weapons": []
        }
        osu_data = None

        if self.has_gq:
            gq_data = database.fetch_to_dict("SELECT * FROM gq_data WHERE id = %s", params=(self.id,))
            # gq_data.pop['xp']
            gq_data['experience'] = get_xp(self.id)
            gq_items = database.fetch_all_to_dict("SELECT * FROM gq_items WHERE owner = %s", params=(self.id,))

            for item in gq_items:
                if item['type'] == 'character':
                    items['characters'].append(item)

                elif item['type'] == 'artifact':
                    items['artifacts'].append(item)

                else:
                    items['weapons'].append(item)

            gq_data['items'] = items

        if self.has_osu:
            osu_data = database.fetch_to_dict("SELECT * FROM osu_users WHERE id = %s", params=(self.osu_id,))

        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "osu data": osu_data,
            "gq data": gq_data,
            "about": self.about,
            "pfp": self.pfp,
            "status": self.status
        }
