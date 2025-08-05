import os
import asyncio
from django.conf import settings

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# --- Función Asíncrona Principal ---
# Esta función contiene la lógica de búsqueda que necesita un entorno asíncrono.
async def _asearch_vector_store(user_query: str) -> list:
    """
    Lógica asíncrona principal para realizar la búsqueda por similitud.
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

        # La búsqueda en sí es una operación que puede bloquear el hilo.
        # La ejecutamos en un hilo separado para no interferir con el bucle de eventos.
        relevant_docs = await asyncio.to_thread(vectorstore.similarity_search, user_query, k=3)
        
        if relevant_docs:
            print(f"BÚSQUEDA VECTORIAL: Se encontraron {len(relevant_docs)} fragmentos relevantes.")
        else:
            print("BÚSQUEDA VECTORIAL: No se encontraron fragmentos relevantes.")
            
        return relevant_docs

    except Exception as e:
        print(f"BÚSQUEDA VECTORIAL: Ocurrió un error al buscar en ChromaDB: {e}")
        return []

# --- Función Síncrona "Envoltorio" ---
# Esta es la función que nuestro orquestador síncrono llamará.
def search_knowledge_base_vector(user_query: str) -> list:
    """
    Envoltorio síncrono que crea un bucle de eventos para ejecutar de forma segura
    la lógica de búsqueda asíncrona.
    """
    print(f"BÚSQUEDA VECTORIAL: Iniciando búsqueda para la consulta: '{user_query}'")
    try:
        # asyncio.run() crea un nuevo bucle de eventos, ejecuta nuestra función
        # asíncrona hasta que termina, y luego cierra el bucle.
        return asyncio.run(_asearch_vector_store(user_query))
    except RuntimeError as e:
        # Manejo de un caso borde donde un bucle ya podría estar corriendo.
        if "cannot run loop while another loop is running" in str(e):
            print("BÚSQUEDA VECTORIAL: Detectado bucle de eventos existente. Creando uno nuevo.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_asearch_vector_store(user_query))
            loop.close()
            return result
        else:
            # Si es otro tipo de RuntimeError, lo relanzamos.
            raise e
