from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ticket, LogInteraccion
from apps.ai_core.orchestrator import process_user_request

# --- ¡VISTA ACTUALIZADA! ---
# Añadimos un nuevo parámetro opcional 'ticket_id' a la función.
@login_required
def chat_view(request, ticket_id=None):
    """
    Gestiona la lógica del chat web. Ahora puede mostrar un ticket específico
    o continuar con la conversación activa en la sesión.
    """
    # Si se proporciona un ticket_id en la URL, lo hacemos el ticket activo.
    if ticket_id:
        # Nos aseguramos de que el ticket pertenezca al usuario actual.
        ticket = get_object_or_404(Ticket, id=ticket_id, usuario=request.user)
        request.session['ticket_id'] = ticket.id
        # Redirigimos a la URL base del chat para limpiar la URL.
        return redirect('tickets:chat')

    # --- El resto de la lógica es la misma que antes ---
    tickets_del_usuario = Ticket.objects.filter(usuario=request.user)

    ticket_activo = None
    logs_conversacion = []
    
    ticket_id_sesion = request.session.get('ticket_id')
    if ticket_id_sesion:
        try:
            ticket_activo = Ticket.objects.get(id=ticket_id_sesion, usuario=request.user)
            logs_conversacion = ticket_activo.logs.all()
        except Ticket.DoesNotExist:
            del request.session['ticket_id']

    if request.method == 'POST':
        mensaje_usuario = request.POST.get('mensaje', '').strip()

        if mensaje_usuario:
            if not ticket_activo or ticket_activo.estado in [Ticket.Estado.RESUELTO_BOT, Ticket.Estado.RESUELTO_TECNICO, Ticket.Estado.CERRADO]:
                ticket_activo = Ticket.objects.create(
                    usuario=request.user,
                    descripcion_inicial=mensaje_usuario
                )
                request.session['ticket_id'] = ticket_activo.id
            
            LogInteraccion.objects.create(
                ticket=ticket_activo,
                mensaje=mensaje_usuario,
                emisor=LogInteraccion.Emisor.USUARIO
            )
            
            process_user_request(ticket_activo.id, mensaje_usuario)

        return redirect('tickets:chat')

    context = {
        'tickets_del_usuario': tickets_del_usuario,
        'ticket_activo': ticket_activo,
        'logs_conversacion': logs_conversacion,
    }
    
    return render(request, 'tickets/chat.html', context)


@login_required
def new_chat_view(request):
    """
    Limpia el ID del ticket de la sesión para forzar la creación de uno nuevo.
    """
    if 'ticket_id' in request.session:
        del request.session['ticket_id']
    
    return redirect('tickets:chat')


@login_required
def rate_ticket_view(request, ticket_id, rating):
    """
    Guarda la calificación enviada por un usuario para un ticket específico.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id, usuario=request.user)

    if 1 <= rating <= 5:
        ticket.calificacion = rating
        ticket.save()
        print(f"Calificación de {rating} guardada para el Ticket #{ticket_id}")

    return redirect('tickets:chat')
