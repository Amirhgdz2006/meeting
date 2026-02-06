from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime, date
from app.modules.meetings.models import (
    MeetingType,
    MeetingLocation,
    MeetingStatus,
)


class MeetingCreateRequest(BaseModel):
    meeting_type: MeetingType
    meeting_location: MeetingLocation
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    participants: List[str] = Field(..., min_length=2)
    meeting_length: int = Field(..., gt=0)
    meeting_date: date
    meeting_room: Optional[str] = None

    @model_validator(mode="after")
    def validate_meeting_room(self):

        if (
            self.meeting_type == MeetingType.IN_PERSON
            and self.meeting_location == MeetingLocation.INTERNAL
        ):
            if not self.meeting_room:
                raise ValueError(
                    "meeting_room is required for in-person internal meetings"
                )
        else:
            if self.meeting_room:
                raise ValueError(
                    "meeting_room should be null for online or external meetings"
                )

        return self

    model_config = {
        "use_enum_values": True
    }

class MeetingResponse(BaseModel):
    id: int
    meeting_type: MeetingType
    meeting_location: MeetingLocation
    title: str
    description: Optional[str]
    participants: List[str]
    meeting_length: int
    meeting_date: date
    meeting_room: Optional[str]
    status: MeetingStatus
    has_permission: bool
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    google_event_id: Optional[str]
    created_by: int
    created_at: datetime
    scheduled_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
        "use_enum_values": True
    }


class MeetingScheduleResponse(BaseModel):
    success: bool
    message: str
    meeting: MeetingResponse
    google_calendar_link: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class TimeSlotSchema(BaseModel):
    start: datetime
    end: datetime

    model_config = {
        "from_attributes": True
    }


class AvailableTimeSlotsResponse(BaseModel):
    meeting_id: int
    available_slots: List[TimeSlotSchema]
    selected_slot_index: int = 0

    model_config = {
        "from_attributes": True
    }
