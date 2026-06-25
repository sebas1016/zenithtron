from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from .forms import (ClienteForm, EquipoForm, IngresoForm, ReporteTecnicoForm, CuentaCobroForm, ItemFormSet)
from .models import (Cliente, Equipo, ImagenHistorial, ImagenIngreso, ReporteTecnico,Ingreso, 
                     CuentaCobro,HistorialEquipo,ContadorIngreso, ImagenSerial)
from django.db.models import Q, Count, F
from django.http import JsonResponse
from django.template.loader import render_to_string
import json
from django.views.decorators.csrf import csrf_exempt

from weasyprint import HTML 
from django.db import IntegrityError, transaction
from django.utils.timezone import now
from ingresos.models import Ingreso
from django.contrib.auth import login
from datetime import timedelta
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.db.models import Max
from django.db.models.functions import ExtractDay, Now
from PIL import Image, ImageOps
from io import BytesIO
from django.core.files.base import ContentFile
import os
import base64

# Al inicio de views.py, fuera de cualquier función — se crea UNA sola vez
# cuando Django arranca el proceso, no en cada request.
try:
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    from weasyprint import FontConfiguration

FONT_CONFIG = FontConfiguration()
# Create your views here.
def inicio(request):
    return render(request, 'gestion/inicio.html')

def convertir_a_webp(imagen_file, calidad=85):
    img = Image.open(imagen_file)
    
    # Corrige orientación automáticamente leyendo EXIF
    img = ImageOps.exif_transpose(img)
    
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGBA')
    else:
        img = img.convert('RGB')
    
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=calidad)
    buffer.seek(0)
    
    nombre_original = os.path.splitext(imagen_file.name)[0]
    return ContentFile(buffer.read(), name=f"{nombre_original}.webp")

def generar_numero_ingreso():
    with transaction.atomic():
        contador, creado = ContadorIngreso.objects.select_for_update().get_or_create(id=1)
        contador.ultimo_numero += 1
        contador.save()

        # Siempre mínimo 4 dígitos, crece si supera 9999
        return f"{contador.ultimo_numero:04}"

def generar_numero_cuenta_cobro():
    
    ultimo = CuentaCobro.objects.select_for_update().order_by('-numero').first()
    return (ultimo.numero + 1) if ultimo else 1

def ingreso_equipo(request):
    if request.method == 'POST':
        cliente_form = ClienteForm(request.POST)
        equipo_form = EquipoForm(request.POST)
        ingreso_form = IngresoForm(request.POST)
        
        if cliente_form.is_valid() and equipo_form.is_valid() and ingreso_form.is_valid():
            #Buscar o crear cliente
            celular = cliente_form.cleaned_data['celular']
            
            cliente, creado =Cliente.objects.get_or_create(
                celular=celular,
                defaults={
                    'nombre': cliente_form.cleaned_data['nombre'],
                    'referencia': cliente_form.cleaned_data['referencia']
                }
                
            )
            
            # Buscar o crear equipo
            marca = equipo_form.cleaned_data['marca']
            if marca == 'Otra':
                marca = request.POST.get('marca_otro')

            equipo, creado = Equipo.objects.get_or_create(
                cliente=cliente,
                marca=marca,
                modelo=equipo_form.cleaned_data['modelo'],
                serial=equipo_form.cleaned_data['serial'],
                defaults={
                    'descripcion_general': equipo_form.cleaned_data['descripcion_general']
                }
            )

            
            #Crear nuevo ingreso
            try:
                with transaction.atomic():
                    ingreso = ingreso_form.save(commit=False)
                    ingreso.numero_ingreso = generar_numero_ingreso()
                    ingreso.equipo = equipo

                    if ingreso.es_garantia:
                        ingreso.estado = 'garantia'
                    elif ingreso.estado == 'garantia':
                        ingreso.estado = 'pendiente'

                    ingreso.save()
            
                    # Guardar Imágenes del Ingreso
                    imagenes = request.FILES.getlist('imagenes')
                    for i, img in enumerate(imagenes, start=1):
                        ImagenIngreso.objects.create(
                            ingreso=ingreso, 
                            imagen=convertir_a_webp(img),
                            orden=i)

                    #Guardar imagenes del serial
                    imagenes_serial = request.FILES.getlist('imagenes_serial')
                    for i, img in enumerate(imagenes_serial, start=1):
                        ImagenSerial.objects.create(
                            equipo=equipo, 
                            imagen=convertir_a_webp(img),
                            orden=i)
                        
            except IntegrityError:
                return HttpResponse("Error al guardar el ingreso. Intenta de nuevo.", status=500)     

            return redirect('ingreso_exitoso', ingreso_id=ingreso.id)

            #return redirect('ingreso_equipo')
            
    else:
        cliente_form = ClienteForm()
        equipo_form = EquipoForm()
        ingreso_form = IngresoForm()
            
    return render(request, 'gestion/ingreso_equipo.html', {
        'cliente_form': cliente_form,
        'equipo_form': equipo_form,
        'ingreso_form': ingreso_form,
        })
    
def detalle_ingreso(request, numero_ingreso):
    ingreso = get_object_or_404(Ingreso, numero_ingreso=numero_ingreso)
    equipo = ingreso.equipo
    cliente = ingreso.equipo.cliente
    historial = HistorialEquipo.objects.filter(ingreso=ingreso).order_by('-fecha')
    imagenes = ingreso.imagenes.all()
    imagenes_serial = equipo.imagenes_serial.all()
    
    from .forms import HistorialForm
    
    if request.method == 'POST':
        form = HistorialForm(request.POST)
        if form.is_valid():
            historial_item = form.save(commit=False)
            historial_item.ingreso = ingreso
            historial_item.realizado_por = None
            ingreso.estado = historial_item.estado
            ingreso.save()
            historial_item.save()
            
            # Captura múltiples imágenes del input llamado "imagen"
            for img in request.FILES.getlist('imagen'):
                ImagenHistorial.objects.create(historial=historial_item, imagen=convertir_a_webp(img))

            return redirect('detalle_ingreso', numero_ingreso=numero_ingreso)
    else:
        form = HistorialForm()
    
    return render(request, 'gestion/detalle_ingreso.html', {
        'ingreso': ingreso,
        'equipo': equipo,
        'cliente': cliente,
        'historial': historial,
        'imagenes': imagenes,
        'imagenes_serial': imagenes_serial,
        'form':form,
    })
    
def listar_ingresos(request):
    estado_filtrado = request.GET.get('estado', '')
    busqueda = request.GET.get('query', '')
    
    ingresos = Ingreso.objects.select_related('equipo__cliente').filter(archivado=False).order_by('-fecha_ingreso')
   
    if estado_filtrado:
        ingresos = ingresos.filter(estado=estado_filtrado, archivado=False)
    
    if busqueda:
        ingresos = ingresos.filter(
            Q(numero_ingreso__icontains=busqueda) | 
            Q(equipo__cliente__nombre__icontains=busqueda) |
            Q(equipo__cliente__celular__icontains=busqueda) |
            Q(equipo__modelo__icontains=busqueda) |
            Q(equipo__marca__icontains=busqueda)
        )
    paginator = Paginator(ingresos, 100)  # 10 por página
    page = request.GET.get('page')
    ingresos_page = paginator.get_page(page)
        
    return render(request, 'gestion/listar_ingresos.html', {
        'ingresos': ingresos_page,
        'estado_filtrado':estado_filtrado,
        'busqueda':busqueda
    })
    
def archivar_ingreso(request, ingreso_id):
    ingreso = get_object_or_404(Ingreso, id=ingreso_id)
    ingreso.archivado = True
    ingreso.archivado_en = now()
    ingreso.save()
    
    return JsonResponse({'ok': True})
def buscar_ingresos_api(request):
    busqueda = request.GET.get('query', '')
    estado   = request.GET.get('estado', '')
    alerta   = request.GET.get('alerta', '')
    page_number = request.GET.get('page', '1')

    ingresos = (
        Ingreso.objects
        .select_related('equipo__cliente')
        .order_by('-fecha_ingreso')
        .annotate(
           
            dias_taller_sql=ExtractDay(Now() - F('fecha_ingreso'))
        )
    )

    if estado:
        ingresos = ingresos.filter(estado=estado)

    if busqueda:
        ingresos = ingresos.filter(
            Q(numero_ingreso__icontains=busqueda)        |
            Q(equipo__cliente__nombre__icontains=busqueda) |
            Q(equipo__cliente__celular__icontains=busqueda)|
            Q(equipo__modelo__icontains=busqueda)        |
            Q(equipo__marca__icontains=busqueda)
        )

    if alerta:
        # El filtro de estado='pendiente' va siempre que haya alerta
        ingresos = ingresos.filter(estado='pendiente')

        if alerta == 'green':
            ingresos = ingresos.filter(dias_taller_sql__lt=6)
        elif alerta == 'con-alerta':
            ingresos = ingresos.filter(dias_taller_sql__gte=6, dias_taller_sql__lte=8)
        elif alerta == 'critico':
            ingresos = ingresos.filter(dias_taller_sql__gt=8)

    paginator = Paginator(ingresos, 10)
    page_obj  = paginator.get_page(page_number)

    html = render_to_string('gestion/fragmento_tabla_ingresos.html', {
        'ingresos': page_obj
    })

    return JsonResponse({
        'html':         html,
        'has_next':     page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'number':       page_obj.number,
        'num_pages':    paginator.num_pages,
    })
    
def dashboard(request):
    """Dashboard principal con KPIs y gráficos"""
    
    # KPIs optimizados en una sola query
    stats = Ingreso.objects.aggregate(
        total=Count('id'),
        activos=Count('id', filter=~Q(estado='entregado')),
        entregados=Count('id', filter=Q(estado='entregado')),
        garantias=Count('id', filter=Q(es_garantia=True))
    )
    
    # Estados con etiquetas legibles
    estados_data = (
        Ingreso.objects.values('estado')
        .annotate(total=Count('id'))
        .order_by('-total')  # Ordenar por cantidad descendente
    )
    
    #Obtener lista de estados unicos para el filtro
    estados_disponibles = (
        Ingreso.objects
        .values_list('estado', flat=True)
        .distinct()
        .order_by('estado')
    )
    
    # Últimos 6 meses con nombres de mes
    hoy = now()
    hace_6_meses = hoy - timedelta(days=180)
    
    ingresos_mes = (
        Ingreso.objects
        .filter(fecha_ingreso__gte=hace_6_meses)
        .annotate(mes=TruncMonth('fecha_ingreso'))  # Más preciso que F('month')
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    
    # Formatear datos para el template
    ingresos_mes_formateados = [
        {
            'mes': item['mes'].strftime('%b %Y'),  # 'Ene 2024'
            'total': item['total']
        }
        for item in ingresos_mes
    ]
    
    context = {
        'total_ingresos': stats['total'],
        'activos': stats['activos'],
        'entregados': stats['entregados'],
        'garantias': stats['garantias'],
        'estados_data': list(estados_data),
        'ingresos_mes': ingresos_mes_formateados,
        'estadis_disponibles': list(estados_disponibles),
    }
    
    return render(request, 'gestion/dashboard.html', context)

#API devuelve estadisticas filtradas a Dashboard
@require_http_methods(["GET"])
def estadisticas_api(request):
    """API para estadísticas filtradas por fecha"""
    
    fecha_inicio = parse_date(request.GET.get('inicio', ''))
    fecha_fin = parse_date(request.GET.get('fin', ''))
    estado = request.GET.get('estado', '')
    
    # Validación de fechas
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        return JsonResponse({
            'error': 'La fecha de inicio no puede ser mayor que la fecha fin'
        }, status=400)
    
    #Construccion de filtros
    ingresos = Ingreso.objects.all()
    
    if fecha_inicio:
        ingresos = ingresos.filter(fecha_ingreso__date__gte=fecha_inicio)
    if fecha_fin:
        ingresos = ingresos.filter(fecha_ingreso__date__lte=fecha_fin)
    if estado:
        ingresos = ingresos.filter(estado=estado)
    
    # KPIs filtrados
    stats = ingresos.aggregate(
        total=Count('id'),
        activos=Count('id', filter=~Q(estado='entregado')),
        entregados=Count('id', filter=Q(estado='entregado')),
        garantias=Count('id', filter=Q(es_garantia=True))
    )
    
    # Estados
    estados_data = (
        ingresos.values('estado')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    
    # Ingresos por mes
    ingresos_mes = (
        ingresos
        .annotate(mes=TruncMonth('fecha_ingreso'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    
    ingresos_mes_formateados = [
        {
            'mes': item['mes'].strftime('%b %Y'),
            'total': item['total']
        }
        for item in ingresos_mes
    ]
    
    data = {
        'total_ingresos': stats['total'],
        'activos': stats['activos'],
        'entregados': stats['entregados'],
        'garantias': stats['garantias'],
        'estados': list(estados_data),
        'ingresos_mes': ingresos_mes_formateados,
    }
    
    return JsonResponse(data)

def ingreso_detalle_api(request, ingreso_id):
    ingreso = get_object_or_404(Ingreso.objects.select_related('equipo__cliente'), id=ingreso_id)
    historial = HistorialEquipo.objects.filter(ingreso=ingreso).order_by('fecha')
    
    data = {
        'numero_ingreso': ingreso.numero_ingreso,
        'fecha_ingreso': ingreso.fecha_ingreso.isoformat(),
        'descripcion_dano': ingreso.descripcion_dano,
        'paga_revision': ingreso.paga_revision,
        'estado': ingreso.estado,
        'recibido_por': str(ingreso.recibido_por) if ingreso.recibido_por else None,
        'es_garantia': ingreso.estado == 'garantia',
        'cliente': {
            'nombre': ingreso.equipo.cliente.nombre,
            'celular': ingreso.equipo.cliente.celular,
            'referencia': ingreso.equipo.cliente.referencia,
        },
        'equipo': {
            'marca': ingreso.equipo.marca,
            'modelo': ingreso.equipo.modelo,
            'serial': ingreso.equipo.serial,
            'descripcion_general': ingreso.equipo.descripcion_general,
        },
        'historial': [
            {
                'fecha': h.fecha.isoformat(),
                'descripcion': h.descripcion,
                'estado': h.estado,
                #'realizado_por': h.realizado_por.get_full_name() if h.realizado_por else "—",
                'costo': float(h.costo) if h.costo else None,
            } for h in historial
        ]
    }
    return JsonResponse(data)

@csrf_exempt  # temporalmente, o maneja CSRF si usas SessionMiddleware
def actualizar_ingreso_api(request, ingreso_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    ingreso = get_object_or_404(Ingreso, id=ingreso_id)
    data = json.loads(request.body)

    ingreso.descripcion_dano = data.get('descripcion_dano', '')
    ingreso.estado = data.get('estado', ingreso.estado)
    ingreso.paga_revision = data.get('paga_revision', False)
    ingreso.es_garantia = data.get('es_garantia', False)
    ingreso.save()
    
    HistorialEquipo.objects.create(
        ingreso=ingreso,
        descripcion=f"Estado: {ingreso.estado}",
        estado=ingreso.estado
    )

    return JsonResponse({'success': True})


def image_to_base64(path):
    """Para logo/QR: lee la imagen del disco tal cual, sin redimensionar."""
    try:
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        ext = path.split('.')[-1].lower()
        mime = 'jpeg' if ext in ('jpg', 'jpeg') else ext
        return f"data:image/{mime};base64,{encoded}"
    except FileNotFoundError:
        return ''


def imagen_a_base64_redimensionada(imagen_field, max_width=700):
    """Para fotos de usuario (ingreso/serial): lee del disco y redimensiona,
    porque en el PDF se muestran como miniaturas de 100x100px — no tiene
    sentido embeber la foto completa de la cámara."""
    if not imagen_field:
        return ''
    try:
        path = imagen_field.path
    except (ValueError, NotImplementedError):
        return ''
    try:
        with Image.open(path) as img:
            fmt = img.format or 'WEBP'
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format=fmt, quality=80)
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/{fmt.lower()};base64,{encoded}"
    except FileNotFoundError:
        return ''


def generar_pdf_ingreso(request, ingreso_id):
    ingreso = get_object_or_404(
        Ingreso.objects.select_related('equipo__cliente', 'recibido_por'),
        id=ingreso_id
    )
    equipo = ingreso.equipo
    cliente = equipo.cliente
    recibido_por = ingreso.recibido_por

    imagenes_rutas = [
        {'ruta': imagen_a_base64_redimensionada(img.imagen)}
        for img in ingreso.imagenes.all().order_by('orden')
    ]

    imagenes_serial_rutas = [
        {'ruta': imagen_a_base64_redimensionada(img.imagen)}
        for img in ImagenSerial.objects.filter(equipo=equipo).order_by('orden')
    ]

    base_img = os.path.join(settings.BASE_DIR, 'ingresos', 'static', 'images')

    html = render_to_string('gestion/pdf_ingreso.html', {
        'ingreso': ingreso,
        'recibido_por': recibido_por,
        'cliente': cliente,
        'equipo': equipo,
        'imagenes': imagenes_rutas,
        'imagenes_serial': imagenes_serial_rutas,
        'logo_base64': image_to_base64(os.path.join(base_img, 'logo.jpg')),
        'qr_base64': image_to_base64(os.path.join(base_img, 'qrcode.png')),
    })

    pdf_file = HTML(string=html).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=ingreso_{ingreso.numero_ingreso}.pdf'
    return response

def ingreso_exitoso(request, ingreso_id):
    ingreso = get_object_or_404(Ingreso, id=ingreso_id)
    return render(request, 'gestion/ingreso_exitoso.html', {
        'ingreso': ingreso,
        'ingreso_id': ingreso_id
    })
    
def crear_reporte_tecnico(request, ingreso_id):
    ingreso = get_object_or_404(Ingreso, id=ingreso_id)

    if request.method == 'POST':
        form = ReporteTecnicoForm(request.POST)
        if form.is_valid():
            reporte = form.save(commit=False)
            reporte.ingreso = ingreso
            reporte.save()
            return redirect('ver_reporte_tecnico', reporte_id=reporte.id)
    else:
        form = ReporteTecnicoForm()

    return render(request, 'gestion/crear_reporte.html', {
        'ingreso': ingreso,
        'form': form,
    })


def ver_reporte_tecnico(request, reporte_id):
    reporte = get_object_or_404(ReporteTecnico, id=reporte_id)
    return render(request, 'gestion/reporte_tecnico.html', {
        'reporte': reporte,
        'ingreso': reporte.ingreso,
    })


def image_to_base64(path):
    """Convierte una imagen del filesystem a base64 para incrustar en el PDF (WeasyPrint)."""
    try:
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        ext = path.split('.')[-1].lower()
        mime = 'jpeg' if ext in ('jpg', 'jpeg') else ext
        return f"data:image/{mime};base64,{encoded}"
    except FileNotFoundError:
        return ''

def generar_pdf_reporte_tecnico(request, reporte_id):
    reporte = get_object_or_404(ReporteTecnico, id=reporte_id)
    ingreso = reporte.ingreso
    equipo = ingreso.equipo

    contexto = {
        'reporte': reporte,
        'ingreso': ingreso,
        'equipo': equipo,
        'logo_base64': image_to_base64(os.path.join(settings.BASE_DIR, 'ingresos', 'static', 'images', 'logou.png')),
        'firma_base64': image_to_base64(os.path.join(settings.BASE_DIR, 'ingresos', 'static', 'images', 'firma.png')),
        'qr_base64': image_to_base64(os.path.join(settings.BASE_DIR, 'ingresos', 'static', 'images', 'qrinstagram.png')),
    }

    html_string = render_to_string('gestion/reporte_tecnico_pdf.html', contexto)
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="reporte_tecnico_{reporte.id}.pdf"'
    return response

def crear_cuenta_cobro(request, ingreso_id):
    ingreso = get_object_or_404(Ingreso, id=ingreso_id)

    if request.method == 'POST':
        form = CuentaCobroForm(request.POST)
        formset = ItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                cuenta = form.save(commit=False)
                cuenta.ingreso = ingreso
                cuenta.numero = generar_numero_cuenta_cobro()
                cuenta.save()

                formset.instance = cuenta
                formset.save()
            return redirect('ver_cuenta_cobro', cuenta_id=cuenta.id)
    else:
        cliente = ingreso.equipo.cliente
        form = CuentaCobroForm(initial={
            'nombre': cliente.nombre,
            'telefono': cliente.celular,
        })
        formset = ItemFormSet()

    return render(request, 'gestion/crear_cuenta_cobro.html', {
        'form': form,
        'formset': formset,
        'ingreso': ingreso,
    })


def ver_cuenta_cobro(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCobro, id=cuenta_id)
    return render(request, 'gestion/cuenta_cobro.html', {
        'cuenta': cuenta,
        'ingreso': cuenta.ingreso,
    })
    
def image_to_base64(path):
    try:
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        ext = path.split('.')[-1].lower()
        mime = 'jpeg' if ext in ('jpg', 'jpeg') else ext
        return f"data:image/{mime};base64,{encoded}"
    except FileNotFoundError:
        return ''


def generar_pdf_cuenta_cobro(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCobro, id=cuenta_id)
    ingreso = cuenta.ingreso
    equipo = ingreso.equipo

    base_img = os.path.join(settings.BASE_DIR, 'ingresos', 'static', 'images')

    contexto = {
        'cuenta': cuenta,
        'ingreso': ingreso,
        'equipo': equipo,
        'logo_base64': image_to_base64(os.path.join(base_img, 'logo.png')),
        'qr_base64': image_to_base64(os.path.join(base_img, 'qrinstagram.png')),
        'firma_base64': image_to_base64(os.path.join(settings.BASE_DIR, 'ingresos', 'static', 'images', 'firma.png')),
    }

    html_string = render_to_string('gestion/cuenta_cobro_pdf.html', contexto)
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="cuenta_cobro_{cuenta.numero}.pdf"'
    return response