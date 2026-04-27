import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# API Key kontrolü (Eğer boşsa terminalde bağırır)
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("🚨 HATA: ANTHROPIC_API_KEY bulunamadı! .env dosyanı kontrol et.")

client = Anthropic(api_key=api_key)

# ───────────────────────────────────────────
# MODELLER (Senin attığın dökümana göre güncel)
# ───────────────────────────────────────────
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-5-20250929"  # Dökümandaki en güncel Sonnet 4.5


# ───────────────────────────────────────────
# INTENT FILTER
# ───────────────────────────────────────────

def intent_kontrol(mesaj: str) -> bool:
    try:
        response = client.messages.create(
            model=MODEL_HAIKU,
            max_tokens=10,
            messages=[{"role": "user", "content": f"Sınavla ilgili mi? Sadece EVET/HAYIR: {mesaj}"}]
        )
        return "EVET" in response.content[0].text.upper()
    except Exception as e:
        print(f"Intent Hatası: {e}")
        return True


# ───────────────────────────────────────────
# ANA AI FONKSİYONU (Sohbet İçin)
# ───────────────────────────────────────────

def ai_cevap_al(mesaj: str, sinav_turu: str, sohbet_gecmisi: list, abone_mi: bool = False) -> str:
    try:
        model_adi = MODEL_SONNET if abone_mi else MODEL_HAIKU

        # Sistem promptu
        sistem = f"Sen bir {sinav_turu} uzmanısın. Kısa ve net cevaplar ver."

        # Mesajları hazırla
        mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]

        response = client.messages.create(
            model=model_adi,
            max_tokens=1000,
            system=sistem,
            messages=mesajlar
        )
        return response.content[0].text
    except Exception as e:
        print(f"AI Cevap Hatası: {e}")
        return "⚠️ Mesajını şu an cevaplayamıyorum kanka, API bağlantısında bir sorun var."


# ───────────────────────────────────────────
# SORU HAZIRLA (Hatanın Kaynağı Burasıydı!)
# ───────────────────────────────────────────

def soru_hazirla(sinav_turu: str, ders: str, konu: str, adet: int, abone_mi: bool = False) -> str:
    try:
        # 🚨 Dökümandaki tam model isimlerini kullanıyoruz
        model_adi = MODEL_SONNET if abone_mi else MODEL_HAIKU

        prompt = f"""Profesyonel {sinav_turu} uzmanı olarak, {ders} dersinin {konu} konusundan {adet} adet soru hazırla.
        Format: Soru, şıklar ve çözüm mutlaka olsun."""

        response = client.messages.create(
            model=model_adi,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        # Hatayı terminalde görmek için burası çok önemli!
        print(f"🚨 Soru Hazırlama API Hatası: {e}")
        raise e  # Hatayı yukarı fırlat ki handlers.py'deki 'except' bloğu çalışsın


# ───────────────────────────────────────────
# TEST
# ───────────────────────────────────────────

if __name__ == "__main__":
    print("🔍 Intent Filter Testi:")
    testler = [
        ("türev konusunu anlat", True),
        ("bugün hava nasıl", False),
        ("KPSS tarih konuları neler", True),
        ("bana şiir yaz", False),
        ("integral nasıl çözülür", True),
    ]

    for mesaj, beklenen in testler:
        sonuc = intent_kontrol(mesaj)
        durum = "✅" if sonuc == beklenen else "❌"
        print(f"{durum} '{mesaj}' → {'İLGİLİ' if sonuc else 'ALAKASIZ'}")

    print("\n📝 Soru Hazırlama Testi:")
    # Parametreleri yeni fonksiyona göre güncelledim
    soru = soru_hazirla("YKS", "Matematik", "Türev", 1, abone_mi=True)
    print(soru)