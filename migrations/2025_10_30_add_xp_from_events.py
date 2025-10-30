import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import environment

environment.database.execute(
    """
    INSERT INTO gq_data (id, score)
    SELECT "user" AS id, SUM(score) as score
    FROM gq_scores
    group by "user"
    ON CONFLICT (id) DO UPDATE
    Set score = EXCLUDED.score
    """
)

# print(environment.database.fetch_all(
#     """
#     SELECT "user" AS id, SUM(score) as score
#     FROM gq_scores
#     group by "user"
#     """
# ))

