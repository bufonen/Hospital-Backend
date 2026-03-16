import sys
import os

# Add project root to sys.path to allow imports when running script from scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import SessionLocal, engine, Base
from database import models
from auth.passwords import hash_password


def create_tables_and_admin():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # verificar si existe admin
        admin = db.query(models.User).filter(models.User.username == 'admin').first()
        if not admin:
            u = models.User(username='admin', full_name='Administrador', email='admin@example.com', hashed_password=hash_password('Admin123!'), role=models.UserRoleEnum.ADMIN)
            db.add(u)
            db.commit()
            print('Usuario admin creado: admin / Admin123!')
        else:
            print('Usuario admin ya existe')
    finally:
        db.close()


if __name__ == '__main__':
    create_tables_and_admin()
