from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DBModelMixin(BaseModel):
    id: UUID
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
