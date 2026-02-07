from typing import List, Dict, Any, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil import tz as dateutil_tz
import pytz
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.modules.users.repositories import get_user_by_email, update_user_google_tokens
from app.integrations.google.calendar import get_user_freebusy
from app.integrations.google.oauth import refresh_google_access_token, is_google_token_expired
from functools import reduce
import logging

logger = logging.getLogger(__name__)


def get_valid_access_token(db: Session, user):
    if is_google_token_expired(user.google_token_expires_at):
        result = refresh_google_access_token(user.google_refresh_token)
        update_user_google_tokens(
            db=db,
            user=user,
            access_token=result['access_token'],
            expires_at=result['expiry']
        )
        return result['access_token']
    return user.google_access_token


# Core algorithm for common free slots

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


def compute_common_meeting_slots(
    people_events: List[List[Dict[str, Any]]],
    duration_minutes: int,
    target_date: datetime,
    work_start_hour: int = 8,
    work_end_hour: int = 21,
    step_minutes: int | None = None,
    target_tz_name: str = "Asia/Tehran",
) -> List[Dict[str, str]]:

    if duration_minutes <= 0:
        return []

    if step_minutes is None or step_minutes <= 0:
        step_minutes = duration_minutes

    meeting_delta = timedelta(minutes=duration_minutes)
    step_delta = timedelta(minutes=step_minutes)

    # -------- timezone resolver --------
    def _resolve_tz(name: str):
        if ZoneInfo:
            try:
                return ZoneInfo(name)
            except Exception:
                pass
        tz = dateutil_tz.gettz(name)
        if tz:
            return tz
        try:
            return pytz.timezone(name)
        except Exception:
            return timezone.utc

    target_tz = _resolve_tz(target_tz_name)

    # -------- normalize target date --------
    if target_date.tzinfo is None:
        target_date = target_date.replace(tzinfo=timezone.utc)

    target_local = target_date.astimezone(target_tz)
    target_day = target_local.date()

    # -------- working hours (LOCAL -> UTC) --------
    def _make_local_dt(hour: int):
        naive = datetime(
            target_day.year,
            target_day.month,
            target_day.day,
            hour, 0, 0
        )
        if hasattr(target_tz, "localize"):  # pytz
            return target_tz.localize(naive)
        return naive.replace(tzinfo=target_tz)

    work_start_utc = _make_local_dt(work_start_hour).astimezone(timezone.utc)
    work_end_utc = _make_local_dt(work_end_hour).astimezone(timezone.utc)

    # -------- parse input events --------
    def _parse_iso_to_utc(dt_str: str) -> datetime:
        if dt_str.endswith("Z"):
            dt = datetime.fromisoformat(dt_str[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    busy_intervals: List[Tuple[datetime, datetime]] = []

    for events in people_events:
        for ev in (events or []):
            try:
                start = _parse_iso_to_utc(ev["start"])
                end = _parse_iso_to_utc(ev["end"])
            except Exception:
                continue

            if end <= start:
                continue

            start = max(start, work_start_utc)
            end = min(end, work_end_utc)

            if end > start:
                busy_intervals.append((start, end))

    # -------- merge busy intervals --------
    if not busy_intervals:
        free_windows = [(work_start_utc, work_end_utc)]
    else:
        busy_intervals.sort(key=lambda x: x[0])
        merged = [busy_intervals[0]]

        for s, e in busy_intervals[1:]:
            last_s, last_e = merged[-1]
            if s <= last_e:
                merged[-1] = (last_s, max(last_e, e))
            else:
                merged.append((s, e))

        free_windows = []
        prev_end = work_start_utc

        for s, e in merged:
            if s > prev_end:
                free_windows.append((prev_end, s))
            prev_end = max(prev_end, e)

        if prev_end < work_end_utc:
            free_windows.append((prev_end, work_end_utc))

    # -------- build slots (UTC → Tehran) --------
    slots: List[Dict[str, str]] = []

    for start_win, end_win in free_windows:
        current = start_win

        # round up to next minute
        if current.second or current.microsecond:
            current = current.replace(second=0, microsecond=0) + timedelta(minutes=1)

        while current + meeting_delta <= end_win:
            start_local = current.astimezone(target_tz)
            end_local = (current + meeting_delta).astimezone(target_tz)

            slots.append({
                "start": start_local.isoformat(),
                "end": end_local.isoformat(),
            })

            current += step_delta

    return slots



def find_available_meeting_slots(db: Session, participants: List[str], meeting_date: datetime, meeting_length: int):

    logger.info(f"Finding available slots for {len(participants)} people on {meeting_date.date()}")
    logger.info(f"Meeting length: {meeting_length} minutes")

    if meeting_date.tzinfo is None:
        meeting_date = meeting_date.replace(tzinfo=timezone.utc)

    time_min = meeting_date.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = meeting_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    people_events: List[List[Dict]] = []

    for email in participants:
        user = get_user_by_email(db, email)
        if not user:
            raise ValueError(f"User with email {email} not found")
        if not user.google_calendar_connected:
            raise ValueError(f"User {email} has not connected Google Calendar")

        access_token = get_valid_access_token(db, user)
        try:
            logger.debug(f"Fetching freebusy for {email}")
            busy_events = get_user_freebusy(access_token=access_token, email=email, time_min=time_min, time_max=time_max)
            logger.debug(f"{email}: {len(busy_events)} busy events")
            people_events.append(busy_events)
        except Exception as e:
            logger.error(f"Failed to fetch calendar data for {email}: {str(e)}")
            raise ValueError(f"Failed to fetch calendar data for {email}: {str(e)}")


    available_slots = compute_common_meeting_slots(
        people_events=people_events,
        duration_minutes=meeting_length,
        target_date=meeting_date,
        work_start_hour=8,
        work_end_hour=21
    )


    result = []
    for slot in available_slots:
        try:
            start_dt = datetime.fromisoformat(slot['start'])
            end_dt = datetime.fromisoformat(slot['end'])
            result.append({'start': start_dt, 'end': end_dt})
        except Exception:
            logger.debug("Skipping malformed slot: %r", slot)


    return result


def create_google_meet_description(meeting_room: str = None):
    description_parts = ["This meeting was automatically scheduled by Meeting Management System."]
    if meeting_room:
        description_parts.append(f"\nMeeting Room: {meeting_room}")
    return "\n".join(description_parts)
