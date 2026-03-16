from database.connection import Base, engine
from database import models

if __name__ == '__main__':
    print('Creando tablas...')
    Base.metadata.create_all(bind=engine)
    print('Tablas creadas (o existentes).')
