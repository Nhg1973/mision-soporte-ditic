# apps/ai_core/graph.py

import os
import json
from typing import List, TypedDict, Literal
from apps.tickets.models import Ticket, LogInteraccion
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from .tools.knowledge_base import search_knowledge_base_vector
from apps.tasks.tasks import notify_technician_task
from langgraph.graph import StateGraph, END
from .topics import get_master_topic_list

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ==============================================================================
# 1. Definición del Estado del Grafo
# ==============================================================================
class GraphState(TypedDict):
    ticket_id: int
    user_input: str
    chat_history: List[BaseMessage]
    final_response: str
    current_topic: str
    topic_confidence: str
    clarification_attempts: int
    topic_locked: bool
    rewritten_query: str
    relevant_docs: List[dict]

# ==============================================================================
# 2. Definición de los Nodos del Grafo (Versión Final y Limpia)
# ==============================================================================

def assemble_context(state: GraphState) -> dict:
    """Carga el historial de la conversación desde la BD."""
    print("--- GRAFO: NODO (assemble_context) ---")
    ticket_id = state['ticket_id']
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        logs = ticket.logs.all().order_by('fecha_creacion')
        chat_history = [HumanMessage(content=log.mensaje) if log.emisor == LogInteraccion.Emisor.USUARIO else AIMessage(content=log.mensaje) for log in logs]
        return {"chat_history": chat_history}
    except Ticket.DoesNotExist:
        return {"chat_history": []}

def determine_topic(state: GraphState) -> dict:
    """Clasifica la consulta del usuario en un tema y evalúa la confianza."""
    print("--- GRAFO: NODO (determine_topic) ---")
    if state.get('topic_locked'):
        print(f"-> Tema ya fijado en: '{state['current_topic']}'. Saltando clasificación.")
        return {"current_topic": state['current_topic'], "topic_confidence": "alta"}

    user_input, chat_history, master_topics = state['user_input'], state['chat_history'], get_master_topic_list()
    # En el nodo determine_topic de tu graph.py

    prompt = (
        "Eres un experto en clasificación de texto para una mesa de ayuda. Tu tarea es analizar la consulta de un usuario "
        "y determinar a cuál de los siguientes temas predefinidos pertenece. Debes también evaluar tu nivel de confianza.\n\n"
        "**Temas Disponibles:**\n"
        f"{', '.join(master_topics)}\n\n"
        "**Instrucciones:**\n"
        "1. Lee la 'Consulta del Usuario' y el 'Historial' para entender el contexto.\n"
        "2. Elige el tema más relevante de la lista de 'Temas Disponibles'.\n"
        "3. Evalúa tu confianza como 'alta', 'media' o 'baja'. La confianza debe ser 'alta' solo si la consulta es muy explícita. "
        "Si es ambigua o muy general, usa 'media'. Si no encaja en ningún tema, elige un tema general y usa 'baja'.\n"
        # --- ¡NUEVA INSTRUCCIÓN! ---
        "4. **MUY IMPORTANTE:** Si la consulta del usuario es una pregunta general como 'quiero actualizar mi página' o 'necesito ayuda', y el historial no da más contexto, es preferible que elijas un tema amplio como 'Información General' con confianza 'media' antes que un tema específico.\n"
        "5. Responde únicamente en formato JSON con las claves 'tema' y 'confianza'. Ejemplo: {\"tema\": \"Identidad Visual Web\", \"confianza\": \"alta\"}\n\n"
        f"**Historial:**\n{chat_history}\n\n"
        f"**Consulta del Usuario:**\n'{user_input}'\n\n"
        "**Respuesta JSON:**"
    )
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=GEMINI_API_KEY, response_mime_type="application/json")
        response = llm.invoke(prompt)
        result = json.loads(response.content)
        topic, confidence = result.get("tema", "Información General"), result.get("confianza", "baja")
        print(f"-> Tema Detectado: '{topic}' con confianza '{confidence}'")
        return {"current_topic": topic, "topic_confidence": confidence, "topic_locked": False, "clarification_attempts": 0}
    except Exception as e:
        print(f"-> ERROR al determinar el tema: {e}")
        return {"current_topic": "Información General", "topic_confidence": "baja"}

def ask_topic_clarification(state: GraphState) -> dict:
    """Genera una pregunta para que el usuario aclare el tema."""
    print("--- GRAFO: NODO (ask_topic_clarification) ---")
    attempts = state.get("clarification_attempts", 0)
    clarification_message = "Para poder ayudarte mejor, ¿podrías describir tu problema con otras palabras o indicar a qué tema se refiere?"
    return {"final_response": clarification_message, "clarification_attempts": attempts + 1}

def rewrite_query(state: GraphState) -> dict:
    """Reformula la pregunta del usuario para optimizar la búsqueda."""
    print("--- GRAFO: NODO (rewrite_query) ---")
    # ... (Esta función puede permanecer como la tenías, es una buena utilidad)
    user_input, chat_history = state['user_input'], state['chat_history']
    prompt = f"Reformula el siguiente mensaje de usuario como una pregunta completa y autónoma, considerando el historial. Historial:{chat_history}\nMensaje: {user_input}\nPregunta:"
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=GEMINI_API_KEY)
    response = llm.invoke(prompt)
    rewritten_query = response.content
    print(f"-> Pregunta optimizada: '{rewritten_query}'")
    return {"rewritten_query": rewritten_query, "topic_locked": True} # Fijamos el tema al proceder con la búsqueda

def search_knowledge_base(state: GraphState) -> dict:
    """Busca en la BD vectorial usando un filtro de tema."""
    print("--- GRAFO: NODO (search_knowledge_base) ---")
    rewritten_query, current_topic = state['rewritten_query'], state.get('current_topic')
    print(f"-> Buscando con la consulta: '{rewritten_query}' y filtro de tema: '{current_topic}'")
    relevant_docs = search_knowledge_base_vector(rewritten_query, topic=current_topic)
    return {"relevant_docs": relevant_docs}

def generate_response(state: GraphState) -> dict:
    """Genera una respuesta basada en el conocimiento encontrado."""
    print("--- GRAFO: NODO (generate_response) ---")
    rewritten_query, relevant_docs = state['rewritten_query'], state['relevant_docs']
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    prompt = (
        "Eres un asistente de soporte experto. Responde la pregunta del usuario basándote ESTRICTAMENTE en el siguiente contexto. "
        "Sé claro y conciso.\n\n"
        f"Pregunta: '{rewritten_query}'\n\n"
        f"Contexto:\n---\n{context}\n---\n\n"
        "Respuesta:"
    )
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2, google_api_key=GEMINI_API_KEY)
    response = llm.invoke(prompt)
    return {"final_response": response.content}

def escalate_to_technician(state: GraphState) -> dict:
    """Prepara un mensaje de escalada y notifica al técnico."""
    print("--- GRAFO: NODO (escalate_to_technician) ---")
    ticket_id, user_input = state['ticket_id'], state['user_input']
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        ticket.estado = Ticket.Estado.ESCALADO
        ticket.save()
    except Ticket.DoesNotExist: pass
    escalation_message = f"No he podido resolver tu consulta sobre '{user_input}'. He escalado el Ticket #{ticket_id} a un técnico."
    notify_technician_task.delay(ticket_id)
    return {"final_response": escalation_message}

# ==============================================================================
# 3. Routers y Construcción del Grafo
# ==============================================================================
def route_by_topic_confidence(state: GraphState) -> Literal["ask_clarification", "rewrite_query", "escalate"]:
    """Router que dirige el flujo basándose en la confianza del tema."""
    print("--- GRAFO: ROUTER (route_by_topic_confidence) ---")
    confidence, attempts = state.get("topic_confidence", "baja"), state.get("clarification_attempts", 0)
    if confidence == "alta":
        return "rewrite_query"
    elif confidence == "media" and attempts < 1:
        return "ask_clarification"
    else:
        return "escalate"

def route_after_search(state: GraphState) -> Literal["generate_response", "escalate_to_technician"]:
    """Router que decide si responder o escalar después de la búsqueda."""
    print("--- GRAFO: ROUTER (route_after_search) ---")
    return "generate_response" if state['relevant_docs'] else "escalate_to_technician"

workflow = StateGraph(GraphState)

# Añadimos los nodos
workflow.add_node("assemble_context", assemble_context)
workflow.add_node("determine_topic", determine_topic)
workflow.add_node("ask_topic_clarification", ask_topic_clarification)
workflow.add_node("rewrite_query", rewrite_query)
workflow.add_node("search_knowledge_base", search_knowledge_base)
workflow.add_node("generate_response", generate_response)
workflow.add_node("escalate_to_technician", escalate_to_technician)

# Construimos el flujo
workflow.set_entry_point("assemble_context")
workflow.add_edge("assemble_context", "determine_topic")

# Primer router: por confianza del tema
workflow.add_conditional_edges(
    "determine_topic",
    route_by_topic_confidence,
    {
        "ask_clarification": "ask_topic_clarification",
        "rewrite_query": "rewrite_query",
        "escalate": "escalate_to_technician"
    }
)
# El camino de la búsqueda
workflow.add_edge("rewrite_query", "search_knowledge_base")

# Segundo router: por resultados de la búsqueda
workflow.add_conditional_edges(
    "search_knowledge_base",
    route_after_search,
    {
        "generate_response": "generate_response",
        "escalate_to_technician": "escalate_to_technician"
    }
)
# Puntos finales
workflow.add_edge("generate_response", END)
workflow.add_edge("escalate_to_technician", END)
workflow.add_edge("ask_topic_clarification", END)

app = workflow.compile()
print("--- GRAFO v3.2 COMPILADO Y LISTO (ARQUITECTURA REFINADA) ---")