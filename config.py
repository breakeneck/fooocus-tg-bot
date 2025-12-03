import os
from dotenv import load_dotenv

load_dotenv()

FOOOCUS_BOT_TOKEN = os.getenv("FOOOCUS_BOT_TOKEN")
FOOOCUS_IP = os.getenv("FOOOCUS_IP", "127.0.0.1")
FOOOCUS_PORT = os.getenv("FOOOCUS_PORT", "8888")

BASE_URL = f"http://{FOOOCUS_IP}:{FOOOCUS_PORT}"

# Safety prompts for content filtering
SAFETY_POSITIVE_PROMPT = "safe, wholesome, family friendly, SFW only, strictly no nudity, no nsfw, no erotic content, no sensuality, no sexual themes, fully covered body, modest attire, non-revealing clothing, non-suggestive poses, avoid cleavage, avoid exposed skin"

SAFETY_NEGATIVE_PROMPT = "nsfw, nudity, naked, erotic, sexual, pornographic, suggestive, revealing clothes, lingerie, swimwear, cleavage, exposed breasts, exposed body, sexual pose, vulgar, explicit content, adult content"
