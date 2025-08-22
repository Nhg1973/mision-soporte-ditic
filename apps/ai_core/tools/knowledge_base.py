# apps/ai_core/tools/knowledge_base.py

import os
import asyncio
from django.conf import settings
from functools import partial
from typing import List

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

SIMILARITY_THRESHOLD = 0.45

# --- ¡FUNCIÓN CORREGIDA Y FINAL! ---
async def _asearch_vector_store(user_query: str, topic: str = None, subtopic: str = None, tags: List[str] = None) -> list:
    """
    Lógica asíncrona principal para realizar la búsqueda, con construcción de
    filtros múltiples robusta para ChromaDB.
    """
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=os.getenv('GEMINI_API_KEY'))
        persist_directory = os.path.join(settings.BASE_DIR, 'chroma_db')
        vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embeddings)

        # --- ¡NUEVA LÓGICA DE CONSTRUCCIÓN DE FILTRO! ---
        conditions = []
        if topic:
            conditions.append({"tema": topic})
        if subtopic and subtopic.lower() != 'general':
            conditions.append({"subtema": subtopic})
        
        if tags:
            tag_filter = {"$or": [{"tags": {"$like": f"%{tag}%"}} for tag in tags]}
            conditions.append(tag_filter)

        # Construimos el filtro final dependiendo de cuántas condiciones haya
        search_filter = None
        if len(conditions) > 1:
            search_filter = {"$and": conditions}
        elif len(conditions) == 1:
            search_filter = conditions[0]
        
        search_kwargs = {'k': 5}
        if search_filter:
            search_kwargs['filter'] = search_filter
            print(f"BÚSQUEDA VECTORIAL: Aplicando filtro compuesto: {search_filter}")

        search_func = partial(vectorstore.similarity_search_with_score, query=user_query, **search_kwargs)
        docs_with_scores = await asyncio.to_thread(search_func)
        
        # ... (el resto de la lógica para filtrar por umbral no cambia) ...
        relevant_docs = []
        if docs_with_scores:
            print(f"BÚSQUEDA VECTORIAL: Se encontraron {len(docs_with_scores)} fragmentos candidatos.")
            for doc, score in docs_with_scores:
                if score < SIMILARITY_THRESHOLD:
                    relevant_docs.append(doc)
            print(f"BÚSQUEDA VECTORIAL: Se encontraron {len(relevant_docs)} fragmentos RELEVANTES.")
        else:
            print("BÚSQUEDA VECTORIAL: No se encontraron fragmentos.")
            
        return relevant_docs

    except Exception as e:
        print(f"BÚSQUEDA VECTORIAL: Ocurrió un error al buscar en ChromaDB: {e}")
        return []

# --- El envoltorio síncrono no necesita cambios, solo pasar los argumentos ---
def search_knowledge_base_vector(user_query: str, topic: str = None, subtopic: str = None, tags: List[str] = None) -> list:
    """Envoltorio síncrono que ejecuta la búsqueda, pasando los filtros."""
    print(f"BÚSQUEDA VECTORIAL: Iniciando búsqueda para la consulta: '{user_query}'")
    try:
        # Pasamos todos los argumentos a la función asíncrona
        return asyncio.run(_asearch_vector_store(user_query, topic=topic, subtopic=subtopic, tags=tags))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_asearch_vector_store(user_query, topic=topic, subtopic=subtopic, tags=tags))
        loop.close()
        return result