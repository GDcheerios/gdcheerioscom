import json

from objects.PSQLConnection import PSQLConnection as DB

DB.connect()
items = DB.get_group("SELECT id, metadata FROM gq_items")
for item in items:
    data = item[1]
    data["id"] = item[0]
    DB.do(f"UPDATE gq_items SET metadata = %s WHERE id = %s" ,
          params=(json.dumps(data), item[0]))
