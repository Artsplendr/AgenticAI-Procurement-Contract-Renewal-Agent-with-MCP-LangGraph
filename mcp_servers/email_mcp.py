import smtplib
from email.mime.text import MIMEText
from mcp_servers.base_mcp import BaseMCP
import config

_PLACEHOLDERS = {"", "...", "your-password", "your-email@gmail.com"}

def _smtp_configured() -> bool:
    """Return True only when SMTP credentials look real (not placeholder values)."""
    return bool(
        config.SMTP_HOST
        and config.SMTP_USER not in _PLACEHOLDERS
        and config.SMTP_PASS not in _PLACEHOLDERS
        and "@" in (config.SMTP_USER or "")
    )

class EmailMCP(BaseMCP):
    async def send(self, to: str, subject: str, body: str):
        if not _smtp_configured():
            print(f"[EmailMCP DRY RUN]\nTo: {to}\nSubject: {subject}\n{body}\n")
            return
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.SMTP_USER
        msg["To"] = to
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
                s.starttls()
                s.login(config.SMTP_USER, config.SMTP_PASS)
                s.sendmail(config.SMTP_USER, [to], msg.as_string())
            print(f"[EmailMCP] Sent: {subject}")
        except smtplib.SMTPException as exc:
            print(f"[EmailMCP DRY RUN — SMTP error: {exc}]\nTo: {to}\nSubject: {subject}\n{body}\n")
