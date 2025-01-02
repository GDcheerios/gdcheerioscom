import json

from GPSystem.GPmain import GPSystem
from crap.Account import Account
from crap.PSQLConnection import PSQLConnection as DB
from crap.gentrys_quest_crap.Item import Item
from crap.gentrys_quest_crap.UserRanking import UserRanking


def ranking(func):
    def wrapper(*args, **kwargs):
        item: Item = func(*args, **kwargs)
        if not item.deleted:
            item.rank_item()

        if item.is_classic:
            result = GQManager.update_user_rating(item.owner, True)
        else:
            result = GQManager.update_user_rating(item.owner, False)

        details = {
            'item': item.jsonify(),
            'user': result
        }

        return details

    return wrapper


class GQManager:
    @staticmethod
    def update_user_rating(id, classic: bool) -> dict:
        # weighting
        character_rating = 0
        artifact_rating = 0
        weapon_rating = 0

        if GPSystem.rater.character_rating_enabled:
            character_rating = GQManager.get_weighted_rating(id, "character", classic)

        if GPSystem.rater.artifact_rating_enabled:
            artifact_rating = GQManager.get_weighted_rating(id, "artifact", classic)

        if GPSystem.rater.weapon_rating_enabled:
            weapon_rating = GQManager.get_weighted_rating(id, "weapon", classic)

        weighted = character_rating + artifact_rating + weapon_rating
        ranking, tier = GPSystem.rater.get_rank(weighted)

        DB.do(
            """
            INSERT INTO rankings (id, weighted, unweighted, c_weighted, c_unweighted, rank, tier, c_rank, c_tier)
            VALUES (%s, %s, (SELECT SUM(rating) FROM gentrys_quest_items WHERE owner = %s), %s, 0, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET
                weighted = CASE 
                    WHEN NOT %s THEN EXCLUDED.weighted 
                    ELSE rankings.weighted 
                END,
                unweighted = CASE 
                    WHEN NOT %s THEN (SELECT SUM(rating) FROM gentrys_quest_items WHERE owner = EXCLUDED.id) 
                    ELSE rankings.unweighted 
                END,
                rank = CASE 
                    WHEN NOT %s THEN EXCLUDED.rank 
                    ELSE rankings.rank 
                END,
                tier = CASE 
                    WHEN NOT %s THEN EXCLUDED.tier 
                    ELSE rankings.tier 
                END,
                c_weighted = CASE 
                    WHEN %s THEN EXCLUDED.c_weighted 
                    ELSE rankings.c_weighted 
                END,
                c_unweighted = CASE 
                    WHEN %s THEN (SELECT SUM(rating) FROM gentrys_quest_items WHERE owner = EXCLUDED.id) 
                    ELSE rankings.c_unweighted 
                END,
                c_rank = CASE 
                    WHEN %s THEN EXCLUDED.c_rank 
                    ELSE rankings.c_rank 
                END,
                c_tier = CASE 
                    WHEN %s THEN EXCLUDED.c_tier 
                    ELSE rankings.c_tier 
                END;
            """,
            params=(
                id,
                weighted if not classic else None,  # for `weighted` column on insert
                id,
                weighted if classic else None,  # for `c_weighted` column on insert
                ranking if not classic else None,
                tier if not classic else None,
                ranking if classic else None,  # for `c_rank` column on insert
                tier if classic else None,  # for `c_tier` column on insert

                # Update conditions for ON CONFLICT
                classic,  # for `weighted`
                classic,  # for `unweighted`
                classic,  # for `rank`
                classic,  # for `tier`
                classic,  # for `c_weighted`
                classic,  # for `c_unweighted`
                classic,  # for `c_rank`
                classic  # for `c_tier`
            )
        )

        return GQManager.get_ranking(id, classic).jsonify()

    @staticmethod
    @ranking
    def update_item(id: int, data):
        return Item.update_to_init(id, data)

    @staticmethod
    @ranking
    def add_item(item_type: str, data, is_classic: bool, owner: int):
        return Item.create_item(item_type, data, is_classic, owner)

    @staticmethod
    @ranking
    def gift_item(item_type: str, data, is_classic: bool, owner: int):
        return Item.gift_item(item_type, data, is_classic, owner)

    @staticmethod
    def gift_item_to_all(item_type: str, data, is_classic: bool):
        table = "gentrys_quest_classic_data" if is_classic else "gentrys_quest_data"
        ids = DB.get_group(f"SELECT id FROM {table}")
        for id in ids:
            Item.gift_item(item_type, data, is_classic, id)

        return "gifted!"

    @staticmethod
    def classic_add_money(id, amount):
        if id == "*":
            DB.do("UPDATE gentrys_quest_classic_data SET new_money = new_money + %s", params=(amount,))
        else:
            DB.do("UPDATE gentrys_quest_classic_data SET new_money = new_money + %s where id = %s", params=(amount, id))
        return amount

    @staticmethod
    @ranking
    def remove_item(id: int):
        return Item.remove(id)

    @staticmethod
    @ranking
    def remove_items(id_list: list):
        x = 0
        while x < len(id_list) - 1:
            DB.do(f"DELETE FROM gentrys_quest_items WHERE ID = %s", params=(id_list[x],))
            x += 1

        return Item.remove(id_list[x])

    @staticmethod
    def submit_classic_data(id: int, start_amount: int, money: int):
        DB.do("""
            INSERT INTO gentrys_quest_classic_data (id, startup_amount, money)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) 
            DO UPDATE SET startup_amount = EXCLUDED.startup_amount, money = EXCLUDED.money, new_money = 0
        """, params=(id, start_amount, money))

        return ":thumbs_up:"

    @staticmethod
    def classic_check_in(id: int):
        Account.set_status(id, "gqc_online")
        return ""

    @staticmethod
    def check_out(id: int):
        Account.set_status(id, "offline")
        return ""

    # <editor-fold desc="getters">

    @staticmethod
    def get_rating(id):
        raise NotImplementedError

    @staticmethod
    def get_item(id) -> Item:
        return Item(id)

    @staticmethod
    def get_data(id, is_classic: bool) -> dict:
        data = {}
        items = DB.get_group(
            """
            SELECT id, type, metadata, is_new
            FROM gentrys_quest_items WHERE owner = %s AND is_classic = %s
            """,
            params=(id, is_classic)
        )

        startup_amount = 0
        money = 0
        new_money = 0

        if is_classic:
            selection = DB.get("SELECT startup_amount, money, new_money FROM gentrys_quest_classic_data WHERE id = %s",
                               params=(id,))
            if selection:
                startup_amount = selection[0]
                money = selection[1]
                new_money = selection[2]

        data["startup amount"] = startup_amount
        data["money"] = money
        data["new money"] = new_money
        data["items"] = items

        return data

    @staticmethod
    def get_weighted_rating(id, object_type: str, classic: bool) -> int:
        rating = 0
        counter = 0
        for item in DB.get_group(
                f"SELECT rating FROM gentrys_quest_items WHERE owner = %s AND type = %s AND is_classic = %s ORDER BY rating desc limit {GPSystem.rater.max_item_rating};",
                params=(id, object_type, classic)):
            rating += item[0] * 0.95 ** counter
            counter += 1

        return rating

    @staticmethod
    def get_items(owner: int, classic: bool):
        items = {
            "characters": [],
            "artifacts": [],
            "weapons": []
        }

        categories = ["character", "artifact", "weapon"]

        for category in categories:
            results = DB.get_group(
                f"""
                SELECT id, 
                       rating, 
                       metadata->>'name' AS name, 
                       RANK() OVER (ORDER BY rating DESC) AS placement
                FROM gentrys_quest_items
                WHERE owner = %s AND type = %s AND is_classic = %s
                ORDER BY rating DESC
                LIMIT {GPSystem.rater.max_item_rating};
                """,
                params=(owner, category, classic)
            )

            items[category + "s"] = [
                {
                    "id": result[0],
                    "rating": result[1],
                    "name": result[2],
                    "placement": result[3]
                }
                for result in results
            ]

        return items

    @staticmethod
    def get_leaderboard(classic: bool, start: int = 0, amount: int = 50, online: bool = False) -> list:
        """
        grab leaderboard data

        @param classic: targeting classic data
        @param start: start index
        @param amount: how many players to pull
        @param online: targeting online players
        @return: leaderboard data
        """
        prefix = 'c_' if classic else ''  # c_ = classic prefix
        online_prefix = 'gqc_' if classic else 'gq_'
        query = f"""
                SELECT rankings.id, accounts.username,
                rankings.{prefix + 'weighted'}, rankings.{prefix + 'rank'}, rankings.{prefix + 'tier'}
                FROM rankings
                INNER JOIN accounts ON rankings.id = accounts.id
                WHERE accounts.status NOT IN ('restricted', 'test') {f"AND accounts.status = '{online_prefix}online'" if online else ""}
                ORDER BY {prefix + 'weighted'} desc
                LIMIT %s OFFSET %s;
            """

        return DB.get_group(query, params=(amount, start))

    @staticmethod
    def get_color(rank: str):
        return GPSystem.rater.rating_colors[rank]

    @staticmethod
    def get_ranking(id: int, classic: bool) -> UserRanking:
        return UserRanking(id, classic)

    # </editor-fold>
