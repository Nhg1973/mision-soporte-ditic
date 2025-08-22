
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
            if not ticket_activo or ticket_activo.estado in [Ticket.Estado.CERRADO]:
                ticket_activo = Ticket.objects.create(
                    usuario=request.user,
                    descripcion_inicial=mensaje_usuario,
                    estado=Ticket.Estado.EN_PROCESO
                )
                request.session['active_ticket_id'] = ticket_activo.id
                graph_state = {}

            LogInteraccion.objects.create(
                ticket=ticket_activo,
                mensaje=mensaje_usuario,
                emisor=LogInteraccion.Emisor.USUARIO
            )

            initial_state = {
                "ticket_id": ticket_activo.id,
                "user_input": mensaje_usuario,
                "current_topic": graph_state.get("current_topic"),
                "topic_locked": graph_state.get("topic_locked", False),
                "clarification_attempts": graph_state.get("clarification_attempts", 0),
            }
            final_state = langgraph_app.invoke(initial_state)

            if final_state.get("final_response"):
                LogInteraccion.objects.create(
                    ticket=ticket_activo,
                    mensaje=final_state["final_response"],
                    emisor=LogInteraccion.Emisor.SISTEMA
                )

            # --- ¡BLOQUE DE CORRECCIÓN! ---
            # Antes de guardar en la sesión, convertimos los objetos no serializables.
            
            # 1. Hacemos una copia del estado para no modificar el original.
            serializable_state = final_state.copy()

            # 2. Convertimos el historial de chat a una lista de diccionarios simples.
            if serializable_state.get("chat_history"):
                serializable_chat_history = []
                for msg in serializable_state["chat_history"]:
                    serializable_chat_history.append({
                        "type": msg.type,      # 'human', 'ai', etc.
                        "content": msg.content # El texto del mensaje
                    })
                serializable_state["chat_history"] = serializable_chat_history

            # 3. Hacemos lo mismo con 'relevant_docs' si contiene objetos Document.
            if serializable_state.get("relevant_docs"):
                serializable_docs = []
                for doc in serializable_state["relevant_docs"]:
                    serializable_docs.append({
                        "page_content": doc.page_content,
                        "metadata": doc.metadata
                    })
                serializable_state["relevant_docs"] = serializable_docs

            # 4. Guardamos la versión 'segura' y serializable en la sesión.
            request.session['graph_state'] = serializable_state
            # --- FIN DEL BLOQUE DE CORRECCIÓN ---

        return redirect('tickets:chat')

    # Pasamos el estado del grafo al contexto de la plantilla
    context = {
        'tickets_del_usuario': tickets_del_usuario,
        'ticket_activo': ticket_activo,
        'logs_conversacion': logs_conversacion,
        # --- ¡CAMBIO CLAVE 2! ---
        # Añadimos el graph_state al contexto para que el HTML pueda usarlo.
        'graph_state': graph_state,
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