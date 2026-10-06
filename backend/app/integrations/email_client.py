"""
Resend transactional email integration.

Uses httpx directly against Resend's REST API rather than adding the
`resend` PyPI package — httpx is already a dependency, and this is a
single simple POST, not worth a new library for.
"""
import httpx

from app.core.config import settings

RESEND_API_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    """Raised on any failure to send — network error, non-2xx response,
    or missing configuration. Callers (the Celery task) decide what to
    do about it; this layer just reports failure clearly."""


def send_follow_up_reminder_email(
    *, to_email: str, to_name: str, lead_name: str, lead_company: str, follow_up_title: str, due_at_iso: str
) -> None:
    if not settings.RESEND_API_KEY:
        # Fails loudly rather than silently no-op'ing — a misconfigured
        # deployment should show up as failed/retrying reminders, not as
        # reminders that quietly never send with no error anywhere.
        raise EmailSendError("RESEND_API_KEY is not configured")

    subject = f"Reminder: {follow_up_title} — {lead_name}"
    html_body = (
        f"<p>Hi {to_name},</p>"
        f"<p>This is a reminder for your follow-up on <strong>{lead_name}</strong> "
        f"({lead_company}):</p>"
        f"<p><strong>{follow_up_title}</strong><br>Due: {due_at_iso}</p>"
        f"<p>— ClientFlow</p>"
    )

    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Network error calling Resend: {exc}") from exc

    if response.status_code >= 400:
        raise EmailSendError(f"Resend returned {response.status_code}: {response.text}")
