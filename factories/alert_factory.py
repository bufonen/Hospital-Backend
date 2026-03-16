"""
Alert Factories - Patrón Abstract Factory para creación de alertas.

Este módulo implementa el patrón Factory para encapsular la lógica de construcción
de diferentes tipos de alertas, separando la creación de la lógica de negocio.

Ventajas:
- Centraliza la lógica de construcción de alertas
- Facilita la extensión (nuevos tipos de alertas)
- Mejora el testing (factories aislados)
- Elimina duplicación de código
- Mantiene el patrón Observer intacto
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from database.models import (
    Alerta, TipoAlertaEnum, EstadoAlertaEnum, 
    PrioridadAlertaEnum, Medicamento, OrdenCompra
)
from uuid import uuid4
from datetime import datetime


class AlertFactory(ABC):
    """
    Factory abstracto base para creación de alertas.
    Define la interfaz común que todos los factories concretos deben implementar.
    
    Responsabilidades:
    - Calcular prioridad según reglas específicas del tipo
    - Generar mensajes descriptivos
    - Construir metadatos estructurados
    - Crear la instancia de Alerta completa
    """
    
    @abstractmethod
    def calculate_priority(self, **kwargs) -> PrioridadAlertaEnum:
        """
        Calcula la prioridad de la alerta según reglas específicas.
        
        Returns:
            PrioridadAlertaEnum: BAJA, MEDIA, ALTA, o CRITICA
        """
        pass
    
    @abstractmethod
    def calculate_type(self, **kwargs) -> TipoAlertaEnum:
        """
        Determina el tipo específico de alerta.
        
        Returns:
            TipoAlertaEnum: Tipo específico de la alerta
        """
        pass
    
    @abstractmethod
    def generate_message(self, **kwargs) -> str:
        """
        Genera el mensaje descriptivo de la alerta.
        
        Returns:
            str: Mensaje legible para el usuario
        """
        pass
    
    @abstractmethod
    def build_metadata(self, **kwargs) -> Dict[str, Any]:
        """
        Construye el diccionario de metadatos específicos del tipo.
        
        Returns:
            Dict[str, Any]: Metadatos estructurados
        """
        pass
    
    @abstractmethod
    def create_alert(self, **kwargs) -> Alerta:
        """
        Crea la instancia completa de Alerta.
        
        Returns:
            Alerta: Instancia lista para persistir
        """
        pass


class StockAlertFactory(AlertFactory):
    """
    Factory para alertas de stock (STOCK_MINIMO, STOCK_CRITICO, STOCK_AGOTADO).
    
    HU-2.01: Alertas de stock bajo
    
    Reglas de prioridad ACTUALIZADAS:
    - stock = 0 → STOCK_AGOTADO / CRITICA
    - stock < minimo → STOCK_CRITICO / ALTA
    - stock == minimo → STOCK_MINIMO / MEDIA
    """
    
    def calculate_type(self, stock: int, minimo_stock: int) -> TipoAlertaEnum:
        """Determina el tipo de alerta de stock según niveles."""
        if stock == 0:
            return TipoAlertaEnum.STOCK_AGOTADO
        elif stock < minimo_stock:
            # CAMBIO: Cualquier stock menor al mínimo es CRÍTICO
            return TipoAlertaEnum.STOCK_CRITICO
        elif stock == minimo_stock:
            return TipoAlertaEnum.STOCK_MINIMO
        else:
            raise ValueError(
                f"No se cumple condición de alerta de stock: "
                f"stock={stock}, minimo={minimo_stock}"
            )
    
    def calculate_priority(self, stock: int, minimo_stock: int) -> PrioridadAlertaEnum:
        """Calcula la prioridad según el nivel de stock."""
        if stock == 0:
            return PrioridadAlertaEnum.CRITICA
        elif stock < minimo_stock:
            # CAMBIO: Cualquier stock menor al mínimo es ALTA prioridad
            return PrioridadAlertaEnum.ALTA
        else:
            return PrioridadAlertaEnum.MEDIA
    
    def generate_message(
        self, 
        medicamento: Medicamento, 
        alert_type: TipoAlertaEnum
    ) -> str:
        """Genera mensaje descriptivo según el tipo de alerta de stock."""
        if alert_type == TipoAlertaEnum.STOCK_AGOTADO:
            return f"Stock agotado: {medicamento.nombre} ({medicamento.presentacion})"
        elif alert_type == TipoAlertaEnum.STOCK_CRITICO:
            return (
                f"Stock crítico: {medicamento.nombre} tiene {medicamento.stock} "
                f"unidades (mínimo: {medicamento.minimo_stock})"
            )
        else:  # STOCK_MINIMO
            return (
                f"Stock mínimo alcanzado: {medicamento.nombre} tiene {medicamento.stock} "
                f"unidades (mínimo: {medicamento.minimo_stock})"
            )
    
    def build_metadata(self, medicamento: Medicamento, **kwargs) -> Dict[str, Any]:
        """Construye metadatos específicos para alertas de stock."""
        return {
            'stock_actual': medicamento.stock,
            'stock_minimo': medicamento.minimo_stock,
            'medicamento_nombre': medicamento.nombre,
            'medicamento_lote': medicamento.lote,
            'medicamento_fabricante': medicamento.fabricante
        }
    
    def create_alert(
        self,
        medicamento: Medicamento,
        alert_type: TipoAlertaEnum = None,
        priority: PrioridadAlertaEnum = None,
        **kwargs
        ) -> Alerta:

        # Usar el tipo y prioridad si vienen desde el servicio
        if alert_type is None:
            alert_type = self.calculate_type(medicamento.stock, medicamento.minimo_stock)

        if priority is None:
            priority = self.calculate_priority(medicamento.stock, medicamento.minimo_stock)

        # Generar mensaje
        message = self.generate_message(medicamento, alert_type)

        # Construir metadatos
        metadata = self.build_metadata(medicamento)

        # Crear instancia
        return Alerta(
            id=str(uuid4()),
            medicamento_id=medicamento.id,
            tipo=alert_type,
            estado=EstadoAlertaEnum.ACTIVA,
            prioridad=priority,
            mensaje=message,
            stock_actual=medicamento.stock,
            stock_minimo=medicamento.minimo_stock,
            metadatos=metadata
        )



class ExpirationAlertFactory(AlertFactory):
    """
    Factory para alertas de vencimiento (VENCIMIENTO_PROXIMO, VENCIMIENTO_INMEDIATO, VENCIDO).
    
    HU-2.02: Alertas de vencimiento
    
    Reglas de prioridad:
    - dias < 0 → VENCIDO / CRITICA
    - dias <= 7 → VENCIMIENTO_INMEDIATO / ALTA
    - dias <= 30 → VENCIMIENTO_PROXIMO / MEDIA
    """
    
    def calculate_type(self, dias_restantes: int) -> TipoAlertaEnum:
        """Determina el tipo de alerta de vencimiento según días restantes."""
        if dias_restantes < 0:
            return TipoAlertaEnum.VENCIDO
        elif dias_restantes <= 7:
            return TipoAlertaEnum.VENCIMIENTO_INMEDIATO
        elif dias_restantes <= 30:
            return TipoAlertaEnum.VENCIMIENTO_PROXIMO
        else:
            raise ValueError(
                f"No se cumple condición de alerta de vencimiento: "
                f"dias_restantes={dias_restantes}"
            )
    
    def calculate_priority(self, dias_restantes: int) -> PrioridadAlertaEnum:
        """Calcula la prioridad según días restantes hasta vencimiento."""
        if dias_restantes < 0:
            return PrioridadAlertaEnum.CRITICA
        elif dias_restantes <= 7:
            return PrioridadAlertaEnum.ALTA
        else:
            return PrioridadAlertaEnum.MEDIA
    
    def generate_message(
        self, 
        medicamento: Medicamento, 
        alert_type: TipoAlertaEnum,
        dias_restantes: int
    ) -> str:
        """Genera mensaje descriptivo según el tipo de alerta de vencimiento."""
        if alert_type == TipoAlertaEnum.VENCIDO:
            return (
                f"VENCIDO: {medicamento.nombre} (lote {medicamento.lote}) "
                f"venció hace {abs(dias_restantes)} días"
            )
        elif alert_type == TipoAlertaEnum.VENCIMIENTO_INMEDIATO:
            return (
                f"Vencimiento inmediato: {medicamento.nombre} (lote {medicamento.lote}) "
                f"vence en {dias_restantes} días"
            )
        else:  # VENCIMIENTO_PROXIMO
            return (
                f"Vencimiento próximo: {medicamento.nombre} (lote {medicamento.lote}) "
                f"vence en {dias_restantes} días"
            )
    
    def build_metadata(
        self, 
        medicamento: Medicamento, 
        dias_restantes: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Construye metadatos específicos para alertas de vencimiento."""
        return {
            'fecha_vencimiento': str(medicamento.fecha_vencimiento),
            'dias_restantes': dias_restantes,
            'lote': medicamento.lote,
            'medicamento_nombre': medicamento.nombre,
            'medicamento_fabricante': medicamento.fabricante
        }
    
    def create_alert(
        self, 
        medicamento: Medicamento, 
        dias_restantes: int,
        **kwargs
    ) -> Alerta:
        """
        Crea una alerta de vencimiento completa.
        
        Args:
            medicamento: Instancia del medicamento próximo a vencer
            dias_restantes: Días restantes hasta vencimiento (puede ser negativo)
        
        Returns:
            Alerta: Instancia lista para persistir
        """
        # Calcular tipo y prioridad
        alert_type = self.calculate_type(dias_restantes)
        priority = self.calculate_priority(dias_restantes)
        
        # Generar mensaje
        message = self.generate_message(medicamento, alert_type, dias_restantes)
        
        # Construir metadatos
        metadata = self.build_metadata(medicamento, dias_restantes)
        
        # Crear instancia
        return Alerta(
            id=str(uuid4()),
            medicamento_id=medicamento.id,
            tipo=alert_type,
            estado=EstadoAlertaEnum.ACTIVA,
            prioridad=priority,
            mensaje=message,
            fecha_vencimiento=medicamento.fecha_vencimiento,
            dias_restantes=dias_restantes,
            lote=medicamento.lote,
            metadatos=metadata
        )


class OrdenRetrasadaAlertFactory(AlertFactory):
    """
    Factory para alertas de órdenes retrasadas (ORDEN_RETRASADA).
    
    HU-4.02: Alertas de órdenes retrasadas
    
    Reglas de prioridad:
    - dias >= 7 → CRITICA
    - dias >= 3 → ALTA
    - dias < 3 → MEDIA
    """
    
    def calculate_type(self, **kwargs) -> TipoAlertaEnum:
        """Las órdenes retrasadas siempre son del mismo tipo."""
        return TipoAlertaEnum.ORDEN_RETRASADA
    
    def calculate_priority(self, dias_retraso: int) -> PrioridadAlertaEnum:
        """Calcula la prioridad según días de retraso."""
        if dias_retraso >= 7:
            return PrioridadAlertaEnum.CRITICA
        elif dias_retraso >= 3:
            return PrioridadAlertaEnum.ALTA
        else:
            return PrioridadAlertaEnum.MEDIA
    
    def generate_message(
        self, 
        orden: OrdenCompra, 
        dias_retraso: int
    ) -> str:
        """Genera mensaje descriptivo para orden retrasada."""
        plural = 's' if dias_retraso != 1 else ''
        return (
            f"Orden {orden.numero_orden} retrasada {dias_retraso} día{plural}. "
            f"Proveedor: {orden.proveedor.nombre}"
        )
    
    def build_metadata(
        self, 
        orden: OrdenCompra, 
        dias_retraso: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Construye metadatos específicos para alertas de órdenes."""
        return {
            'orden_id': str(orden.id),
            'numero_orden': orden.numero_orden,
            'proveedor_id': str(orden.proveedor_id),
            'proveedor_nombre': orden.proveedor.nombre,
            'proveedor_nit': orden.proveedor.nit,
            'fecha_prevista': str(orden.fecha_prevista_entrega),
            'dias_retraso': dias_retraso,
            'total_estimado': float(orden.total_estimado)
        }
    
    def create_alert(
        self, 
        orden: OrdenCompra, 
        dias_retraso: int,
        **kwargs
    ) -> Alerta:
        """
        Crea una alerta de orden retrasada completa.
        
        Args:
            orden: Instancia de la orden retrasada
            dias_retraso: Cantidad de días de retraso
        
        Returns:
            Alerta: Instancia lista para persistir
        """
        # Calcular tipo y prioridad
        alert_type = self.calculate_type()
        priority = self.calculate_priority(dias_retraso)
        
        # Generar mensaje
        message = self.generate_message(orden, dias_retraso)
        
        # Construir metadatos
        metadata = self.build_metadata(orden, dias_retraso)
        
        # Crear instancia
        return Alerta(
            id=str(uuid4()),
            medicamento_id=None,  # Órdenes no están asociadas a medicamentos específicos
            tipo=alert_type,
            estado=EstadoAlertaEnum.ACTIVA,
            prioridad=priority,
            mensaje=message,
            metadatos=metadata
        )


class AlertFactoryRegistry:
    """
    Registry centralizado para acceder a los factories.
    Implementa el patrón Singleton para mantener una única instancia de cada factory.
    
    Uso:
        factory = AlertFactoryRegistry.get_factory('stock')
        alerta = factory.create_alert(medicamento=med)
    """
    
    # Instancias singleton de cada factory
    _factories: Dict[str, AlertFactory] = {
        'stock': StockAlertFactory(),
        'expiration': ExpirationAlertFactory(),
        'orden_retrasada': OrdenRetrasadaAlertFactory()
    }
    
    @classmethod
    def get_factory(cls, alert_category: str) -> AlertFactory:
        """
        Obtiene el factory apropiado según la categoría.
        
        Args:
            alert_category: Categoría de alerta ('stock', 'expiration', 'orden_retrasada')
        
        Returns:
            AlertFactory: Factory correspondiente
        
        Raises:
            ValueError: Si la categoría no está registrada
        """
        factory = cls._factories.get(alert_category)
        if not factory:
            raise ValueError(
                f"No factory registered for category: {alert_category}. "
                f"Available: {list(cls._factories.keys())}"
            )
        return factory
    
    @classmethod
    def register_factory(cls, category: str, factory: AlertFactory):
        """
        Registra un nuevo factory (útil para extensiones futuras).
        
        Args:
            category: Nombre de la categoría
            factory: Instancia del factory
        """
        cls._factories[category] = factory
    
    @classmethod
    def list_categories(cls) -> list:
        """
        Lista todas las categorías registradas.
        
        Returns:
            list: Lista de categorías disponibles
        """
        return list(cls._factories.keys())
