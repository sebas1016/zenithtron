from django.db import models
from django.db.models import Sum, F
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.db import transaction
from django.db import IntegrityError
from datetime import datetime, timedelta
import os

ESTADOS_CHOICES = [
    ('pendiente', 'Pendiente por revisión'),
    ('reparacion', 'En reparación'),
    ('revisado', 'Revisado'),
    ('autorizado', 'Autorizado'),
    ('reparado', 'Reparado'),
    ('entregado', 'Entregado'),
    ('devolucion', 'Devolución'),
    ('garantia', 'Garantía'),
   
]


# Create your models here.
class Recibidor(models.Model):
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'Recibidor'
        verbose_name_plural = 'Recibidores'
        ordering = ['nombre']

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    celular = models.CharField(max_length=20)
    referencia = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.nombre}"
    
class Equipo(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    serial = models.CharField(max_length=100, blank=True, null=True)
    descripcion_general = models.TextField()
    
    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.serial or 'sin serial'})"
    
class Ingreso(models.Model):
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    fecha_ingreso = models.DateTimeField(auto_now_add=True, db_index=True)
    descripcion_dano = models.TextField()
    paga_revision = models.BooleanField(default=False)
    recibido_por= models.ForeignKey(Recibidor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Recibido por')
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES, default='pendiente', db_index=True)
    numero_ingreso = models.CharField(max_length=10, unique=True, editable=False, blank=True, db_index=True)
    es_garantia = models.BooleanField(default=False) 
    archivado = models.BooleanField(default=False, db_index=True)
    archivado_en = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Ingreso {self.numero_ingreso}"
    
    def calcular_dias_habiles(self, fecha_inicio, fecha_fin):
        """Calcula dias habliles (excluye sabados y domingos)"""
        dias_habiles = 0
        fecha_actual = fecha_inicio.date() if hasattr(fecha_inicio, 'date') else fecha_inicio
        fecha_final = fecha_fin.date() if hasattr(fecha_fin, 'date') else fecha_fin
        
        while fecha_actual <= fecha_final:
            
            if fecha_actual.weekday() < 5:
                dias_habiles += 1
            fecha_actual += timedelta(days=1)
            
        return dias_habiles
    
    def dias_en_taller(self):
        """Calcula los días que lleva el equipo en el taller"""
        from django.utils.timezone import now
        if self.estado != 'pendiente':
            return 0
        hoy = now() 
        dias_habiles = self.calcular_dias_habiles(self.fecha_ingreso, hoy)
        
        return max(0, dias_habiles - 1)
    
    def requiere_alerta(self):
        """Retorna True si el equipo está pendiente y requiere seguimineto"""
        return self.estado == 'pendiente'
    
    def nivel_alerta(self):
        """Retorna nivel alerta: normal, advertencia, critico"""
        if self.estado != 'pendiente':
            return 'normal'
        
        dias = self.dias_en_taller()
        if dias > 8:
            return 'critico'
        elif dias > 5 and dias <= 8:
            return 'advertencia'
        else:
            return 'green'
    
    def obtener_mensaje_alerta(self):
        """Retorna un mensaje descriptivo según el nivel de alerta"""
        dias = self.dias_en_taller()
        nivel = self.nivel_alerta()
        
        mensajes = {
            'green': f'Reciente: {dias} día{"s" if dias != 1 else ""} hábil{"es" if dias != 1 else ""}',
            'advertencia': f'Atención: {dias} días hábiles sin revisar',
            'critico': f'¡URGENTE!: {dias} días hábiles sin revisar'
        }
        
        return mensajes.get(nivel, f'{dias} días hábiles en taller')
    
    class Meta:
        ordering = ['-fecha_ingreso']
        verbose_name = 'Ingreso'
        verbose_name_plural = 'Ingresos'
    
class HistorialEquipo(models.Model):
    ingreso = models.ForeignKey(Ingreso, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES) #Ej: "En revision", "Reparado", Garantía
    costo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.estado} - {self.fecha.strftime('%d/%m/%y')}"

def ruta_imagen_ingreso(instance, filename):
        ext = filename.split('.')[-1]
        numero = instance.ingreso.numero_ingreso
        orden = instance.orden

        return f"ingresosMedia/{numero}/{numero}_{orden}.{ext}"

class ImagenIngreso(models.Model):
    ingreso = models.ForeignKey(Ingreso, on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to=ruta_imagen_ingreso)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    orden = models.IntegerField(default=1)
    
    def __str__(self):
        return f"Imagen de ingreso {self.ingreso.numero_ingreso}"
    
    
        
class ImagenHistorial(models.Model):
    historial = models.ForeignKey(HistorialEquipo, on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to='historial/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Imagen en historial {self.historial}"

class ContadorIngreso(models.Model):
    ultimo_numero = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Contador de Ingreso"

    def __str__(self):
        return f"Último número: {self.ultimo_numero}"

def ruta_imagen_serial(instance, filename):
    ext = filename.split('.')[-1]
    equipo_id = instance.equipo_id
    orden = instance.orden

    return f"equipos/{equipo_id}/{equipo_id}_{orden}.{ext}"

class ImagenSerial(models.Model):
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='imagenes_serial')
    imagen = models.ImageField(upload_to=ruta_imagen_serial)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    orden = models.IntegerField(default=1)
    
    class Meta:
        verbose_name = 'Imagen de serial'
        verbose_name_plural = 'Imagenes de serial'
        
    def __str__(self):
        return f"serial {self.equipo.serial} - {self.fecha_subida.strftime('%d/%m/%Y')}"
    
class ReporteTecnico(models.Model):
    ingreso = models.ForeignKey(Ingreso, on_delete=models.CASCADE, related_name='reportes')
    fecha = models.DateField(auto_now_add=True)
    descripcion_trabajo = models.TextField(verbose_name='Descripción del trabajo')
    valor = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='valor (COP)')
    creado_en = models.DateField(auto_now_add=True)
    
    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Reporte Técnico'
        verbose_name_plural = 'Reporte Técnicos'
    
    def __str__(self):
        return f"Reporte {self.ingreso.numero_ingreso} - ${self.valor:,.0f}"

class CuentaCobro(models.Model):
    ingreso = models.ForeignKey(Ingreso, on_delete=models.CASCADE, related_name='cuenta_cobro')
    numero = models.PositiveIntegerField(unique=True, editable=False, verbose_name='Numero cuenta de cobro')
    fecha = models.DateField(auto_now_add=True)
    nombre = models.CharField(max_length=100, verbose_name='nombre cliente')
    id_cedula = models.CharField(max_length=20, verbose_name='Cedula o NIT')
    direccion = models.CharField(max_length=200, verbose_name='Direccion cliente')
    telefono = models.CharField(max_length=15, verbose_name='Telefono o celular')
    ciudad = models.CharField(max_length=30, verbose_name='ciuda de residencia')
    forma_pago = models.CharField(max_length=50, default='Transferencia', verbose_name='Forma de pago')
    
    def total(self):
        return self.detalle_items.aggregate(
            total=Sum(F('cantidad') * F('valor_unitario'))
        )['total'] or 0
    
    def __str__(self):
        return f"Cuenta de cobro {self.ingreso} - {self.nombre}"
    
class ItemCuentaCobro(models.Model):
    cuenta = models.ForeignKey(CuentaCobro, on_delete=models.CASCADE, related_name='detalle_items')
    cantidad = models.PositiveIntegerField(verbose_name='cantidad')
    concepto = models.TextField(verbose_name='Concepto de cobro')
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='valor unitario (COP)')
    
    def subtotal(self):
        return self.cantidad * self.valor_unitario
    
    def __str__(self):
        return f"{self.concepto} ({self.cantidad} X {self.valor_unitario})"