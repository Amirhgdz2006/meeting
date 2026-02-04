from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from app.core.config.settings import settings


def build_calendar_service(access_token: str):
    """ساخت سرویس Google Calendar با access token"""
    credentials = Credentials(token=access_token)
    service = build('calendar', 'v3', credentials=credentials)
    return service


def get_user_freebusy(
    access_token: str, 
    email: str, 
    time_min: datetime, 
    time_max: datetime
) -> Dict:
    """
    دریافت اطلاعات freebusy یک کاربر در بازه زمانی مشخص
    
    Args:
        access_token: Google access token
        email: ایمیل کاربر
        time_min: شروع بازه زمانی
        time_max: پایان بازه زمانی
    
    Returns:
        Dict حاوی busy times
    """
    service = build_calendar_service(access_token)
    
    body = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "items": [{"id": email}],
        "timeZone": settings.TIMEZONE
    }
    
    freebusy_result = service.freebusy().query(body=body).execute()
    return freebusy_result.get('calendars', {}).get(email, {})


def find_common_free_slots(
    users_busy_times: List[Dict],
    meeting_date: datetime,
    meeting_length: int,
    working_hours_start: int = 8,
    working_hours_end: int = 21
) -> List[Dict[str, datetime]]:
    """
    پیدا کردن تایم‌های خالی مشترک بین همه شرکت‌کنندگان
    
    Args:
        users_busy_times: لیست busy times همه کاربران
        meeting_date: تاریخ جلسه
        meeting_length: طول جلسه به دقیقه
        working_hours_start: ساعت شروع کاری (پیش‌فرض ۸ صبح)
        working_hours_end: ساعت پایان کاری (پیش‌فرض ۹ شب)
    
    Returns:
        لیستی از time slots خالی
    """
    # تعریف بازه زمانی کاری روز
    # اگر meeting_date timezone-aware نیست، اضافه کن
    if meeting_date.tzinfo is None:
        meeting_date = meeting_date.replace(tzinfo=timezone.utc)
    
    day_start = meeting_date.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
    day_end = meeting_date.replace(hour=working_hours_end, minute=0, second=0, microsecond=0)
    
    # جمع‌آوری تمام busy times
    all_busy_periods = []
    for user_busy in users_busy_times:
        busy_list = user_busy.get('busy', [])
        for busy in busy_list:
            start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
            all_busy_periods.append({'start': start, 'end': end})
    
    # مرتب کردن busy periods بر اساس زمان شروع
    all_busy_periods.sort(key=lambda x: x['start'])
    
    # ادغام busy periods همپوشانی‌دار
    merged_busy = []
    for busy in all_busy_periods:
        if not merged_busy or merged_busy[-1]['end'] < busy['start']:
            merged_busy.append(busy)
        else:
            merged_busy[-1]['end'] = max(merged_busy[-1]['end'], busy['end'])
    
    # پیدا کردن free slots
    free_slots = []
    current_time = day_start
    
    for busy in merged_busy:
        if busy['start'] > current_time:
            # یک free slot پیدا کردیم
            slot_duration = (busy['start'] - current_time).total_seconds() / 60
            if slot_duration >= meeting_length:
                free_slots.append({
                    'start': current_time,
                    'end': busy['start']
                })
        current_time = max(current_time, busy['end'])
    
    # چک کردن آخرین بازه
    if current_time < day_end:
        slot_duration = (day_end - current_time).total_seconds() / 60
        if slot_duration >= meeting_length:
            free_slots.append({
                'start': current_time,
                'end': day_end
            })
    
    # تقسیم free slots به بازه‌های با طول meeting_length
    available_slots = []
    for slot in free_slots:
        current = slot['start']
        while current + timedelta(minutes=meeting_length) <= slot['end']:
            available_slots.append({
                'start': current,
                'end': current + timedelta(minutes=meeting_length)
            })
            current += timedelta(minutes=15)  # هر ۱۵ دقیقه یک slot پیشنهادی
    
    return available_slots


def create_calendar_event(
    access_token: str,
    summary: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    attendees: List[str],
    location: Optional[str] = None,
    conference_data: bool = False
) -> Dict:
    """
    ایجاد یک event در Google Calendar
    
    Args:
        access_token: Google access token
        summary: عنوان جلسه
        description: توضیحات جلسه
        start_time: زمان شروع
        end_time: زمان پایان
        attendees: لیست ایمیل شرکت‌کنندگان
        location: محل جلسه (اختیاری)
        conference_data: آیا Google Meet link اضافه بشه؟
    
    Returns:
        Dict حاوی اطلاعات event ساخته شده
    """
    service = build_calendar_service(access_token)
    
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': settings.TIMEZONE,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': settings.TIMEZONE,
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
                'requestId': f"meet-{datetime.now().timestamp()}",
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


def update_calendar_event(
    access_token: str,
    event_id: str,
    updates: Dict
) -> Dict:
    """
    آپدیت کردن یک event موجود
    
    Args:
        access_token: Google access token
        event_id: شناسه event
        updates: تغییرات مورد نظر
    
    Returns:
        Dict حاوی اطلاعات event آپدیت شده
    """
    service = build_calendar_service(access_token)
    
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    event.update(updates)
    
    updated_event = service.events().update(
        calendarId='primary',
        eventId=event_id,
        body=event,
        sendUpdates='all'
    ).execute()
    
    return updated_event


def delete_calendar_event(access_token: str, event_id: str) -> None:
    """
    حذف یک event از کلندر
    
    Args:
        access_token: Google access token
        event_id: شناسه event
    """
    service = build_calendar_service(access_token)
    service.events().delete(
        calendarId='primary',
        eventId=event_id,
        sendUpdates='all'
    ).execute()