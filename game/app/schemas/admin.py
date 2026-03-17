"""Schemas for admin bot endpoints."""

from pydantic import BaseModel, Field


class AdminTopupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)


class AdminBanRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class AdminTopupResponse(BaseModel):
    username: str
    new_bank: int


class AdminBanResponse(BaseModel):
    username: str
    is_banned: bool
