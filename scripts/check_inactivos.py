"""
Script para verificar el estado de medicamentos inactivos en la BD
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database.connection import SessionLocal
from database import models

def check_all():
    """Verifica el estado de TODOS los medicamentos."""
    db = SessionLocal()
    
    try:
        # Query directo sin filtros
        todos = db.query(models.Medicamento).all()
        
        print("=" * 80)
        print("📊 ESTADO DE TODOS LOS MEDICAMENTOS EN LA BASE DE DATOS")
        print("=" * 80)
        print()
        
        activos = []
        inactivos_visibles = []
        inactivos_ocultos = []
        
        for med in todos:
            if med.estado.value == 'ACTIVO':
                activos.append(med)
            elif med.estado.value == 'INACTIVO':
                if med.is_deleted:
                    inactivos_ocultos.append(med)
                else:
                    inactivos_visibles.append(med)
        
        # Resumen
        print(f"Total medicamentos: {len(todos)}")
        print(f"  • Activos: {len(activos)}")
        print(f"  • Inactivos VISIBLES (is_deleted=False): {len(inactivos_visibles)}")
        print(f"  • Inactivos OCULTOS (is_deleted=True): {len(inactivos_ocultos)}")
        print()
        
        # Detalle de activos
        if activos:
            print("✅ MEDICAMENTOS ACTIVOS:")
            for med in activos:
                print(f"   • {med.nombre} ({med.lote}) - Stock: {med.stock}")
            print()
        
        # Detalle de inactivos visibles
        if inactivos_visibles:
            print("👁️  MEDICAMENTOS INACTIVOS VISIBLES (Admin puede verlos):")
            for med in inactivos_visibles:
                print(f"   • {med.nombre} ({med.lote})")
                print(f"     estado=INACTIVO, is_deleted=False ✅")
            print()
        
        # Detalle de inactivos ocultos
        if inactivos_ocultos:
            print("❌ MEDICAMENTOS INACTIVOS OCULTOS (Admin NO puede verlos):")
            for med in inactivos_ocultos:
                print(f"   • {med.nombre} ({med.lote})")
                print(f"     estado=INACTIVO, is_deleted=True ❌ PROBLEMA AQUÍ")
            print()
            print("⚠️  PROBLEMA IDENTIFICADO:")
            print("   Estos medicamentos tienen is_deleted=True")
            print("   El endpoint los filtra automáticamente")
            print("   Ejecuta: python scripts/fix_inactivos.py")
            print()
        
        # Test del query del endpoint
        print("=" * 80)
        print("🔍 SIMULACIÓN DEL QUERY DEL ENDPOINT")
        print("=" * 80)
        print()
        
        # Simular query del endpoint sin filtro de estado (admin ve todos)
        query_sin_filtro = db.query(models.Medicamento).filter(
            models.Medicamento.is_deleted == False
        ).all()
        
        print(f"GET /medicamentos/ (Admin sin filtro):")
        print(f"  → Retorna {len(query_sin_filtro)} medicamento(s)")
        for med in query_sin_filtro:
            print(f"    • {med.nombre} - {med.estado.value}")
        print()
        
        # Simular query con filtro INACTIVO
        query_inactivos = db.query(models.Medicamento).filter(
            models.Medicamento.is_deleted == False,
            models.Medicamento.estado == models.EstadoEnum.INACTIVO
        ).all()
        
        print(f"GET /medicamentos/?estado=INACTIVO:")
        print(f"  → Retorna {len(query_inactivos)} medicamento(s)")
        if query_inactivos:
            for med in query_inactivos:
                print(f"    • {med.nombre} ({med.lote})")
        else:
            print("    (ninguno)")
            if inactivos_ocultos:
                print(f"    ⚠️  Hay {len(inactivos_ocultos)} inactivo(s) pero con is_deleted=True")
        print()
        
    finally:
        db.close()


if __name__ == "__main__":
    check_all()
