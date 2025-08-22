import os
import json
from typing import List, TypedDict, Literal
from apps.tickets.models import Ticket, LogInteraccion, KnowledgeDocument
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from .tools.knowledge_base import search_knowledge_base_vector
from apps.tasks.tasks import notify_technician_task
from langgraph.graph import StateGraph, END

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ==============================================================================
# 1. Definición del Estado del Grafo (Versión Final y Definitiva)
# ==============================================================================
class GraphState(TypedDict):
    """
    Estado final que soporta la clasificación jerárquica y el enrutamiento avanzado.
    """
    # --- Datos de la Conversación ---
    ticket_id: int
    user_input: str
    chat_history: List[BaseMessage]
    final_response: str
    
    # --- Contexto Dinámico ---
    temas_disponibles: List[str]
    subtemas_disponibles: List[str]
    tags_disponibles: List[str]
    
    # --- Datos de Interpretación ---
    tema_detectado: str
    subtema_detectado: str
    confianza: str
    ruta_de_resolucion: str
    
    # --- Flujo de Búsqueda ---
    rewritten_query: str
    relevant_docs: List[Document]

    clarification_attempts: int

# ==============================================================================
# 2. Nodos del Grafo
# ==============================================================================

def assemble_context(state: GraphState) -> dict:
    """Carga el historial y la lista dinámica de temas, subtemas y tags desde la BD."""
    print("--- GRAFO: NODO (assemble_context) ---")
    ticket_id = state['ticket_id']
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        logs = ticket.logs.all().order_by('fecha_creacion')
        chat_history = [HumanMessage(content=log.mensaje) if log.emisor == LogInteraccion.Emisor.USUARIO else AIMessage(content=log.mensaje) for log in logs]
    except Ticket.DoesNotExist:
        chat_history = []
    
    processed_docs = KnowledgeDocument.objects.filter(estado_procesamiento='COMPLETED')
    temas_disponibles = list(processed_docs.values_list('tema', flat=True).distinct())
    subtemas_disponibles = list(processed_docs.exclude(subtema__isnull=True).exclude(subtema__exact='').values_list('subtema', flat=True).distinct())
    
    all_tags_lists = processed_docs.exclude(tags__isnull=True).exclude(tags__exact='').values_list('tags', flat=True)
    tags_disponibles = set()
    for tag_string in all_tags_lists:
        tags = [tag.strip() for tag in tag_string.split(',')]
        tags_disponibles.update(tags)
    
    if not temas_disponibles:
        temas_disponibles = list(KnowledgeDocument.TemaChoices.labels)
    
    print(f"-> Temas disponibles: {temas_disponibles}")
    print(f"-> Subtemas/Entidades disponibles: {subtemas_disponibles}")
    print(f"-> Tags disponibles: {sorted(list(tags_disponibles))}")
    
    return {
        "chat_history": chat_history, 
        "temas_disponibles": temas_disponibles,
        "subtemas_disponibles": subtemas_disponibles,
        "tags_disponibles": sorted(list(tags_disponibles))
    }

def interpret_query(state: GraphState) -> dict:
    """Super-Nodo con prompt mejorado para entender el contexto conversacional y evitar bucles."""
    print("--- GRAFO: NODO (interpret_query) ---")
    user_input, chat_history, temas_disponibles, subtemas_disponibles = state['user_input'], state['chat_history'], state['temas_disponibles'], state['subtemas_disponibles']
    
    # --- ¡PROMPT DEFINITIVO CON LÓGICA CONVERSACIONAL! ---
    prompt = (
        "Eres un experto en NLU para una mesa de ayuda. Tu tarea es analizar la consulta y el historial para crear un plan de acción en JSON. Sigue estas reglas en orden de prioridad:\n\n"
        "**Reglas de Decisión para 'ruta_de_resolucion':**\n"
        "1. **SI el último mensaje en el historial fue una pregunta del bot pidiendo aclarar un sistema, Y la nueva consulta del usuario menciona una entidad conocida (como 'INFOGES', 'VPN'), la ruta DEBE ser 'base_de_conocimiento' y la confianza 'alta'.**\n"
        "2. SI la consulta menciona un problema físico que requiere acción (ej: 'no enciende', 'está roto'), la ruta DEBE ser 'intervencion_humana'.\n"
        "3. SI la consulta es muy vaga y NO menciona una entidad específica (ej: 'no funciona'), la ruta DEBE ser 'pedir_aclaracion'.\n"
        "4. SI la consulta no es de DITIC (ej: 'recibo de sueldo'), la ruta DEBE ser 'tema_ajeno'.\n"
        "5. EN CUALQUIER OTRO CASO que parezca una pregunta informativa con una entidad clara, la ruta debe ser 'base_de_conocimiento'.\n\n"
        "**Jerarquía a completar:**\n"
        f"- **tema:** Elige de: {', '.join(temas_disponibles)}.\n"
        f"- **subtema:** Identifica la entidad específica (ej: 'INFOGES'). Usa la lista de entidades conocidas como referencia: {', '.join(subtemas_disponibles)}. Si no hay, usa 'General'.\n"
        "- **ruta_de_resolucion:** Elige según las reglas de arriba.\n"
        "- **confianza:** Evalúa tu confianza general: 'alta', 'media', 'baja'.\n\n"
        f"**Historial:** {chat_history}\n**Consulta del Usuario:** '{user_input}'\n\n"
        "**JSON (solo el objeto con claves en minúscula):**"
    )
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=GEMINI_API_KEY, model_kwargs={"response_mime_type": "application/json"})
        response = llm.invoke(prompt)
        result = json.loads(response.content)
        print(f"-> Plan de Acción del LLM: {result}")
        
        return {
            "tema_detectado": result.get("tema", "General"),
            "subtema_detectado": result.get("subtema", "General"),
            "ruta_de_resolucion": result.get("ruta_de_resolucion", "pedir_aclaracion"),
            "confianza": result.get("confianza", "baja")
        }
    except Exception as e:
        print(f"-> ERROR al interpretar la consulta: {e}")
        return {"ruta_de_resolucion": "intervencion_humana", "confianza": "baja"}

def rewrite_query_and_search(state: GraphState) -> dict:
    """Implementa la búsqueda jerárquica en cascada."""
    print("--- GRAFO: NODO (rewrite_query_and_search) ---")
    user_input, chat_history, tema_detectado, subtema_detectado, entidades = state['user_input'], state['chat_history'], state['tema_detectado'], state['subtema_detectado'], state.get('entidades_detectadas', [])
    
    rewrite_prompt = f"Reformula el siguiente mensaje de usuario como una pregunta clara y autónoma. Historial:{chat_history}\nMensaje: {user_input}\nPregunta:"
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=GEMINI_API_KEY)
    response = llm.invoke(rewrite_prompt)
    rewritten_query = response.content.strip()
    print(f"-> Pregunta optimizada: '{rewritten_query}'")

    print(f"-> 1er Intento (Quirúrgico): Buscando por tema='{tema_detectado}' y subtema='{subtema_detectado}'")
    relevant_docs = search_knowledge_base_vector(rewritten_query, topic=tema_detectado, subtopic=subtema_detectado)
    
    if not relevant_docs and entidades:
        print(f"-> 2do Intento (Lateral): Buscando por tema='{tema_detectado}' y tags={entidades}")
        relevant_docs = search_knowledge_base_vector(rewritten_query, topic=tema_detectado, tags=entidades)

    if not relevant_docs:
        print(f"-> 3er Intento (Amplio): Buscando solo por tema='{tema_detectado}'")
        relevant_docs = search_knowledge_base_vector(rewritten_query, topic=tema_detectado)

    print(f"-> Búsqueda finalizada. Se encontraron {len(relevant_docs)} fragmentos.")
    return {"rewritten_query": rewritten_query, "relevant_docs": relevant_docs}

def rewrite_query_and_search(state: GraphState) -> dict:
    """Implementa la búsqueda jerárquica en cascada."""
    print("--- GRAFO: NODO (rewrite_query_and_search) ---")
    user_input, chat_history, tema_detectado, subtema_detectado, entidades = state['user_input'], state['chat_history'], state['tema_detectado'], state['subtema_detectado'], state.get('entidades_detectadas', [])
    
    rewrite_prompt = f"Reformula el siguiente mensaje de usuario como una pregunta clara y autónoma. Historial:{chat_history}\nMensaje: {user_input}\nPregunta:"
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=GEMINI_API_KEY)
    response = llm.invoke(rewrite_prompt)
    rewritten_query = response.content.strip()
    print(f"-> Pregunta optimizada: '{rewritten_query}'")

    print(f"-> 1er Intento (Quirúrgico): Buscando por tema='{tema_detectado}' y subtema='{subtema_detectado}'")
    relevant_docs = search_knowledge_base_vector(rewritten_query, topic=tema_detectado, subtopic=subtema_detectado)
    
    if not relevant_docs and entidades:
        print(f"-> 2do Intento (Lateral): Buscando por tema='{tema_detectado}' y tags={entidades}")
        relevant_docs = search_knowledge_base_vector(rewritten_query, topic=tema_detectado, tags=entidades)

    if not relevant_docs:
        print(f"-> 3er Intento (Amplio): Buscando solo por tema='{tema_detectado}'")
        relevant_docs = search_knowledge_base_vector(rewritten_query, topic=tema_detectado)

    print(f"-> Búsqueda finalizada. Se encontraron {len(relevant_docs)} fragmentos.")
    return {"rewritten_query": rewritten_query, "relevant_docs": relevant_docs}

def generate_response(state: GraphState) -> dict:
    """Genera una respuesta final, sintetizando la información del contexto."""
    print("--- GRAFO: NODO (generate_response) ---")
    rewritten_query, relevant_docs, chat_history = state['rewritten_query'], state['relevant_docs'], state['chat_history']
    context = "\n\n---\n\n".join([doc.page_content for doc in relevant_docs])
    prompt = (
        "Eres un asistente de soporte experto. Sintetiza la información del contexto para dar una respuesta directa y útil a la pregunta del usuario. No hables *sobre* el contexto, úsalo. Si la información es parcial, entrégala y explica qué falta.\n"
        f"Historial: {chat_history}\nPregunta: '{rewritten_query}'\nContexto:\n{context}\nRespuesta:"
    )
    llm_resp = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2, google_api_key=GEMINI_API_KEY)
    response = llm_resp.invoke(prompt)
    return {"final_response": response.content}

def ask_clarification(state: GraphState) -> dict:
    """Genera una pregunta para aclarar la consulta del usuario."""
    print("--- GRAFO: NODO (ask_clarification) ---")
    attempts = state.get("clarification_attempts", 0)
    return {
        "final_response": "No estoy seguro de entender completamente tu consulta. ¿Podrías indicarme el sistema o equipo específico al que te refieres?",
        "clarification_attempts": attempts + 1
    }

def escalate_human(state: GraphState) -> dict:
    """Prepara un mensaje de escalada y notifica al equipo correspondiente según el tema detectado en la consulta."""
    print("--- GRAFO: NODO (escalate_human - Lógica Diferenciada) ---")
    ticket_id = state['ticket_id']
    user_input = state['user_input']
    tema_detectado = state.get("tema_detectado", "General")

    if tema_detectado == KnowledgeDocument.TemaChoices.SOFTWARE:
        equipo = "la Mesa de Ayuda (Software)"
        estado_ticket = Ticket.Estado.ESCALADO_ADMIN
    elif tema_detectado == KnowledgeDocument.TemaChoices.HARDWARE:
        equipo = "un técnico de Soporte (Hardware)"
        estado_ticket = Ticket.Estado.ESCALADO
    elif tema_detectado == KnowledgeDocument.TemaChoices.ABUSO:
        equipo = "el equipo de Control"
        estado_ticket = Ticket.Estado.ESCALADO_ADMIN
    else:
        equipo = "un miembro del equipo de soporte"
        estado_ticket = Ticket.Estado.ESCALADO
    
    print(f"-> Decisión de escalamiento: Tema='{tema_detectado}', Equipo='{equipo}'")
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        ticket.estado = estado_ticket
        ticket.save()
        notify_technician_task.delay(ticket.id)
    except Ticket.DoesNotExist: pass
    
    escalation_message = f"He derivado tu consulta sobre '{user_input}' a {equipo} (Ticket #{ticket_id}). Se pondrán en contacto a la brevedad."
    return {"final_response": escalation_message}

# --- ¡ÚNICA FUNCIÓN MODIFICADA! ---
def main_router(state: GraphState) -> Literal["search", "clarify", "escalate"]:
    """
    Router principal que implementa la regla de "Entidad No Negociable" y el límite de aclaraciones.
    Esta versión es la definitiva, alineada con la estrategia final.
    """
    print("--- GRAFO: ROUTER PRINCIPAL (LÓGICA FINAL) ---")
    
    ruta = state.get("ruta_de_resolucion", "pedir_aclaracion")
    confianza = state.get("confianza", "baja")
    subtema_detectado = state.get("subtema_detectado", "General")
    attempts = state.get("clarification_attempts", 0)

    # Regla 1: Límite de Aclaraciones
    if attempts >= 2:
        print("-> Límite de aclaraciones alcanzado. Escalando.")
        return "escalate"

    # Regla 2: Obedecer la orden de aclarar
    if ruta == "pedir_aclaracion":
        print("-> Plan del LLM es 'pedir_aclaracion'. Forzando aclaración.")
        return "clarify"

    # Regla 3: Entidad No Negociable
    if subtema_detectado.lower() == 'general':
        print(f"-> Entidad no detectada ('{subtema_detectado}'). Forzando aclaración.")
        return "clarify"

    # Regla 4: Confianza Baja como última red de seguridad
    if confianza == "baja":
        print("-> Confianza BAJA. Escalando.")
        return "escalate"

    # Si pasamos todas las validaciones, obedecemos el plan
    if ruta == "base_de_conocimiento":
        print(f"-> Confianza {confianza} y Entidad '{subtema_detectado}' OK. Procediendo a buscar.")
        return "search"
    else: # intervencion_humana, tema_ajeno
        print(f"-> Ruta del Plan es '{ruta}'. Escalando.")
        return "escalate"

def route_after_search(state: GraphState) -> Literal["generate_response", "escalate_human"]:
    """Router secundario que actúa después de la búsqueda."""
    print("--- GRAFO: ROUTER SECUNDARIO (POST-BÚSQUEDA) ---")
    if state["relevant_docs"]:
        print("-> Búsqueda exitosa. Generando respuesta.")
        return "generate_response"
    else:
        print("-> Búsqueda sin resultados. Escalando.")
        return "escalate_human"

# ==============================================================================
# 3. Construcción y Compilación del Grafo
# ==============================================================================
workflow = StateGraph(GraphState)

workflow.add_node("assemble_context", assemble_context)
workflow.add_node("interpret_query", interpret_query)
workflow.add_node("ask_clarification", ask_clarification)
workflow.add_node("rewrite_query_and_search", rewrite_query_and_search)
workflow.add_node("generate_response", generate_response)
workflow.add_node("escalate_human", escalate_human)

workflow.set_entry_point("assemble_context")
workflow.add_edge("assemble_context", "interpret_query")

workflow.add_conditional_edges(
    "interpret_query",
    main_router,
    {"search": "rewrite_query_and_search", "clarify": "ask_clarification", "escalate": "escalate_human"}
)
workflow.add_conditional_edges("rewrite_query_and_search", route_after_search)

workflow.add_edge("generate_response", END)
workflow.add_edge("ask_clarification", END)
workflow.add_edge("escalate_human", END)

app = workflow.compile()

print("--- GRAFO FINAL (v5.4) COMPILADO Y LISTO ---")