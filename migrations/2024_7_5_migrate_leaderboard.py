from objects.PSQLConnection import PSQLConnection as DB

DB.connect()

data = [{"id": 1, "name": "BIgbodyMekhi", "score": 988, "id_ref": 75},
        {"id": 2, "name": "GDcheerios", "score": 2951, "id_ref": 1},
        {"id": 3, "name": "Henchman", "score": 2647, "id_ref": 77},
        {"id": 4, "name": "GDcheerios", "score": 12376, "id_ref": 1},
        {"id": 5, "name": "Henchman", "score": 13595, "id_ref": 77},
        {"id": 6, "name": "GDcheerios", "score": 107172, "id_ref": 1},
        {"id": 7, "name": "BIgbodyMekhi", "score": 665005, "id_ref": 75},
        {"id": 8, "name": "moof", "score": 404, "id_ref": None},
        {"id": 9, "name": "SPIZZLE", "score": 1029, "id_ref": 32},
        {"id": 10, "name": "testscore", "score": 455, "id_ref": None},
        {"id": 11, "name": "testscore", "score": 186, "id_ref": None},
        {"id": 12, "name": "GDcheerios", "score": 140280, "id_ref": 1},
        {"id": 13, "name": "Henchman", "score": 424185, "id_ref": 77},
        {"id": 14, "name": "GDcheerios", "score": 320042, "id_ref": 1},
        {"id": 15, "name": "BIgbodyMekhi", "score": 25268116, "id_ref": 75},
        {"id": 16, "name": "counget", "score": 2285, "id_ref": None},
        {"id": 17, "name": "counget", "score": 5987, "id_ref": None},
        {"id": 18, "name": "vinny", "score": 77, "id_ref": None},
        {"id": 19, "name": "vinny", "score": 469, "id_ref": None},
        {"id": 20, "name": "vinny", "score": 454, "id_ref": None},
        {"id": 21, "name": "vinny", "score": 124, "id_ref": None},
        {"id": 22, "name": "vinny", "score": 520, "id_ref": None},
        {"id": 23, "name": "vinny", "score": 122, "id_ref": None},
        {"id": 24, "name": "vinny", "score": 734, "id_ref": None},
        {"id": 25, "name": "vinny", "score": 87, "id_ref": None},
        {"id": 26, "name": "vinny", "score": 99, "id_ref": None},
        {"id": 27, "name": "vinny", "score": 93, "id_ref": None},
        {"id": 28, "name": "sharp", "score": 1425416, "id_ref": None},
        {"id": 29, "name": "InfernoVolt", "score": 9127, "id_ref": 42},
        {"id": 30, "name": "Benlm420", "score": 1280, "id_ref": 79},
        {"id": 31, "name": "Benlm420", "score": 3103, "id_ref": 79},
        {"id": 32, "name": "Benlm420", "score": 4474, "id_ref": 79},
        {"id": 33, "name": "Benlm420", "score": 262378, "id_ref": 79},
        {"id": 34, "name": "peterparkermj", "score": 1390, "id_ref": 27},
        {"id": 35, "name": "peterparkermj", "score": 933, "id_ref": 27},
        {"id": 36, "name": "peterparkermj", "score": 708, "id_ref": 27},
        {"id": 37, "name": "peterparkermj", "score": 1206, "id_ref": 27},
        {"id": 38, "name": "Monvee", "score": 591, "id_ref": 6},
        {"id": 39, "name": "Monvee", "score": 720, "id_ref": 6},
        {"id": 40, "name": "Suspect", "score": 111, "id_ref": 9},
        {"id": 41, "name": "Suspect", "score": 1361, "id_ref": 9},
        {"id": 42, "name": "Suspect", "score": 617, "id_ref": 9},
        {"id": 43, "name": "peterparkermj", "score": 46336, "id_ref": 27},
        {"id": 44, "name": "Suspect", "score": 4023, "id_ref": 9},
        {"id": 45, "name": "Dukecj1", "score": 80953, "id_ref": 44}]

for score in data:
        DB.do("INSERT INTO leaderboard_scores values (%s, %s, %s, %s, %s)",
                params=(
                        score["id"],
                        score["name"],
                        score["score"],
                        1,
                        score["id_ref"]
                )
        )

DB.end()