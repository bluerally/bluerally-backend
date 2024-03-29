from pydantic import BaseModel
from typing import Optional


class NotificationBaseDto(BaseModel):
    type: str
    related_id: Optional[int] = None
    message: str
    is_global: bool


class NotificationSpecificDto(NotificationBaseDto):
    target_user_id: int


class NotificationDto(NotificationBaseDto):
    id: int
    created_at: str
    is_read: bool


class NotificationReadDto(BaseModel):
    user_id: int
    read_at: str
    notification_id: int
