from django.urls import path
from . import views

# Este nombre nos ayuda a referenciar estas URLs de forma más sencilla.
app_name = 'dashboard'

urlpatterns = [
    # La ruta vacía ('') dentro de esta app corresponderá a /dashboard/
    # La asociamos a la vista 'dashboard_view' que crearemos a continuación.
    path('', views.dashboard_view, name='main'),
]
