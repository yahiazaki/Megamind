"""Google Calendar integration (OAuth 'Web application' client, token stored in data/google/)."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import get_settings

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.readonly"]
_pending_flows: dict[str, object] = {}

# Local development runs over http://localhost
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def _client_file():
    return get_settings().google_dir / "client_secret.json"


def _token_file():
    return get_settings().google_dir / "token.json"


def _redirect_uri() -> str:
    return get_settings().public_base_url.rstrip("/") + "/api/google/callback"


def status() -> dict:
    return {"client_configured": _client_file().exists(), "connected": _token_file().exists(),
            "redirect_uri": _redirect_uri()}


def auth_url() -> str:
    from google_auth_oauthlib.flow import Flow
    if not _client_file().exists():
        raise RuntimeError("Put your Google OAuth client file at data/google/client_secret.json first")
    flow = Flow.from_client_secrets_file(str(_client_file()), scopes=SCOPES, redirect_uri=_redirect_uri())
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    _pending_flows[state] = flow
    return url


def finish_auth(state: str, code: str) -> None:
    flow = _pending_flows.pop(state, None)
    if flow is None:
        raise RuntimeError("Sign-in session expired, start again from the settings page")
    flow.fetch_token(code=code)
    _token_file().write_text(flow.credentials.to_json(), encoding="utf-8")


def disconnect() -> None:
    _token_file().unlink(missing_ok=True)


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not _token_file().exists():
        return None
    creds = Credentials.from_authorized_user_info(json.loads(_token_file().read_text(encoding="utf-8")), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _token_file().write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(title: str, start: datetime, end: datetime | None, notes: str = "", all_day: bool = False) -> str:
    svc = _service()
    if svc is None:
        return ""
    tz = get_settings().timezone
    if all_day:
        body_time = {"start": {"date": start.date().isoformat()},
                     "end": {"date": (start.date() + timedelta(days=1)).isoformat()}}
    else:
        end = end or start + timedelta(hours=1)
        body_time = {"start": {"dateTime": start.isoformat(), "timeZone": tz},
                     "end": {"dateTime": end.isoformat(), "timeZone": tz}}
    body = {"summary": title, "description": notes + "\n\n(created by Megamind)", **body_time,
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 30}]}}
    ev = svc.events().insert(calendarId="primary", body=body).execute()
    return ev.get("id", "")


def delete_event(event_id: str) -> None:
    svc = _service()
    if svc and event_id:
        try:
            svc.events().delete(calendarId="primary", eventId=event_id).execute()
        except Exception as e:
            log.warning("could not delete Google event %s: %s", event_id, e)


def events_for(day: date) -> list[dict]:
    svc = _service()
    if svc is None:
        return []
    tz = ZoneInfo(get_settings().timezone)
    start = datetime.combine(day, datetime.min.time(), tz)
    end = start + timedelta(days=1)
    res = svc.events().list(calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(),
                            singleEvents=True, orderBy="startTime").execute()
    out = []
    for ev in res.get("items", []):
        st = ev.get("start", {})
        out.append({"id": ev.get("id"), "title": ev.get("summary", "(no title)"),
                    "start": st.get("dateTime") or st.get("date"), "all_day": "date" in st,
                    "description": ev.get("description", "")})
    return out
