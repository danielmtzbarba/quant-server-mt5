from . import utils
from common_logging import setup_logging
logger = setup_logging("messaging-service", tag="MESSAGING", color="blue")

class Message(object):
    def __init__(self, request) -> None:
        self._request = request
        self._msg_data = None
        self._is_valid_message = False
        self._status = None
        self._extract_msg_data()
    
    def _extract_msg_data(self):
        try:
            # Navigate the payload
            entry = self._request.get('entry', [{}])[0]
            change = entry.get('changes', [{}])[0]
            value = change.get('value', {})
            
            # Check for messages
            messages = value.get('messages')
            if messages and len(messages) > 0:
                self._msg_data = messages[0]
                self._contacts = value.get('contacts', [{}])[0]
                self._is_valid_message = True
            else:
                # Could be a status update (sent, delivered, read)
                statuses = value.get('statuses')
                if statuses:
                    self._status = statuses[0].get('status')
                    logger.debug(f"Received status update: {self._status}")
                else:
                    logger.debug(f"Received non-message payload: {value}")
                self._is_valid_message = False
                
        except Exception as e:
            logger.error(f"Error parsing WhatsApp payload: {e}")
            self._is_valid_message = False
    
    @property
    def is_message(self):
        return self._is_valid_message

    @property
    def number(self):
        if not self._msg_data:
            return None
        return utils.replace_start(self._msg_data['from'])
    
    @property
    def id(self):
        if not self._msg_data:
            return None
        return self._msg_data['id']
    
    @property
    def name(self):
        if not self._is_valid_message:
            return "Unknown"
        return self._contacts.get('profile', {}).get('name', 'User')

    @property
    def text(self):
        if not self._msg_data:
            return ""
        return utils.get_message_body(self._msg_data)

    @property
    def is_read(self):
        return self._status == "read"

    @property
    def status(self):
        return self._status
