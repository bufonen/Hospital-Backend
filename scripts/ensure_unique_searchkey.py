import sys
import os

# Ensure project root is on sys.path so `database` package is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import engine
from sqlalchemy import text
from sqlalchemy.orm import Session

"""This script checks for duplicate search_key values in medicamentos and
reports them. If none are found, it will (attempt to) create a unique
constraint/index on the medicamentos.search_key column.

Run with:
    python scripts/ensure_unique_searchkey.py

If duplicates are found, it will print them and exit without changing the DB.
"""


if __name__ == '__main__':
    with Session(engine) as session:
        res = session.execute(text("SELECT search_key, COUNT(*) as cnt FROM medicamentos GROUP BY search_key HAVING COUNT(*)>1;"))
        rows = res.fetchall()
        if rows:
            print('Se encontraron duplicados en search_key:')
            for r in rows:
                print(r)
            print('Por favor resuelve manualmente los duplicados antes de crear el índice único.')
        else:
            print('No se encontraron duplicados. Creando índice/constraint único...')
            try:
                # Add unique constraint via ALTER TABLE (SQL Server syntax)
                session.execute(text('ALTER TABLE medicamentos ADD CONSTRAINT uq_medicamentos_search_key UNIQUE (search_key);'))
                session.commit()
                print('Constraint único creado correctamente.')
            except Exception as e:
                print('Error al crear constraint:', e)
                print('Puede que ya exista o que necesites permisos.')