from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ticket, LogInteraccion
from apps.ai_core.orchestrator import process_user_request

@login_required
def chat_view(request, ticket_id=None):
    """
    Gestiona la lógica del chat web, ahora con un manejo de sesión robusto.
    """
    # Si se pasa un ticket_id en la URL, se establece como la conversación activa.
    if ticket_id:
        ticket = get_object_or_404(Ticket, id=ticket_id, usuario=request.user)
        request.session['active_ticket_id'] = ticket.id
        return redirect('tickets:chat')

    # Obtenemos todos los tickets del usuario para el historial.
    tickets_del_usuario = Ticket.objects.filter(usuario=request.user)
    
    # Buscamos el ticket activo en la sesión.
    ticket_activo = None
    logs_conversacion = []
    active_ticket_id = request.session.get('active_ticket_id')
    if active_ticket_id:
        try:
            ticket_activo = Ticket.objects.get(id=active_ticket_id, usuario=request.user)
            logs_conversacion = ticket_activo.logs.all()
        except Ticket.DoesNotExist:
            del request.session['active_ticket_id']

    # Procesamos el envío de un nuevo mensaje.
    if request.method == 'POST':
        mensaje_usuario = request.POST.get('mensaje', '').strip()
        if mensaje_usuario:
            # --- LÓGICA CORREGIDA ---
            # Si el ticket activo está resuelto o no hay ninguno, creamos uno nuevo.
            if not ticket_activo or ticket_activo.estado in [Ticket.Estado.RESUELTO_TECNICO, Ticket.Estado.CERRADO]:#Ticket.Estado.RESUELTO_BOT,
                ticket_activo = Ticket.objects.create(
                    usuario=request.user,
                    descripcion_inicial=mensaje_usuario
                )
                request.session['active_ticket_id'] = ticket_activo.id
            
            # Guardamos el nuevo mensaje en el log del ticket activo.
            LogInteraccion.objects.create(
                ticket=ticket_activo,
                mensaje=mensaje_usuario,
                emisor=LogInteraccion.Emisor.USUARIO
            )
            
            # Le pasamos el control al orquestador.
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
    Limpia el ID del ticket activo de la sesión para forzar una nueva conversación.
    """
    if 'active_ticket_id' in request.session:
        del request.session['active_ticket_id']
    return redirect('tickets:chat')


@login_required
def rate_ticket_view(request, ticket_id, rating):
    """
    Procesa la calificación, CIERRA el ticket y limpia la sesión.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id, usuario=request.user)

    # Solo permite calificar tickets que no estén ya cerrados.
    if ticket.estado != Ticket.Estado.CERRADO:
        if 1 <= rating <= 5:
            ticket.calificacion = rating
            # ¡Paso clave! Marcamos el ticket como cerrado.
            ticket.estado = Ticket.Estado.CERRADO 
            ticket.save()

        # ¡Paso clave 2! Limpiamos la sesión para que el siguiente chat sea nuevo.
        if request.session.get('active_ticket_id') == ticket.id:
            del request.session['active_ticket_id']

    return redirect('tickets:chat')

