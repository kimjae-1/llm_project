from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass


class ChatRequest(BaseModel):
    user_id: str = Field(..., title="User ID")
    session_number: int = Field(..., title="Session Number")
    question: str = Field(..., title="question")

@dataclass
class ChatResponse:
    final_message: str = Field(..., title="Response answer")

