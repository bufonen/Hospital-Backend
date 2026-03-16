from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.connection import get_db
from database import models
from schemas.user import UserCreate, UserOut, UserUpdate
from auth.passwords import hash_password, verify_password
from auth.security import require_admin, get_current_user
from typing import List, Optional
from schemas.response import MessageOut
from services.user_service import UserService
from fastapi import Depends
from database.connection import get_db


def get_user_service(db=Depends(get_db)) -> UserService:
    return UserService(db)

router = APIRouter()


@router.post('/', response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), service: UserService = Depends(get_user_service)):
    existing = db.query(models.User).filter((models.User.username == payload.username) | (models.User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Usuario o email ya existen')

    payload_dict = payload.model_dump()
    raw_pw = payload_dict.pop('password', None)
    payload_dict['hashed_password'] = hash_password(raw_pw) if raw_pw else None
    if payload_dict.get('role') == 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No está permitido crear usuarios con rol admin a través de este endpoint')
    payload_dict['role'] = models.UserRoleEnum(payload.role)
    u = service.create_user(payload_dict)
    return u


@router.post('/create_admin', response_model=UserOut)
def create_admin(payload: UserCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin), service: UserService = Depends(get_user_service)):
    existing = db.query(models.User).filter((models.User.username == payload.username) | (models.User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Usuario o email ya existen')

    payload_dict = payload.model_dump()
    raw_pw = payload_dict.pop('password', None)
    payload_dict['hashed_password'] = hash_password(raw_pw) if raw_pw else None
    payload_dict['role'] = models.UserRoleEnum('admin')
    u = service.create_user(payload_dict)
    return u


@router.get('/me', response_model=UserOut)
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db), service: UserService = Depends(get_user_service)):
    user = service.get_user(current_user.get('sub'))
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    return user


@router.get('/', response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user), service: UserService = Depends(get_user_service)):
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No tiene permisos')
    users = service.list_users()
    return users


@router.get('/{user_id}', response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user), service: UserService = Depends(get_user_service)):
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    if current_user.get('role') != 'admin' and current_user.get('sub') != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No tiene permisos')
    return user


@router.put('/{user_id}', response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user), service: UserService = Depends(get_user_service)):
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')

    is_admin = current_user.get('role') == 'admin'
    is_owner = current_user.get('sub') == str(user.id)
    if not (is_admin or is_owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No tiene permisos')

    # non-admin cannot change role
    if payload.role and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No puede cambiar el rol')

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.role and is_admin:
        user.role = models.UserRoleEnum(payload.role)

    user = service.update_user(user)
    return user


# Delete user (admin only)
@router.delete('/{user_id}')
def delete_user(user_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user), service: UserService = Depends(get_user_service)) -> MessageOut:
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No tiene permisos')
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    service.delete_user(user)
    return MessageOut(message='Usuario eliminado')