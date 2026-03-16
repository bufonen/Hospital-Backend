"""
Schemas Pydantic para Alertas.
HU-2: Sistema de alertas automatizado.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date, datetime
from enum import Enum


class TipoAlertaEnum(str, Enum):
    STOCK_MINIMO = 'STOCK_MINIMO'
    STOCK_CRITICO = 'STOCK_CRITICO'
    STOCK_AGOTADO = 'STOCK_AGOTADO'
    VENCIMIENTO_PROXIMO = 'VENCIMIENTO_PROXIMO'
    VENCIMIENTO_INMEDIATO = 'VENCIMIENTO_INMEDIATO'
    VENCIDO = 'VENCIDO'
    ORDEN_RETRASADA = 'ORDEN_RETRASADA'


class EstadoAlertaEnum(str, Enum):
    ACTIVA = 'ACTIVA'
    PENDIENTE_REPOSICION = 'PENDIENTE_REPOSICION'
    RESUELTA = 'RESUELTA'


class PrioridadAlertaEnum(str, Enum):
    BAJA = 'BAJA'
    MEDIA = 'MEDIA'
    ALTA = 'ALTA'
    CRITICA = 'CRITICA'


class AlertaBase(BaseModel):
    """Base para alertas."""
    tipo: TipoAlertaEnum
    mensaje: str
    prioridad: PrioridadAlertaEnum


class AlertaOut(BaseModel):
    """
    Schema de salida para alertas.
    HU-2.01 y HU-2.02: Información completa de alerta.
    """
    id: str
    medicamento_id: Optional[str] = None
    tipo: TipoAlertaEnum
    estado: EstadoAlertaEnum
    prioridad: PrioridadAlertaEnum
    mensaje: str
    
    # Datos específicos de stock
    stock_actual: Optional[int] = None
    stock_minimo: Optional[int] = None
    
    # Datos específicos de vencimiento
    fecha_vencimiento: Optional[date] = None
    dias_restantes: Optional[int] = None
    lote: Optional[str] = None
    
    # Metadatos
    metadatos: Optional[Dict[str, Any]] = None
    
    # Auditoría
    created_at: datetime
    updated_at: Optional[datetime] = None
    resuelta_at: Optional[datetime] = None
    resuelta_by: Optional[str] = None
    notificada: bool = False
    notificada_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class AlertaWithMedicamento(AlertaOut):
    """
    Alerta con información del medicamento asociado.
    Útil para vistas de lista completa.
    """
    medicamento_nombre: str
    medicamento_presentacion: str
    medicamento_fabricante: str
    medicamento_lote: str
    
    model_config = {"from_attributes": True}


class AlertaUpdateEstado(BaseModel):
    """
    Schema para actualizar estado de una alerta.
    HU-2.01 y HU-2.02: Usuario marca alerta como resuelta.
    """
    estado: EstadoAlertaEnum
    notas: Optional[str] = Field(None, description="Notas opcionales sobre la resolución")


class AlertaStats(BaseModel):
    """
    Estadísticas de alertas para dashboard.
    HU-2: Resumen de alertas activas.
    """
    total_activas: int
    por_tipo: Dict[str, int]
    por_prioridad: Dict[str, int]
    por_estado: Dict[str, int]
    
    # Resumen de últimas 24 horas
    creadas_hoy: int
    resueltas_hoy: int


class NotificacionOut(BaseModel):
    """
    Schema para notificaciones de alertas en Redis.
    HU-2: Notificaciones a usuarios autorizados.
    """
    alert_id: str
    event_type: str  # 'created', 'updated', 'resolved'
    alert_type: str
    priority: str
    medicamento_nombre: str
    medicamento_fabricante: Optional[str] = ''
    medicamento_presentacion: Optional[str] = ''
    medicamento_lote: Optional[str] = ''
    mensaje: str
    timestamp: str


class ScanResultOut(BaseModel):
    """
    Resultado de escaneo manual de alertas.
    Útil para endpoints de monitoreo.
    """
    scan_type: str  # 'stock' o 'expiration'
    timestamp: datetime
    scanned: int
    alerts_created: int
    alerts_updated: int
    alerts_resolved: int = 0
    
    model_config = {"from_attributes": True}
