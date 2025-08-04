from celery import shared_task
from apps.tickets.models import Ticket, TechnicianProfile
# --- ¡NUEVA IMPORTACIÓN! ---
# Importamos nuestro nuevo sender de Telegram.
from telegram_bot.sender import send_telegram_message_sync

@shared_task
def notify_technician_task(ticket_id):
    """
    Tarea de Celery para notificar a un técnico sobre un nuevo ticket escalado.
    """
    print(f"CELERY: ¡Tarea recibida! Notificar al técnico sobre el Ticket #{ticket_id}.")
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # --- Lógica para encontrar un técnico ---
        # Buscamos el primer perfil de técnico que esté activo y tenga un ID de Telegram.
        # En un sistema real, aquí habría una lógica más compleja de asignación.
        active_technician = TechnicianProfile.objects.filter(
            is_active_technician=True,
            telegram_chat_id__isnull=False
        ).first()

        if active_technician:
            print(f"CELERY: Técnico encontrado: {active_technician.user.username}. Enviando notificación...")
            
            # Formateamos un mensaje claro para el técnico.
            message = (
                f"🔔 *Nuevo Ticket Asignado*\n\n"
                f"*Ticket ID:* #{ticket.id}\n"
                f"*Usuario:* {ticket.usuario.username}\n"
                f"*Consulta:* _{ticket.descripcion_inicial}_"
            )
            
            # Usamos nuestro sender para enviar el mensaje.
            send_telegram_message_sync(active_technician.telegram_chat_id, message)
            
            return f"Notificación para el ticket {ticket_id} enviada a {active_technician.user.username}."
        else:
            print("CELERY: No se encontraron técnicos activos con un ID de Telegram para notificar.")
            return "No se encontraron técnicos activos."

    except Ticket.DoesNotExist:
        print(f"CELERY: Error - No se encontró el ticket con ID {ticket_id}.")
        return "Ticket no encontrado."

