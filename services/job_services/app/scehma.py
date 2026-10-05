from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


#This is the Enum class the option for object values is fixed
class JobStatus(str , Enum):
    applied = "Applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"

#This BaseModel class Verifies the request Payload for the format
class JobCreate(BaseModel):
    company : str = Field(min_length=1)
    role: str = Field(min_length=1)
    status: JobStatus = JobStatus.applied
    applied_on: date = Field(default_factory=date.today)
    note: str | None = None

# This class verifies the response structure
class JobOut(JobCreate):
    id: str