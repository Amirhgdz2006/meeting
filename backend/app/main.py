from fastapi import FastAPI
from app.db.session.session import engine, Base


from app.modules.meetings.domain.meeting_model import Meeting
from app.modules.users.domain.user_model import User

app = FastAPI()


