import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import environment

environment.database.execute(
    """
    INSERT INTO gq_data (id)
    SELECT a.id
    FROM accounts a
    LEFT JOIN gq_data d ON d.id = a.id
    WHERE d.id IS NULL
    """
)

environment.database.execute(
    """
    INSERT INTO gq_rankings (id)
    SELECT a.id
    FROM accounts a
    LEFT JOIN gq_rankings r ON r.id = a.id
    WHERE r.id IS NULL
    """
)