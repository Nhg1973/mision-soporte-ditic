# apps/ai_core/tools/knowledge_base.py

import os
import asyncio
from django.conf import settings
from functools import partial

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

SIMILARITY_THRESHOLD = 0.5

# --- ¡CAMBIO 1: AÑADIDO NUEVO PARÁMETRO 'topic'! ---
async def _asearch_vector_store(user_query: str, topic: str = None) -> list:
    """
    Lógica asíncrona principal para realizar la búsqueda, ahora con filtrado por tema.
    """
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            print("BÚSQUEDA VECTORIAL: Error - La clave de API de Gemini no está configurada.")
            return []

        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=gemini_api_key)
        persist_directory = os.path.join(settings.BASE_DIR, 'chroma_db')
        
        if not os.path.exists(persist_directory):
            print("BÚSQUEDA VECTORIAL: Error - El directorio de ChromaDB no existe.")
            return []

        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )

        # --- ¡CAMBIO 2: CONSTRUCCIÓN DEL FILTRO DE BÚSQUEDA! ---
        search_filter = {}
        if topic:
            # Este es el filtro de metadatos que ChromaDB usará.
            # Buscará solo en los chunks donde el metadato 'tema' coincida.
            search_filter = {"tema": topic}
            print(f"BÚSQUEDA VECTORIAL: Aplicando filtro de tema: '{topic}'")

        # --- ¡CAMBIO 3: LLAMADA A LA BÚSQUEDA CON EL FILTRO! ---
        # Usamos functools.partial para pasar argumentos nombrados de forma segura a asyncio.to_thread
        search_func = partial(
            vectorstore.similarity_search_with_score, 
            query=user_query, 
            k=5, 
            filter=search_filter # Aquí pasamos el filtro
        )
        docs_with_scores = await asyncio.to_thread(search_func)
        
        if not docs_with_scores:
            print("BÚSQUEDA VECTORIAL: No se encontraron fragmentos (incluso con filtro).")
            return []

        print(f"BÚSQUEDA VECTORIAL: Se encontraron {len(docs_with_scores)} fragmentos candidatos.")
        
        relevant_docs = []
        for doc, score in docs_with_scores:
            print(f"  - Documento candidato con puntuación: {score:.4f}")
            if score < SIMILARITY_THRESHOLD:
                relevant_docs.append(doc)

        if relevant_docs:
            print(f"BÚSQUEDA VECTORIAL: Se encontraron {len(relevant_docs)} fragmentos RELEVANTES (puntuación < {SIMILARITY_THRESHOLD}).")
        else:
            print(f"BÚSQUEDA VECTORIAL: Ningún fragmento superó el umbral de relevancia.")
            
        return relevant_docs

    except Exception as e:
        print(f"BÚSQUEDA VECTORIAL: Ocurrió un error al buscar en ChromaDB: {e}")
        return []

# --- ¡CAMBIO 4: AÑADIDO NUEVO PARÁMETRO 'topic' AL ENVOLTORIO! ---
def search_knowledge_base_vector(user_query: str, topic: str = None) -> list:
    """
    Envoltorio síncrono que ejecuta la búsqueda, pasando el filtro de tema.
    """
    print(f"BÚSQUEDA VECTORIAL: Iniciando búsqueda para la consulta: '{user_query}'")
    try:
        # Aquí pasamos el 'topic' a la función asíncrona
        return asyncio.run(_asearch_vector_store(user_query, topic=topic))
    except RuntimeError as e:
        if "cannot run loop while another loop is running" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_asearch_vector_store(user_query, topic=topic))
            loop.close()
            return result
        else:
            raise e
