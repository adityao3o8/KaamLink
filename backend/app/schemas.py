from typing import Any, Optional
from pydantic import BaseModel, Field


class JobExtracted(BaseModel):
    skill: Optional[str] = None
    count: Optional[int] = 1
    date: Optional[str] = None
    location: Optional[str] = None
    wage_per_day: Optional[int] = None
    language: Optional[str] = "English"
    missing_fields: list[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None


class JobResponse(BaseModel):
    job_id: int
    transcript: str
    language: str
    extracted: JobExtracted
    needs_clarification: bool = False
    demo_mode: bool = False
    provider: str = "Groq (Whisper + Llama)"


class WorkerExtracted(BaseModel):
    name: Optional[str] = None
    skill: Optional[str] = None
    experience_years: Optional[int] = 1
    area: Optional[str] = None
    availability: list[str] = Field(default_factory=list)
    languages: Optional[str] = "Hindi"
    expected_wage: Optional[int] = 700
    phone: Optional[str] = None
    profile_text: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None


class WorkerResponse(BaseModel):
    worker_id: Optional[int] = None
    transcript: str
    extracted: WorkerExtracted
    saved: bool = False
    message: str = ""
    demo_mode: bool = False
    provider: str = "Groq (Whisper + Llama)"


class ScoreBreakdown(BaseModel):
    embedding: float
    reliability: float
    wage_fit: float
    area_match: float
    total: float


class MatchCard(BaseModel):
    worker_id: int
    name: str
    skill: str
    area: str
    experience_years: int
    expected_wage: int
    reliability: float
    languages: list[str]
    phone_masked: str
    score: ScoreBreakdown


class MatchResponse(BaseModel):
    job_id: int
    matches: list[MatchCard]
    shortlist_ms: int


class AlertBubble(BaseModel):
    alert_id: int
    worker_id: int
    worker_name: str
    language: str
    message: str
    response: Optional[str] = None
    status: str = "sent"
    confirmed: bool = False
    phone: Optional[str] = None
    score: float
    wave: int = 1


class AlertResponse(BaseModel):
    job_id: int
    alerts: list[AlertBubble]
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_count: int = 0
    needed: int = 1


class AlertReplyRequest(BaseModel):
    response: str


class RatingRequest(BaseModel):
    job_id: int
    worker_id: int
    stars: int


class TextJobRequest(BaseModel):
    text: str
    language_hint: Optional[str] = "auto"
    demo_mode: bool = False


class TextWorkerRequest(BaseModel):
    text: str
    phone: Optional[str] = None
    language_hint: Optional[str] = "auto"
    demo_mode: bool = False


class ConfirmWorkerRequest(BaseModel):
    transcript: str
    name: str
    skill: str
    experience_years: int = 1
    area: str
    availability: list[str] = Field(default_factory=list)
    languages: str = "Hindi"
    expected_wage: int = 700
    phone: str = "9000000000"
    profile_text: str = ""


class MetricsResponse(BaseModel):
    extraction_accuracy: float
    extraction_details: list[dict[str, Any]]
    avg_time_to_shortlist_ms: float
    match_acceptance_rate: float
    total_jobs: int
    total_alerts: int
    total_accepts: int
    eval_results: Optional[dict[str, Any]] = None


class WageSuggestResponse(BaseModel):
    skill: str
    area: str
    median: int
    p25: int
    p75: int
    sample_size: int
    offered: Optional[int] = None
    is_lowball: bool = False
    message: str = ""


class RagRequest(BaseModel):
    question: str
    language: Optional[str] = "English"
    demo_mode: bool = False


class RagResponse(BaseModel):
    answer: str
    sources: list[str]
    language: str
