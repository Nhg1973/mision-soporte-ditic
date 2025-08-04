from django.contrib import admin
from django.urls import path, include # Asegúrate de que 'include' esté importado

urlpatterns = [
    path('admin/', admin.site.urls),
    # Añade esta línea para que la URL principal del sitio
    # sea manejada por nuestra app de tickets.
    path('', include('apps.tickets.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
]
