from django import forms
from apps.tickets.models import KnowledgeDocument

class DocumentUploadForm(forms.ModelForm):
    """
    Formulario para subir nuevos documentos a la base de conocimiento.
    Usamos un ModelForm para que se construya automáticamente a partir de nuestro modelo.
    """
    class Meta:
        model = KnowledgeDocument
        # Especificamos los campos que queremos mostrar en el formulario.
        fields = ['nombre', 'archivo', 'categoria']
        # Añadimos clases de Bootstrap a los campos para que se vean bien.
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'categoria': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nombre': 'Nombre del Documento',
            'archivo': 'Seleccionar Archivo (.txt, .pdf)',
            'categoria': 'Categoría (ej. Hardware, Software, VPN)',
        }
