import logging

from flask import Blueprint, jsonify

import environment

status_api_blueprint = Blueprint("status_api", __name__)


@status_api_blueprint.get("/status/information")
def get_status_information():
    """
    Returns overall status information for the status page.
    Shape:
    {
      "request_data": { ... },
      "account_data": { ... },
      "gq": { ... },
      "osu": { ... },
      "timeseries": {
          "requests_last_24h": [...],
          "endpoint_stats": [...]
      },
      "services": { ... }
    }
    """
    try:
        # Overall request stats
        request_data = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint                        AS total_requests,
                AVG(duration)::float                    AS avg_duration,
                SUM(CASE WHEN successful THEN 1 ELSE 0 END)::bigint AS successful_requests,
                SUM(CASE WHEN NOT successful THEN 1 ELSE 0 END)::bigint AS failed_requests
            FROM requests
            """
        ) or {}

        # Last 24 hours, grouped by hour for graphs
        request_timeseries = environment.database.fetch_all_to_dict(
            """
            SELECT
                date_trunc('hour', sent)                       AS bucket,
                COUNT(*)::bigint                               AS request_count,
                AVG(duration)::float                           AS avg_duration,
                SUM(CASE WHEN successful THEN 1 ELSE 0 END)::bigint AS successful_requests,
                SUM(CASE WHEN NOT successful THEN 1 ELSE 0 END)::bigint AS failed_requests
            FROM requests
            WHERE sent >= now() - interval '24 hours'
            GROUP BY bucket
            ORDER BY bucket
            """
        ) or []

        # Per-endpoint breakdown (top 10)
        endpoint_stats = environment.database.fetch_all_to_dict(
            """
            SELECT
                endpoint,
                COUNT(*)::bigint                               AS request_count,
                AVG(duration)::float                           AS avg_duration,
                SUM(CASE WHEN successful THEN 1 ELSE 0 END)::bigint AS successful_requests,
                SUM(CASE WHEN NOT successful THEN 1 ELSE 0 END)::bigint AS failed_requests
            FROM requests
            GROUP BY endpoint
            ORDER BY request_count DESC
            LIMIT 10
            """
        ) or []

        # Accounts: totals, supporters, admins
        account_data = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint                                    AS total_accounts,
                SUM(CASE WHEN is_supporter THEN 1 ELSE 0 END)::bigint AS supporters,
                SUM(CASE WHEN is_admin THEN 1 ELSE 0 END)::bigint     AS admins
            FROM accounts
            """
        ) or {}

        # Gentry's Quest overview
        gq_overview = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint             AS players,
                COALESCE(SUM(score), 0)::bigint AS total_score,
                COALESCE(SUM(money), 0)::bigint AS total_money,
                AVG(score)::float            AS avg_score
            FROM gq_data
            """
        ) or {}

        gq_lb_overview = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint AS total_leaderboards,
                SUM(CASE WHEN online THEN 1 ELSE 0 END)::bigint AS online_leaderboards
            FROM gq_leaderboards
            """
        ) or {}

        gq_scores_overview = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint AS total_scores
            FROM gq_scores
            """
        ) or {}

        # osu! overview (users)
        osu_overview = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint               AS users,
                AVG(performance)::float        AS avg_performance,
                AVG(accuracy)::float           AS avg_accuracy,
                MIN(rank)                      AS best_rank,
                MAX(last_refresh)              AS last_refresh
            FROM osu_users
            """
        ) or {}

        # osu! matches overview
        osu_matches_overview = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(*)::bigint AS open_matches
            FROM osu_matches
            WHERE open = TRUE AND ended = FALSE
            """
        ) or {}

        osu_active_players = environment.database.fetch_to_dict(
            """
            SELECT
                COUNT(DISTINCT u.user)::bigint AS active_players
            FROM osu_match_users u
                     JOIN osu_matches m ON m.id = u.match
            WHERE m.open = TRUE AND m.ended = FALSE
            """
        ) or {}

        # Simple "services" view based on server key/value pairs.
        server_rows = environment.database.fetch_all_to_dict("SELECT key, value FROM server") or []
        services = {row["key"]: row["value"] for row in server_rows}

        response = {
            "request_data": {
                "total_requests": request_data.get("total_requests") or 0,
                "avg_duration": request_data.get("avg_duration"),  # seconds
                "successful_requests": request_data.get("successful_requests") or 0,
                "failed_requests": request_data.get("failed_requests") or 0,
            },
            "account_data": {
                "total_accounts": account_data.get("total_accounts") or 0,
                "supporters": account_data.get("supporters") or 0,
                "admins": account_data.get("admins") or 0,
            },
            "gq": {
                "players": gq_overview.get("players") or 0,
                "total_score": gq_overview.get("total_score") or 0,
                "total_money": gq_overview.get("total_money") or 0,
                "avg_score": gq_overview.get("avg_score"),
                "total_scores": gq_scores_overview.get("total_scores") or 0,
                "total_leaderboards": gq_lb_overview.get("total_leaderboards") or 0,
                "online_leaderboards": gq_lb_overview.get("online_leaderboards") or 0,
            },
            "osu": {
                "users": osu_overview.get("users") or 0,
                "avg_performance": osu_overview.get("avg_performance"),
                "avg_accuracy": osu_overview.get("avg_accuracy"),
                "best_rank": osu_overview.get("best_rank"),
                "last_refresh": (
                    osu_overview.get("last_refresh").isoformat()
                    if osu_overview.get("last_refresh") is not None
                    else None
                ),
                "open_matches": osu_matches_overview.get("open_matches") or 0,
                "active_players": osu_active_players.get("active_players") or 0,
            },
            "timeseries": {
                "requests_last_24h": [
                    {
                        "timestamp": row["bucket"].isoformat() if row["bucket"] is not None else None,
                        "request_count": row["request_count"],
                        "avg_duration": row["avg_duration"],
                        "successful_requests": row["successful_requests"],
                        "failed_requests": row["failed_requests"],
                    }
                    for row in request_timeseries
                    if row.get("bucket") is not None
                ],
                "endpoint_stats": endpoint_stats,
            },
            "services": services,
        }

        return jsonify(response)
    except Exception:
        logging.exception("[status] Failed to build status information")
        return jsonify({"error": "status_error"}), 500