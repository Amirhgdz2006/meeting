from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime
from typing import List, Dict, Optional
import logging
import pytz
from dateutil import parser

logger = logging.getLogger(__name__)

TEHRAN_TZ = pytz.timezone('Asia/Tehran')


def build_calendar_service(access_token: str):
    credentials = Credentials(token=access_token)
    service = build('calendar', 'v3', credentials=credentials)
    return service


def _normalize_iso_z(dt_str: str) -> str:
    if dt_str.endswith('Z'):
        return dt_str[:-1] + '+00:00'
    return dt_str


def parse_datetime_string(dt_str: str) -> datetime:
    dt = parser.isoparse(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(TEHRAN_TZ)


def get_user_freebusy(access_token: str, email: str, time_min: datetime, time_max: datetime) -> List[Dict[str, str]]:
    service = build_calendar_service(access_token)

    if time_min.tzinfo is None:
        time_min = TEHRAN_TZ.localize(time_min)
    if time_max.tzinfo is None:
        time_max = TEHRAN_TZ.localize(time_max)

    body = {
        "timeMin": time_min.astimezone(pytz.UTC).isoformat(),
        "timeMax": time_max.astimezone(pytz.UTC).isoformat(),
        "items": [{"id": email}],
        "timeZone": "Asia/Tehran"
    }

    try:
        freebusy_result = service.freebusy().query(body=body).execute()
    except Exception as e:
        logger.exception("Google FreeBusy query failed")
        raise

    calendar_entry = freebusy_result.get('calendars', {}).get(email, {})
    busy = []
    if isinstance(calendar_entry, dict):
        busy = calendar_entry.get('busy', []) or []
    else:
        logger.warning("freebusy returned unexpected calendar entry shape for %s: %r", email, calendar_entry)
        busy = []

    normalized = []
    for ev in busy:
        s = ev.get('start')
        e = ev.get('end')
        if not s or not e:
            continue

        s_dt = parse_datetime_string(_normalize_iso_z(s))
        e_dt = parse_datetime_string(_normalize_iso_z(e))

        normalized.append({
            "start": s_dt.isoformat(),
            "end": e_dt.isoformat()
        })

    return normalized


# ------------------------------

def create_calendar_event(access_token: str, summary: str, description: str,
                          start_time: datetime, end_time: datetime,
                          attendees: List[str], location: Optional[str] = None,
                          conference_data: bool = False):
    service = build_calendar_service(access_token)

    if start_time.tzinfo is None:
        start_time = TEHRAN_TZ.localize(start_time)
    else:
        start_time = start_time.astimezone(TEHRAN_TZ)

    if end_time.tzinfo is None:
        end_time = TEHRAN_TZ.localize(end_time)
    else:
        end_time = end_time.astimezone(TEHRAN_TZ)


    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'Asia/Tehran',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'Asia/Tehran',
        },
        'attendees': [{'email': email} for email in attendees],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 30},
            ],
        },
    }

    if location:
        event['location'] = location

    if conference_data:
        event['conferenceData'] = {
            'createRequest': {
                'requestId': f"meet-{int(datetime.now().timestamp())}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }

    created_event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1 if conference_data else 0,
        sendUpdates='all'
    ).execute()

    return created_event


def update_calendar_event(access_token: str, event_id: str, updates: Dict):
    service = build_calendar_service(access_token)

    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    if not isinstance(event, dict):
        raise ValueError("Fetched event is malformed")

    event.update(updates)

    updated_event = service.events().update(
        calendarId='primary',
        eventId=event_id,
        body=event,
        sendUpdates='all'
    ).execute()

    return updated_event


def delete_calendar_event(access_token: str, event_id: str):
    service = build_calendar_service(access_token)
    service.events().delete(
        calendarId='primary',
        eventId=event_id,
        sendUpdates='all'
    ).execute()
