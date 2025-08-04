from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    # Ruta existente para el chat
    path('', views.chat_view, name='chat'),
    # Esta ruta manejará la lógica para iniciar una nueva conversación.
    path('nuevo/', views.new_chat_view, name='new_chat'),
    # Esta ruta recibirá el ID del ticket y la calificación (un número del 1 al 5).
    path('calificar/<int:ticket_id>/<int:rating>/', views.rate_ticket_view, name='rate_ticket'),
    # Esta ruta recibirá el ID del ticket que el usuario quiere ver.
    path('ticket/<int:ticket_id>/', views.chat_view, name='select_ticket'),
]
