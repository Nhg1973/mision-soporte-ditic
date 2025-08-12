# telegram_bot/handlers.py

from telegram import Update
from telegram.ext import ContextTypes
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from apps.tickets.models import Ticket, LogInteraccion
# Importamos la app de LangGraph, ¡el cerebro del sistema!
from apps.ai_core.graph import app as langgraph_app

# Esta es la única función que necesitamos. Es el punto de entrada para todos los mensajes.
@sync_to_async
def handle_message(update: Update):
    """
    Procesa mensajes de Telegram. Mantiene el hilo de la conversación buscando
    tickets activos para el usuario antes de crear uno nuevo.
    """
    message = update.message
    if not message or not message.text or message.text.startswith('/'):
        # Ignoramos mensajes que no son de texto o que son comandos (como /resolver)
        return

    telegram_username = message.from_user.username
    if not telegram_username:
        # Es buena práctica requerir un nombre de usuario.
        # await message.reply_text("Por favor, configura un nombre de usuario en tu perfil de Telegram.")
        # O podemos generar uno si no existe:
        telegram_username = f"telegram_user_{message.from_user.id}"

    user_text = message.text

    # --- LÓGICA DE GESTIÓN DE CONVERSACIÓN ---

    # 1. Buscamos o creamos el usuario de Django.
    user, _ = User.objects.get_or_create(username=telegram_username)

    # 2. Buscamos un ticket ACTIVO para este usuario.
    active_ticket = Ticket.objects.filter(
        usuario=user,
        estado__in=[Ticket.Estado.NUEVO, Ticket.Estado.EN_PROCESO, Ticket.Estado.ESCALADO]
    ).order_by('-fecha_creacion').first()

    # 3. Si no hay ticket activo, CREAMOS uno nuevo.
    if not active_ticket:
        print(f"HANDLER: No se encontró ticket activo para {telegram_username}. Creando uno nuevo.")
        active_ticket = Ticket.objects.create(
            usuario=user,
            descripcion_inicial=user_text,
            canal_origen=Ticket.Canal.TELEGRAM,
            estado=Ticket.Estado.EN_PROCESO
        )
    else:
        print(f"HANDLER: Continuando conversación en ticket #{active_ticket.id} para {telegram_username}.")

    # 4. Guardamos el mensaje del usuario en el log del ticket correcto.
    LogInteraccion.objects.create(
        ticket=active_ticket,
        mensaje=user_text,
        emisor=LogInteraccion.Emisor.USUARIO
    )

    # 5. Invocamos el grafo de LangGraph (igual que en la web).
    initial_state = {
        "ticket_id": active_ticket.id,
        "user_input": user_text,
    }
    final_state = langgraph_app.invoke(initial_state)
    bot_response = final_state.get('final_response', 'Lo siento, no pude procesar tu solicitud.')

    # 6. Guardamos la respuesta del bot en el log.
    LogInteraccion.objects.create(
        ticket=active_ticket,
        mensaje=bot_response,
        emisor=LogInteraccion.Emisor.SISTEMA
    )
    
    # 7. Enviamos la respuesta de vuelta al usuario en Telegram.
    # Esta parte requiere que tu bot tenga permisos para enviar mensajes.
    # await update.message.reply_text(bot_response)
    print(f"HANDLER: Respuesta para {telegram_username}: {bot_response}")


# Nota: La función que envía el mensaje (`reply_text`) está comentada
# para que no falle si no has configurado la librería `python-telegram-bot`
# con un `Application` builder. El `print` te mostrará la respuesta en la consola.