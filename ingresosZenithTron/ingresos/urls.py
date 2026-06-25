from django.urls import path
from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ingreso/', views.ingreso_equipo, name='ingreso_equipo'),
    path('ingreso/<str:numero_ingreso>/', views.detalle_ingreso, name='detalle_ingreso'),
    path('ingresos/', views.listar_ingresos, name='listar_ingresos'),
    path('api/buscar-ingresos/', views.buscar_ingresos_api, name='buscar_ingresos_api'),
    path('api/ingresos/<int:ingreso_id>/', views.ingreso_detalle_api, name='ingreso_detalle_api'),
    path('api/ingresos/<int:ingreso_id>/actualizar/', views.actualizar_ingreso_api, name='actualizar_ingreso_api'),
    path('api/ingresos/<int:ingreso_id>/archivar/', views.archivar_ingreso, name='archivar_ingreso'),
    path('ingresos/<int:ingreso_id>/pdf/', views.generar_pdf_ingreso, name='pdf_ingreso'),
    path('ingreso-exitoso/<int:ingreso_id>/', views.ingreso_exitoso, name='ingreso_exitoso'),
    path('estadisticas-api/', views.estadisticas_api, name='estadisticas-api'),
    path('ingreso/<int:ingreso_id>/reporte/nuevo/', views.crear_reporte_tecnico, name='crear_reporte_tecnico'),
    path('reporte/<int:reporte_id>/', views.ver_reporte_tecnico, name='ver_reporte_tecnico'),
    path('reporte-tecnico/<int:reporte_id>/pdf/', views.generar_pdf_reporte_tecnico, name='generar_pdf_reporte_tecnico'),
    path('cuenta-cobro/<int:ingreso_id>/crear/', views.crear_cuenta_cobro, name='crear_cuenta_cobro'),
    path('cuenta-cobro/<int:cuenta_id>/', views.ver_cuenta_cobro, name='ver_cuenta_cobro'),
    path('cuenta-cobro/<int:cuenta_id>/pdf/', views.generar_pdf_cuenta_cobro, name='generar_pdf_cuenta_cobro'),
   

]