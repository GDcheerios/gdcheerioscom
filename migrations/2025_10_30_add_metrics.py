import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import environment

environment.database.execute(
    """
    INSERT INTO gq_metrics (user_id, recorded_at, rank, gp)
    SELECT
        gr.id AS user_id,
        now() AS recorded_at,
        0 AS rank,
        0 AS gp
    FROM gq_rankings gr
    """
)

