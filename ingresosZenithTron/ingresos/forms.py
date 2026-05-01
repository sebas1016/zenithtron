from django import forms
from django.forms import inlineformset_factory
from .models import (Cliente, Equipo, Ingreso, HistorialEquipo, Recibidor, ReporteTecnico,
                     CuentaCobro, ItemCuentaCobro)
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'celular', 'referencia']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre completo'}),
            'celular': forms.TextInput(attrs={'placeholder': 'Celular'}),
            'referencia': forms.TextInput(attrs={'placeholder': 'Referencia o punto de referencia', 'list': 'referencia'}),
        }
class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ['marca', 'modelo', 'serial', 'descripcion_general']
        widgets = {
            'marca': forms.TextInput(attrs={'placeholder': 'Marca del equipo', 'list': 'marcas'}),
            'modelo': forms.TextInput(attrs={'placeholder': 'Modelo'}),
            'serial': forms.TextInput(attrs={'placeholder': 'Serial'}),
            'descripcion_general': forms.Textarea(attrs={
                'placeholder': 'Descripción general del equipo',
                'rows': 3
            }),
        }
    
class IngresoForm(forms.ModelForm):
    
    class Meta:
        model = Ingreso
        fields = ['descripcion_dano', 'recibido_por', 'paga_revision', 'es_garantia']
        widgets = {
            'descripcion_dano': forms.Textarea(attrs={
                'placeholder': 'Describa el daño o motivo del ingreso',
                'rows': 3
            }),
        }
        
        labels = {
            'recibido_por': 'Recibido por',
            'descripcion_dano': 'Descripción Daño',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recibido_por'].queryset = Recibidor.objects.filter(activo=True)
        self.fields['recibido_por'].empty_label = 'Seleccione quien recibe'
class BusquedaForm(forms.Form):
    query = forms.CharField(label='Buscar por nombre, celular, modelo o serial', max_length=100)
    
class HistorialForm(forms.ModelForm):
    class Meta:
        model = HistorialEquipo
        fields = ['descripcion', 'estado','costo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'estado': forms.Select(),
        }

    
class ReporteTecnicoForm(forms.ModelForm):
    class Meta:
        model = ReporteTecnico
        fields = ['descripcion_trabajo', 'valor']
        widgets = {
            'descripcion_trabajo': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Ej: Cambio leds, mantenimiento general'
            }),
            'valor': forms.NumberInput(attrs={
                'placeholder': '450000',
                'min': '0'
            }),
        }
        labels = {
            'descripcion_trabajo': 'Descripción del trabajo',
            'valor': 'Valor de la reparación (COP)',
        }

class CuentaCobroForm(forms.ModelForm):
    class Meta:
        model = CuentaCobro
        fields = ['nombre', 'id_cedula', 'direccion', 'telefono', 'ciudad', 'forma_pago']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre completo'}), 
            'id_cedula': forms.TextInput(attrs={'placeholder': 'Cedula o Nit'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección'}), 
            'telefono': forms.TextInput(attrs={'placeholder': 'Celular'}), 
            'ciudad': forms.TextInput(attrs={'placeholder': 'Ciudad'}), 
            'forma_pago': forms.TextInput(attrs={'placeholder': 'Forma de pago'}),
        }
       
        
        
ItemFormSet = inlineformset_factory(
            CuentaCobro,
            ItemCuentaCobro,
            fields=['cantidad', 'concepto', 'valor_unitario'],
            extra=1,
            min_num=0,
            validate_min=True,
            can_delete=True,
            widgets={
                'cantidad': forms.NumberInput(attrs={'placeholder': '1'}),
                'concepto': forms.Textarea(attrs={'placeholder': 'Ej: Reparación tarjeta madre', 'rows': 1}),
                'valor_unitario': forms.NumberInput(attrs={'placeholder': '150000'}),
            })       