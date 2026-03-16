"""
Script de migración para actualizar search_key de medicamentos existentes.

Este script actualiza todos los medicamentos en la base de datos para que su
search_key NO incluya el lote, alineándose con la corrección de HU-1.01.

ANTES: search_key = "nombre|presentacion|fabricante|lote"
DESPUÉS: search_key = "nombre|presentacion|fabricante"

Uso:
    python scripts/migrate_search_key.py
"""
import sys
import os

# Agregar el directorio padre al path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import get_db, engine, Base
from database import models
from utils.text import normalize_text
from sqlalchemy.orm import Session


def migrate_search_keys():
    """Actualiza el search_key de todos los medicamentos para remover el lote."""
    
    # Crear sesión
    db = next(get_db())
    
    try:
        # Obtener todos los medicamentos
        medicamentos = db.query(models.Medicamento).all()
        
        print(f"🔍 Encontrados {len(medicamentos)} medicamentos para migrar...")
        
        updated_count = 0
        skipped_count = 0
        
        for med in medicamentos:
            # Calcular nuevo search_key (sin lote)
            new_search_key = f"{normalize_text(med.nombre)}|{normalize_text(med.presentacion)}|{normalize_text(med.fabricante)}"
            
            # Solo actualizar si cambió
            if med.search_key != new_search_key:
                old_key = med.search_key
                med.search_key = new_search_key
                db.add(med)
                updated_count += 1
                print(f"✅ Actualizado: {med.nombre} (Lote: {med.lote})")
                print(f"   Antes:  {old_key}")
                print(f"   Después: {new_search_key}")
            else:
                skipped_count += 1
        
        # Commit de todos los cambios
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Migración completada exitosamente:")
            print(f"   - {updated_count} medicamentos actualizados")
            print(f"   - {skipped_count} medicamentos sin cambios")
        else:
            print(f"\n✅ No se requieren actualizaciones. Todos los medicamentos ya tienen el formato correcto.")
    
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error durante la migración: {e}")
        raise
    
    finally:
        db.close()


if __name__ == '__main__':
    print("="*70)
    print("   MIGRACIÓN DE SEARCH_KEY - Remover Lote")
    print("="*70)
    print()
    print("Este script actualizará el search_key de todos los medicamentos")
    print("para remover el lote y alinearse con HU-1.01.")
    print()
    
    respuesta = input("¿Desea continuar? (s/n): ").lower()
    
    if respuesta == 's':
        print()
        migrate_search_keys()
    else:
        print("\n❌ Migración cancelada por el usuario.")
