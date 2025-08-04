# Este archivo asegura que la app de Celery se cargue cuando Django se inicie.
from .celery import app as celery_app

__all__ = ('celery_app',)