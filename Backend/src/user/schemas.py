# --------------------------
# Pydantic Schemas
# --------------------------
from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    token_type: Literal["Bearer", "bearer"]


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateUserModel(BaseModel):
    auth_provider_id: UUID = Field(..., unique=True)
    email: str
