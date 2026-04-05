import os

api_token = os.getenv("WHATSAPP_API_TOKEN")
auth_token = os.getenv("WHATSAPP_AUTH_TOKEN")
url = os.getenv("WHATSAPP_URL", "https://graph.facebook.com/v17.0/142601282278212/messages")