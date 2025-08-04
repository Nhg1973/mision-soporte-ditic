import os
from celery import Celery
# --- ¡NUEVAS LÍNEAS! ---
# Importamos la librería y cargamos las variables de entorno
# al inicio de este archivo.
from dotenv import load_dotenv
load_dotenv()

# Establece el módulo de configuración de Django por defecto para el programa 'celery'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Crea la instancia de la aplicación Celery
app = Celery('core')

# Carga la configuración desde el settings.py de Django.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubre las tareas en todas las aplicaciones de Django instaladas.
app.autodiscover_tasks()
