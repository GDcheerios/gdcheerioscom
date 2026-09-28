import re
from urllib.parse import quote, urlsplit

import requests


def _changelog_sort_key(entry: dict) -> tuple:
    """Sort ISO-dated changelogs newest-first with natural version ordering."""
    version_parts = tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.findall(r"\d+|[^\d]+", str(entry.get("version", "")))
    )
    return str(entry.get("date") or ""), version_parts


class Storage:
    hostname: str
    username: str
    password: str
    session: requests.Session

    def __init__(self, hostname: str, username: str, password: str):
        hostname = hostname.strip().rstrip("/")
        if "://" not in hostname:
            hostname = f"http://{hostname}"
        parsed_hostname = urlsplit(hostname)
        if parsed_hostname.hostname == "gdcheeriosstorage" and parsed_hostname.port is None:
            hostname = f"{hostname}:8000"
        self.hostname = hostname
        self.username = username
        self.password = password

        self.session = requests.Session()
        self.session.auth = (self.username, self.password)

    def upload_profile_picture(self, file):
        response = self.session.post(
            f"{self.hostname}/api/upload",
            data={"path": "gdcheerioscom/pfps"},
            files={"files": (file.filename, file.stream, file.mimetype)},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["saved"][0]

    def get_latest_changelog(
        self,
        project: str = "gdcheerioscom",
        output_format: str = "json",
    ) -> dict | None:
        if output_format not in {"json", "html", "markdown"}:
            raise ValueError("output_format must be json, html, or markdown")

        response = self.session.get(f"{self.hostname}/api/changelogs", timeout=30)
        response.raise_for_status()
        project_changelogs = next(
            (item for item in response.json().get("projects", []) if item.get("slug") == project),
            None,
        )
        if not project_changelogs:
            return None

        published_entries = sorted(
            (
                entry for entry in project_changelogs.get("entries", [])
                if entry.get("live") is True and entry.get("version")
            ),
            key=_changelog_sort_key,
            reverse=True,
        )
        latest = published_entries[0] if published_entries else None
        if latest is None:
            return None

        detail_response = self.session.get(
            f"{self.hostname}/api/changelogs/{quote(project, safe='')}/{quote(str(latest['version']), safe='')}",
            params={"format": output_format},
            timeout=30,
        )
        detail_response.raise_for_status()
        if output_format == "json":
            return detail_response.json()
        return {**latest, output_format: detail_response.text}

    def get_changelogs(
        self,
        output_format: str = "html",
        project: str | None = None,
    ) -> list[dict]:
        """Return published changelogs, grouped by project."""
        if output_format not in {"json", "html", "markdown"}:
            raise ValueError("output_format must be json, html, or markdown")

        response = self.session.get(f"{self.hostname}/api/changelogs", timeout=30)
        response.raise_for_status()

        projects = response.json().get("projects", [])
        if project is not None:
            projects = [item for item in projects if item.get("slug") == project]

        published_projects = []
        for item in projects:
            slug = item.get("slug")
            if not slug:
                continue

            entries = []
            sorted_entries = sorted(
                item.get("entries", []),
                key=_changelog_sort_key,
                reverse=True,
            )
            for entry in sorted_entries:
                if entry.get("live") is not True or not entry.get("version"):
                    continue

                version = str(entry["version"])
                detail_response = self.session.get(
                    f"{self.hostname}/api/changelogs/{quote(slug, safe='')}/{quote(version, safe='')}",
                    params={"format": output_format},
                    timeout=30,
                )
                detail_response.raise_for_status()
                detail = detail_response.json() if output_format == "json" else {
                    **entry,
                    output_format: detail_response.text,
                }
                entries.append(detail)

            if entries:
                published_projects.append({**item, "entries": entries})

        return published_projects
