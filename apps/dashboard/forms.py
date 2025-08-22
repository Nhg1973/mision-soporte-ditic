# apps/dashboard/forms.py

from django import forms
from django.core.exceptions import ValidationError
from apps.tickets.models import KnowledgeDocument

class DocumentUploadForm(forms.ModelForm):
    """
    Formulario para subir nuevos documentos (versión simplificada).
    El administrador solo necesita clasificar el documento en su nivel más alto.
    El subtema y los tags se generarán automáticamente.
    """
    class Meta:
        model = KnowledgeDocument
        # Mostramos solo los campos que el administrador debe rellenar manualmente
        fields = ['nombre', 'archivo', 'tipo_documento', 'tema']
        
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'tema': forms.Select(attrs={'class': 'form-select'}),
        }
        
        labels = {
            'nombre': 'Nombre Descriptivo del Documento',
            'archivo': 'Seleccionar Archivo (.pdf)',
            'tipo_documento': 'Tipo de Documento',
            'tema': 'Tema Principal (Categoría General)',
        }

    def clean_archivo(self, *args, **kwargs):
        """
        Valida que el archivo subido sea realmente un PDF.
        """
        archivo = self.cleaned_data.get('archivo', False)
        if archivo:
            archivo.seek(0)
            magic_number = archivo.read(5)
            archivo.seek(0)
            if magic_number != b'%PDF-':
                raise ValidationError("El archivo subido no parece ser un PDF válido.")
        return super().clean(*args, **kwargs).get('archivo')


