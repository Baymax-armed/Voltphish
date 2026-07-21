"""SQLAlchemy models for VoltPhish."""
from .apikey import ApiKey
from .attachment import Attachment
from .base import utcnow
from .campaign import Campaign, CampaignStatus
from .event import Event, EventType
from .group import Group, Target
from .job import Job, JobStatus
from .page import LandingPage
from .profile import SendingProfile
from .reported_email import ReportedEmail, ReportStatus
from .result import Result, ResultStatus
from .setting import Setting
from .template import Template
from .training import (
    Difficulty,
    EnrollmentStatus,
    QuizQuestion,
    TrainingEnrollment,
    TrainingModule,
)
from .user import Session, User, UserRole
from .webhook import Webhook

__all__ = [
    "utcnow",
    "User",
    "UserRole",
    "Session",
    "Group",
    "Target",
    "Template",
    "LandingPage",
    "SendingProfile",
    "Campaign",
    "CampaignStatus",
    "Result",
    "ResultStatus",
    "Event",
    "EventType",
    "Job",
    "JobStatus",
    "Webhook",
    "ApiKey",
    "Attachment",
    "Setting",
    "ReportedEmail",
    "ReportStatus",
    "TrainingModule",
    "QuizQuestion",
    "TrainingEnrollment",
    "Difficulty",
    "EnrollmentStatus",
]
