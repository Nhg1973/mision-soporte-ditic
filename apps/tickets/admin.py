from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Ticket, LogInteraccion, TechnicianProfile
from .models import Ticket, LogInteraccion, TechnicianProfile, KnowledgeDocument

# ==============================================================================
# Vista Personalizada para los Logs de Interacción (Inline)
# ==============================================================================
# Esto permite ver los logs directamente desde la página del ticket.
class LogInteraccionInline(admin.TabularInline):
    model = LogInteraccion
    extra = 0  # No mostrar formularios de logs vacíos para añadir.
    readonly_fields = ('mensaje', 'emisor', 'fecha_creacion')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

# ==============================================================================
# Vista Personalizada para el Modelo Ticket
# ==============================================================================
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    # Columnas que se mostrarán en la lista de tickets.
    list_display = (
        'id',
        'usuario',
        'estado',
        'canal_origen',
        'fecha_creacion',
        'calificacion'
    )
    
    # Filtros en la barra lateral derecha.
    list_filter = ('estado', 'canal_origen', 'fecha_creacion', 'calificacion')
    
    # Barra de búsqueda.
    search_fields = ('id', 'usuario__username', 'descripcion_inicial')
    
    # Campos de solo lectura en la vista de detalle.
    readonly_fields = ('id', 'fecha_creacion', 'fecha_actualizacion')

    # Muestra los logs de la conversación directamente en la página del ticket.
    inlines = [LogInteraccionInline]

# ==============================================================================
# Integramos el Perfil del Técnico en la página de administración de Usuarios
# ==============================================================================

# 1. Definimos un "inline" para el perfil. Esto significa que se mostrará
#    dentro de la página de otro modelo (en este caso, el modelo User).
class TechnicianProfileInline(admin.StackedInline):
    model = TechnicianProfile
    can_delete = False
    verbose_name_plural = 'Perfil de Técnico'
    fields = ('telegram_chat_id', 'is_active_technician')

# 2. Extendemos la vista de administración de usuarios por defecto de Django.
class UserAdmin(BaseUserAdmin):
    inlines = (TechnicianProfileInline,)

# 3. Re-registramos el admin del modelo User para que use nuestra versión extendida.
#    Primero lo quitamos del registro y luego lo volvemos a registrar con la nueva clase.
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# ==============================================================================
# Vista de Admin para la Base de Conocimiento
# ==============================================================================
@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'estado_procesamiento', 'cargado_por', 'fecha_carga')
    list_filter = ('estado_procesamiento', 'categoria', 'fecha_carga')
    search_fields = ('nombre', 'archivo')
    readonly_fields = ('estado_procesamiento', 'cargado_por', 'fecha_carga', 'ultimo_error')

    def save_model(self, request, obj, form, change):
        # Asigna automáticamente el usuario que está subiendo el archivo.
        if not obj.pk: # Solo al crear el objeto
            obj.cargado_por = request.user
        super().save_model(request, obj, form, change)



