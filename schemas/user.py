from pydantic import BaseModel, Field, EmailStr, validator
from uuid import UUID
from typing import Optional


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str]
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Optional[str] = 'farmaceutico'

    @validator('role')
    def role_valid(cls, v):
        allowed = {'admin', 'farmaceutico', 'compras'}
        if v not in allowed:
            raise ValueError('role must be one of: admin, farmaceutico, compras')
        return v


class UserOut(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str]
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str]
    email: Optional[EmailStr]
    password: Optional[str]
    role: Optional[str]
