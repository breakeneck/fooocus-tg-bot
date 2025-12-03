import os
from dotenv import load_dotenv

load_dotenv()

FOOOCUS_BOT_TOKEN = os.getenv("FOOOCUS_BOT_TOKEN")
FOOOCUS_IP = os.getenv("FOOOCUS_IP", "127.0.0.1")
FOOOCUS_PORT = os.getenv("FOOOCUS_PORT", "8888")

BASE_URL = f"http://{FOOOCUS_IP}:{FOOOCUS_PORT}"

# Safety prompts for content filtering
SAFETY_POSITIVE_PROMPT = "underage is forbidden, adult only, fully clothed adult woman, strictly no nudity, strictly no exposed skin, no cleavage, no lingerie, no underwear, no erotic expression, no sensuality, no sexual themes, no sexual gestures, professional portrait style, modest outfit, conservative clothing, safe for work, family-safe realistic photography"

SAFETY_NEGATIVE_PROMPT = "nsfw, nude, naked, topless, bottomless, nipples, breasts, exposed skin, erotic, sensual, seductive, sexual position, sexual act, porn, pornographic, hentai, explicit content, genitalia, vagina, penis, oral, intercourse, sex, sexual organ, fetish, bdsm, lingerie, swimsuit, bikini, cleavage, revealing clothes, suggestive pose"
