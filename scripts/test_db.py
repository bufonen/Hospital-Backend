from database.connection import SessionLocal, engine, Base
from database import models
from auth.passwords import hash_password

if __name__ == '__main__':
    print('Creando tablas (si es necesario) y probando inserción...')
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print('Error al crear tablas:', e)
        raise

    db = SessionLocal()
    try:
        u = db.query(models.User).filter(models.User.username=='testuser').first()
        if not u:
            new = models.User(username='testuser', full_name='Test User', email='test@example.com', hashed_password=hash_password('Test123!'), role=models.UserRoleEnum.FARMACEUTICO)
            db.add(new)
            db.commit()
            print('Usuario test creado')
        else:
            print('Usuario test ya existe')
        u2 = db.query(models.User).filter(models.User.username=='testuser').first()
        print('Encontrado:', bool(u2))
    except Exception as e:
        print('Error en operación DB:', repr(e))
    finally:
        db.close()
