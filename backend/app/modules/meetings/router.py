from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.session.session import get_db
from app.modules.meetings.schemas import (
    MeetingCreateRequest,
    AvailableTimeSlotsResponse,
    MeetingScheduleResponse,
    MeetingResponse
)
from app.modules.meetings.services import (
    create_new_meeting,
    schedule_meeting,
    get_meeting_details
)

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post("/create", response_model=AvailableTimeSlotsResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting_endpoint(
    meeting_request: MeetingCreateRequest,
    db: Session = Depends(get_db)
):
    """
    ایجاد جلسه جدید و دریافت تایم‌های خالی پیشنهادی
    
    این endpoint:
    1. جلسه رو در دیتابیس میسازه
    2. شرکت‌کنندگان رو اضافه میکنه
    3. تایم‌های خالی مشترک رو پیدا میکنه
    4. لیست تایم‌های پیشنهادی رو برمیگردونه
    
    Body:
    ```json
    {
        "meeting_type": "online" | "in_person",
        "meeting_location": "internal" | "external",
        "title": "نام جلسه",
        "people": ["email1@example.com", "email2@example.com"],
        "meeting_length": 60,
        "meeting_date": "2026-02-10",
        "meeting_room": "Room A",
        "description": "توضیحات جلسه"
    }
    ```
    """
    try:
        # فعلا current_user_id رو hardcode میکنیم
        # بعدا از JWT token استخراج میشه
        current_user_id = 1
        
        result = create_new_meeting(
            db=db,
            meeting_request=meeting_request,
            current_user_id=current_user_id
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create meeting: {str(e)}"
        )


@router.post("/{meeting_id}/schedule", response_model=MeetingScheduleResponse)
async def schedule_meeting_endpoint(
    meeting_id: int,
    selected_slot_index: int = 0,
    db: Session = Depends(get_db)
):
    """
    Schedule کردن جلسه با تایم انتخاب شده
    
    این endpoint:
    1. تایم انتخاب شده رو از لیست تایم‌های خالی میگیره
    2. مجوز جلسه رو چک میکنه (فعلا همیشه True)
    3. جلسه رو در Google Calendar همه شرکت‌کنندگان ست میکنه
    4. وضعیت جلسه رو به SCHEDULED تغییر میده
    
    Parameters:
    - meeting_id: شناسه جلسه
    - selected_slot_index: ایندکس تایم انتخاب شده (پیش‌فرض 0 برای تست)
    """
    try:
        result = schedule_meeting(
            db=db,
            meeting_id=meeting_id,
            selected_slot_index=selected_slot_index
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule meeting: {str(e)}"
        )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting_endpoint(
    meeting_id: int,
    db: Session = Depends(get_db)
):
    """
    دریافت جزئیات کامل یک جلسه
    
    Parameters:
    - meeting_id: شناسه جلسه
    """
    try:
        meeting = get_meeting_details(db=db, meeting_id=meeting_id)
        return meeting
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get meeting: {str(e)}"
        )


@router.post("/quick-schedule", response_model=MeetingScheduleResponse, status_code=status.HTTP_201_CREATED)
async def quick_schedule_meeting(
    meeting_request: MeetingCreateRequest,
    db: Session = Depends(get_db)
):
    """
    ایجاد و Schedule کردن جلسه در یک درخواست (برای تست راحت‌تر)
    
    این endpoint هم جلسه رو میسازه و هم مستقیما اولین تایم خالی رو Schedule میکنه
    """
    try:
        # فعلا current_user_id رو hardcode میکنیم
        current_user_id = 1
        
        # ۱. ایجاد جلسه و پیدا کردن تایم‌ها
        available_slots_response = create_new_meeting(
            db=db,
            meeting_request=meeting_request,
            current_user_id=current_user_id
        )
        
        # ۲. مستقیما اولین تایم رو Schedule میکنیم
        result = schedule_meeting(
            db=db,
            meeting_id=available_slots_response.meeting_id,
            selected_slot_index=0  # اولین تایم
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to quick schedule meeting: {str(e)}"
        )