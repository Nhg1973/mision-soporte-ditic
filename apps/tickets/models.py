
from django.db import models
from django.contrib.auth.models import User

# ==============================================================================
# Modelo Principal: Ticket
# ==============================================================================
class Ticket(models.Model):
    class Estado(models.TextChoices):
        NUEVO = 'NUEVO', 'Nuevo'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        ESCALADO = 'ESCALADO', 'Escalado a Técnico'
        ESCALADO_ADMIN = 'ESCALADO_ADMIN', 'Escalado a Mesa de Entrada'
        RESUELTO_BOT = 'RESUELTO_BOT', 'Resuelto por Bot'
        RESUELTO_TECNICO = 'RESUELTO_TECNICO', 'Resuelto por Técnico'
        CERRADO = 'CERRADO', 'Cerrado'

    class Canal(models.TextChoices):
        WEB = 'WEB', 'Web'
        TELEGRAM = 'TELEGRAM', 'Telegram'

    class Calificacion(models.IntegerChoices):
        MALA = 1, 'Mala'
        REGULAR = 2, 'Regular'
        BUENA = 3, 'Buena'
        MUY_BUENA = 4, 'Muy Buena'
        EXCELENTE = 5, 'Excelente'

    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="tickets", verbose_name="Usuario"
    )
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.NUEVO, verbose_name="Estado del Ticket"
    )
    canal_origen = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.WEB, verbose_name="Canal de Origen"
    )
    descripcion_inicial = models.TextField(
        blank=True, null=True, verbose_name="Descripción Inicial del Usuario"
    )
    descripcion_confirmada_ia = models.TextField(
        blank=True, null=True, verbose_name="Resumen de la IA"
    )
    calificacion = models.IntegerField(
        choices=Calificacion.choices, null=True, blank=True, verbose_name="Calificación del Usuario"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return f"Ticket #{self.id} - {self.usuario.username} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Ticket de Soporte"
        verbose_name_plural = "Tickets de Soporte"
        ordering = ['-fecha_creacion']

# ==============================================================================
# Modelo de Registro: LogInteraccion
# ==============================================================================
class LogInteraccion(models.Model):
    class Emisor(models.TextChoices):
        SISTEMA = 'SISTEMA', 'Sistema'
        USUARIO = 'USUARIO', 'Usuario'
        # ¡NUEVOS EMISORES! Para mayor claridad en el chat
        TECNICO = 'TECNICO', 'Técnico'
        MESA_ENTRADA = 'MESA_ENTRADA', 'Mesa de Entrada'

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="logs", verbose_name="Ticket Asociado"
    )
    mensaje = models.TextField(verbose_name="Contenido del Mensaje")
    emisor = models.CharField(
        max_length=15, choices=Emisor.choices, verbose_name="Emisor" # Aumentamos el max_length
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return f"Log del Ticket #{self.ticket.id} por {self.emisor}"

    class Meta:
        verbose_name = "Log de Interacción"
        verbose_name_plural = "Logs de Interacciones"
        ordering = ['fecha_creacion']

# ==============================================================================
# Modelo de Perfil: TechnicianProfile
# ==============================================================================
class TechnicianProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="technician_profile", verbose_name="Usuario"
    )
    telegram_chat_id = models.CharField(
        max_length=100, blank=True, null=True, unique=True, verbose_name="ID de Chat de Telegram",
        help_text="El ID único del chat de Telegram para enviarle notificaciones."
    )
    is_active_technician = models.BooleanField(
        default=True, verbose_name="Técnico Activo",
        help_text="Desmarcar para que este técnico no reciba nuevas notificaciones de tickets."
    )

    def __str__(self):
        return f"Perfil de Técnico para {self.user.username}"

    class Meta:
        verbose_name = "Perfil de Técnico"
        verbose_name_plural = "Perfiles de Técnicos"

# ==============================================================================
# Modelo de Base de Conocimiento: KnowledgeDocument
# ==============================================================================

class KnowledgeDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente de Procesamiento'
        PROCESSING = 'PROCESSING', 'Procesando'
        COMPLETED = 'COMPLETED', 'Procesado Exitosamente'
        FAILED = 'FAILED', 'Falló el Procesamiento'
    
    class DocumentType(models.TextChoices):
        CONOCIMIENTO_GENERAL = 'CONOCIMIENTO_GENERAL', 'Conocimiento General'
        MANUAL_TECNICO = 'MANUAL_TECNICO', 'Manual Técnico'
        
    class TemaChoices(models.TextChoices):
        SOFTWARE = 'Software', 'Software'
        HARDWARE = 'Hardware', 'Hardware'
        ABUSO = 'Abuso del sistema', 'Abuso del sistema'
        GENERAL = 'General', 'General'

    nombre = models.CharField(max_length=255, verbose_name="Nombre del Documento")
    archivo = models.FileField(upload_to='knowledge_base/', verbose_name="Archivo")
    
    # --- ESTRUCTURA DE CLASIFICACIÓN FINAL ---
    tipo_documento = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
        default=DocumentType.CONOCIMIENTO_GENERAL,
        verbose_name="Tipo de Documento"
    )
    tema = models.CharField(
        max_length=50, 
        choices=TemaChoices.choices, 
        default=TemaChoices.GENERAL,
        verbose_name="Tema Principal"
    )
    subtema = models.CharField(
        max_length=255, 
        blank=True, null=True, 
        verbose_name="Subtema o Entidad Principal (ej. Infoges, VPN)"
    )
    tags = models.TextField(
        blank=True, null=True, verbose_name="Tags (separados por comas)",
        help_text="Palabras clave relevantes, ej: acceso, contraseña, instalación"
    )
    
    # --- CAMPOS DE ESTADO Y REGISTRO ---
    estado_procesamiento = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Estado de Procesamiento"
    )
    cargado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="documentos_cargados",
        verbose_name="Cargado por"
    )
    fecha_carga = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Carga")
    ultimo_error = models.TextField(blank=True, null=True, verbose_name="Último Error")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Documento de Conocimiento"
        verbose_name_plural = "Documentos de Conocimiento"
        ordering = ['-fecha_carga']

# ==============================================================================
# - Bandeja de Salida para Telegram
# ==============================================================================
class OutgoingTelegramMessage(models.Model):
    """
    Representa un mensaje que está en cola para ser enviado a través de Telegram.
    El script del poller revisará esta tabla y enviará los mensajes pendientes.
    """
    # En lugar de relacionarlo con un Ticket, es más flexible guardando
    # directamente el chat_id y el texto.
    telegram_chat_id = models.CharField(
        max_length=100,
        verbose_name="ID de Chat de Telegram de Destino"
    )
    message_text = models.TextField(
        verbose_name="Contenido del Mensaje"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )

    def __str__(self):
        return f"Mensaje para {self.telegram_chat_id} creado el {self.fecha_creacion}"

    class Meta:
        verbose_name = "Mensaje Saliente de Telegram"
        verbose_name_plural = "Mensajes Salientes de Telegram"
        ordering = ['fecha_creacion']
