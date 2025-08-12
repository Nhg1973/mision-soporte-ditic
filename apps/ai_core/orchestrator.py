import os
from apps.tickets.models import Ticket, LogInteraccion
from .tools.knowledge_base import search_knowledge_base_vector
from apps.tasks.tasks import notify_technician_task
from langchain_google_genai import ChatGoogleGenerativeAI

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def process_user_request(ticket_id, mensaje_actual):
    """
    Orquesta la respuesta usando un modelo con memoria conversacional.
    """
    print(f"ORQUESTADOR: Procesando ticket #{ticket_id} con el mensaje: '{mensaje_actual}'")
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        print(f"ORQUESTADOR: Error - No se encontró el ticket #{ticket_id}")
        return

    # 1. Obtenemos el historial completo de la conversación para darle memoria al bot.
    conversation_logs = ticket.logs.all().order_by('fecha_creacion')
    chat_history = "\n".join(
        [f"{log.get_emisor_display()}: {log.mensaje}" for log in conversation_logs]
    )

    # 2. Buscamos en la base de conocimiento usando el último mensaje.
    relevant_docs = search_knowledge_base_vector(mensaje_actual)
    context = "\n\n".join([doc.page_content for doc in relevant_docs]) if relevant_docs else "No se encontró información relevante en la base de conocimiento."

    # 3. Creamos el prompt conversacional que incluye el historial.
    prompt = (
        "Eres un asistente experto de la mesa de ayuda de DITIC para la Cancillería Argentina. "
        "Tu tarea es continuar la siguiente conversación de manera útil y coherente.\n\n"
        "**Instrucción Clave:** Analiza el historial completo de la conversación para entender el contexto. "
        "Tu respuesta debe basarse en el último mensaje del usuario, pero considerando todo lo que se ha hablado antes.\n\n"
        "Usa el siguiente contexto de la base de conocimiento si es relevante para la última pregunta del usuario. "
        "Si la base de conocimiento no ayuda, o si el usuario está respondiendo a una pregunta que hiciste, usa tu razonamiento para continuar la conversación de forma natural.\n\n"
        "Si tienes suficiente información para resolver el problema, hazlo. Si necesitas más detalles, haz preguntas claras. "
        "Si determinas que no puedes resolverlo, escala el problema a un técnico.\n\n"
        "--- INICIO DEL CONTEXTO DE LA BASE DE CONOCIMIENTO ---\n"
        "{context}\n"
        "--- FIN DEL CONTEXTO ---\n\n"
        "--- INICIO DEL HISTORIAL DE LA CONVERSACIÓN ---\n"
        "{chat_history}\n"
        "--- FIN DEL HISTORIAL ---\n\n"
        "Tu tarea es generar la siguiente respuesta del 'Sistema':"
    ).format(context=context, chat_history=chat_history)

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.3,
            google_api_key=GEMINI_API_KEY
        )
        response = llm.invoke(prompt)
        respuesta_ia = response.content if hasattr(response, "content") else str(response)

        LogInteraccion.objects.create(
            ticket=ticket,
            mensaje=respuesta_ia,
            emisor=LogInteraccion.Emisor.SISTEMA
        )
        print(f"ORQUESTADOR: Respuesta generada para el ticket #{ticket.id}")

        # Lógica de decisión: si la IA pide más información o dice que no sabe, escalamos.
        if "no puedo ayudarte" in respuesta_ia.lower() or "necesito más información" in respuesta_ia.lower() or "no contiene información" in respuesta_ia.lower():
             escalate_to_technician(ticket, "La IA determinó que se necesita asistencia humana.")
        else:
             # Si parece una solución, lo marcamos como resuelto por el bot.
             ticket.estado = Ticket.Estado.RESUELTO_BOT
             ticket.save()

    except Exception as e:
        print(f"ORQUESTADOR: Error al llamar a Gemini: {e}")
        escalate_to_technician(ticket, "Error en la API de IA.")


def escalate_to_technician(ticket, reason):
    """
    Función auxiliar para escalar un ticket a un técnico.
    """
    # Verificamos si el ticket ya fue escalado para no enviar notificaciones duplicadas.
    if ticket.estado == Ticket.Estado.ESCALADO:
        print(f"ORQUESTADOR: El ticket #{ticket.id} ya está escalado. No se enviará nueva notificación.")
        return

    print(f"ORQUESTADOR: Escalando a técnico. Razón: {reason}")
    ticket.estado = Ticket.Estado.ESCALADO
    ticket.save()
    
    # Este log es para el usuario y se añade a la conversación.
    mensaje_escalada = (
        f"He escalado tu consulta a un técnico con la siguiente nota: '{reason}'. "
        f"Se ha creado el Ticket #{ticket.id} y un técnico lo revisará a la brevedad."
    )
    LogInteraccion.objects.create(
        ticket=ticket,
        mensaje=mensaje_escalada,
        emisor=LogInteraccion.Emisor.SISTEMA
    )
    
    # --- LOG DE DEPURACIÓN AÑADIDO ---
    print(f"ORQUESTADOR: [DEBUG] Preparando para enviar tarea a Celery para el ticket #{ticket.id}...")
    notify_technician_task.delay(ticket.id)
    
    print(f"ORQUESTADOR: [DEBUG] Tarea para el ticket #{ticket.id} enviada a la cola de Celery.")

