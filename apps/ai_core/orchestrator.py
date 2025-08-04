from apps.tickets.models import Ticket, LogInteraccion
from .tools.knowledge_base import search_knowledge_base
from apps.tasks.tasks import notify_technician_task

# --- ¡CORRECCIÓN EN LA FIRMA DE LA FUNCIÓN! ---
# Ahora la función acepta el 'mensaje_actual' que le pasamos desde la vista.
def process_user_request(ticket_id, mensaje_actual):
    """
    Orquesta la respuesta a una nueva solicitud de usuario, analizando el mensaje más reciente.
    """
    print(f"ORQUESTADOR: Procesando ticket #{ticket_id} con el mensaje: '{mensaje_actual}'")
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        print(f"ORQUESTADOR: Error - No se encontró el ticket #{ticket_id}")
        return

    # --- ¡CORRECCIÓN EN LA LÓGICA! ---
    # Buscamos una solución basada en el 'mensaje_actual', no en la descripción inicial del ticket.
    solucion = search_knowledge_base(mensaje_actual)

    if solucion:
        print(f"ORQUESTADOR: Solución encontrada. Resolviendo automáticamente.")
        ticket.estado = Ticket.Estado.RESUELTO_BOT
        ticket.save()

        LogInteraccion.objects.create(
            ticket=ticket,
            mensaje=solucion,
            emisor=LogInteraccion.Emisor.SISTEMA
        )
        print(f"ORQUESTADOR: Ticket #{ticket.id} resuelto por el bot.")
    else:
        print(f"ORQUESTADOR: No se encontró solución. Escalando a técnico.")
        ticket.estado = Ticket.Estado.ESCALADO
        ticket.save()

        mensaje_escalada = (
            f"¡Gracias por tu consulta sobre '{mensaje_actual}'! "
            f"He creado el Ticket #{ticket.id} y un técnico lo revisará a la brevedad."
        )
        LogInteraccion.objects.create(
            ticket=ticket,
            mensaje=mensaje_escalada,
            emisor=LogInteraccion.Emisor.SISTEMA
        )
        
        notify_technician_task.delay(ticket.id)
        
        print(f"ORQUESTADOR: Ticket #{ticket.id} escalado y tarea de notificación enviada a Celery.")


