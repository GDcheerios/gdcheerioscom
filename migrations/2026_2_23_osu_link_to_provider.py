import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import environment

environment.database.execute(
    """
    INSERT INTO auth_identities (user_id, provider, provider_subject)
    SELECT a.id, 'osu', a.osu_id::text
    FROM accounts a
    WHERE a.osu_id IS NOT NULL
      AND a.osu_id <> 0
    """
)