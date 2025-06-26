"""
I want to put all the data into sql db.
I'm migrating all account data into sql!
"""
import json
import os

from objects.PSQLConnection import PSQLConnection


psql = PSQLConnection()
for id in os.listdir("accounts"):
    data = json.load(open(f"accounts/{id}", "r"))
    id = data["id"]

    query = """
INSERT INTO accounts (id, username, password, email, osu_id, about)
VALUES (%s, %s, %s, %s, %s, %s)
"""
    username = data['username']
    if len(username) > 24:
        username = username[:24]

    params = (
        id,
        username,
        data["password"],
        'email@poop.com',
        data["metadata"]["osu id"],
        data["metadata"]["about me"]
    )

    psql.do(query, params)

    # gqc data
    if data["metadata"]["Gentry's Quest Classic data"]:
        query = """
        insert into gentrys_quest_classic_data (id, startup_amount, money)
        values (%s, %s, %s)
        """

        params = (
            data["id"],
            data["metadata"]["Gentry's Quest Classic data"]["startupamount"],
            data["metadata"]["Gentry's Quest Classic data"]["inventory"]["money"]
        )

        psql.do(query, params)

        inventory = data["metadata"]["Gentry's Quest Classic data"]["inventory"]
        for character in inventory["characters"]:
            query = """
            insert into gq_items (type, metadata, rating, owner, is_classic)
            values (%s, %s, %s, %s, %s)
            """

            params = (
                "character",
                json.dumps(character),
                None,
                id,
                "true"
            )

            psql.do(query, params)

        for artifact in inventory["artifacts"]:
            query = """
            insert into gentrys_quest_items (type, metadata, rating, owner, is_classic)
            values (%s, %s, %s, %s, %s)
            """

            params = (
                "artifact",
                json.dumps(artifact),
                None,
                id,
                "true"
            )

            psql.do(query, params)

        for weapon in inventory["weapons"]:
            query = """
            insert into gentrys_quest_items (type, metadata, rating, owner, is_classic)
            values (%s, %s, %s, %s, %s)
            """

            params = (
                "weapon",
                json.dumps(weapon),
                None,
                id,
                "true"
            )

            psql.do(query, params)


psql.end()
