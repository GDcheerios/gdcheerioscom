import smtplib, ssl
from email.message import EmailMessage
import environment


class EmailManager:
    @staticmethod
    def send_verification_email(to_email: str, username: str, verify_link: str):
        msg = EmailMessage()
        msg["Subject"] = "Verify your email"
        msg["From"] = environment.smtp_email
        msg["To"] = to_email
        msg.set_content(f"Hi {username},\n\nPlease verify your email:\n{verify_link}\n\nThis link expires in 24 hours.\n")

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(environment.smtp_host, 465, context=context) as server:
            server.login(environment.smtp_email, environment.smtp_password)
            server.send_message(msg)
