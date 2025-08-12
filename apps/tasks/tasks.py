import os
from celery import shared_task
from django.conf import settings

from apps.tickets.models import Ticket, TechnicianProfile, KnowledgeDocument
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
    Tarea de Celery para procesar un documento subido.
    """
    # ... (código existente sin cambios)
    print(f"CELERY: Iniciando procesamiento para el Documento #{document_id}")
    try:
        doc = KnowledgeDocument.objects.get(id=document_id)
        doc.estado_procesamiento = KnowledgeDocument.Status.PROCESSING
        doc.save()

        file_path = os.path.join(settings.MEDIA_ROOT, doc.archivo.name)
        
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        from langchain.text_splitter import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)
        
        print(f"CELERY: Enriqueciendo {len(chunks)} fragmentos con metadatos de tema...")
        for i, chunk in enumerate(chunks):
            # Metadatos existentes
            chunk.metadata['document_id'] = str(doc.id)
            chunk.metadata['document_name'] = doc.nombre
            chunk.metadata['chunk_index'] = i
            
            # ¡NUEVOS METADATOS DE TEMA!
            # Usamos la categoría guardada desde el formulario.
            if doc.categoria:
                # Si la categoría es "TemaPrincipal/SubTema", los separamos.
                parts = doc.categoria.split('/')
                chunk.metadata['tema'] = parts[0]
                if len(parts) > 1:
                    chunk.metadata['subtema'] = parts[1]
                else:
                    chunk.metadata['subtema'] = 'General' # Un subtema por defecto

        # Imprimimos un ejemplo para verificar
        if chunks:
          print(f"CELERY: Ejemplo de metadatos del primer chunk: {chunks[0].metadata}")
      

        print(f"CELERY: Documento #{doc.id} dividido en {len(chunks)} fragmentos.")

        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("La clave de API de Gemini no está configurada en el archivo .env")

        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=gemini_api_key)
        
        from langchain_community.vectorstores import Chroma
        persist_directory = os.path.join(settings.BASE_DIR, 'chroma_db')
        
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=persist_directory
        )
        
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
