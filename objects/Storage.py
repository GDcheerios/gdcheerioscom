import requests
from urllib.parse import quote, urlsplit


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

        response = self.session.get(
            f"{self.hostname}/api/changelogs",
            timeout=30,
        )
        response.raise_for_status()

        projects = response.json().get("projects", [])
        project_changelogs = next(
            (item for item in projects if item.get("slug") == project),
            None,
        )
        if not project_changelogs or not project_changelogs.get("entries"):
            return None

        latest = project_changelogs["entries"][0]
        version = latest.get("version")
        if not version:
            return None

        response = self.session.get(
            f"{self.hostname}/api/changelogs/{quote(project, safe='')}/{quote(str(version), safe='')}",
            params={"format": output_format},
            timeout=30,
        )
        response.raise_for_status()
        if output_format == "json":
            return response.json()
        return {**latest, output_format: response.text}
