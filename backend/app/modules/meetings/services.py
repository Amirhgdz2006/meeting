from typing import Any, Dict, List, Optional
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
import logging
from app.core.redis_client import redis_client
from app.core.security import create_access_token
import json
from app.modules.meetings.models import MeetingStatus, MeetingType
from app.modules.meetings.repositories import (
    get_meeting_by_id,
    create_meeting,
    update_meeting,
    update_meeting_status,
    delete_meeting
)
from app.modules.meetings.schemas import (
    MeetingCreateRequestRedis,
    MeetingCreateRequest,
    MeetingResponse,
    MeetingScheduleResponse,
    TimeSlotSchema,
    AvailableTimeSlotsResponse
)
from app.modules.meetings.utils import (
    find_available_meeting_slots,
    get_valid_access_token,
    create_google_meet_description
)
from app.modules.users.repositories import get_user_by_email, get_user_by_id
from app.integrations.google.calendar import create_calendar_event
from datetime import time as dt_time
from app.modules.meetings.algorithm import select_meeting_approvers



def create_new_meeting_redis(db: Session, meeting_request: MeetingCreateRequestRedis, current_user_id: int):

    participants_emails: List[str] = []
    for email in meeting_request.participants:
        user = get_user_by_email(db, email)
        if not user:
            raise ValueError(f"User with email {email} not found")
        participants_emails.append(email)


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

    serializable_slots = [
        {"start": slot["start"].isoformat(), "end": slot["end"].isoformat()}
        for slot in available_slots
    ]

    redis_client.set(
        f"user_id:{current_user_id}",
        json.dumps({
                "meeting_type": meeting_request.meeting_type.value if hasattr(meeting_request.meeting_type, "value") else meeting_request.meeting_type,
                "meeting_location": meeting_request.meeting_location.value if hasattr(meeting_request.meeting_location, "value") else meeting_request.meeting_location,
                "title": meeting_request.title,
                "description": meeting_request.description,
                "participants": participants_emails,
                "meeting_length": meeting_request.meeting_length,
                "meeting_date": str(meeting_request.meeting_date),
                "meeting_room": meeting_request.meeting_room,
                "meeting_available_times": serializable_slots,
                "status": MeetingStatus.PENDING.value,
                "has_permission": True,
                "created_by": current_user_id
            })
    )

    return AvailableTimeSlotsResponse(
        available_slots=time_slots
    )



def schedule_meeting(db: Session, meeting_id: int):
    
    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")

    participants: List[str] = meeting.participants or []
    if not participants:
        raise ValueError("Meeting has no participants")

    if not meeting.meeting_date:
        raise ValueError("Meeting has no meeting_date set")
    
    if not meeting.start_time:
        raise ValueError("Meeting has no start_time set")
    
    if not meeting.end_time:
        raise ValueError("Meeting has no end_time set")

    if not meeting.has_permission:
        raise ValueError("Meeting does not have permission to be scheduled")

    description = meeting.description or ""
    description += "\n\n" + create_google_meet_description(meeting.meeting_room)
    needs_conference = (meeting.meeting_type == MeetingType.ONLINE)


    organizer = get_user_by_id(db, meeting.created_by)
    if not organizer:
        raise ValueError("Organizer not found")

    if not organizer.google_calendar_connected:
        raise ValueError("Organizer calendar not connected")

    if not organizer.google_access_token or not organizer.google_token_expires_at:
        raise ValueError("Organizer has no valid token")

    try:
        access_token = get_valid_access_token(db, organizer)

        created_event = create_calendar_event(
            access_token=access_token,
            summary=meeting.title,
            description=description,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            attendees=participants,
            location=meeting.meeting_room if meeting.meeting_room else None,
            conference_data=needs_conference
        )

        if not created_event or not isinstance(created_event, dict):
            raise ValueError("Invalid event response from Google")

        primary_event_id = created_event.get("id")
        if not primary_event_id:
            raise ValueError("No event ID returned from Google")

    except Exception as e:
        logging.error(f"Failed to create calendar event: {str(e)}")
        raise ValueError(f"Failed to create calendar event: {str(e)}")


    update_data = {
        "google_event_id": primary_event_id,
        "scheduled_at": datetime.now(timezone.utc)
    }

    meeting = update_meeting(db, meeting, update_data)

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

    return MeetingScheduleResponse(
        success=True,
        message="Meeting scheduled successfully",
        meeting=meeting_response,
        google_calendar_link=None
    )


def create_new_meeting(db: Session, meeting_request: MeetingCreateRequest, current_user_id: int):

    participants_data: List[Dict[str, Any]] = []
    participants_emails: List[str] = []
    
    for email in meeting_request.participants:
        user = get_user_by_email(db, email)
        if not user:
            raise ValueError(f"User with email {email} not found")
        participants_emails.append(email)

        participants_data.append({
            "user_email": user.email,
            "org_level": user.org_level,
            "hire_date": user.hire_date.strftime("%Y-%m") if isinstance(user.hire_date, (date, datetime)) else user.hire_date
        })


    approvers = select_meeting_approvers(participants_data)

    current_user = get_user_by_id(db=db, id=current_user_id)

    if approvers == [] or (len(approvers) == 1 and approvers[0]["user_email"] == current_user.email):
        has_permission = True
        meeting_status = MeetingStatus.APPROVED

        meeting_data = {
        "meeting_type": meeting_request.meeting_type,
        "meeting_location": meeting_request.meeting_location,
        "title": meeting_request.title,
        "description": meeting_request.description,
        "participants": participants_emails,
        "meeting_length": meeting_request.meeting_length,
        "meeting_date": meeting_request.meeting_date,
        "meeting_room": meeting_request.meeting_room,
        "start_time": meeting_request.start_time,
        "end_time" : meeting_request.end_time,
        "status": meeting_status,
        "has_permission": has_permission,
        "created_by": current_user_id
        }

        meeting = create_meeting(db, meeting_data)
        result = schedule_meeting(db=db, meeting_id=meeting.id)

        return result



    else:
        has_permission = False
        meeting_status = MeetingStatus.PENDING


        meeting_data = {
            "meeting_type": meeting_request.meeting_type,
            "meeting_location": meeting_request.meeting_location,
            "title": meeting_request.title,
            "description": meeting_request.description,
            "participants": participants_emails,
            "meeting_length": meeting_request.meeting_length,
            "meeting_date": meeting_request.meeting_date,
            "meeting_room": meeting_request.meeting_room,
            "start_time": meeting_request.start_time,
            "end_time" : meeting_request.end_time,
            "status": meeting_status,
            "has_permission": has_permission,
            "created_by": current_user_id
        }

        meeting = create_meeting(db, meeting_data)

        return meeting





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
