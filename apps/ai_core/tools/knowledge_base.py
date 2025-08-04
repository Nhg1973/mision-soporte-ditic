# --- Base de Conocimiento Simulada ---
# En un sistema real, esto sería una base de datos vectorial (FAISS, ChromaDB).
# Para nuestro prototipo, un diccionario es rápido y efectivo.
# La clave es una tupla de palabras clave, y el valor es la solución.

KNOWLEDGE_BASE = {
    ('clave', 'contraseña', 'olvidé', 'perdí', 'acceso'): {
        'solucion': (
            "¡Entendido! Parece que tienes un problema con tu contraseña. "
            "Puedes restablecerla tú mismo siguiendo estos pasos:\n"
            "1. Ve a la página de intranet.\n"
            "2. Haz clic en '¿Olvidaste tu contraseña?'.\n"
            "3. Sigue las instrucciones que recibirás en tu correo.\n\n"
            "Si eso no funciona, avísame y crearé un ticket para que un técnico te ayude."
        )
    },
    ('impresora', 'imprimir', 'no funciona', 'papel', 'tóner'): {
        'solucion': (
            "Ok, un problema con la impresora. Antes de escalar esto, probemos lo básico:\n"
            "1. Asegúrate de que la impresora esté encendida y conectada a la red.\n"
            "2. Verifica que tenga papel y tóner.\n"
            "3. Intenta apagarla y volver a encenderla después de 30 segundos.\n\n"
            "Si después de estos pasos sigues sin poder imprimir, dímelo y un técnico se pondrá en contacto."
        )
    },
    ('vpn', 'conectar', 'remoto', 'desde casa'): {
        'solucion': (
            "Para problemas de conexión a la VPN, la solución más común es reinstalar el perfil de conexión.\n"
            "Puedes encontrar la guía paso a paso en este enlace: https://www.reddit.com/r/fortinet/comments/13iw66q/internal_vpn/\n\n"
            "¡Normalmente eso soluciona el 90% de los casos!"
        )
    },
}

def search_knowledge_base(user_query: str) -> str | None:
    """
    Busca en la base de conocimiento si alguna palabra clave coincide con la consulta del usuario.

    Args:
        user_query: El texto enviado por el usuario (en minúsculas).

    Returns:
        La solución en formato de texto si se encuentra una coincidencia, o None si no se encuentra.
    """
    query_words = set(user_query.lower().split())
    
    for keywords, data in KNOWLEDGE_BASE.items():
        # Verificamos si alguna de las palabras clave está en la consulta del usuario
        if any(keyword in query_words for keyword in keywords):
            print(f"ORQUESTADOR: Coincidencia encontrada en la base de conocimiento con las palabras clave: {keywords}")
            return data['solucion']
            
    # Si el bucle termina sin encontrar coincidencias
    print("ORQUESTADOR: No se encontraron soluciones en la base de conocimiento.")
    return None
