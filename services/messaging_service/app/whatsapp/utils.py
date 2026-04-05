import requests
import whatsapp as wa
from common_logging import setup_logging
logger = setup_logging("messaging-service", tag="MESSAGING", color="magenta")

def replace_start(s):
    if s.startswith("521"):
        return "52" + s[3:]
    else:
        return s

def get_message_body(message):
    if 'type' not in message:
        text = 'mensaje no reconocido'
        return text

    typeMessage = message['type']
    if typeMessage == 'text':
        text = message['text']['body']
    elif typeMessage == 'button':
        text = message['button']['text']
    elif typeMessage == 'interactive' and message['interactive']['type'] == 'list_reply':
        text = message['interactive']['list_reply']['title']
    elif typeMessage == 'interactive' and message['interactive']['type'] == 'button_reply':
        text = message['interactive']['button_reply']['title']
    else:
        text = 'mensaje no procesado'
    return text

def send_message(data):
    try:
        whatsapp_token = wa.api_token
        whatsapp_url = wa.url
        
        if not whatsapp_token:
            logger.error("WHATSAPP_API_TOKEN is not set!")
            return "Token missing", 401
            
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + whatsapp_token
        }
        
        logger.debug(f"Sending message to {whatsapp_url}")
        response = requests.post(whatsapp_url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.debug("Message sent successfully (200 OK).")
            return 'Mensaje enviado', 200
        else:
            logger.error(f"Failed to send message. Status: {response.status_code}, Response: {response.text}")
            return 'Error al enviar mensaje', response.status_code
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while sending message to {whatsapp_url}")
        return "Timeout error", 504
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error while sending message to {whatsapp_url}: {e}")
        return "Connection error", 503
    except Exception as e:
        logger.exception("Unexpected exception in send_message")
        return str(e), 500