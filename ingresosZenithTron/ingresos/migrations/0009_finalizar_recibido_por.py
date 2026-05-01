from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingresos', '0008_migrar_recibido_por'),
    ]

    operations = [
        # Primero elimina el campo temporal
        migrations.RemoveField(
            model_name='ingreso',
            name='recibido_por_nuevo',
        ),
        # Luego convierte recibido_por de CharField a ForeignKey
        # Para esto primero lo eliminamos
        migrations.RemoveField(
            model_name='ingreso',
            name='recibido_por',
        ),
        # Y lo volvemos a crear como ForeignKey
        migrations.AddField(
            model_name='ingreso',
            name='recibido_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='ingresos.recibidor',
                verbose_name='Recibido por',
            ),
        ),
    ]