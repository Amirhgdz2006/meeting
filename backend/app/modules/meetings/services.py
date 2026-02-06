from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import logging

from app.modules.meetings.models import MeetingStatus, MeetingType
from app.modules.meetings.repositories import (
    get_meeting_by_id,
    create_meeting,
    update_meeting,
    update_meeting_status,
    delete_meeting
)
from app.modules.meetings.schemas import (
    MeetingCreateRequest,
    MeetingResponse,
    MeetingScheduleResponse,
    TimeSlotSchema,
    AvailableTimeSlotsResponse
)
from app.modules.meetings.utils import (
    find_available_meeting_slots,
    check_meeting_permission,
    get_valid_access_token,
    create_google_meet_description
)
from app.modules.users.repositories import get_user_by_email
from app.integrations.google.calendar import create_calendar_event
from datetime import time as dt_time

logger = logging.getLogger(__name__)


def create_new_meeting(db: Session, meeting_request: MeetingCreateRequest, current_user_id: int):

    participants_emails: List[str] = []
    for email in meeting_request.participants:
        user = get_user_by_email(db, email)
        if not user:
            raise ValueError(f"User with email {email} not found")
        participants_emails.append(email)

    meeting_data = {
        "meeting_type": meeting_request.meeting_type,
        "meeting_location": meeting_request.meeting_location,
        "title": meeting_request.title,
        "description": meeting_request.description,
        "participants": participants_emails,
        "meeting_length": meeting_request.meeting_length,
        "meeting_date": meeting_request.meeting_date,
        "meeting_room": meeting_request.meeting_room,
        "status": MeetingStatus,
        "has_permission": True,
        "created_by": current_user_id
    }

    meeting = create_meeting(db, meeting_data)


    meeting_date_dt = datetime.combine(
        meeting_request.meeting_date,
        dt_time(8, 0, 0)
    ).replace(tzinfo=timezone.utc)


    available_slots = find_available_meeting_slots(
        db=db,
        participants=participants_emails,
        meeting_date=meeting_date_dt,
        meeting_length=meeting_request.meeting_length
    )

    if not available_slots:
        raise ValueError("No available time slots found for this meeting")


    time_slots = [
        TimeSlotSchema(start=slot["start"], end=slot["end"])
        for slot in available_slots
    ]

    return AvailableTimeSlotsResponse(
        meeting_id=meeting.id,
        available_slots=time_slots,
        selected_slot_index=0
    )


def schedule_meeting(db: Session, meeting_id: int, selected_slot_index: int = 0):

    logger.info(f"Scheduling meeting {meeting_id}")

    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")


    if meeting.status == MeetingStatus.APPROVED:
        raise ValueError("Meeting is already scheduled")


    participants: List[str] = meeting.participants or []
    if not participants:
        raise ValueError("Meeting has no participants")

    logger.info("Meeting participants: %s", participants)


    if not meeting.meeting_date:
        raise ValueError("Meeting has no meeting_date set")

    meeting_date_dt = datetime.combine(
        meeting.meeting_date,
        dt_time(8, 0, 0)
    ).replace(tzinfo=timezone.utc)

    available_slots = find_available_meeting_slots(
        db=db,
        participants=participants,
        meeting_date=meeting_date_dt,
        meeting_length=meeting.meeting_length
    )

    if not available_slots or selected_slot_index >= len(available_slots):
        raise ValueError("Selected time slot is not available")

    selected_slot = available_slots[selected_slot_index]
    start_time = selected_slot["start"]
    end_time = selected_slot["end"]

    logger.info("Selected slot %d: %s - %s", selected_slot_index, start_time.isoformat(), end_time.isoformat())


    has_permission = check_meeting_permission(meeting)
    if not has_permission:
        raise ValueError("Meeting does not have permission to be scheduled")


    creator_user = None
    for email in participants:
        user = get_user_by_email(db, email)
        if user and getattr(user, "google_calendar_connected", False):
            creator_user = user
            break

    if not creator_user:
        raise ValueError("No participant with a connected Google Calendar was found to create the event")


    creator_access_token = get_valid_access_token(db, creator_user)


    description = meeting.description or ""
    description += "\n\n" + create_google_meet_description(meeting.meeting_room)
    needs_conference = (meeting.meeting_type == MeetingType.ONLINE)


    event = create_calendar_event(
        access_token=creator_access_token,
        summary=meeting.title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        attendees=participants,
        location=meeting.meeting_room if meeting.meeting_room else None,
        conference_data=needs_conference
    )

    event_id = event.get("id")
    google_link = event.get("htmlLink")

    logger.info("Calendar event created with id=%s", event_id)


    update_data = {
        "start_time": start_time,
        "end_time": end_time,
        "google_event_id": event_id,
        "has_permission": has_permission,
        "scheduled_at": datetime.now(timezone.utc)
    }

    meeting = update_meeting(db, meeting, update_data)
    meeting = update_meeting_status(db, meeting, MeetingStatus.APPROVED)


    meeting_response = MeetingResponse(
        id=meeting.id,
        meeting_type=meeting.meeting_type,
        meeting_location=meeting.meeting_location,
        title=meeting.title,
        description=meeting.description,
        participants=meeting.participants or [],
        meeting_length=meeting.meeting_length,
        meeting_date=meeting.meeting_date,
        meeting_room=meeting.meeting_room,
        status=meeting.status,
        has_permission=meeting.has_permission,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        google_event_id=meeting.google_event_id,
        created_by=meeting.created_by,
        created_at=meeting.created_at,
        scheduled_at=meeting.scheduled_at
    )

    logger.info("Meeting %s scheduled successfully", meeting_id)

    return MeetingScheduleResponse(
        success=True,
        message="Meeting scheduled successfully",
        meeting=meeting_response,
        google_calendar_link=google_link
    )


def get_meeting_details(db: Session, meeting_id: int):

    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")

    participants = meeting.participants or []

    return MeetingResponse(
        id=meeting.id,
        meeting_type=meeting.meeting_type,
        meeting_location=meeting.meeting_location,
        title=meeting.title,
        description=meeting.description,
        participants=participants,
        meeting_length=meeting.meeting_length,
        meeting_date=meeting.meeting_date,
        meeting_room=meeting.meeting_room,
        status=meeting.status,
        has_permission=meeting.has_permission,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        google_event_id=meeting.google_event_id,
        created_by=meeting.created_by,
        created_at=meeting.created_at,
        scheduled_at=meeting.scheduled_at
    )
