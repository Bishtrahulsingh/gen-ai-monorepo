import enum
from typing import List
from pydantic import BaseModel,Field


class Severity(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class RiskSchema(BaseModel):
    risk: str
    severity: enum.Enum


class MemoResponse(BaseModel):
    executive_summary: str = Field(..., title="summary", description="summary of analysis")
    key_risks:List[RiskSchema]
    open_questions: List[str]
    confidence: float