import re
import smtplib, ssl
from email.message import EmailMessage
from email.utils import parseaddr
import environment


class EmailManager:
    _EMAIL_RE = re.compile(
        r"^(?=.{1,254}$)"
        r"(?=.{1,64}@)"
        r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
        r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
        r"@"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}$"
    )

    @staticmethod
    def validate_email(to_email: str) -> tuple[bool, str]:
        if not to_email:
            return False, "Email is required."

        email = to_email.strip()

        _, parsed = parseaddr(email)
        if parsed != email:
            return False, "Email must be a plain address like name@example.com."

        if " " in email:
            return False, "Email must not contain spaces."

        if email.count("@") != 1:
            return False, "Email must contain a single '@'."

        local, domain = email.split("@", 1)

        if ".." in local or ".." in domain:
            return False, "Email must not contain consecutive dots."

        if local.startswith(".") or local.endswith("."):
            return False, "Email local-part must not start or end with a dot."

        if domain.startswith("-") or domain.endswith("-"):
            return False, "Email domain must not start or end with a dash."

        if not EmailManager._EMAIL_RE.match(email):
            return False, "Email format looks invalid."

        return True, ""

    @staticmethod
    def send_verification_email(to_email: str, username: str, verify_link: str):
        ok, reason = EmailManager.validate_email(to_email)
        if not ok:
            raise ValueError(reason)

        msg = EmailMessage()
        msg["Subject"] = "Verify your email"
        msg["From"] = environment.smtp_email
        msg["To"] = to_email.strip()
        msg.set_content(
            f"Hi {username},\n\n"
            f"Please verify your email:\n{verify_link}\n\n"
            f"This link expires in 24 hours.\n"
        )

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(environment.smtp_host, 465, context=context) as server:
            server.login(environment.smtp_email, environment.smtp_password)
            server.send_message(msg)
