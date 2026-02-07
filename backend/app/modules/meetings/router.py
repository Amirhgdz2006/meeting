from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from app.core.security.jwt import verify_token
from typing import List
from app.core.redis_client import redis_client
from app.core.config.settings import settings
from app.db.session.session import get_db
from app.modules.meetings.schemas import (
    MeetingCreateRequestRedis,
    MeetingCreateRequest,
    AvailableTimeSlotsResponse,
    MeetingScheduleResponse,
    MeetingResponse
)
from app.modules.meetings.services import (
    create_new_meeting_redis,
    create_new_meeting,
    schedule_meeting,
    get_meeting_details
)
import json

router = APIRouter(prefix="/meetings", tags=["Meetings"])

@router.post("/available-times", response_model=AvailableTimeSlotsResponse, status_code=status.HTTP_201_CREATED)
async def available_meeting_times(request:Request, meeting_request: MeetingCreateRequestRedis, db: Session = Depends(get_db)):

    try:

        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        payload = verify_token(token)

        if payload is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid token payload")

        result = create_new_meeting_redis(db=db, meeting_request=meeting_request, current_user_id=user_id)

        return result

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to find available times for meating: {str(e)}")





@router.get("/create/{selected_slot_index}", response_model=MeetingScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting_endpoint(selected_slot_index: int, request:Request, db: Session = Depends(get_db)):

    try:

        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        payload = verify_token(token)

        if payload is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid token payload")

        redis_raw = redis_client.get(f"user_id:{user_id}")
        if not redis_raw:
            raise ValueError("No draft meeting found in Redis")

        if isinstance(redis_raw, str):
            redis_data = json.loads(redis_raw)
        else:
            redis_data = redis_raw

        
        result = create_new_meeting(
            db=db,
            meeting_request=MeetingCreateRequest(
                    meeting_type = redis_data["meeting_type"],
                    meeting_location=redis_data["meeting_location"],
                    title=redis_data["title"],
                    description=redis_data.get("description"),
                    participants=redis_data["participants"],
                    meeting_length=redis_data["meeting_length"],
                    meeting_date=redis_data["meeting_date"],
                    start_time=redis_data["meeting_available_times"][selected_slot_index]["start"],
                    end_time=redis_data["meeting_available_times"][selected_slot_index]["end"],
                    meeting_room=redis_data["meeting_room"]
                    ),
                    current_user_id=user_id
        )
        
        redis_client.delete(f"user_id:{user_id}")
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


# @router.post("/{meeting_id}/schedule", response_model=MeetingScheduleResponse)
# async def schedule_meeting_endpoint(
#     meeting_id: int,
#     selected_slot_index: int = 0,
#     db: Session = Depends(get_db)
# ):

#     try:
#         result = schedule_meeting(
#             db=db,
#             meeting_id=meeting_id,
#             selected_slot_index=selected_slot_index
#         )
        
#         return result
        
#     except ValueError as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(e)
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to schedule meeting: {str(e)}"
#         )





@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting_endpoint(meeting_id: int, db: Session = Depends(get_db)):

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


