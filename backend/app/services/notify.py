"""Email notifications via Resend.

Resend REST API: ``POST https://api.resend.com/emails`` with a Bearer key and a
JSON body ``{from, to, subject, html}``. If ``RESEND_API_KEY`` is unset, every
notification is logged instead of sent, so the app runs fine without email.

All functions are safe to run in a FastAPI BackgroundTask: they never raise, so
a mail failure can't break the request that triggered it.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("notify")

_BRAND = "#6366f1"


def _link(path: str) -> str:
    base = settings.app_base_url.rstrip("/")
    return f"{base}{path}" if base else ""


def _wrap(heading: str, body_html: str, cta_path: str = "", cta_label: str = "") -> str:
    cta = ""
    url = _link(cta_path) if cta_path else ""
    if url and cta_label:
        cta = (
            f'<a href="{url}" style="display:inline-block;margin-top:18px;'
            f"background:{_BRAND};color:#fff;text-decoration:none;padding:10px 18px;"
            f'border-radius:8px;font-weight:600">{cta_label}</a>'
        )
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;
margin:0 auto;padding:24px;color:#1f2430">
  <div style="font-size:20px;font-weight:700;margin-bottom:16px">
    <span style="color:{_BRAND}">&#9670;</span> Karuna<span style="color:#8a93a6">Admin</span>
  </div>
  <h2 style="font-size:18px;margin:0 0 10px">{heading}</h2>
  <div style="font-size:14px;line-height:1.6;color:#39414f">{body_html}</div>
  {cta}
  <p style="font-size:12px;color:#9aa3b5;margin-top:24px">
    You're receiving this because you have an account on Karuna Admin.
  </p>
</div>"""


def _send(to: list[str], subject: str, html: str) -> None:
    recipients = [e for e in to if e]
    if not recipients:
        return
    if not settings.resend_api_key:
        logger.info("[notify:mock] to=%s subject=%s", recipients, subject)
        return
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from,
                "to": recipients,
                "subject": subject,
                "html": html,
            },
            timeout=20.0,
        )
        if resp.status_code >= 400:
            logger.warning("Resend error %s: %s", resp.status_code, resp.text[:300])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Resend send failed: %s", exc)


# --------------------------------------------------------------------------- #
# Event notifications
# --------------------------------------------------------------------------- #
def deliverable_assigned(
    to_email: str, to_name: str, title: str, project_name: str, project_id: int
) -> None:
    html = _wrap(
        f"You've been assigned a deliverable",
        f"Hi {to_name},<br><br>You've been assigned <b>{title}</b> on the project "
        f"<b>{project_name}</b>. Please upload the required documentation and mark "
        f"it as submitted when ready.",
        f"/projects/{project_id}",
        "Open project",
    )
    _send([to_email], f"Assigned: {title}", html)


def deliverable_added(
    to_email: str, to_name: str, title: str, project_name: str, project_id: int
) -> None:
    html = _wrap(
        "A new deliverable was added",
        f"Hi {to_name},<br><br>A new deliverable <b>{title}</b> was added to "
        f"<b>{project_name}</b>.",
        f"/projects/{project_id}",
        "View deliverable",
    )
    _send([to_email], f"New deliverable: {title}", html)


def deliverable_submitted(
    admin_emails: list[str], title: str, project_name: str,
    submitter_name: str, project_id: int,
) -> None:
    html = _wrap(
        "A deliverable was submitted",
        f"<b>{submitter_name}</b> submitted documentation for <b>{title}</b> on "
        f"<b>{project_name}</b>. It's ready for review.",
        f"/projects/{project_id}",
        "Review deliverable",
    )
    _send(admin_emails, f"Submitted: {title}", html)


def dev_card_assigned(
    to_email: str, to_name: str, title: str, project_name: str, project_id: int
) -> None:
    html = _wrap(
        "A ticket was assigned to you",
        f"Hi {to_name},<br><br>You've been assigned the ticket <b>{title}</b> on "
        f"<b>{project_name}</b>.",
        f"/projects/{project_id}",
        "Open board",
    )
    _send([to_email], f"Ticket assigned: {title}", html)


def commercial_card_assigned(to_email: str, to_name: str, title: str) -> None:
    html = _wrap(
        "A commercial opportunity was assigned to you",
        f"Hi {to_name},<br><br>You've been assigned the opportunity <b>{title}</b>.",
        "/commercial",
        "Open commercial board",
    )
    _send([to_email], f"Opportunity assigned: {title}", html)


def user_welcome(to_email: str, to_name: str, role: str, temp_password: str) -> None:
    html = _wrap(
        "Welcome to Karuna Admin",
        f"Hi {to_name},<br><br>An account was created for you with the role "
        f"<b>{role}</b>.<br><br>Email: <b>{to_email}</b><br>"
        f"Temporary password: <b>{temp_password}</b><br><br>"
        f"Please sign in and change your password.",
        "/login",
        "Sign in",
    )
    _send([to_email], "Your Karuna Admin account", html)
