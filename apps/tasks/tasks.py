from celery import shared_task
from django.conf import settings
from apps.tickets.models import KnowledgeDocument, Ticket, TechnicianProfile, OutgoingTelegramMessage
import os
import json

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma

from telegram_bot.sender import send_telegram_message_sync


# ==============================================================================
# Tarea de Notificación al Técnico (Mejorada)
# ==============================================================================
@shared_task
def notify_technician_task(ticket_id):
    """
    Tarea de Celery para notificar a un técnico sobre un nuevo ticket escalado.
    """
    print(f"CELERY: ¡Tarea recibida! Notificar al técnico sobre el Ticket #{ticket_id}.")
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # Lógica para encontrar un técnico disponible (sin cambios)
        active_technician = TechnicianProfile.objects.filter(
            is_active_technician=True,
            telegram_chat_id__isnull=False
        ).first()

        if active_technician:
            print(f"CELERY: Técnico encontrado: {active_technician.user.username}. Enviando notificación...")
            
            # --- ¡MENSAJE MEJORADO! ---
            # Ahora el mensaje es más detallado e incluye instrucciones claras.
            # Usamos formato Markdown para una mejor visualización en Telegram.
            message = (
                f"🔔 *Nuevo Ticket Asignado*\n\n"
                f"*Ticket ID:* `{ticket.id}`\n"
                f"*Usuario:* {ticket.usuario.username}\n\n"
                f"*Consulta:*\n_{ticket.descripcion_inicial}_\n\n"
                f"--- \n"
                f"Para resolver, responda a este mensaje con:\n"
                f"`/resolver <su mensaje de solución>`"
            )
            
            # Usamos nuestro sender para enviar el mensaje.
            send_telegram_message_sync(active_technician.telegram_chat_id, message)
            
            return f"Notificación para el ticket {ticket_id} enviada a {active_technician.user.username}."
        else:
            print("CELERY: No se encontraron técnicos activos con un ID de Telegram para notificar.")
            return "No se encontraron técnicos activos."

    except Ticket.DoesNotExist:
        print(f"CELERY: Error - No se encontró el ticket con ID {ticket_id}.")
        return "Ticket no encontrado."

# ==============================================================================
# Tarea de Procesamiento de Documentos (sin cambios)
# ==============================================================================

@shared_task
def process_document_task(document_id):
    """
    Tarea de Celery (versión inteligente). Extrae subtema y tags para CADA chunk
    de manera automática, analizando su contenido específico.
    """
    print(f"CELERY: Iniciando procesamiento inteligente para el Documento #{document_id}")
    doc = None
    try:
        doc = KnowledgeDocument.objects.get(id=document_id)
        doc.estado_procesamiento = KnowledgeDocument.Status.PROCESSING
        doc.save()

        file_path = os.path.join(settings.MEDIA_ROOT, doc.archivo.name)
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)
        
        print(f"CELERY: Analizando {len(chunks)} fragmentos para extraer metadatos dinámicamente...")
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=gemini_api_key, model_kwargs={"response_mime_type": "application/json"})
        
        enriched_chunks = []
        all_tags = set()
        all_subtopics = set()

        for i, chunk in enumerate(chunks):
            # --- ANÁLISIS AUTOMÁTICO POR CHUNK ---
            analysis_prompt = (
                f"Analiza el siguiente fragmento de texto de un documento cuyo tema principal es '{doc.tema}'.\n"
                "1. **subtema:** Genera un título o encabezado muy conciso que describa este fragmento específico (ej: 'Acceso con Contraseña', 'Configuración de VPN', 'Instalación de Impresora').\n"
                "2. **tags:** Extrae una lista de 2 a 4 palabras clave o entidades relevantes del fragmento (ej: ['login', 'password', 'acceso']).\n\n"
                "**IMPORTANTE:** Tu respuesta debe ser únicamente un objeto JSON con las claves 'subtema' y 'tags'.\n\n"
                f"Fragmento de Texto:\n---\n{chunk.page_content}\n---\n\nJSON:"
            )
            
            response = llm.invoke(analysis_prompt)
            result = json.loads(response.content)
            
            subtema = result.get('subtema', 'General')
            tags = result.get('tags', [])
            
            # Añadimos los metadatos completos al chunk
            chunk.metadata['document_id'] = str(doc.id)
            chunk.metadata['document_name'] = doc.nombre
            chunk.metadata['document_type'] = doc.tipo_documento
            chunk.metadata['tema'] = doc.tema # El tema general del documento
            chunk.metadata['subtema'] = subtema # El subtema específico de ESTE chunk
            chunk.metadata['tags'] = ", ".join(tags) # Guardamos los tags como un string
            chunk.metadata['source'] = doc.archivo.name
            chunk.metadata['page'] = chunk.metadata.get('page', 0) + 1
            enriched_chunks.append(chunk)

            # Guardamos los tags y subtemas para el registro principal del documento (como un resumen)
            all_tags.update(tags)
            all_subtopics.add(subtema)
            
            print(f"-> Chunk {i+1}/{len(chunks)} analizado. Subtema: '{subtema}'")

        # Actualizamos el documento principal con un resumen de todos los tags y subtemas encontrados
        doc.subtema = ", ".join(sorted(list(all_subtopics)))
        doc.tags = ", ".join(sorted(list(all_tags)))
        doc.save()

        if enriched_chunks:
            print(f"CELERY: Ejemplo de metadatos del primer chunk: {enriched_chunks[0].metadata}")
        
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=gemini_api_key)
        persist_directory = os.path.join(settings.BASE_DIR, 'chroma_db')
        
        Chroma.from_documents(documents=enriched_chunks, embedding=embeddings, persist_directory=persist_directory)
        
        print(f"CELERY: Embeddings creados y guardados en ChromaDB para el Documento #{doc.id}")

        doc.estado_procesamiento = KnowledgeDocument.Status.COMPLETED
        doc.ultimo_error = None
        doc.save()

        return f"Documento {document_id} procesado exitosamente."

    except Exception as e:
        print(f"CELERY: ERROR al procesar el Documento #{document_id}: {e}")
        if 'doc' in locals():
            doc.estado_procesamiento = KnowledgeDocument.Status.FAILED
            doc.ultimo_error = str(e)
            doc.save()
        raise e
