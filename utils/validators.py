"""
Utilidades de validación.
"""
import uuid
from typing import Tuple


def validate_uuid(value: str, field_name: str = "id") -> Tuple[bool, str]:
    """
    Valida que un string sea un UUID válido.
    
    Args:
        value: String a validar
        field_name: Nombre del campo (para el mensaje de error)
    
    Returns:
        Tuple (is_valid: bool, error_message: str)
        - Si es válido: (True, "")
        - Si no es válido: (False, "Mensaje de error descriptivo")
    
    Ejemplo:
        is_valid, error = validate_uuid("abc123")
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
    """
    if not value:
        return False, f"{field_name} no puede estar vacío"
    
    try:
        uuid.UUID(str(value))
        return True, ""
    except (ValueError, AttributeError, TypeError) as e:
        return False, f"{field_name} debe ser un UUID válido. Recibido: {value}"
