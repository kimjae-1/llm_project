from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.session import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[int] = mapped_column(
        Integer, autoincrement=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    session_number: Mapped[int] = mapped_column(primary_key=True)
    messages: Mapped[Optional[List[dict]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
