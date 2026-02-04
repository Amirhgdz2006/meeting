from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.modules.meetings.models import Meeting, MeetingParticipant, MeetingStatus


def create_meeting(db: Session, meeting_data: dict) -> Meeting:
    """ایجاد یک جلسه جدید"""
    meeting = Meeting(**meeting_data)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def get_meeting_by_id(db: Session, meeting_id: int) -> Optional[Meeting]:
    """دریافت جلسه با ID"""
    return db.query(Meeting).filter(Meeting.id == meeting_id).first()


def update_meeting(db: Session, meeting: Meeting, update_data: dict) -> Meeting:
    """آپدیت کردن اطلاعات جلسه"""
    for key, value in update_data.items():
        setattr(meeting, key, value)
    db.commit()
    db.refresh(meeting)
    return meeting


def update_meeting_status(db: Session, meeting: Meeting, status: MeetingStatus) -> Meeting:
    """آپدیت کردن وضعیت جلسه"""
    meeting.status = status
    if status == MeetingStatus.SCHEDULED:
        meeting.scheduled_at = datetime.utcnow()
    db.commit()
    db.refresh(meeting)
    return meeting


def add_meeting_participant(db: Session, meeting_id: int, user_id: int, email: str) -> MeetingParticipant:
    """اضافه کردن شرکت‌کننده به جلسه"""
    participant = MeetingParticipant(
        meeting_id=meeting_id,
        user_id=user_id,
        email=email
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def get_meeting_participants(db: Session, meeting_id: int) -> List[MeetingParticipant]:
    """دریافت لیست شرکت‌کنندگان جلسه"""
    return db.query(MeetingParticipant).filter(
        MeetingParticipant.meeting_id == meeting_id
    ).all()


def delete_meeting_participants(db: Session, meeting_id: int) -> None:
    """حذف تمام شرکت‌کنندگان یک جلسه"""
    db.query(MeetingParticipant).filter(
        MeetingParticipant.meeting_id == meeting_id
    ).delete()
    db.commit()


def get_user_meetings(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Meeting]:
    """دریافت جلسات یک کاربر"""
    participant_meeting_ids = db.query(MeetingParticipant.meeting_id).filter(
        MeetingParticipant.user_id == user_id
    ).subquery()
    
    return db.query(Meeting).filter(
        Meeting.id.in_(participant_meeting_ids)
    ).offset(skip).limit(limit).all()


def cancel_meeting(db: Session, meeting: Meeting) -> Meeting:
    """کنسل کردن جلسه"""
    meeting.status = MeetingStatus.CANCELLED
    db.commit()
    db.refresh(meeting)
    return meeting