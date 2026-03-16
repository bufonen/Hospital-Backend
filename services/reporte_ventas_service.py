"""
Service para reportes y proyecciones de ventas.
HU-3.02: Reporte y Proyección de Ventas
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date
from database.models import (
    Venta, DetalleVenta, Medicamento,
    EstadoVentaEnum
)
from typing import Dict, Any, List
from datetime import date, datetime, timedelta
from decimal import Decimal
from collections import defaultdict
import statistics


class ReporteVentasService:
    """
    Service para reportes y proyecciones de ventas.
    
    HU-3.02: Análisis de ventas y proyecciones de demanda
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def generar_reporte_ventas(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        medicamento_id: str = None,
        estado: str = None
    ) -> Dict[str, Any]:
        """
        Genera reporte de ventas por período.
        
        HU-3.02: "Given que ingreso un rango de fechas válido
                  When genero el reporte de ventas
                  Then veo una tabla con medicamentos vendidos, unidades e ingresos"
        
        Returns:
            Dict con ventas consolidadas por medicamento
        """
        try:
            # Query: Detalles de ventas en el rango
            query = self.db.query(
                DetalleVenta.medicamento_id,
                Medicamento.nombre.label('medicamento_nombre'),
                Medicamento.fabricante.label('medicamento_fabricante'),
                Medicamento.presentacion.label('medicamento_presentacion'),
                func.sum(DetalleVenta.cantidad).label('total_unidades'),
                func.sum(DetalleVenta.subtotal).label('total_ingresos'),
                func.count(Venta.id.distinct()).label('numero_ventas'),
                func.avg(DetalleVenta.precio_unitario).label('precio_promedio')
            ).join(
                Venta, DetalleVenta.venta_id == Venta.id
            ).join(
                Medicamento, DetalleVenta.medicamento_id == Medicamento.id
            ).filter(
                and_(
                    cast(Venta.fecha_venta, Date) >= fecha_inicio,
                    cast(Venta.fecha_venta, Date) <= fecha_fin
                )
            )
            
            # Filtro opcional por estado
            if estado:
                query = query.filter(Venta.estado == estado)
            else:
                # Por defecto, solo ventas confirmadas
                query = query.filter(Venta.estado == EstadoVentaEnum.CONFIRMADA)
            
            # Filtro opcional por medicamento
            if medicamento_id:
                query = query.filter(DetalleVenta.medicamento_id == medicamento_id)
            
            # Agrupar
            query = query.group_by(
                DetalleVenta.medicamento_id,
                Medicamento.nombre,
                Medicamento.fabricante,
                Medicamento.presentacion
            )
            
            resultados = query.all()
            
            # Si no hay datos
            if not resultados:
                return {
                    'ok': True,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin,
                    'total_ventas': 0,
                    'total_medicamentos': 0,
                    'gran_total_ingresos': 0.0,
                    'ventas_por_medicamento': [],
                    'mensaje': 'No se encontraron ventas en este período'
                }
            
            # Construir respuesta
            ventas_por_medicamento = []
            gran_total = Decimal('0')
            total_ventas = 0
            
            for row in resultados:
                total_ingresos = Decimal(str(row.total_ingresos))
                total_unidades = int(row.total_unidades)
                precio_promedio = Decimal(str(row.precio_promedio)) if row.precio_promedio else Decimal('0')
                
                ventas_por_medicamento.append({
                    'medicamento_id': str(row.medicamento_id),
                    'medicamento_nombre': row.medicamento_nombre,
                    'medicamento_fabricante': row.medicamento_fabricante,
                    'medicamento_presentacion': row.medicamento_presentacion,
                    'total_unidades': total_unidades,
                    'total_ingresos': float(total_ingresos),
                    'numero_ventas': int(row.numero_ventas),
                    'precio_promedio': float(precio_promedio)
                })
                
                gran_total += total_ingresos
                total_ventas += int(row.numero_ventas)
            
            # Ordenar por ingresos (mayor a menor)
            ventas_por_medicamento.sort(key=lambda x: x['total_ingresos'], reverse=True)
            
            return {
                'ok': True,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'total_ventas': total_ventas,
                'total_medicamentos': len(ventas_por_medicamento),
                'gran_total_ingresos': float(gran_total),
                'ventas_por_medicamento': ventas_por_medicamento,
                'mensaje': None
            }
            
        except Exception as e:
            print(f"Error en generar_reporte_ventas: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al generar reporte: {str(e)}'
            }
    
    def generar_proyeccion_demanda(
        self,
        periodo_dias: int = 90,
        meses_historico: int = 12,
        medicamento_id: str = None
    ) -> Dict[str, Any]:
        """
        Genera proyección de demanda basada en historial de ventas.
        
        HU-3.02: "Given historial ventas 12 meses,
                  When solicito proyección a 90 días,
                  Then muestro estimación por medicamento y gráfico de tendencia"
        
        Método: Promedio móvil simple
        
        Reglas de negocio:
        - Mínimo 6 meses de historial
        - Proyección = (Promedio mensual) * (Período en meses)
        
        Returns:
            Dict con proyecciones por medicamento
        """
        try:
            # Calcular fecha de corte
            fecha_actual = date.today()
            fecha_inicio_historico = fecha_actual - timedelta(days=meses_historico * 30)
            
            # Query: Ventas confirmadas en el período histórico
            query = self.db.query(
                DetalleVenta.medicamento_id,
                Medicamento.nombre.label('medicamento_nombre'),
                Medicamento.fabricante.label('medicamento_fabricante'),
                Medicamento.presentacion.label('medicamento_presentacion'),
                func.sum(DetalleVenta.cantidad).label('total_historico'),
                func.count(func.distinct(cast(Venta.fecha_venta, Date))).label('dias_con_ventas')
            ).join(
                Venta, DetalleVenta.venta_id == Venta.id
            ).join(
                Medicamento, DetalleVenta.medicamento_id == Medicamento.id
            ).filter(
                and_(
                    Venta.estado == EstadoVentaEnum.CONFIRMADA,
                    cast(Venta.fecha_venta, Date) >= fecha_inicio_historico,
                    cast(Venta.fecha_venta, Date) <= fecha_actual
                )
            )
            
            if medicamento_id:
                query = query.filter(DetalleVenta.medicamento_id == medicamento_id)
            
            query = query.group_by(
                DetalleVenta.medicamento_id,
                Medicamento.nombre,
                Medicamento.fabricante,
                Medicamento.presentacion
            )
            
            resultados = query.all()
            
            # Validar que haya suficiente historial
            if not resultados:
                return {
                    'ok': True,
                    'fecha_corte': fecha_actual,
                    'periodo_proyeccion_dias': periodo_dias,
                    'meses_historial': meses_historico,
                    'proyecciones': [],
                    'mensaje': 'No hay datos suficientes para proyectar demanda',
                    'advertencias': [
                        f'Se requiere al menos 6 meses de historial de ventas'
                    ]
                }
            
            # Generar proyecciones
            proyecciones = []
            advertencias = []
            
            for row in resultados:
                medicamento_id_actual = str(row.medicamento_id)
                total_historico = int(row.total_historico)
                dias_con_ventas = int(row.dias_con_ventas)
                
                # Obtener stock actual (sumar todos los lotes)
                stock_actual = self.db.query(func.sum(Medicamento.stock)).filter(
                    Medicamento.nombre == row.medicamento_nombre,
                    Medicamento.fabricante == row.medicamento_fabricante,
                    Medicamento.presentacion == row.medicamento_presentacion,
                    Medicamento.is_deleted == False
                ).scalar() or 0
                
                # Calcular promedio mensual
                meses_reales = meses_historico
                promedio_mensual = Decimal(str(total_historico)) / Decimal(str(meses_reales))
                
                # Proyección para el período solicitado
                meses_proyeccion = Decimal(str(periodo_dias)) / Decimal('30')
                demanda_proyectada = promedio_mensual * meses_proyeccion
                
                # Calcular stock recomendado (demanda proyectada + 20% de margen)
                stock_recomendado = int(demanda_proyectada * Decimal('1.2'))
                
                # Determinar si requiere reposición
                requiere_reposicion = stock_actual < stock_recomendado
                
                # Determinar tendencia (comparar últimos 3 meses vs anteriores)
                fecha_mitad = fecha_actual - timedelta(days=int(meses_historico * 15))
                
                ventas_recientes = self.db.query(func.sum(DetalleVenta.cantidad)).join(
                    Venta, DetalleVenta.venta_id == Venta.id
                ).filter(
                    and_(
                        DetalleVenta.medicamento_id == medicamento_id_actual,
                        Venta.estado == EstadoVentaEnum.CONFIRMADA,
                        cast(Venta.fecha_venta, Date) >= fecha_mitad
                    )
                ).scalar() or 0
                
                ventas_antiguas = self.db.query(func.sum(DetalleVenta.cantidad)).join(
                    Venta, DetalleVenta.venta_id == Venta.id
                ).filter(
                    and_(
                        DetalleVenta.medicamento_id == medicamento_id_actual,
                        Venta.estado == EstadoVentaEnum.CONFIRMADA,
                        cast(Venta.fecha_venta, Date) >= fecha_inicio_historico,
                        cast(Venta.fecha_venta, Date) < fecha_mitad
                    )
                ).scalar() or 0
                
                # Determinar tendencia
                if ventas_antiguas == 0:
                    tendencia = "SIN_DATOS"
                    confianza = "BAJA"
                elif ventas_recientes > ventas_antiguas * 1.2:
                    tendencia = "CRECIENTE"
                    confianza = "ALTA" if dias_con_ventas > 90 else "MEDIA"
                elif ventas_recientes < ventas_antiguas * 0.8:
                    tendencia = "DECRECIENTE"
                    confianza = "ALTA" if dias_con_ventas > 90 else "MEDIA"
                else:
                    tendencia = "ESTABLE"
                    confianza = "ALTA" if dias_con_ventas > 90 else "MEDIA"
                
                # Ajustar confianza según historial
                if meses_historico < 6:
                    confianza = "BAJA"
                    advertencias.append(
                        f"{row.medicamento_nombre}: Menos de 6 meses de historial"
                    )
                
                proyecciones.append({
                    'medicamento_id': medicamento_id_actual,
                    'medicamento_nombre': row.medicamento_nombre,
                    'medicamento_fabricante': row.medicamento_fabricante,
                    'medicamento_presentacion': row.medicamento_presentacion,
                    'promedio_mensual': float(promedio_mensual),
                    'total_historico': total_historico,
                    'meses_con_datos': meses_reales,
                    'demanda_proyectada': float(demanda_proyectada),
                    'stock_actual': int(stock_actual),
                    'stock_recomendado': stock_recomendado,
                    'requiere_reposicion': requiere_reposicion,
                    'tendencia': tendencia,
                    'confianza': confianza
                })
            
            # Ordenar por demanda proyectada (mayor a menor)
            proyecciones.sort(key=lambda x: x['demanda_proyectada'], reverse=True)
            
            return {
                'ok': True,
                'fecha_corte': fecha_actual,
                'periodo_proyeccion_dias': periodo_dias,
                'meses_historial': meses_historico,
                'proyecciones': proyecciones,
                'mensaje': None,
                'advertencias': list(set(advertencias))  # Eliminar duplicados
            }
            
        except Exception as e:
            print(f"Error en generar_proyeccion_demanda: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al generar proyección: {str(e)}'
            }
    
    def obtener_estadisticas_ventas(
        self,
        fecha_inicio: date = None,
        fecha_fin: date = None
    ) -> Dict[str, Any]:
        """Obtiene estadísticas generales de ventas"""
        try:
            if not fecha_inicio:
                fecha_inicio = date.today() - timedelta(days=30)
            if not fecha_fin:
                fecha_fin = date.today()
            
            # Ventas confirmadas
            ventas_confirmadas = self.db.query(func.count(Venta.id)).filter(
                and_(
                    Venta.estado == EstadoVentaEnum.CONFIRMADA,
                    cast(Venta.fecha_venta, Date) >= fecha_inicio,
                    cast(Venta.fecha_venta, Date) <= fecha_fin
                )
            ).scalar() or 0
            
            # Ventas pendientes
            ventas_pendientes = self.db.query(func.count(Venta.id)).filter(
                Venta.estado == EstadoVentaEnum.PENDIENTE
            ).scalar() or 0
            
            # Total ingresos
            total_ingresos = self.db.query(func.sum(Venta.total)).filter(
                and_(
                    Venta.estado == EstadoVentaEnum.CONFIRMADA,
                    cast(Venta.fecha_venta, Date) >= fecha_inicio,
                    cast(Venta.fecha_venta, Date) <= fecha_fin
                )
            ).scalar() or Decimal('0')
            
            # Promedio por venta
            promedio_venta = total_ingresos / ventas_confirmadas if ventas_confirmadas > 0 else Decimal('0')
            
            # Medicamento más vendido
            medicamento_top = self.db.query(
                Medicamento.nombre,
                func.sum(DetalleVenta.cantidad).label('total')
            ).join(
                DetalleVenta, Medicamento.id == DetalleVenta.medicamento_id
            ).join(
                Venta, DetalleVenta.venta_id == Venta.id
            ).filter(
                and_(
                    Venta.estado == EstadoVentaEnum.CONFIRMADA,
                    cast(Venta.fecha_venta, Date) >= fecha_inicio,
                    cast(Venta.fecha_venta, Date) <= fecha_fin
                )
            ).group_by(
                Medicamento.nombre
            ).order_by(
                func.sum(DetalleVenta.cantidad).desc()
            ).first()
            
            return {
                'ok': True,
                'total_ventas_confirmadas': ventas_confirmadas,
                'total_ventas_pendientes': ventas_pendientes,
                'total_ingresos': float(total_ingresos),
                'medicamento_mas_vendido': medicamento_top[0] if medicamento_top else None,
                'promedio_venta': float(promedio_venta),
                'periodo_analizado': f'{fecha_inicio} - {fecha_fin}'
            }
            
        except Exception as e:
            print(f"Error en obtener_estadisticas_ventas: {e}")
            return {
                'ok': False,
                'error': 'database_error',
                'message': f'Error al obtener estadísticas: {str(e)}'
            }
