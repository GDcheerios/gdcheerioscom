# mekhi has too many poop artifacts
# we remove them :)

from objects.PSQLConnection import PSQLConnection as DB

DB.connect()

artifacts = DB.get_group("select id, metadata from gentrys_quest_items where owner = 75 and type = 'artifact';")

compensation = 0
id_list = []


for id, metadata in artifacts:
    if metadata["star rating"] <= 4:
        id_list.append(id)
        compensation += metadata["star rating"] * 10

placeholders = ', '.join(['%s'] * len(id_list))
DB.do(f"DELETE FROM gentrys_quest_items WHERE id IN ({placeholders})", params=tuple(id_list))

print("give the guy $", compensation)
