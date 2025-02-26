import json
from PSQLConnection import PSQLConnection as DB

from GPSystemTest.GPmain import GPSystem


class Item:
    id = None
    type = None
    rating = None
    version = None
    owner = None
    metadata = None

    def __init__(self, id: int, deleted: bool = False):
        super().__init__(id, deleted)
        print(f"loading item {id}")
        item_result = DB.get("SELECT id, type, rating, is_classic, version, owner, metadata FROM gentrys_quest_items WHERE id = %s", params=(id,))
        if not item_result:
            print(f"couldn't find item {id}")
            return

        self.id = id
        self.type = item_result[1]
        self.rating = item_result[2]
        self.is_classic = item_result[3]
        self.version = item_result[4]
        self.owner = item_result[5]
        self.metadata = item_result[6]

        self.deleted = deleted

    @staticmethod
    def update_to_init(id: int, data):
        """
        update item then return
        """

        new_item = Item(id)
        new_item.update(data)
        return new_item

    @staticmethod
    def create_item(item_type: str, data, owner: int):
        new_item = Item(DB.get("INSERT INTO gentrys_quest_items "
                               "(type, metadata, is_classic, version, owner) "
                               "VALUES (%s, %s, %s, %s, %s) "
                               "RETURNING id",
                               params=(item_type, data, True, 0, owner))[0])
        return new_item

    @staticmethod
    def gift_item(item_type: str, data, owner: int):
        new_item = Item(DB.get("INSERT INTO gentrys_quest_items "
                               "(type, metadata, is_classic, version, owner, is_new) "
                               "VALUES (%s, %s, %s, %s, %s, true) "
                               "RETURNING id",
                               params=(item_type, data, True, 0, owner))[0])
        return new_item

    def jsonify(self):
        return {
            'id': self.id,
            'type': self.type,
            'rating': self.rating,
            'is classic': self.is_classic,
            'version': self.version,
            'owner': self.owner,
            'metadata': self.metadata
        }
