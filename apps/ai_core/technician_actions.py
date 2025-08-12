from apps.tickets.models import Ticket, LogInteraccion
from django.contrib.auth.models import User

# Reemplaza la función existente en tu archivo de acciones del técnico
# (probablemente apps/ai_core/technician_actions.py)

from apps.tickets.models import Ticket, LogInteraccion
from django.contrib.auth.models import User

def add_technician_reply(ticket_id: int, reply_message: str, technician_user: User):
    """
    Añade la respuesta de un técnico al log de un ticket y lo mantiene
    activo (EN_PROCESO) para que el usuario pueda responder o calificar.
    """
    print(f"ACTION: Añadiendo respuesta del técnico {technician_user.username} al Ticket #{ticket_id}")
    try:
        ticket = Ticket.objects.get(id=ticket_id)

        # CAMBIO CLAVE 1: No cerramos el ticket. Lo pasamos a 'EN_PROCESO'.
        # Esto indica que la "pelota" está del lado del usuario ahora.
        if ticket.estado != Ticket.Estado.CERRADO:
            ticket.estado = Ticket.Estado.EN_PROCESO
            ticket.save()
            print(f"ACTION: Ticket #{ticket_id} puesto en estado EN_PROCESO.")

        # CAMBIO CLAVE 2: El mensaje es directo. Es la respuesta del técnico,
        # no un aviso formal, para que se sienta como un chat real.
        LogInteraccion.objects.create(
            ticket=ticket,
            mensaje=reply_message,
            emisor=LogInteraccion.Emisor.SISTEMA # Idealmente, aquí podrías tener un emisor 'TECNICO'
        )
        
        print(f"ACTION: Respuesta del técnico añadida exitosamente al Ticket #{ticket_id}.")

    except Ticket.DoesNotExist:
        print(f"ACTION: Error - No se encontró el ticket con ID {ticket_id}.")
    except Exception as e:
        print(f"ACTION: Ocurrió un error inesperado al añadir la respuesta al ticket #{ticket_id}: {e}")

