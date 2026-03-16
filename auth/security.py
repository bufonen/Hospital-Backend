from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .jwt import verify_token
from sqlalchemy.orm import Session
from database.connection import get_db
from database import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")

    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

    return {"sub": str(user.id), "username": user.username, "role": user.role.value}


def require_admin(current_user: dict = Depends(get_current_user)):
    """Solo administradores pueden ejecutar esta acción."""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para esta acción.")
    return current_user


def require_farmaceutico_or_admin(current_user: dict = Depends(get_current_user)):
    """Farmacéuticos y administradores pueden ejecutar esta acción."""
    role = current_user.get('role')
    if role not in ['farmaceutico', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Esta acción requiere rol de farmacéutico o administrador."
        )
    return current_user

def require_farmaceutico(user: dict = Depends(get_current_user)):
    if user["role"].upper() != "FARMACEUTICO":
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos de farmacéutico"
        )
    return user



def require_compras_or_admin(current_user: dict = Depends(get_current_user)):
    """Responsables de compras y administradores pueden ejecutar esta acción."""
    role = current_user.get('role')
    if role not in ['compras', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Esta acción requiere rol de compras o administrador."
        )
    return current_user


def is_admin(current_user: dict) -> bool:
    """Verifica si el usuario actual es administrador (sin lanzar excepción)."""
    return current_user.get('role') == 'admin'
