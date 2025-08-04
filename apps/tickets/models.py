from django.db import models
from django.contrib.auth.models import User

# ==============================================================================
# Modelo Principal: Ticket
# ==============================================================================
# Almacena la información central de cada solicitud de soporte.
class Ticket(models.Model):
    # --- Opciones para los campos de elección (choices) ---
    class Estado(models.TextChoices):
        NUEVO = 'NUEVO', 'Nuevo'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        ESCALADO = 'ESCALADO', 'Escalado a Técnico'
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

    # --- Campos del Modelo ---
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="Usuario"
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.NUEVO,
        verbose_name="Estado del Ticket"
    )
    canal_origen = models.CharField(
        max_length=10,
        choices=Canal.choices,
        default=Canal.WEB,
        verbose_name="Canal de Origen"
    )
    descripcion_inicial = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción Inicial del Usuario"
    )
    descripcion_confirmada_ia = models.TextField(
        blank=True,
        null=True,
        verbose_name="Resumen de la IA"
    )
    calificacion = models.IntegerField(
        choices=Calificacion.choices,
        null=True,
        blank=True,
        verbose_name="Calificación del Usuario"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )

    def __str__(self):
        # Esta función define cómo se mostrará un objeto Ticket en el admin de Django.
        return f"Ticket #{self.id} - {self.usuario.username} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Ticket de Soporte"
        verbose_name_plural = "Tickets de Soporte"
        ordering = ['-fecha_creacion']


# ==============================================================================
# Modelo de Registro: LogInteraccion
# ==============================================================================
# Guarda cada mensaje de la conversación para tener un historial completo.
class LogInteraccion(models.Model):
    class Emisor(models.TextChoices):
        SISTEMA = 'SISTEMA', 'Sistema'
        USUARIO = 'USUARIO', 'Usuario'

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Ticket Asociado"
    )
    mensaje = models.TextField(verbose_name="Contenido del Mensaje")
    emisor = models.CharField(
        max_length=10,
        choices=Emisor.choices,
        verbose_name="Emisor"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )

    def __str__(self):
        return f"Log del Ticket #{self.ticket.id} por {self.emisor}"

    class Meta:
        verbose_name = "Log de Interacción"
        verbose_name_plural = "Logs de Interacciones"
        ordering = ['fecha_creacion']

# ==============================================================================
# Modelo de Perfil: TechnicianProfile
# ==============================================================================
# Extiende el modelo de Usuario para añadir campos específicos para los técnicos.
class TechnicianProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="technician_profile",
        verbose_name="Usuario"
    )
    telegram_chat_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        verbose_name="ID de Chat de Telegram",
        help_text="El ID único del chat de Telegram para enviarle notificaciones."
    )
    is_active_technician = models.BooleanField(
        default=True,
        verbose_name="Técnico Activo",
        help_text="Desmarcar para que este técnico no reciba nuevas notificaciones de tickets."
    )

    def __str__(self):
        return f"Perfil de Técnico para {self.user.username}"

    class Meta:
        verbose_name = "Perfil de Técnico"
        verbose_name_plural = "Perfiles de Técnicos"
