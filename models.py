# models.py
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Enum, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker
import enum
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_URL")
engine = create_engine(DB_PATH, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)
Base = declarative_base()

class StatusEnum(str, enum.Enum):
    scheduled = "scheduled"
    processing = "processing"
    uploaded = "uploaded"
    failed = "failed"

class ScheduledItem(Base):
    __tablename__ = "scheduled_items"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    media_type = Column(String, nullable=False)  # image or video
    post_type = Column(String, nullable=False)   # post or reel
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(Enum(StatusEnum), default=StatusEnum.scheduled)
    caption = Column(Text, default="")
    log = Column(Text, default="")  # store upload logs/errors

def init_db():
    Base.metadata.create_all(bind=engine)
