import uuid
import datetime
from sqlalchemy import UUID,func,DateTime
from sqlalchemy.orm import Mapped,mapped_column,DeclarativeBase


class Base(DeclarativeBase):
    __abstract__ = True
    id:Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),default=uuid.uuid4)
    created_at:Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at:Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())