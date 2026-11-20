"""
DisMaker - Yapılandırma ve Çevre Değişkenleri Yönetimi
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Proje dizin kökü ve .env yükleme
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Token ve Anahtarlar
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Gemini Model Öncelik Sıralaması
# Google API üzerinde doğrulanmış en hızlı ve aktif modeller
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-flash-lite-latest").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()

# Dinamik model fallback zinciri (Free tier ile tam uyumlu, test edilmiş modeller)
GEMINI_MODEL_CASCADE = [
    GEMINI_PRIMARY_MODEL,
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    GEMINI_FALLBACK_MODEL
]

# Yinelenenleri temizle ama sırayı koru
_seen = set()
GEMINI_MODELS = []
for m in GEMINI_MODEL_CASCADE:
    if m and m not in _seen:
        _seen.add(m)
        GEMINI_MODELS.append(m)

# Bot Ayarları
BOT_PREFIX = os.getenv("BOT_PREFIX", "!").strip()
DB_PATH = BASE_DIR / "dismaker.db"

# Tasarım & Renk Sabitleri (Swiss / Minimalist Standart)
COLOR_SUCCESS = 0x10B981  # Zümrüt Yeşili
COLOR_INFO = 0x3B82F6     # Saf Mavi
COLOR_WARNING = 0xF59E0B  # Mat Kehribar
COLOR_DANGER = 0xEF4444   # Saf Kırmızı
COLOR_NEUTRAL = 0x18181B  # Derin Karbon (#18181b)
COLOR_EMBED_DEFAULT = 0x27272A # Mat Grafit

def is_configured() -> tuple[bool, list[str]]:
    """
    Gerekli anahtarların geçerli şekilde girilip girilmediğini denetler.
    """
    missing = []
    placeholders = [
        "BURAYA_DISCORD_BOT_TOKENINIZI_GIRIN",
        "your_discord_bot_token_here",
        "",
    ]
    gemini_placeholders = [
        "BURAYA_GEMINI_API_KEYINIZI_GIRIN",
        "your_gemini_api_key_here",
        "",
    ]

    if DISCORD_BOT_TOKEN in placeholders:
        missing.append("DISCORD_BOT_TOKEN")
    if GEMINI_API_KEY in gemini_placeholders:
        missing.append("GEMINI_API_KEY")

    return (len(missing) == 0, missing)
