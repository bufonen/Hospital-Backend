"""
Service para generación de reportes de compras.
HU-4.03: Comparación de Precios
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database.models import (
    OrdenCompra, DetalleOrdenCompra, Proveedor, Medicamento,
    EstadoOrdenEnum, EstadoProveedorEnum
)
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from decimal import Decimal
from collections import defaultdict


class ReporteService:
    """
    Service para lógica de reportes de compras.
    
    HU-4.03: Comparación de precios y reportes consolidados.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def comparar_precios(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        medicamento_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compara precios entre proveedores por medicamento.
        
        HU-4.03: "Given 3 proveedores con precios distintos,
                  When ejecuto comparativo en rango 6 meses,
                  Then muestro tabla por medicamento y promedio precio proveedor"
        
        Returns:
            Dict con estructura de ComparacionPreciosResponse
        """
        try:
            # Query base: Detalles de órdenes RECIBIDAS en el rango
            query = self.db.query(
                DetalleOrdenCompra.medicamento_id,
                Medicamento.nombre.label('medicamento_nombre'),
                Medicamento.fabricante.label('medicamento_fabricante'),
                Medicamento.presentacion.label('medicamento_presentacion'),
                OrdenCompra.proveedor_id,
                Proveedor.nombre.label('proveedor_nombre'),
                Proveedor.nit.label('proveedor_nit'),
                func.sum(DetalleOrdenCompra.cantidad_solicitada).label('total_unidades'),
                func.sum(DetalleOrdenCompra.subtotal).label('total_dinero'),
                func.count(OrdenCompra.id.distinct()).label('numero_ordenes')
            ).join(
                OrdenCompra, DetalleOrdenCompra.orden_compra_id == OrdenCompra.id
            ).join(
                Medicamento, DetalleOrdenCompra.medicamento_id == Medicamento.id
            ).join(
                Proveedor, OrdenCompra.proveedor_id == Proveedor.id
            ).filter(
                and_(
                    OrdenCompra.estado == EstadoOrdenEnum.RECIBIDA,
                    OrdenCompra.fecha_recepcion >= datetime.combine(fecha_inicio, datetime.min.time()),
                    OrdenCompra.fecha_recepcion < datetime.combine(fecha_fin + timedelta(days=1), datetime.min.time())
                )
            )
            
            # Filtro opcional por medicamento
            if medicamento_id:
                query = query.filter(DetalleOrdenCompra.medicamento_id == medicamento_id)
            
            # Agrupar por medicamento y proveedor
            query = query.group_by(
                DetalleOrdenCompra.medicamento_id,
                Medicamento.nombre,
                Medicamento.fabricante,
                Medicamento.presentacion,
                OrdenCompra.proveedor_id,
                Proveedor.nombre,
                Proveedor.nit
            )
            
            resultados = query.all()
            
            # Si no hay datos
            if not resultados:
                return {
                    'ok': True,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin,
                    'total_medicamentos': 0,
                    'total_proveedores': 0,
                    'comparaciones': [],
                    'mensaje': 'No hay datos suficientes para comparación en el período seleccionado'
                }
            
            # Organizar por medicamento
            medicamentos_dict = defaultdict(lambda: {
                'medicamento_nombre': '',
                'medicamento_fabricante': '',
                'medicamento_presentacion': '',
                'proveedores': []
            })
            
            proveedores_set = set()
            
            for row in resultados:
                med_id = str(row.medicamento_id)
                prov_id = str(row.proveedor_id)
                
                # Información del medicamento
                if not medicamentos_dict[med_id]['medicamento_nombre']:
                    medicamentos_dict[med_id]['medicamento_nombre'] = row.medicamento_nombre
                    medicamentos_dict[med_id]['medicamento_fabricante'] = row.medicamento_fabricante
                    medicamentos_dict[med_id]['medicamento_presentacion'] = row.medicamento_presentacion
                
                # Calcular precio promedio
                total_unidades = int(row.total_unidades)
                total_dinero = Decimal(str(row.total_dinero))
                precio_promedio = total_dinero / total_unidades if total_unidades > 0 else Decimal('0')
                
                # Agregar datos del proveedor
                medicamentos_dict[med_id]['proveedores'].append({
                    'proveedor_id': prov_id,
                    'proveedor_nombre': row.proveedor_nombre,
                    'proveedor_nit': row.proveedor_nit,
                    'total_unidades_compradas': total_unidades,
                    'total_dinero_invertido': float(total_dinero),
                    'precio_promedio': float(precio_promedio),
                    'numero_ordenes': int(row.numero_ordenes)
                })
                
                proveedores_set.add(prov_id)
            
            # Construir lista de comparaciones
            comparaciones = []
            for med_id, med_data in medicamentos_dict.items():
                # Ordenar proveedores por precio promedio (menor a mayor)
                med_data['proveedores'].sort(key=lambda x: x['precio_promedio'])
                
                # Identificar mejor precio
                mejor_precio_proveedor_id = None
                mejor_precio = None
                if med_data['proveedores']:
                    mejor = med_data['proveedores'][0]
                    mejor_precio_proveedor_id = mejor['proveedor_id']
                    mejor_precio = mejor['precio_promedio']
                
                comparaciones.append({
                    'medicamento_id': med_id,
                    'medicamento_nombre': med_data['medicamento_nombre'],
                    'medicamento_fabricante': med_data['medicamento_fabricante'],
                    'medicamento_presentacion': med_data['medicamento_presentacion'],
                    'proveedores': med_data['proveedores'],
                    'mejor_precio_proveedor_id': mejor_precio_proveedor_id,
                    'mejor_precio': mejor_precio
                })
            
            # Ordenar por nombre de medicamento
            comparaciones.sort(key=lambda x: x['medicamento_nombre'])
            
            return {
                'ok': True,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'total_medicamentos': len(medicamentos_dict),
                'total_proveedores': len(proveedores_set),
                'comparaciones': comparaciones,
                'mensaje': None
            }
            
        except Exception as e:
            print(f"Error en comparar_precios: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al generar comparación: {str(e)}'
            }
    
    def generar_reporte_compras(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        proveedor_id: Optional[str] = None,
        medicamento_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera reporte consolidado de compras por período.
        
        HU-4.03: "Given que ingreso un rango de fechas válido
                  When genero el reporte de compras
                  Then veo una tabla con total comprado por proveedor y medicamento"
        
        Returns:
            Dict con estructura de ReporteComprasResponse
        """
        try:
            # Query: Detalles de órdenes RECIBIDAS con orden_id
            query = self.db.query(
                DetalleOrdenCompra.medicamento_id,
                Medicamento.nombre.label('medicamento_nombre'),
                Medicamento.fabricante.label('medicamento_fabricante'),
                Medicamento.presentacion.label('medicamento_presentacion'),
                OrdenCompra.id.label('orden_id'),  # Agregar orden_id
                OrdenCompra.proveedor_id,
                Proveedor.nombre.label('proveedor_nombre'),
                Proveedor.nit.label('proveedor_nit'),
                func.sum(DetalleOrdenCompra.cantidad_solicitada).label('total_unidades'),
                func.sum(DetalleOrdenCompra.subtotal).label('total_dinero'),
                func.count(OrdenCompra.id.distinct()).label('numero_ordenes')
            ).join(
                OrdenCompra, DetalleOrdenCompra.orden_compra_id == OrdenCompra.id
            ).join(
                Medicamento, DetalleOrdenCompra.medicamento_id == Medicamento.id
            ).join(
                Proveedor, OrdenCompra.proveedor_id == Proveedor.id
            ).filter(
                and_(
                    OrdenCompra.estado == EstadoOrdenEnum.RECIBIDA,
                    OrdenCompra.fecha_recepcion >= datetime.combine(fecha_inicio, datetime.min.time()),
                    OrdenCompra.fecha_recepcion < datetime.combine(fecha_fin + timedelta(days=1), datetime.min.time())
                )
            )
            
            # Filtros opcionales
            if proveedor_id:
                query = query.filter(OrdenCompra.proveedor_id == proveedor_id)
            
            if medicamento_id:
                query = query.filter(DetalleOrdenCompra.medicamento_id == medicamento_id)
            
            # Agrupar (incluir orden_id)
            query = query.group_by(
                DetalleOrdenCompra.medicamento_id,
                Medicamento.nombre,
                Medicamento.fabricante,
                Medicamento.presentacion,
                OrdenCompra.id,  # Agregar orden_id al group by
                OrdenCompra.proveedor_id,
                Proveedor.nombre,
                Proveedor.nit
            )
            
            resultados = query.all()
            
            # Si no hay datos
            if not resultados:
                return {
                    'ok': True,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin,
                    'total_ordenes': 0,
                    'total_proveedores': 0,
                    'total_medicamentos': 0,
                    'gran_total_invertido': 0.0,
                    'detalles': [],
                    'totales_por_proveedor': [],
                    'mensaje': 'No se encontraron compras en este período'
                }
            
            # Construir detalles
            detalles = []
            proveedores_dict = defaultdict(lambda: {
                'proveedor_nombre': '',
                'proveedor_nit': '',
                'ordenes_ids': set(),  # Usamos set para IDs únicos, luego convertimos a int
                'total_items': 0,
                'total_invertido': Decimal('0')
            })
            
            gran_total = Decimal('0')
            medicamentos_set = set()
            
            for row in resultados:
                total_unidades = int(row.total_unidades)
                total_dinero = Decimal(str(row.total_dinero))
                precio_promedio = total_dinero / total_unidades if total_unidades > 0 else Decimal('0')
                
                prov_id = str(row.proveedor_id)
                med_id = str(row.medicamento_id)
                orden_id = str(row.orden_id)
                
                #detalle individual
                detalles.append({
                    'medicamento_id': med_id,
                    'medicamento_nombre': row.medicamento_nombre,
                    'medicamento_fabricante': row.medicamento_fabricante,
                    'medicamento_presentacion': row.medicamento_presentacion,
                    'proveedor_id': prov_id,
                    'proveedor_nombre': row.proveedor_nombre,
                    'proveedor_nit': row.proveedor_nit,
                    'total_unidades_compradas': total_unidades,
                    'total_dinero_invertido': float(total_dinero),
                    'numero_ordenes': int(row.numero_ordenes),
                    'precio_promedio': float(precio_promedio)
                })
                
                #acumular por proveedor
                if not proveedores_dict[prov_id]['proveedor_nombre']:
                    proveedores_dict[prov_id]['proveedor_nombre'] = row.proveedor_nombre
                    proveedores_dict[prov_id]['proveedor_nit'] = row.proveedor_nit
                
                #agregar orden_id al set para contar ordenes unicas
                proveedores_dict[prov_id]['ordenes_ids'].add(orden_id)
                proveedores_dict[prov_id]['total_items'] += total_unidades
                proveedores_dict[prov_id]['total_invertido'] += total_dinero
                
                gran_total += total_dinero
                medicamentos_set.add(med_id)
            
            #totales por proveedor
            totales_por_proveedor = []
            for prov_id, prov_data in proveedores_dict.items():
                totales_por_proveedor.append({
                    'proveedor_id': prov_id,
                    'proveedor_nombre': prov_data['proveedor_nombre'],
                    'proveedor_nit': prov_data['proveedor_nit'],
                    'total_ordenes': len(prov_data['ordenes_ids']),  #convertir set a int
                    'total_items': prov_data['total_items'],
                    'total_invertido': float(prov_data['total_invertido'])
                })
            
            #ordenar detalles por medicamento
            detalles.sort(key=lambda x: x['medicamento_nombre'])
            
            #ordenar totales por proveedor
            totales_por_proveedor.sort(key=lambda x: x['proveedor_nombre'])
            
            #contar ordenes unicas
            query_ordenes = self.db.query(func.count(OrdenCompra.id.distinct())).filter(
                and_(
                    OrdenCompra.estado == EstadoOrdenEnum.RECIBIDA,
                    OrdenCompra.fecha_recepcion >= fecha_inicio,
                    OrdenCompra.fecha_recepcion <= fecha_fin
                )
            )
            if proveedor_id:
                query_ordenes = query_ordenes.filter(OrdenCompra.proveedor_id == proveedor_id)
            
            total_ordenes = query_ordenes.scalar() or 0
            
            return {
                'ok': True,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'total_ordenes': total_ordenes,
                'total_proveedores': len(proveedores_dict),
                'total_medicamentos': len(medicamentos_set),
                'gran_total_invertido': float(gran_total),
                'detalles': detalles,
                'totales_por_proveedor': totales_por_proveedor,
                'mensaje': None
            }
            
        except Exception as e:
            print(f"Error en generar_reporte_compras: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al generar reporte: {str(e)}'
            }
            
