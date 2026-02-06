from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from app.modules.meetings.models import Meeting, MeetingStatus


def get_meeting_by_id(db: Session, meeting_id: int):
    return db.query(Meeting).filter(Meeting.id == meeting_id).first()


def create_meeting(db: Session, meeting_data: dict):
    meeting = Meeting(**meeting_data)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def update_meeting(db: Session, meeting: Meeting, update_data: dict):
    for key, value in update_data.items():
        setattr(meeting, key, value)
    db.commit()
    db.refresh(meeting)
    return meeting


def update_meeting_status(db: Session, meeting: Meeting, status: MeetingStatus):
    meeting.status = status
    db.commit()
    db.refresh(meeting)
    return meeting


def delete_meeting(db: Session, meeting_id: int):
    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        return False

    db.delete(meeting)
    db.commit()
    return True
