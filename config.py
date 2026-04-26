import os
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────────────────────────
# API ANAHTARLARI
# ───────────────────────────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ───────────────────────────────────────────
# BOT AYARLARI
# ───────────────────────────────────────────

BOT_ADI = "Sınav Asistanı"
UCRETSIZ_HAK = 7          # Yeni kullanıcıya verilen ücretsiz hak
GUNLUK_LIMIT = 70         # Abonelere günlük mesaj limiti
ABONELIK_STARS = 80        # 1 aylık
ABONELIK_3AY_STARS = 250   # 3 aylık

# Telegram Stars — 1 Star ≈ 0.013$ civarı
# 70 TL ≈ 2.2$ → yaklaşık 170 Stars
ABONELIK_STARS = 80

# ───────────────────────────────────────────
# KONTROL
# ───────────────────────────────────────────

if __name__ == "__main__":
    print("🔧 Config Kontrolü:")
    print(f"  TELEGRAM_TOKEN   : {'✅ var' if TELEGRAM_TOKEN else '❌ eksik'}")
    print(f"  ANTHROPIC_API_KEY: {'✅ var' if ANTHROPIC_API_KEY else '❌ eksik'}")
    print(f"  Abonelik fiyatı  : {ABONELIK_3AY_STARS} TL / {ABONELIK_STARS} Stars")
    print(f"  Günlük limit     : {GUNLUK_LIMIT} mesaj")
    print(f"  Ücretsiz hak     : {UCRETSIZ_HAK} mesaj")