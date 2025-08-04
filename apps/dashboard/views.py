from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg
from apps.tickets.models import Ticket

@staff_member_required
def dashboard_view(request):
    """
    Calcula las métricas clave y las muestra en el dashboard.
    """
    # --- Cálculo de Métricas (sin cambios) ---
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

    # --- ¡CAMBIO CLAVE AQUÍ! ---
    # Preparamos los datos para el gráfico de una forma más estructurada.
    
    # 1. Obtenemos los conteos de la base de datos como antes.
    tickets_by_status_raw = (
        Ticket.objects
        .values('estado')
        .annotate(count=Count('id'))
    )
    status_counts = {item['estado']: item['count'] for item in tickets_by_status_raw}

    # 2. Creamos una lista de diccionarios que la plantilla pueda entender fácilmente.
    status_data = []
    for key, display_name in Ticket.Estado.choices:
        count = status_counts.get(key, 0)
        percentage = (count / total_tickets * 100) if total_tickets > 0 else 0
        status_data.append({
            'display_name': display_name,
            'count': count,
            'percentage': percentage,
        })

    # Preparamos el contexto para pasarlo a la plantilla HTML.
    context = {
        'total_tickets': total_tickets,
        'open_tickets_count': open_tickets_count,
        'resolved_tickets_count': resolved_tickets_count,
        'average_rating': average_rating,
        # Pasamos nuestra nueva lista de datos estructurados.
        'status_data': status_data,
    }
    
    return render(request, 'dashboard/main.html', context)
