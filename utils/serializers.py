"""
Utilidades para serialización de modelos a DTOs.
"""
from database.models import OrdenCompra, DetalleOrdenCompra
from datetime import date


def serialize_orden_compra(orden: OrdenCompra) -> dict:
    """
    Serializa una orden de compra incluyendo datos anidados del proveedor y medicamentos.
    
    Resuelve el problema de campos nulos en:
    - proveedor_nombre
    - proveedor_nit
    - medicamento_nombre
    - medicamento_fabricante
    - medicamento_presentacion
    """
    # Datos del proveedor
    proveedor_nombre = None
    proveedor_nit = None
    if orden.proveedor:
        proveedor_nombre = orden.proveedor.nombre
        proveedor_nit = orden.proveedor.nit
    
    # Serializar detalles con información del medicamento
    detalles_serializados = []
    for detalle in orden.detalles:
        detalle_dict = {
            'id': str(detalle.id),
            'orden_compra_id': str(detalle.orden_compra_id),
            'medicamento_id': str(detalle.medicamento_id),
            'cantidad_solicitada': detalle.cantidad_solicitada,
            'cantidad_recibida': detalle.cantidad_recibida,
            'precio_unitario': float(detalle.precio_unitario),
            'subtotal': float(detalle.subtotal),
            'lote_esperado': detalle.lote_esperado,
            'fecha_vencimiento_esperada': detalle.fecha_vencimiento_esperada.isoformat() if detalle.fecha_vencimiento_esperada else None,
            # Datos del medicamento
            'medicamento_nombre': detalle.medicamento.nombre if detalle.medicamento else None,
            'medicamento_fabricante': detalle.medicamento.fabricante if detalle.medicamento else None,
            'medicamento_presentacion': detalle.medicamento.presentacion if detalle.medicamento else None,
        }
        detalles_serializados.append(detalle_dict)
    
    # Calcular días hasta entrega
    dias_hasta_entrega = None
    esta_retrasada = False
    if orden.estado.value in ['PENDIENTE', 'ENVIADA', 'RETRASADA']:
        hoy = date.today()
        delta = orden.fecha_prevista_entrega - hoy
        dias_hasta_entrega = delta.days
        esta_retrasada = dias_hasta_entrega < 0 and orden.estado.value != 'RECIBIDA'
    
    return {
        'id': str(orden.id),
        'numero_orden': orden.numero_orden,
        'proveedor_id': str(orden.proveedor_id),
        'proveedor_nombre': proveedor_nombre,
        'proveedor_nit': proveedor_nit,
        'fecha_creacion': orden.fecha_creacion.isoformat(),
        'fecha_prevista_entrega': orden.fecha_prevista_entrega.isoformat(),
        'fecha_envio': orden.fecha_envio.isoformat() if orden.fecha_envio else None,
        'fecha_recepcion': orden.fecha_recepcion.isoformat() if orden.fecha_recepcion else None,
        'estado': orden.estado.value,
        'observaciones': orden.observaciones,
        'total_estimado': float(orden.total_estimado),
        'created_by': orden.created_by,
        'recibido_by': orden.recibido_by,
        'updated_at': orden.updated_at.isoformat() if orden.updated_at else None,
        'detalles': detalles_serializados,
        'dias_hasta_entrega': dias_hasta_entrega,
        'esta_retrasada': esta_retrasada
    }
