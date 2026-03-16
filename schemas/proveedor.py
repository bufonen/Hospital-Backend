"""
Schemas Pydantic para Proveedores.
HU-4.01: Manejo de Proveedores
"""
from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional
from datetime import datetime
import re


class ProveedorBase(BaseModel):
    """Schema base con campos comunes."""
    nombre: str = Field(..., min_length=1, max_length=200, description="Nombre del proveedor")
    telefono: Optional[str] = Field(None, max_length=50, description="Teléfono de contacto")
    email: Optional[EmailStr] = Field(None, description="Email de contacto")
    direccion: Optional[str] = Field(None, max_length=500, description="Dirección física")


class ProveedorCreate(ProveedorBase):
    """
    Schema para creación de proveedor.
    
    HU-4.01: Validaciones
    - NIT es requerido, único y numérico
    - Email debe tener formato válido (EmailStr)
    - Nombre es obligatorio
    """
    nit: str = Field(..., min_length=5, max_length=50, description="NIT del proveedor (solo números y guiones)")
    
    @field_validator('nit')
    @classmethod
    def validate_nit(cls, v: str) -> str:
        """
        Valida que el NIT tenga formato numérico válido.
        HU-4.01: "El NIT debe seguir formato numérico con validación de longitud"
        
        Formatos aceptados:
        - Solo números: "123456789"
        - Con guión verificador: "123456789-0"
        """
        # Remover espacios
        v = v.strip()
        
        # Permitir números y un guión opcional para dígito verificador
        if not re.match(r'^\d+(-\d)?$', v):
            raise ValueError('El NIT debe contener solo números, opcionalmente con un guión y dígito verificador (ej: 123456789-0)')
        
        # Validar longitud mínima (sin contar el guión)
        nit_numeros = v.replace('-', '')
        if len(nit_numeros) < 5:
            raise ValueError('El NIT debe tener al menos 5 dígitos')
        
        return v


class ProveedorUpdate(BaseModel):
    """
    Schema para actualización de proveedor.
    
    HU-4.01: "Edición de campos excepto el NIT y ID"
    Nota: NIT e ID NO están incluidos, no se pueden editar.
    """
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    telefono: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    direccion: Optional[str] = Field(None, max_length=500)
    estado: Optional[str] = Field(None, pattern="^(ACTIVO|INACTIVO)$")


class ProveedorOut(ProveedorBase):
    """
    Schema de salida (response) con todos los campos.
    Incluye campos de auditoría.
    """
    id: str
    nit: str
    estado: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Para compatibilidad con SQLAlchemy models


class ProveedorShortOut(BaseModel):
    """
    Schema resumido para listas y búsquedas rápidas.
    Útil para dropdowns y autocomplete.
    """
    id: str
    nit: str
    nombre: str
    estado: str
    
    class Config:
        from_attributes = True
