"""
Service para lógica de negocio de Proveedores.
HU-4.01: Manejo de Proveedores
"""
from sqlalchemy.orm import Session
from database.models import Proveedor, EstadoProveedorEnum, AuditLog
from repositories.proveedor_repo import ProveedorRepository
from typing import Optional, Dict, Any, List
from datetime import datetime


class ProveedorService:
    """
    Service para lógica de negocio de proveedores.
    
    Responsabilidades (Service Layer Pattern):
    - Validaciones de negocio
    - Transacciones (commit/rollback)
    - Auditoría de cambios
    - Orquestación de operaciones
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProveedorRepository(db)
    
    def create_proveedor(
        self, 
        payload: Dict[str, Any], 
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea un nuevo proveedor.
        
        HU-4.01: "Given datos válidos, When se crea un registro de un proveedor, 
                  Then registro creado con ID único"
        
        Validaciones:
        - NIT único (no duplicados)
        - Campos obligatorios presentes
        
        Returns:
            Dict con 'ok': bool, 'proveedor': Proveedor, 'error': str (si falla)
        """
        try:
            # Validar NIT único
            existing = self.repo.get_by_nit(payload['nit'])
            if existing:
                return {
                    'ok': False,
                    'error': 'duplicate_nit',
                    'message': 'El NIT ingresado ya está asociado a un proveedor existente',
                    'existing_id': str(existing.id)
                }
            
            # Crear proveedor
            proveedor = Proveedor(
                nit=payload['nit'],
                nombre=payload['nombre'],
                telefono=payload.get('telefono'),
                email=payload.get('email'),
                direccion=payload.get('direccion'),
                estado=EstadoProveedorEnum.ACTIVO,
                created_by=user_id
            )
            
            self.repo.create(proveedor)
            self.db.flush()
            self.db.refresh(proveedor)
            
            # Auditoría
            audit = AuditLog(
                entidad='proveedores',
                entidad_id=proveedor.id,
                usuario_id=user_id,
                accion='CREATE',
                metadatos={
                    'nit': proveedor.nit,
                    'nombre': proveedor.nombre
                }
            )
            self.db.add(audit)
            
            self.db.commit()
            
            return {
                'ok': True,
                'proveedor': proveedor
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creando proveedor: {e}")
            return {
                'ok': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    def get_proveedor(self, proveedor_id: str) -> Optional[Proveedor]:
        """Obtiene un proveedor por ID."""
        return self.repo.get_by_id(proveedor_id)
    
    def list_proveedores(
        self, 
        estado: Optional[str] = None,
        nombre: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Proveedor]:
        """
        Lista proveedores con filtros.
        
        Args:
            estado: 'ACTIVO' o 'INACTIVO'
            nombre: Búsqueda por nombre
            limit: Límite de resultados
            offset: Offset para paginación
        """
        estado_enum = None
        if estado:
            try:
                estado_enum = EstadoProveedorEnum(estado.upper())
            except ValueError:
                pass  # Si no es válido, no filtrar
        
        return self.repo.list(
            estado=estado_enum,
            nombre=nombre,
            limit=limit,
            offset=offset
        )
    
    def update_proveedor(
        self, 
        proveedor_id: str, 
        changes: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Actualiza un proveedor.
        
        HU-4.01: "Given que existe un proveedor registrado When edito su información 
                  y guardo cambios Then los datos se actualizan correctamente"
        
        Reglas:
        - NO se puede editar NIT ni ID
        - Solo actualiza campos que cambiaron
        - Registra auditoría de cada cambio
        
        Returns:
            Dict con 'ok': bool, 'updated': bool, 'proveedor': Proveedor
        """
        try:
            proveedor = self.repo.get_by_id(proveedor_id)
            if not proveedor:
                return {
                    'ok': False,
                    'error': 'not_found',
                    'message': 'Proveedor no encontrado'
                }
            
            # Detectar cambios y aplicar
            audit_entries = []
            campos_editables = ['nombre', 'telefono', 'email', 'direccion', 'estado']
            
            for field in campos_editables:
                if field in changes:
                    new_value = changes[field]
                    old_value = getattr(proveedor, field)
                    
                    # Convertir estado a Enum si es necesario
                    if field == 'estado' and isinstance(new_value, str):
                        try:
                            new_value = EstadoProveedorEnum(new_value.upper())
                        except ValueError:
                            continue  # Ignorar valor inválido
                    
                    # Solo actualizar si cambió
                    if str(new_value) != str(old_value):
                        audit_entries.append((field, str(old_value), str(new_value)))
                        setattr(proveedor, field, new_value)
            
            if not audit_entries:
                return {
                    'ok': True,
                    'updated': False,
                    'message': 'No se detectaron cambios'
                }
            
            # Actualizar metadata
            proveedor.updated_by = user_id
            self.repo.update(proveedor)
            
            # Crear logs de auditoría
            for field, old_val, new_val in audit_entries:
                audit = AuditLog(
                    entidad='proveedores',
                    entidad_id=proveedor.id,
                    usuario_id=user_id,
                    accion='UPDATE',
                    campo=field,
                    valor_anterior=old_val,
                    valor_nuevo=new_val
                )
                self.db.add(audit)
            
            self.db.flush()
            self.db.refresh(proveedor)
            self.db.commit()
            
            return {
                'ok': True,
                'updated': True,
                'proveedor': proveedor
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error actualizando proveedor: {e}")
            return {
                'ok': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    def deactivate_proveedor(
        self, 
        proveedor_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Desactiva un proveedor (soft delete).
        
        HU-4.01: Cambio de estado a INACTIVO en lugar de borrado físico.
        
        Returns:
            Dict con 'ok': bool, 'proveedor': Proveedor
        """
        try:
            proveedor = self.repo.get_by_id(proveedor_id)
            if not proveedor:
                return {
                    'ok': False,
                    'error': 'not_found',
                    'message': 'Proveedor no encontrado'
                }
            
            if proveedor.estado == EstadoProveedorEnum.INACTIVO:
                return {
                    'ok': False,
                    'error': 'already_inactive',
                    'message': 'El proveedor ya está inactivo'
                }
            
            # Cambiar estado
            proveedor.estado = EstadoProveedorEnum.INACTIVO
            proveedor.updated_by = user_id
            self.repo.update(proveedor)
            
            # Auditoría
            audit = AuditLog(
                entidad='proveedores',
                entidad_id=proveedor.id,
                usuario_id=user_id,
                accion='DEACTIVATE',
                metadatos={'estado_anterior': 'ACTIVO'}
            )
            self.db.add(audit)
            
            self.db.commit()
            
            return {
                'ok': True,
                'proveedor': proveedor
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error desactivando proveedor: {e}")
            return {
                'ok': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    def activate_proveedor(
        self, 
        proveedor_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reactiva un proveedor inactivo.
        
        Returns:
            Dict con 'ok': bool, 'proveedor': Proveedor
        """
        try:
            proveedor = self.repo.get_by_id(proveedor_id)
            if not proveedor:
                return {
                    'ok': False,
                    'error': 'not_found',
                    'message': 'Proveedor no encontrado'
                }
            
            if proveedor.estado == EstadoProveedorEnum.ACTIVO:
                return {
                    'ok': False,
                    'error': 'already_active',
                    'message': 'El proveedor ya está activo'
                }
            
            # Cambiar estado
            proveedor.estado = EstadoProveedorEnum.ACTIVO
            proveedor.updated_by = user_id
            self.repo.update(proveedor)
            
            # Auditoría
            audit = AuditLog(
                entidad='proveedores',
                entidad_id=proveedor.id,
                usuario_id=user_id,
                accion='ACTIVATE',
                metadatos={'estado_anterior': 'INACTIVO'}
            )
            self.db.add(audit)
            
            self.db.commit()
            
            return {
                'ok': True,
                'proveedor': proveedor
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Error activando proveedor: {e}")
            return {
                'ok': False,
                'error': 'database_error',
                'message': str(e)
            }
    
    def search_proveedores(self, query: str, limit: int = 10) -> List[Proveedor]:
        """
        Búsqueda rápida de proveedores.
        Útil para autocomplete y dropdowns.
        """
        return self.repo.search(query, limit)
    
    def get_stats(self) -> Dict[str, int]:
        """
        Obtiene estadísticas básicas de proveedores.
        
        Returns:
            Dict con contadores de proveedores activos e inactivos
        """
        return {
            'total': self.repo.count_all(),
            'activos': self.repo.count_all(EstadoProveedorEnum.ACTIVO),
            'inactivos': self.repo.count_all(EstadoProveedorEnum.INACTIVO)
        }
