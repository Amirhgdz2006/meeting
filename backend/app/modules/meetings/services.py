from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from app.modules.meetings.models import MeetingStatus, MeetingType
from app.modules.meetings.repositories import (
    create_meeting,
    get_meeting_by_id,
    update_meeting,
    update_meeting_status,
    add_meeting_participant,
    get_meeting_participants
)
from app.modules.meetings.schemas import (
    MeetingCreateRequest,
    MeetingResponse,
    TimeSlotSchema,
    AvailableTimeSlotsResponse,
    MeetingScheduleResponse,
    MeetingParticipantSchema
)
from app.modules.meetings.utils import (
    find_available_meeting_slots,
    check_meeting_permission,
    get_valid_access_token,
    create_google_meet_description
)
from app.modules.users.repositories import get_user_by_email
from app.integrations.google.calendar import create_calendar_event


def create_new_meeting(
    db: Session,
    meeting_request: MeetingCreateRequest,
    current_user_id: int
) -> AvailableTimeSlotsResponse:
    """
    ایجاد جلسه جدید و پیدا کردن تایم‌های خالی
    
    Steps:
    1. ساخت meeting در دیتابیس با status=PENDING
    2. اضافه کردن participants
    3. پیدا کردن تایم‌های خالی مشترک
    4. برگرداندن لیست تایم‌ها
    
    Args:
        db: Database session
        meeting_request: اطلاعات جلسه
        current_user_id: ID کاربر جاری که جلسه رو ایجاد میکنه
    
    Returns:
        AvailableTimeSlotsResponse حاوی meeting_id و لیست تایم‌های خالی
    """
    # ۱. ساخت meeting
    meeting_data = {
        'title': meeting_request.title,
        'description': meeting_request.description,
        'meeting_type': meeting_request.meeting_type,
        'meeting_location': meeting_request.meeting_location,
        'meeting_room': meeting_request.meeting_room,
        'meeting_date': meeting_request.meeting_date,
        'meeting_length': meeting_request.meeting_length,
        'status': MeetingStatus.PENDING,
        'has_permission': True,  # فعلا همیشه True
        'created_by': current_user_id
    }
    
    meeting = create_meeting(db, meeting_data)
    
    # ۲. اضافه کردن participants
    for email in meeting_request.people:
        user = get_user_by_email(db, email)
        if not user:
            raise ValueError(f"User with email {email} not found")
        
        add_meeting_participant(
            db=db,
            meeting_id=meeting.id,
            user_id=user.id,
            email=email
        )
    
    # ۳. پیدا کردن تایم‌های خالی
    from datetime import time as dt_time
    meeting_date_dt = datetime.combine(
        meeting_request.meeting_date,
        dt_time(0, 0, 0)
    )
    # تبدیل به timezone-aware
    if meeting_date_dt.tzinfo is None:
        meeting_date_dt = meeting_date_dt.replace(tzinfo=timezone.utc)
    
    available_slots = find_available_meeting_slots(
        db=db,
        emails=meeting_request.people,
        meeting_date=meeting_date_dt,
        meeting_length=meeting_request.meeting_length
    )
    
    if not available_slots:
        raise ValueError("No available time slots found for this meeting")
    
    # ۴. تبدیل به schema
    time_slots = [
        TimeSlotSchema(start=slot['start'], end=slot['end'])
        for slot in available_slots
    ]
    
    return AvailableTimeSlotsResponse(
        meeting_id=meeting.id,
        available_slots=time_slots,
        selected_slot_index=0  # برای تست اولین slot
    )


def schedule_meeting(
    db: Session,
    meeting_id: int,
    selected_slot_index: int = 0
) -> MeetingScheduleResponse:
    """
    Schedule کردن جلسه با تایم انتخاب شده
    
    Steps:
    1. دریافت meeting از دیتابیس
    2. دوباره پیدا کردن تایم‌های خالی
    3. انتخاب تایم بر اساس index
    4. چک کردن مجوز (فعلا همیشه True)
    5. ست کردن جلسه در Google Calendar همه شرکت‌کنندگان
    6. آپدیت کردن meeting با زمان نهایی و status=SCHEDULED
    
    Args:
        db: Database session
        meeting_id: شناسه جلسه
        selected_slot_index: ایندکس تایم انتخاب شده (پیش‌فرض 0)
    
    Returns:
        MeetingScheduleResponse
    """
    # ۱. دریافت meeting
    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")
    
    if meeting.status == MeetingStatus.SCHEDULED:
        raise ValueError("Meeting is already scheduled")
    
    # ۲. دریافت participants
    participants = get_meeting_participants(db, meeting_id)
    emails = [p.email for p in participants]
    
    # ۳. پیدا کردن تایم‌های خالی دوباره
    from datetime import time as dt_time
    meeting_date_dt = datetime.combine(
        meeting.meeting_date,
        dt_time(0, 0, 0)
    )
    # تبدیل به timezone-aware
    if meeting_date_dt.tzinfo is None:
        meeting_date_dt = meeting_date_dt.replace(tzinfo=timezone.utc)
    
    available_slots = find_available_meeting_slots(
        db=db,
        emails=emails,
        meeting_date=meeting_date_dt,
        meeting_length=meeting.meeting_length
    )
    
    if not available_slots or selected_slot_index >= len(available_slots):
        raise ValueError("Selected time slot is not available")
    
    selected_slot = available_slots[selected_slot_index]
    start_time = selected_slot['start']
    end_time = selected_slot['end']
    
    # ۴. چک کردن مجوز
    has_permission = check_meeting_permission(meeting)
    
    if not has_permission:
        raise ValueError("Meeting does not have permission to be scheduled")
    
    # ۵. ایجاد event در Google Calendar
    # دریافت access token کاربری که جلسه رو ساخته
    creator = get_user_by_email(db, participants[0].email)
    creator_access_token = get_valid_access_token(db, creator)
    
    # ساخت توضیحات
    description = meeting.description or ""
    description += "\n\n" + create_google_meet_description(meeting.meeting_room)
    
    # تعیین اینکه آیا Google Meet link نیاز هست
    needs_conference = (meeting.meeting_type == MeetingType.ONLINE)
    
    # ساخت event
    event = create_calendar_event(
        access_token=creator_access_token,
        summary=meeting.title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        attendees=emails,
        location=meeting.meeting_room if meeting.meeting_room else None,
        conference_data=needs_conference
    )
    
    # ۶. آپدیت کردن meeting
    update_data = {
        'start_time': start_time,
        'end_time': end_time,
        'google_event_id': event['id'],
        'has_permission': has_permission
    }
    
    meeting = update_meeting(db, meeting, update_data)
    meeting = update_meeting_status(db, meeting, MeetingStatus.SCHEDULED)
    
    # ساخت response
    participants_schema = [
        MeetingParticipantSchema(
            id=p.id,
            user_id=p.user_id,
            email=p.email,
            response_status=p.response_status
        )
        for p in participants
    ]
    
    meeting_response = MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        meeting_type=meeting.meeting_type,
        meeting_location=meeting.meeting_location,
        meeting_room=meeting.meeting_room,
        meeting_date=meeting.meeting_date,
        meeting_length=meeting.meeting_length,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        status=meeting.status,
        has_permission=meeting.has_permission,
        google_event_id=meeting.google_event_id,
        created_by=meeting.created_by,
        created_at=meeting.created_at,
        scheduled_at=meeting.scheduled_at,
        participants=participants_schema
    )
    
    google_link = event.get('htmlLink')
    
    return MeetingScheduleResponse(
        success=True,
        message="Meeting scheduled successfully",
        meeting=meeting_response,
        google_calendar_link=google_link
    )


def get_meeting_details(db: Session, meeting_id: int) -> MeetingResponse:
    """
    دریافت جزئیات کامل یک جلسه
    
    Args:
        db: Database session
        meeting_id: شناسه جلسه
    
    Returns:
        MeetingResponse
    """
    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")
    
    participants = get_meeting_participants(db, meeting_id)
    participants_schema = [
        MeetingParticipantSchema(
            id=p.id,
            user_id=p.user_id,
            email=p.email,
            response_status=p.response_status
        )
        for p in participants
    ]
    
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        meeting_type=meeting.meeting_type,
        meeting_location=meeting.meeting_location,
        meeting_room=meeting.meeting_room,
        meeting_date=meeting.meeting_date,
        meeting_length=meeting.meeting_length,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        status=meeting.status,
        has_permission=meeting.has_permission,
        google_event_id=meeting.google_event_id,
        created_by=meeting.created_by,
        created_at=meeting.created_at,
        scheduled_at=meeting.scheduled_at,
        participants=participants_schema
    )