# apps/tickets/management/commands/update_topics.py

import os
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.tickets.models import KnowledgeDocument

class Command(BaseCommand):
    help = 'Genera el archivo topics.py dinámicamente desde los documentos en la base de datos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando la generación del archivo de temas...'))

        # Usamos defaultdict para agrupar subtemas bajo su tema principal fácilmente.
        topic_hierarchy = defaultdict(list)

        # 1. Obtenemos todos los documentos que han sido procesados exitosamente.
        processed_docs = KnowledgeDocument.objects.filter(
            estado_procesamiento=KnowledgeDocument.Status.COMPLETED
        ).exclude(categoria__isnull=True).exclude(categoria__exact='')

        if not processed_docs.exists():
            self.stdout.write(self.style.WARNING('No se encontraron documentos procesados con categorías para generar la lista de temas.'))
            return

        # 2. Iteramos sobre los documentos y extraemos los temas y subtemas.
        for doc in processed_docs:
            categoria = doc.categoria
            parts = [part.strip() for part in categoria.split('/')]
            
            if len(parts) >= 1:
                main_topic = parts[0]
                sub_topic = parts[1] if len(parts) > 1 else 'General'
                
                # Añadimos el subtema a la lista del tema principal, evitando duplicados.
                if sub_topic not in topic_hierarchy[main_topic]:
                    topic_hierarchy[main_topic].append(sub_topic)
        
        # 3. Definimos la ruta del archivo que vamos a escribir.
        topics_file_path = os.path.join(settings.BASE_DIR, 'apps', 'ai_core', 'topics.py')

        # 4. Escribimos el contenido en el archivo topics.py.
        try:
            with open(topics_file_path, 'w', encoding='utf-8') as f:
                f.write("# Este archivo es generado automáticamente por el comando 'update_topics'.\n")
                f.write("# No lo edites manualmente.\n\n")
                f.write("TOPIC_HIERARCHY = {\n")
                for topic, subtopics in sorted(topic_hierarchy.items()):
                    f.write(f'    "{topic}": [\n')
                    for subtopic in sorted(subtopics):
                        f.write(f'        "{subtopic}",\n')
                    f.write('    ],\n')
                f.write("}\n\n")

                f.write("def get_master_topic_list():\n")
                f.write("    \"\"\"\n")
                f.write("    Genera una lista plana de todos los temas y subtemas para el clasificador.\n")
                f.write("    \"\"\"\n")
                f.write("    master_list = []\n")
                f.write("    for main_topic, sub_topics in TOPIC_HIERARCHY.items():\n")
                f.write("        master_list.append(main_topic)\n")
                f.write("        master_list.extend(sub_topics)\n")
                f.write("    return master_list\n")
            
            self.stdout.write(self.style.SUCCESS(f'¡Éxito! El archivo "{topics_file_path}" ha sido actualizado con {len(topic_hierarchy)} temas.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error al escribir el archivo de temas: {e}'))