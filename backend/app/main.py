from fastapi import FastAPI
from app.db.session.session import engine, Base

# Import مدل‌ها اینجا (مهم!)
from app.modules.meetings.domain.meeting_model import Meeting
from app.modules.users.domain.user_model import User

app = FastAPI()

# ساخت جدول‌ها
Base.metadata.create_all(bind=engine)
