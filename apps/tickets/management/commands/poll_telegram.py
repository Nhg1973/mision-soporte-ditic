import os
import asyncio
import telegram
import re
from django.core.management.base import BaseCommand
from telegram_bot.handlers import handle_message
from apps.tickets.models import OutgoingTelegramMessage, TechnicianProfile
from asgiref.sync import sync_to_async
from telegram_bot.sender import send_telegram_message_sync
from apps.ai_core.technician_actions import add_technician_reply



@sync_to_async
def process_technician_reply(update):
    """
    Procesa un mensaje para ver si es una respuesta de un técnico con un comando.
    VERSIÓN CON LOGS DE DEPURACIÓN.
    """
    message = update.message
    print("\n--- DEPURANDO RESPUESTA DE TÉCNICO ---")

    # 1. Verificar si es una respuesta
    if not message.reply_to_message:
        print("-> FALLÓ: El mensaje no es una respuesta a otro mensaje.")
        return False
    print("-> OK: El mensaje es una respuesta.")

    # 2. Verificar si el autor es un técnico
    technician_chat_id = str(message.from_user.id)
    print(f"-> ID de Chat del remitente: {technician_chat_id}")
    try:
        technician_profile = TechnicianProfile.objects.get(telegram_chat_id=technician_chat_id)
        print(f"-> OK: El remitente es el técnico registrado: {technician_profile.user.username}")
    except TechnicianProfile.DoesNotExist:
        print(f"-> FALLÓ: El ID de chat {technician_chat_id} no corresponde a ningún técnico en la base de datos.")
        return False

    # 3. Extraer el Ticket ID del mensaje original
    original_message_text = message.reply_to_message.text
    print(f"-> Texto del mensaje original: '{original_message_text}'")
    # LÍNEA CORREGIDA
    ticket_id_match = re.search(r"Ticket ID:\s*(\d+)", original_message_text)
    
    if not ticket_id_match:
        print("-> FALLÓ: No se pudo encontrar el patrón 'Ticket ID: `(número)`' en el mensaje original.")
        return False
    
    ticket_id = int(ticket_id_match.group(1))
    print(f"-> OK: Ticket ID extraído: {ticket_id}")

    # 4. Parsear el comando
    technician_text = message.text
    print(f"-> Texto del técnico: '{technician_text}'")
    if technician_text.startswith('/resolver '):
        print("-> OK: El comando '/resolver' fue encontrado.")
        resolution_message = technician_text.replace('/resolver ', '', 1).strip()
        
        if not resolution_message:
            print("-> FALLÓ: El comando '/resolver' está vacío.")
            return False

        print(f"-> ÉXITO: Procesando la resolución para el ticket #{ticket_id}.")
        add_technician_reply(ticket_id, resolution_message, technician_profile.user)
        return True
        
    print("-> FALLÓ: El mensaje no comienza con '/resolver '.")
    return False

async def process_outgoing_messages():
    """
    Revisa la bandeja de salida y envía los mensajes pendientes.
    """
    get_messages = sync_to_async(list)(OutgoingTelegramMessage.objects.all())
    outgoing_messages = await get_messages
    
    if outgoing_messages:
        print(f"POLLER: Se encontraron {len(outgoing_messages)} mensajes salientes para enviar.")
    
    for msg in outgoing_messages:
        try:
            success = await sync_to_async(send_telegram_message_sync)(
                chat_id=msg.telegram_chat_id, # <-- Ahora lee directamente el chat_id
                message=msg.message_text
            )
            if success:
                print(f"POLLER: Mensaje para ticket #{msg.ticket.id} enviado. Eliminando de la cola.")
                await sync_to_async(msg.delete)()
        except Exception as e:
            print(f"POLLER: Error al procesar mensaje saliente para ticket #{msg.ticket.id}: {e}")

class Command(BaseCommand):
    help = 'Inicia el bot de Telegram en modo polling y procesa la bandeja de salida.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando bot de Telegram...'))
        asyncio.run(self.main_loop())

    async def main_loop(self):
        TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        update_id = 0

        while True:
            try:
                updates = await bot.get_updates(offset=update_id, timeout=1)
                for update in updates:
                    update_id = update.update_id + 1
                    
                    # --- LÓGICA DE ENRUTAMIENTO ---
                    # Primero, vemos si es una respuesta de un técnico
                    is_technician_reply = await process_technician_reply(update)
                    
                    # Si no fue una respuesta de técnico, lo procesamos como un mensaje de usuario normal
                    if not is_technician_reply:
                        await handle_message(update)

                # Buscamos y enviamos mensajes salientes
                await process_outgoing_messages()
                await asyncio.sleep(3)

            except telegram.error.NetworkError:
                self.stdout.write(self.style.ERROR('Error de red. Reintentando...'))
                await asyncio.sleep(5)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error inesperado en el bucle principal: {e}'))
                await asyncio.sleep(10)
