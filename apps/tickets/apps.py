from django.apps import AppConfig

class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # CORRECCIÓN: Especifica la ruta completa de la aplicación
    name = 'apps.tickets'
