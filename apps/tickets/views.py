
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ticket, LogInteraccion
from apps.ai_core.graph import app as langgraph_app

@login_required
def chat_view(request, ticket_id=None):
    """
    Gestiona la lógica del chat web. Ahora invoca el grafo de LangGraph
    para procesar las solicitudes de los usuarios.
    """
    if ticket_id:
        ticket = get_object_or_404(Ticket, id=ticket_id, usuario=request.user)
        request.session['active_ticket_id'] = ticket.id
        return redirect('tickets:chat')

    tickets_del_usuario = Ticket.objects.filter(usuario=request.user)
    
    ticket_activo = None
    logs_conversacion = []
    active_ticket_id = request.session.get('active_ticket_id')
    if active_ticket_id:
        try:
            ticket_activo = Ticket.objects.get(id=active_ticket_id, usuario=request.user)
            logs_conversacion = ticket_activo.logs.all()
        except Ticket.DoesNotExist:
            del request.session['active_ticket_id']

    graph_state = request.session.get('graph_state', {})

    if request.method == 'POST':
        mensaje_usuario = request.POST.get('mensaje', '').strip()
        if mensaje_usuario:
            # Lógica para crear un ticket nuevo si es necesario (ESTA PARTE ESTÁ BIEN)
            if not ticket_activo or ticket_activo.estado in [Ticket.Estado.RESUELTO_BOT, Ticket.Estado.RESUELTO_TECNICO, Ticket.Estado.CERRADO]:
                ticket_activo = Ticket.objects.create(
                    usuario=request.user,
                    descripcion_inicial=mensaje_usuario,
                    estado=Ticket.Estado.EN_PROCESO # ¡Mejora! Nace 'En Proceso'.
                )
                request.session['active_ticket_id'] = ticket_activo.id

            # Guardamos el mensaje del usuario (ESTA PARTE ESTÁ BIEN)
            LogInteraccion.objects.create(
                ticket=ticket_activo,
                mensaje=mensaje_usuario,
                emisor=LogInteraccion.Emisor.USUARIO
            )

            # --- ¡INTEGRACIÓN CON LANGGRAPH! ---
            initial_state = {
                "ticket_id": ticket_activo.id,
                "user_input": mensaje_usuario,
                "current_topic": graph_state.get("current_topic"),
                "topic_locked": graph_state.get("topic_locked", False),
                "clarification_attempts": graph_state.get("clarification_attempts", 0),
            }
            final_state = langgraph_app.invoke(initial_state)

            # Guardamos la respuesta final generada por el grafo (ESTA PARTE ESTÁ BIEN)
            if final_state.get("final_response"):
                LogInteraccion.objects.create(
                    ticket=ticket_activo,
                    mensaje=final_state["final_response"],
                    emisor=LogInteraccion.Emisor.SISTEMA
                )

            # ¡YA NO HACEMOS NADA MÁS! EL TICKET SIGUE 'EN PROCESO'.

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
        if 1 <= int(rating) <= 5:
            ticket.calificacion = rating
            # ¡PASO CLAVE 1! Marcamos el ticket como cerrado.
            ticket.estado = Ticket.Estado.CERRADO 
            ticket.save()

        # ¡PASO CLAVE 2! Limpiamos la sesión para que el siguiente chat sea nuevo,
        # sin importar si la calificación fue válida o no.
        if 'active_ticket_id' in request.session:
            del request.session['active_ticket_id']

    return redirect('tickets:chat')