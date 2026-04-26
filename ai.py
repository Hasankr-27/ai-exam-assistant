import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────
# INTENT FILTER
# ───────────────────────────────────────────

def intent_kontrol(mesaj: str) -> bool:
    """
    Kullanıcının mesajının sınav konularıyla ilgili olup olmadığını kontrol eder.
    True  → ilgili, cevap verilebilir
    False → alakasız, reddedilmeli
    """
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": f"""Sen bir sınav asistanısın (YKS/KPSS/DGS).
Kullanıcının mesajı sınav konularıyla ilgili mi?
Sadece "EVET" veya "HAYIR" yaz, başka hiçbir şey yazma.

Mesaj: {mesaj}"""
            }
        ]
    )

    cevap = response.content[0].text.strip().upper()
    return cevap == "EVET"


# ───────────────────────────────────────────
# ANA AI FONKSİYONU
# ───────────────────────────────────────────

SISTEM_PROMPTLARI = {
    "YKS": """Sen YKS (Üniversite Giriş Sınavı) konusunda uzman bir öğretmensin.
Türkçe, Matematik, Fizik, Kimya, Biyoloji, Tarih, Coğrafya, Felsefe konularında yardımcı olursun.
Konu anlatımlarını kısa ve öz tut. Formülleri ve önemli noktaları vurgula.
Sadece YKS ile ilgili sorulara cevap ver.""",

    "KPSS": """Sen KPSS (Kamu Personeli Seçme Sınavı) konusunda uzman bir öğretmensin.
Genel Yetenek, Genel Kültür, Eğitim Bilimleri konularında yardımcı olursun.
Konu anlatımlarını kısa ve öz tut. Önemli noktaları ve sık çıkan konuları vurgula.
Sadece KPSS ile ilgili sorulara cevap ver.""",

    "DGS": """Sen DGS (Dikey Geçiş Sınavı) konusunda uzman bir öğretmensin.
Sayısal ve Sözel bölüm konularında yardımcı olursun.
Konu anlatımlarını kısa ve öz tut. Temel kavramları ve formülleri vurgula.
Sadece DGS ile ilgili sorulara cevap ver.""",

    "AGS": """Sen AGS (Alan Giriş Sınavı) konusunda uzman bir öğretmensin.
Temel matematik, Türkçe ve alan derslerinde yardımcı olursun.
Konu anlatımlarını kısa ve öz tut. Önemli noktaları vurgula.
Sadece AGS ile ilgili sorulara cevap ver."""

}


def ai_cevap_al(mesaj: str, sinav_turu: str, sohbet_gecmisi: list) -> str:
    """
    Kullanıcının mesajına AI cevabı üretir.
    sohbet_gecmisi: [{"role": "user/assistant", "content": "..."}]
    """
    sistem = SISTEM_PROMPTLARI.get(sinav_turu, SISTEM_PROMPTLARI["YKS"])

    # Sohbet geçmişine yeni mesajı ekle
    mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        system=sistem,
        messages=mesajlar
    )

    return response.content[0].text


# ───────────────────────────────────────────
# SORU HAZIRLA
# ───────────────────────────────────────────

def soru_hazirla(konu: str, sinav_turu: str) -> str:
    """
    Belirtilen konuda çoktan seçmeli soru üretir.
    """
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""{sinav_turu} sınavı için {konu} konusunda 1 adet çoktan seçmeli soru hazırla.
Format şöyle olsun:
Soru: ...
A) ...
B) ...
C) ...
D) ...
E) ...
Cevap: (sadece harf)
Açıklama: (kısa)"""
            }
        ]
    )

    return response.content[0].text


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
    soru = soru_hazirla("türev", "YKS")
    print(soru)