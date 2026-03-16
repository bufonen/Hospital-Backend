"""
Script para arreglar medicamentos inactivos con is_deleted=True

Este script actualiza todos los medicamentos con:
- estado = INACTIVO
- is_deleted = True

Para cambiarlos a:
- estado = INACTIVO
- is_deleted = False

Esto permite que los admins puedan verlos y reactivarlos.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database.connection import SessionLocal
from database import models
from sqlalchemy import and_

def fix_inactivos():
    """Actualiza medicamentos inactivos para que sean visibles."""
    db = SessionLocal()
    
    try:
        # Buscar medicamentos con estado=INACTIVO y is_deleted=True
        medicamentos = db.query(models.Medicamento).filter(
            and_(
                models.Medicamento.estado == models.EstadoEnum.INACTIVO,
                models.Medicamento.is_deleted == True
            )
        ).all()
        
        if not medicamentos:
            print("✅ No hay medicamentos inactivos con is_deleted=True")
            print("   Todos los medicamentos están correctos.")
            return
        
        print(f"🔍 Encontrados {len(medicamentos)} medicamento(s) con is_deleted=True")
        print()
        
        for med in medicamentos:
            print(f"📦 {med.nombre} ({med.presentacion})")
            print(f"   ID: {med.id}")
            print(f"   Estado: {med.estado}")
            print(f"   is_deleted: {med.is_deleted} → False")
            
            # Actualizar
            med.is_deleted = False
            db.add(med)
        
        # Commit de todos los cambios
        db.commit()
        
        print()
        print(f"✅ Actualizados {len(medicamentos)} medicamento(s)")
        print("   Ahora son visibles con filtro estado=INACTIVO")
        print("   Los admins pueden reactivarlos")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def listar_inactivos():
    """Lista todos los medicamentos inactivos para verificar."""
    db = SessionLocal()
    
    try:
        # Buscar TODOS los inactivos (incluidos is_deleted=True)
        medicamentos = db.query(models.Medicamento).filter(
            models.Medicamento.estado == models.EstadoEnum.INACTIVO
        ).all()
        
        print(f"\n📋 Medicamentos INACTIVOS en la base de datos:")
        print(f"   Total: {len(medicamentos)}")
        print()
        
        if not medicamentos:
            print("   (ninguno)")
            return
        
        for med in medicamentos:
            deleted_status = "❌ is_deleted=True (NO VISIBLE)" if med.is_deleted else "✅ is_deleted=False (VISIBLE)"
            print(f"   • {med.nombre} - {deleted_status}")
            print(f"     Lote: {med.lote} | Stock: {med.stock}")
        
        print()
        
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Script de Reparación: Medicamentos Inactivos")
    print("=" * 60)
    print()
    
    # Primero listar el estado actual
    listar_inactivos()
    
    # Preguntar confirmación
    print()
    respuesta = input("¿Actualizar medicamentos inactivos? (s/n): ")
    
    if respuesta.lower() in ['s', 'si', 'y', 'yes']:
        print()
        fix_inactivos()
        
        # Listar nuevamente para verificar
        listar_inactivos()
    else:
        print("❌ Operación cancelada")
