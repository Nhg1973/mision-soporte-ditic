import os
import requests
from django.conf import settings

def send_telegram_message_sync(chat_id: str, message: str) -> bool:
    """
    Función SÍNCRONA y robusta para enviar mensajes a Telegram usando peticiones HTTP directas.
    
    Args:
        chat_id: El ID del chat de Telegram al que se enviará el mensaje.
        message: El texto del mensaje a enviar.
        
    Returns:
        True si el mensaje se envió con éxito, False en caso contrario.
    """
    # Obtenemos el token del bot desde las variables de entorno.
    # Es una buena práctica leerlo desde settings.py para centralizar la configuración.
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        print("ERROR CRÍTICO: La variable de entorno TELEGRAM_BOT_TOKEN no fue encontrada.")
        return False

    # Construimos la URL de la API de Telegram para el método sendMessage
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Preparamos los datos que vamos a enviar en la petición POST
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown' # Permite usar formato como *negrita* o _cursiva_
    }

    print(f"SENDER: Intentando enviar mensaje a chat_id {chat_id}...")

    try:
        # Hacemos la petición POST. El timeout es importante para no quedarnos colgados.
        response = requests.post(url, data=payload, timeout=10)
        
        # Verificamos si la API de Telegram nos dio una respuesta exitosa (código 200).
        if response.status_code == 200:
            print("SENDER: Mensaje enviado a Telegram exitosamente.")
            return True
        else:
            # Si hay un error, lo mostramos en los logs para poder depurarlo.
            print(f"SENDER: Error al enviar mensaje a Telegram: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"SENDER: Excepción al intentar conectar con la API de Telegram: {e}")
        return False
