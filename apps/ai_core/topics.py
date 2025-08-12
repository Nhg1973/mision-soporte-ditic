TOPIC_HIERARCHY = {
    "Identidad Visual Web": [
        "[cite_start]Diseño General y Estructura",       
        "[cite_start]Página de Inicio",                   
        "[cite_start]Contenidos Más Consultados",         
        "[cite_start]Panel de Noticias",                  
        "[cite_start]Panel de Iniciativas",               
        "[cite_start]Bloque de Contacto y Mapa",          
    ],
    "Secciones de Contenido": [
        "[cite_start]Sección Asistencia Consular",        
        "[cite_start]Sección Noticias",                   
        "[cite_start]Sección Contacto",                   
    ],
    "Trámites y Documentación": [
        "[cite_start]Apostilla de la Haya",               
        "[cite_start]DNI para Residentes",                
        "[cite_start]Pasaporte de Emergencia",            
        "[cite_start]Certificado de Antecedentes Penales",
        "[cite_start]Opción de Nacionalidad Argentina",   
    ],
    "Información General": [
        "[cite_start]Datos de Representaciones",          
        "[cite_start]Contacto y Redes Sociales",              ]
}

def get_master_topic_list():
    """
    Genera una lista plana de todos los temas y subtemas para el clasificador.
    """
    master_list = []
    for main_topic, sub_topics in TOPIC_HIERARCHY.items():
        master_list.append(main_topic)
        master_list.extend(sub_topics)
    return master_list