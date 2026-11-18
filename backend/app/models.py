import json
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

SKILLS = ["mason", "painter", "plumber", "electrician", "helper", "carpenter"]


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=False)
    skill = Column(String(40), nullable=False, index=True)
    experience_years = Column(Integer, default=1)
    area = Column(String(80), nullable=False)
    languages = Column(String(120), default="Hindi")
    expected_wage = Column(Integer, default=700)
    availability = Column(Text, default="[]")
    reliability = Column(Float, default=4.0)
    profile_text = Column(Text, default="")
    embedding = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)

    alerts = relationship("Alert", back_populates="worker")
    ratings = relationship("Rating", back_populates="worker")

    def availability_list(self):
        try:
            return json.loads(self.availability or "[]")
        except json.JSONDecodeError:
            return []

    def languages_list(self):
        return [x.strip() for x in (self.languages or "").split(",") if x.strip()]

    def embedding_vector(self):
        try:
            return json.loads(self.embedding or "[]")
        except json.JSONDecodeError:
            return []


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    transcript = Column(Text, default="")
    skill = Column(String(40), nullable=True)
    count = Column(Integer, default=1)
    date = Column(String(20), nullable=True)
    location = Column(String(120), nullable=True)
    wage_per_day = Column(Integer, nullable=True)
    language = Column(String(40), default="English")
    missing_fields = Column(Text, default="[]")
    clarifying_question = Column(Text, nullable=True)
    status = Column(String(40), default="draft")
    shortlist_ms = Column(Integer, nullable=True)
    demo_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    alerts = relationship("Alert", back_populates="job")
    ratings = relationship("Rating", back_populates="job")
    timeline = relationship("TimelineEvent", back_populates="job")

    def missing_fields_list(self):
        try:
            return json.loads(self.missing_fields or "[]")
        except json.JSONDecodeError:
            return []


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    message = Column(Text, nullable=False)
    language = Column(String(40), default="English")
    response = Column(String(10), nullable=True)  # yes|no|None
    status = Column(String(20), default="sent")  # sent|accepted|declined|timed_out
    confirmed = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    score_breakdown = Column(Text, default="{}")
    wave = Column(Integer, default=1)
    sent_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="alerts")
    worker = relationship("Worker", back_populates="alerts")


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    stars = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="ratings")
    worker = relationship("Worker", back_populates="ratings")


class MetricEvent(Base):
    __tablename__ = "metric_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(60), nullable=False)
    value = Column(Float, default=0.0)
    meta = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class ApiCache(Base):
    __tablename__ = "api_cache"

    id = Column(String(64), primary_key=True)  # sha256
    response = Column(Text, nullable=False)
    kind = Column(String(40), default="chat")
    created_at = Column(DateTime, default=datetime.utcnow)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="timeline")


class HistoricalJob(Base):
    __tablename__ = "historical_jobs"

    id = Column(Integer, primary_key=True, index=True)
    skill = Column(String(40), nullable=False, index=True)
    area = Column(String(80), nullable=False, index=True)
    wage = Column(Integer, nullable=False)
    date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(120), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)

    def embedding_vector(self):
        try:
            return json.loads(self.embedding or "[]")
        except json.JSONDecodeError:
            return []
