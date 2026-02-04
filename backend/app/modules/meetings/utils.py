from typing import List, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.modules.users.repositories import get_user_by_email
from app.integrations.google.calendar import get_user_freebusy, find_common_free_slots
from app.integrations.google.oauth import refresh_google_access_token, is_google_token_expired


def get_valid_access_token(db: Session, user) -> str:
    """
    دریافت access token معتبر (در صورت نیاز refresh میکنه)
    
    Args:
        db: Database session
        user: User object
    
    Returns:
        str: Valid access token
    """
    if is_google_token_expired(user.google_token_expires_at):
        # Refresh token
        result = refresh_google_access_token(user.google_refresh_token)
        
        # آپدیت کردن token جدید در دیتابیس
        from app.modules.users.repositories import update_user_google_tokens
        update_user_google_tokens(
            db=db,
            user=user,
            access_token=result['access_token'],
            expires_at=result['expiry']
        )
        return result['access_token']
    
    return user.google_access_token


def fetch_users_busy_times(
    db: Session,
    emails: List[str],
    meeting_date: datetime
) -> tuple[List[Dict], List[object]]:
    """
    دریافت busy times همه کاربران در تاریخ مشخص
    
    Args:
        db: Database session
        emails: لیست ایمیل شرکت‌کنندگان
        meeting_date: تاریخ جلسه
    
    Returns:
        tuple: (لیست busy times, لیست user objects)
    """
    users_busy_times = []
    users = []
    
    # تعریف بازه زمانی روز
    from datetime import time as dt_time
    time_min = datetime.combine(meeting_date.date(), dt_time(0, 0, 0))
    time_max = datetime.combine(meeting_date.date(), dt_time(23, 59, 59))
    
    # تبدیل به timezone-aware
    if time_min.tzinfo is None:
        time_min = time_min.replace(tzinfo=timezone.utc)
    if time_max.tzinfo is None:
        time_max = time_max.replace(tzinfo=timezone.utc)
    
    for email in emails:
        user = get_user_by_email(db, email)
        
        if not user:
            raise ValueError(f"User with email {email} not found")
        
        if not user.google_calendar_connected:
            raise ValueError(f"User {email} has not connected Google Calendar")
        
        # دریافت valid access token
        access_token = get_valid_access_token(db, user)
        
        # دریافت freebusy
        busy_times = get_user_freebusy(
            access_token=access_token,
            email=email,
            time_min=time_min,
            time_max=time_max
        )
        
        users_busy_times.append(busy_times)
        users.append(user)
    
    return users_busy_times, users


def find_available_meeting_slots(
    db: Session,
    emails: List[str],
    meeting_date: datetime,
    meeting_length: int
) -> List[Dict[str, datetime]]:
    """
    پیدا کردن تایم‌های خالی مشترک برای جلسه
    
    Args:
        db: Database session
        emails: لیست ایمیل شرکت‌کنندگان
        meeting_date: تاریخ جلسه
        meeting_length: طول جلسه به دقیقه
    
    Returns:
        لیست time slots خالی
    """
    users_busy_times, _ = fetch_users_busy_times(db, emails, meeting_date)
    
    available_slots = find_common_free_slots(
        users_busy_times=users_busy_times,
        meeting_date=meeting_date,
        meeting_length=meeting_length
    )
    
    return available_slots


def check_meeting_permission(meeting) -> bool:
    """
    چک کردن اینکه آیا جلسه مجوز ست شدن داره یا نه
    
    این تابع در آینده براساس الگوریتم شما پیاده‌سازی میشه
    فعلا همیشه True برمی‌گردونه
    
    Args:
        meeting: Meeting object
    
    Returns:
        bool: True اگر مجوز داشته باشه
    """
    # TODO: پیاده‌سازی الگوریتم چک کردن مجوز
    return True


def create_google_meet_description(meeting_room: str = None) -> str:
    """
    ساخت توضیحات برای Google Calendar event
    
    Args:
        meeting_room: نام اتاق جلسه (اختیاری)
    
    Returns:
        str: توضیحات فرمت شده
    """
    description_parts = ["This meeting was automatically scheduled by Meeting Management System."]
    
    if meeting_room:
        description_parts.append(f"\nMeeting Room: {meeting_room}")
    
    return "\n".join(description_parts)