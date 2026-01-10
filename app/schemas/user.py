from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import AuthProvider
from app.schemas.common import DBModelMixin


class UserBase(BaseModel):
    email: EmailStr | None = None
    display_name: str = Field(default="놀자Go 사용자", max_length=255)
    profile_image_url: str | None = None
    phone_number: str | None = None
    location_name: str | None = None
    run_speed: int | None = Field(default=None, ge=1, le=10)
    stamina: int | None = Field(default=None, ge=1, le=10)


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=6)
    password_confirm: str = Field(min_length=6)

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info):
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Passwords do not match")
        return v
    password_confirm: str = Field(min_length=6)


class KakaoUserCreate(BaseModel):
    access_token: str = Field(min_length=1)
    email: EmailStr | None = None
    display_name: str | None = None


class UserUpdate(UserBase):
    pass


class UserOut(DBModelMixin):
    email: EmailStr | None = None
    display_name: str
    profile_image_url: str | None = None
    phone_number: str | None = None
    location_name: str | None = None
    run_speed: int | None = None
    stamina: int | None = None
    provider: AuthProvider
    provider_account_id: str | None = None
    is_active: bool
