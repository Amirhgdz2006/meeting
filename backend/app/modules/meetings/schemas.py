from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime, date, time
from app.modules.meetings.models import MeetingType, MeetingLocation, MeetingStatus


class MeetingCreateRequest(BaseModel):
    meeting_type: MeetingType
    meeting_location: MeetingLocation
    title: str = Field(..., min_length=1, max_length=255)
    people: List[str] = Field(..., min_items=1)  # لیست ایمیل‌های شرکت‌کنندگان
    meeting_length: int = Field(..., gt=0, description="مدت زمان جلسه به دقیقه")
    meeting_date: date
    meeting_room: Optional[str] = None
    description: Optional[str] = None
    
    @validator('meeting_room')
    def validate_meeting_room(cls, v, values):
        """
        اگر جلسه حضوری و داخلی باشه، meeting_room الزامیه
        """
        meeting_type = values.get('meeting_type')
        meeting_location = values.get('meeting_location')
        
        if meeting_type == MeetingType.IN_PERSON and meeting_location == MeetingLocation.INTERNAL:
            if not v:
                raise ValueError('meeting_room is required for in-person internal meetings')
        else:
            # برای بقیه حالت‌ها meeting_room باید null باشه
            if v:
                raise ValueError('meeting_room should be null for online or external meetings')
        
        return v
    
    class Config:
        use_enum_values = True


class TimeSlotSchema(BaseModel):
    start: datetime
    end: datetime
    
    class Config:
        from_attributes = True


class AvailableTimeSlotsResponse(BaseModel):
    meeting_id: int
    available_slots: List[TimeSlotSchema]
    selected_slot_index: int = 0  # برای تست، اولین slot انتخاب میشه
    
    class Config:
        from_attributes = True


class MeetingParticipantSchema(BaseModel):
    id: int
    user_id: int
    email: str
    response_status: str
    
    class Config:
        from_attributes = True


class MeetingResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    meeting_type: MeetingType
    meeting_location: MeetingLocation
    meeting_room: Optional[str]
    meeting_date: date
    meeting_length: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: MeetingStatus
    has_permission: bool
    google_event_id: Optional[str]
    created_by: int
    created_at: datetime
    scheduled_at: Optional[datetime]
    participants: List[MeetingParticipantSchema] = []
    
    class Config:
        from_attributes = True
        use_enum_values = True


class MeetingScheduleResponse(BaseModel):
    success: bool
    message: str
    meeting: MeetingResponse
    google_calendar_link: Optional[str] = None
    
    class Config:
        from_attributes = True