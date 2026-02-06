from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum as SQLEnum, Date, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
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
    CANCELLED = "cancelled"


class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)

    meeting_type = Column(SQLEnum(MeetingType), nullable=False)
    meeting_location = Column(SQLEnum(MeetingLocation), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    participants = Column(JSON, nullable=False, default=list)

    meeting_length = Column(Integer, nullable=False)

    meeting_date = Column(Date, nullable=True)

    meeting_room = Column(String, nullable=True)

    status = Column(SQLEnum(MeetingStatus), default=MeetingStatus.PENDING)
    has_permission = Column(Boolean, default=True)

    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    

    google_event_id = Column(String, nullable=True)
    
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    scheduled_at = Column(DateTime, nullable=True)

