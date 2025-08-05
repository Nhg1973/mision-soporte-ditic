from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg
from django.contrib import messages
from apps.tickets.models import Ticket, KnowledgeDocument
from .forms import DocumentUploadForm
# --- ¡NUEVA IMPORTACIÓN! ---
# Importamos nuestra nueva tarea de Celery para procesar documentos.
from apps.tasks.tasks import process_document_task

@staff_member_required
def dashboard_view(request):
    """
    Calcula métricas, muestra la lista de documentos y maneja la subida de nuevos archivos,
    disparando la tarea de procesamiento en segundo plano.
    """
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.cargado_por = request.user
            document.save()
            
            # --- ¡CONEXIÓN CON CELERY! ---
            # Después de guardar el documento, disparamos la tarea asíncrona,
            # pasándole el ID del nuevo documento.
            process_document_task.delay(document.id)
            
            messages.success(request, f"Documento '{document.nombre}' subido. El procesamiento ha comenzado en segundo plano.")
            return redirect('dashboard:main')
        else:
            messages.error(request, "Hubo un error al subir el documento. Por favor, revisa los campos.")
    else:
        form = DocumentUploadForm()

    # --- El resto del código no cambia ---
    total_tickets = Ticket.objects.count()
    open_tickets_count = Ticket.objects.filter(
        estado__in=[Ticket.Estado.NUEVO, Ticket.Estado.EN_PROCESO, Ticket.Estado.ESCALADO]
    ).count()
    resolved_tickets_count = Ticket.objects.filter(
        estado__in=[Ticket.Estado.RESUELTO_BOT, Ticket.Estado.RESUELTO_TECNICO]
    ).count()
    average_rating_result = Ticket.objects.filter(calificacion__isnull=False).aggregate(
        avg_rating=Avg('calificacion')
    )
    average_rating = average_rating_result['avg_rating'] or 0
    
    tickets_by_status_raw = (
        Ticket.objects
        .values('estado')
        .annotate(count=Count('id'))
    )
    status_counts = {item['estado']: item['count'] for item in tickets_by_status_raw}

    status_data = []
    for key, display_name in Ticket.Estado.choices:
        count = status_counts.get(key, 0)
        percentage = (count / total_tickets * 100) if total_tickets > 0 else 0
        status_data.append({
            'display_name': display_name,
            'count': count,
            'percentage': percentage,
        })

    knowledge_documents = KnowledgeDocument.objects.all()

    context = {
        'total_tickets': total_tickets,
        'open_tickets_count': open_tickets_count,
        'resolved_tickets_count': resolved_tickets_count,
        'average_rating': average_rating,
        'status_data': status_data,
        'upload_form': form,
        'knowledge_documents': knowledge_documents,
    }
    
    return render(request, 'dashboard/main.html', context)

