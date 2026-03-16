from typing import Optional, List
from sqlalchemy.orm import Session
from database import models


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, payload: dict) -> models.User:
        u = models.User(**payload)
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def count_admins(self) -> int:
        return self.db.query(models.User).filter(models.User.role == models.UserRoleEnum.ADMIN).count()

    def create_admin(self, payload: dict) -> models.User:
        # payload must include hashed_password and necessary fields
        payload['role'] = models.UserRoleEnum.ADMIN
        return self.create_user(payload)

    def get_user(self, user_id: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def list_users(self) -> List[models.User]:
        return self.db.query(models.User).all()

    def update_user(self, user: models.User) -> models.User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user: models.User) -> None:
        self.db.delete(user)
        self.db.commit()
