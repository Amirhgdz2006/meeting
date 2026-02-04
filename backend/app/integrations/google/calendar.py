from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from app.core.config.settings import settings
import pytz


def build_calendar_service(access_token: str):
    """ساخت سرویس Google Calendar با access token"""
    credentials = Credentials(token=access_token)
    service = build('calendar', 'v3', credentials=credentials)
    return service


def parse_datetime_string(dt_str: str) -> datetime:
    """
    Parse کردن string تاریخ به datetime با timezone awareness
    
    Args:
        dt_str: رشته تاریخ (مثلا "2024-02-04T09:00:00Z" یا "2024-02-04T09:00:00+00:00")
    
    Returns:
        datetime object با timezone UTC
    """
    # حذف Z و تبدیل به +00:00
    if dt_str.endswith('Z'):
        dt_str = dt_str.replace('Z', '+00:00')
    
    # Parse کردن
    dt = datetime.fromisoformat(dt_str)
    
    # اطمینان از timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # تبدیل به UTC
        dt = dt.astimezone(timezone.utc)
    
    return dt


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
    
    # اطمینان از timezone awareness
    if time_min.tzinfo is None:
        time_min = time_min.replace(tzinfo=timezone.utc)
    if time_max.tzinfo is None:
        time_max = time_max.replace(tzinfo=timezone.utc)
    
    body = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "items": [{"id": email}],
        "timeZone": "UTC"
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
    # اطمینان از timezone awareness
    if meeting_date.tzinfo is None:
        meeting_date = meeting_date.replace(tzinfo=timezone.utc)
    
    # تعریف بازه زمانی کاری روز - استفاده از تاریخ meeting_date
    day_start = meeting_date.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
    day_end = meeting_date.replace(hour=working_hours_end, minute=0, second=0, microsecond=0)
    
    # جمع‌آوری و normalize کردن تمام busy times
    all_busy_periods = []
    for user_busy in users_busy_times:
        busy_list = user_busy.get('busy', [])
        for busy in busy_list:
            try:
                start = parse_datetime_string(busy['start'])
                end = parse_datetime_string(busy['end'])
                
                # فقط busy periods داخل روز کاری رو در نظر بگیریم
                # اگه busy period قبل از شروع روز کاری شروع شده، از شروع روز کاری حسابش کن
                if start < day_start and end > day_start:
                    start = day_start
                
                # اگه busy period بعد از پایان روز کاری تموم میشه، تا پایان روز کاری حسابش کن
                if start < day_end and end > day_end:
                    end = day_end
                
                # فقط اگه busy period داخل بازه کاری بود اضافه کن
                if start < day_end and end > day_start:
                    all_busy_periods.append({'start': start, 'end': end})
                    
            except (KeyError, ValueError) as e:
                # اگه فرمت تاریخ اشتباه بود، skip کن
                continue
    
    # مرتب کردن busy periods بر اساس زمان شروع
    all_busy_periods.sort(key=lambda x: x['start'])
    
    # ادغام busy periods همپوشانی‌دار یا نزدیک به هم (با margin 5 دقیقه)
    merged_busy = []
    margin = timedelta(minutes=5)
    
    for busy in all_busy_periods:
        if not merged_busy:
            merged_busy.append(busy)
        else:
            last_busy = merged_busy[-1]
            # اگه busy جدید با آخری overlap داره یا خیلی نزدیکه، ادغامشون کن
            if busy['start'] <= last_busy['end'] + margin:
                merged_busy[-1]['end'] = max(last_busy['end'], busy['end'])
            else:
                merged_busy.append(busy)
    
    # پیدا کردن free slots
    free_slots = []
    current_time = day_start
    
    for busy in merged_busy:
        if busy['start'] > current_time:
            # یک free slot پیدا کردیم
            slot_duration_minutes = (busy['start'] - current_time).total_seconds() / 60
            
            # فقط اگه طول slot از meeting_length بیشتر یا مساوی بود
            if slot_duration_minutes >= meeting_length:
                free_slots.append({
                    'start': current_time,
                    'end': busy['start']
                })
        
        current_time = max(current_time, busy['end'])
    
    # چک کردن آخرین بازه (از آخرین busy تا پایان روز کاری)
    if current_time < day_end:
        slot_duration_minutes = (day_end - current_time).total_seconds() / 60
        if slot_duration_minutes >= meeting_length:
            free_slots.append({
                'start': current_time,
                'end': day_end
            })
    
    # تقسیم free slots به بازه‌های با طول meeting_length
    # با interval 15 دقیقه‌ای
    available_slots = []
    interval_minutes = 15
    
    for slot in free_slots:
        current = slot['start']
        slot_end = slot['end']
        
        # تا وقتی که میشه یک meeting با طول meeting_length در این slot جا بدیم
        while current + timedelta(minutes=meeting_length) <= slot_end:
            available_slots.append({
                'start': current,
                'end': current + timedelta(minutes=meeting_length)
            })
            current += timedelta(minutes=interval_minutes)
    
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
    
    # اطمینان از timezone awareness
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
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