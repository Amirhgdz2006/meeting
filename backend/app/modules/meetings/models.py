from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.session.session import Base


class MeetingType(str, enum.Enum):
    ONLINE = "online"
    IN_PERSON = "in_person"


class MeetingLocation(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class MeetingStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class Meeting(Base):
    __tablename__ = "meetings"
    
    # Primary info
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Meeting type and location
    meeting_type = Column(SQLEnum(MeetingType), nullable=False)
    meeting_location = Column(SQLEnum(MeetingLocation), nullable=False)
    meeting_room = Column(String, nullable=True)  # فقط برای حضوری و داخلی
    
    # Timing
    meeting_date = Column(Date, nullable=False)
    meeting_length = Column(Integer, nullable=False)  # به دقیقه
    start_time = Column(DateTime, nullable=True)  # زمان نهایی که انتخاب شده
    end_time = Column(DateTime, nullable=True)
    
    # Status and permission
    status = Column(SQLEnum(MeetingStatus), default=MeetingStatus.PENDING)
    has_permission = Column(Boolean, default=True)  # فعلا همیشه True
    
    # Google Calendar
    google_event_id = Column(String, nullable=True)  # برای sync با گوگل کلندر
    
    # Metadata
    created_by = Column(Integer, nullable=False)  # user_id که جلسه رو ساخته
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scheduled_at = Column(DateTime, nullable=True)  # زمانی که جلسه schedule شده


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    email = Column(String, nullable=False)  # برای راحتی کار با گوگل کلندر
    
    # Response status
    response_status = Column(String, default="needsAction")  # needsAction, accepted, declined, tentative
    
    created_at = Column(DateTime, default=datetime.utcnow)