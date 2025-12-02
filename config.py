import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FOOOCUS_IP = os.getenv("FOOOCUS_IP", "127.0.0.1")
FOOOCUS_PORT = os.getenv("FOOOCUS_PORT", "8888")

BASE_URL = f"http://{FOOOCUS_IP}:{FOOOCUS_PORT}"
