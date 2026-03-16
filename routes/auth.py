from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database.connection import get_db
from database import models
from auth.passwords import verify_password
from auth.jwt import create_access_token
from schemas.response import TokenOut
from typing import Optional

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

router = APIRouter()

#función auxiliar para autenticar usuario
async def authenticate_user(username: str, password: str, db: Session) -> models.User:
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not bool(user.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    return user

@router.post("/signin", response_model=TokenOut)
async def login_user(
    username: str = Form(...),
    password: str = Form(...),
    grant_type: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Endpoint para login desde Blazor"""
    user = await authenticate_user(username, password, db)
    token_data = {"sub": str(user.id), "username": user.username, "role": user.role.value}
    access_token = create_access_token(token_data)
    return TokenOut(access_token=access_token, token_type="bearer")

@router.post('/login', response_model=TokenOut)
async def login_json(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Endpoint para login con JSON"""
    user = await authenticate_user(login_data.username, login_data.password, db)
    token_data = {"sub": str(user.id), "username": user.username, "role": user.role.value}
    access_token = create_access_token(token_data)
    return TokenOut(access_token=access_token, token_type="bearer")

@router.post('/token', response_model=TokenOut)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuario o contraseña inválidos')
    if not verify_password(form_data.password, str(user.hashed_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuario o contraseña inválidos')

    if user.is_active is not True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Usuario inactivo')

    token_data = {"sub": str(user.id), "username": user.username, "role": user.role.value}
    access_token = create_access_token(token_data)
    return TokenOut(access_token=access_token, token_type="bearer")
