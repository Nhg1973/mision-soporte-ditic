# apps/dashboard/forms.py

from django import forms
from apps.tickets.models import KnowledgeDocument
# ¡Importamos nuestra jerarquía de temas!
from apps.ai_core.topics import TOPIC_HIERARCHY

def get_topic_choices():
    """
    Genera una lista de tuplas con formato para el ChoiceField de Django,
    agrupando los subtemas bajo su tema principal.
    """
    choices = [('', '---------')]  # Opción vacía
    for main_topic, sub_topics in TOPIC_HIERARCHY.items():
        # Formato para sub-opciones agrupadas: (NombreGrupo, [(valor, etiqueta), ...])
        formatted_sub_topics = [(f"{main_topic}/{sub_topic}", sub_topic) for sub_topic in sub_topics]
        choices.append((main_topic, formatted_sub_topics))
    return choices

class DocumentUploadForm(forms.ModelForm):
    """
    Formulario para subir nuevos documentos a la base de conocimiento.
    El campo 'categoría' ahora es un menú desplegable basado en nuestra jerarquía de temas.
    """
    # ¡CAMBIO CLAVE! Sobrescribimos el campo 'categoria'
    categoria = forms.ChoiceField(
        choices=get_topic_choices, 
        required=True,
        label="Tema del Documento",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = KnowledgeDocument
        fields = ['nombre', 'archivo', 'categoria']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nombre': 'Nombre del Documento',
            'archivo': 'Seleccionar Archivo (.pdf)',
        }