import uuid
from sqlalchemy import Column, String, Integer, Date, DateTime, Boolean, Enum, ForeignKey, func, JSON, Numeric
from sqlalchemy.orm import relationship
from .connection import Base
import enum
from sqlalchemy import UniqueConstraint
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.dialects.postgresql import UUID

class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mssql':
            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        elif dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, bytes):
            try:
                value = value.decode()
            except Exception:
                value = str(value)
        if not isinstance(value, str):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return str(value)
        except Exception:
            return value


class EstadoEnum(enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    PENDIENTE_SYNC = "PENDIENTE_SYNC"


class Medicamento(Base):
    __tablename__ = 'medicamentos'

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String(200), nullable=False)
    fabricante = Column(String(200), nullable=False)
    presentacion = Column(String(200), nullable=False)
    lote = Column(String(100), nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    minimo_stock = Column(Integer, nullable=True)
    precio = Column(Numeric(12, 2), nullable=False, server_default="0")
    principio_activo = Column(String(300), nullable=True)
    principio_activo_search = Column(String(300), nullable=True, index=True)
    estado = Column(Enum(EstadoEnum), default=EstadoEnum.ACTIVO, nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(100), nullable=True)
    search_key = Column(String(400), nullable=False, unique=True)

    movimientos = relationship('Movimiento', back_populates='medicamento')


class MovimientoTipoEnum(enum.Enum):
    ENTRADA = 'ENTRADA'
    SALIDA = 'SALIDA'


class Movimiento(Base):
    __tablename__ = 'movimientos'

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    medicamento_id = Column(GUID(), ForeignKey('medicamentos.id'))
    tipo = Column(Enum(MovimientoTipoEnum), nullable=False)
    cantidad = Column(Integer, nullable=False)
    usuario_id = Column(String(100), nullable=True)
    motivo = Column(String(200), nullable=True)
    fecha = Column(DateTime, server_default=func.now())

    medicamento = relationship('Medicamento', back_populates='movimientos')


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    entidad = Column(String(100), nullable=False)
    entidad_id = Column(GUID(), nullable=False)
    usuario_id = Column(String(100), nullable=True)
    accion = Column(String(50), nullable=False)
    campo = Column(String(200), nullable=True)
    valor_anterior = Column(String(1000), nullable=True)
    valor_nuevo = Column(String(1000), nullable=True)
    metadatos = Column(JSON, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())


class UserRoleEnum(enum.Enum):
    ADMIN = 'admin'
    FARMACEUTICO = 'farmaceutico'
    COMPRAS = 'compras'


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        UniqueConstraint('username', name='uq_users_username'),
        UniqueConstraint('email', name='uq_users_email'),
    )

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), nullable=False)
    full_name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.FARMACEUTICO, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class TipoAlertaEnum(enum.Enum):
    STOCK_MINIMO = 'STOCK_MINIMO'
    STOCK_CRITICO = 'STOCK_CRITICO'
    STOCK_AGOTADO = 'STOCK_AGOTADO'
    VENCIMIENTO_PROXIMO = 'VENCIMIENTO_PROXIMO'
    VENCIMIENTO_INMEDIATO = 'VENCIMIENTO_INMEDIATO'
    VENCIDO = 'VENCIDO'
    ORDEN_RETRASADA = 'ORDEN_RETRASADA'  # HU-4.02: Alertas de órdenes retrasadas


class EstadoAlertaEnum(enum.Enum):
    ACTIVA = 'ACTIVA'
    PENDIENTE_REPOSICION = 'PENDIENTE_REPOSICION'
    RESUELTA = 'RESUELTA'


class PrioridadAlertaEnum(enum.Enum):
    BAJA = 'BAJA'
    MEDIA = 'MEDIA'
    ALTA = 'ALTA'
    CRITICA = 'CRITICA'


class Alerta(Base):
    """
    Modelo para sistema de alertas automatizado.
    HU-2.01: Alertas de stock bajo
    HU-2.02: Alertas de vencimiento
    HU-4.02: Alertas de órdenes retrasadas
    
    Incluye:
    - Persistencia de alertas generadas
    - Historial completo con estados
    - Priorización automática
    - Trazabilidad de acciones
    """
    __tablename__ = 'alertas'
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    medicamento_id = Column(GUID(), ForeignKey('medicamentos.id'), nullable=True)  # Nullable para alertas de órdenes
    tipo = Column(Enum(TipoAlertaEnum), nullable=False)
    estado = Column(Enum(EstadoAlertaEnum), default=EstadoAlertaEnum.ACTIVA, nullable=False)
    prioridad = Column(Enum(PrioridadAlertaEnum), nullable=False)
    mensaje = Column(String(500), nullable=False)
    
    # Datos específicos para alertas de stock
    stock_actual = Column(Integer, nullable=True)
    stock_minimo = Column(Integer, nullable=True)
    
    # Datos específicos para alertas de vencimiento
    fecha_vencimiento = Column(Date, nullable=True)
    dias_restantes = Column(Integer, nullable=True)
    lote = Column(String(100), nullable=True)
    
    # Metadatos adicionales
    metadatos = Column(JSON, nullable=True)
    
    # Auditoría y trazabilidad
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
    resuelta_at = Column(DateTime, nullable=True)
    resuelta_by = Column(String(100), nullable=True)
    notificada = Column(Boolean, default=False)
    notificada_at = Column(DateTime, nullable=True)
    
    # Relación con medicamento
    medicamento = relationship('Medicamento', backref='alertas')


class EstadoProveedorEnum(enum.Enum):
    ACTIVO = 'ACTIVO'
    INACTIVO = 'INACTIVO'


class Proveedor(Base):
    """
    Modelo para gestión de proveedores.
    HU-4.01: Manejo de Proveedores
    
    Incluye:
    - Información básica del proveedor
    - Validación de NIT único
    - Control de estado ACTIVO/INACTIVO
    - Auditoría de creación y modificación
    """
    __tablename__ = 'proveedores'
    __table_args__ = (
        UniqueConstraint('nit', name='uq_proveedores_nit'),
    )
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    nit = Column(String(50), nullable=False, unique=True)  # Validación numérica en service
    nombre = Column(String(200), nullable=False)
    telefono = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)  # Validación de formato en schema
    direccion = Column(String(500), nullable=True)
    estado = Column(Enum(EstadoProveedorEnum), default=EstadoProveedorEnum.ACTIVO, nullable=False)
    
    # Auditoría
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
    
    # Relaciones
    ordenes_compra = relationship('OrdenCompra', back_populates='proveedor')


class EstadoOrdenEnum(enum.Enum):
    PENDIENTE = 'PENDIENTE'
    ENVIADA = 'ENVIADA'
    RECIBIDA = 'RECIBIDA'
    RETRASADA = 'RETRASADA'


class OrdenCompra(Base):
    """
    Modelo para gestión de órdenes de compra.
    HU-4.02: Post-Orden
    
    Incluye:
    - Gestión de estados del ciclo de vida de la orden
    - Detección automática de retrasos
    - Trazabilidad completa
    - Relación con proveedor y detalles (productos)
    """
    __tablename__ = 'ordenes_compra'
    __table_args__ = (
        UniqueConstraint('numero_orden', name='uq_ordenes_numero'),
    )
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    numero_orden = Column(String(50), nullable=False, unique=True)  # Ej: OC-2025-0001
    proveedor_id = Column(GUID(), ForeignKey('proveedores.id'), nullable=False)
    
    # Fechas
    fecha_creacion = Column(DateTime, server_default=func.now())
    fecha_prevista_entrega = Column(Date, nullable=False)
    fecha_envio = Column(DateTime, nullable=True)
    fecha_recepcion = Column(DateTime, nullable=True)
    
    # Estado y observaciones
    estado = Column(Enum(EstadoOrdenEnum), default=EstadoOrdenEnum.PENDIENTE, nullable=False)
    observaciones = Column(String(1000), nullable=True)
    
    # Total calculado
    total_estimado = Column(Numeric(12, 2), nullable=False, server_default="0")
    
    # Auditoría
    created_by = Column(String(100), nullable=True)
    recibido_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
    
    # Relaciones
    proveedor = relationship('Proveedor', back_populates='ordenes_compra')
    detalles = relationship('DetalleOrdenCompra', back_populates='orden', cascade='all, delete-orphan')


class DetalleOrdenCompra(Base):
    """
    Modelo para items/productos de una orden de compra.
    HU-4.02: Detalle de productos en orden
    
    Incluye:
    - Productos solicitados vs recibidos
    - Precios unitarios y subtotales
    - Información de lote esperado
    """
    __tablename__ = 'detalle_orden_compra'
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    orden_compra_id = Column(GUID(), ForeignKey('ordenes_compra.id'), nullable=False)
    medicamento_id = Column(GUID(), ForeignKey('medicamentos.id'), nullable=False)
    
    # Cantidades
    cantidad_solicitada = Column(Integer, nullable=False)
    cantidad_recibida = Column(Integer, nullable=False, default=0)
    
    # Precios
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)  # cantidad_solicitada * precio_unitario
    
    # Información esperada del lote
    lote_esperado = Column(String(100), nullable=True)
    fecha_vencimiento_esperada = Column(Date, nullable=True)
    
    # Relaciones
    orden = relationship('OrdenCompra', back_populates='detalles')
    medicamento = relationship('Medicamento')


class EstadoVentaEnum(enum.Enum):
    PENDIENTE = 'PENDIENTE'
    CONFIRMADA = 'CONFIRMADA'
    CANCELADA = 'CANCELADA'


class MetodoPagoEnum(enum.Enum):
    EFECTIVO = 'EFECTIVO'
    TARJETA = 'TARJETA'
    TRANSFERENCIA = 'TRANSFERENCIA'
    OTRO = 'OTRO'


class Venta(Base):
    """
    Modelo para registro de ventas.
    HU-3.01: Registro de Ventas
    
    Incluye:
    - Registro de venta con estado
    - Método de pago
    - Totales calculados
    - Auditoría completa
    """
    __tablename__ = 'ventas'
    __table_args__ = (
        UniqueConstraint('numero_venta', name='uq_ventas_numero'),
    )
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    numero_venta = Column(String(50), nullable=False, unique=True)  # Ej: VT-2025-0001
    
    # Fechas y estado
    fecha_venta = Column(DateTime, server_default=func.now())
    estado = Column(Enum(EstadoVentaEnum), default=EstadoVentaEnum.PENDIENTE, nullable=False)
    
    # Pago
    metodo_pago = Column(Enum(MetodoPagoEnum), nullable=True)
    total = Column(Numeric(12, 2), nullable=False, server_default="0")
    
    # Cliente (opcional)
    cliente_nombre = Column(String(200), nullable=True)
    cliente_documento = Column(String(50), nullable=True)
    
    # Observaciones
    observaciones = Column(String(500), nullable=True)
    
    # Auditoría
    created_by = Column(String(100), nullable=True)  # Usuario que registró la venta
    created_at = Column(DateTime, server_default=func.now())
    confirmada_at = Column(DateTime, nullable=True)
    cancelada_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
    
    # Relaciones
    detalles = relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')


class DetalleVenta(Base):
    """
    Modelo para items/productos de una venta.
    HU-3.01: Detalle de productos vendidos
    
    Incluye:
    - Productos vendidos con cantidades
    - Precios y subtotales
    - Trazabilidad de lotes (FIFO/FEFO)
    """
    __tablename__ = 'detalle_venta'
    
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    venta_id = Column(GUID(), ForeignKey('ventas.id'), nullable=False)
    medicamento_id = Column(GUID(), ForeignKey('medicamentos.id'), nullable=False)
    
    # Cantidades y precios
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)  # cantidad * precio_unitario
    
    # Información del lote (para trazabilidad FIFO/FEFO)
    lote = Column(String(100), nullable=True)
    
    # Relaciones
    venta = relationship('Venta', back_populates='detalles')
    medicamento = relationship('Medicamento')

