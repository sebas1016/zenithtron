from django.contrib import admin
from .models import (Cliente, Equipo, Ingreso, HistorialEquipo, Recibidor)

# Register your models here.
@admin.register(Recibidor)
class RecibidorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    list_editable = ['activo']
    search_fields = ['nombre']