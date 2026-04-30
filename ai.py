import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────
# SINAV DERSLERİ
# ───────────────────────────────────────────

SINAV_DERSLERI = {
    "YKS": {
        "TYT Türkçe": "türkçe, paragraf, dil bilgisi",
        "TYT Matematik": "temel matematik, sayılar, cebir",
        "TYT Fizik": "fizik temel konular",
        "TYT Kimya": "kimya temel konular",
        "TYT Biyoloji": "biyoloji temel konular",
        "TYT Tarih": "tarih",
        "TYT Coğrafya": "coğrafya",
        "TYT Felsefe": "felsefe, mantık",
        "AYT Matematik": "ileri matematik, türev, integral, limit",
        "AYT Fizik": "ileri fizik",
        "AYT Kimya": "ileri kimya",
        "AYT Biyoloji": "ileri biyoloji",
        "AYT Edebiyat": "türk dili ve edebiyatı",
        "AYT Tarih": "ileri tarih",
        "AYT Coğrafya": "ileri coğrafya",
    },
    "KPSS": {
        "Türkçe": "türkçe, paragraf, dil bilgisi",
        "Matematik": "matematik, sayısal",
        "Tarih": "türk tarihi, osmanlı, cumhuriyet",
        "Coğrafya": "türkiye coğrafyası",
        "Vatandaşlık": "anayasa, vatandaşlık bilgisi",
        "Din": "din kültürü",
        "Eğitim Bilimleri": "gelişim psikolojisi, öğrenme, program geliştirme, ölçme değerlendirme",
    },
    "DGS": {
        "Matematik": "matematik, sayısal",
        "Geometri": "geometri",
        "Türkçe": "türkçe, sözel",
        "Anlam Bilgisi": "anlam bilgisi, kelime",
    },
    "ALES": {
        "Sayısal Matematik": "matematik, sayısal",
        "Sözel Türkçe": "türkçe, sözel, anlam",
    },
    "DIGER": {
        "Türkçe": "türkçe",
        "Matematik": "matematik",
        "Yabancı Dil": "yabancı dil, ingilizce",
        "Alan Dersi": "alan dersi",
    }
}

# ───────────────────────────────────────────
# SİSTEM PROMPTLARI
# ───────────────────────────────────────────

SISTEM_PROMPTLARI = {
    "YKS": """Sen YKS (Üniversite Giriş Sınavı) konusunda uzman bir öğretmensin.
TYT ve AYT bölümlerinde tüm derslerde yardımcı olursun.
Sadece YKS konularıyla ilgili sorulara cevap ver.
Kısa, öz ve anlaşılır anlat.""",

    "KPSS": """Sen KPSS (Kamu Personeli Seçme Sınavı) konusunda uzman bir öğretmensin.
Genel Yetenek, Genel Kültür ve Eğitim Bilimleri alanlarında yardımcı olursun.
Sadece KPSS konularıyla ilgili sorulara cevap ver.
Kısa, öz ve anlaşılır anlat.""",

    "DGS": """Sen DGS (Dikey Geçiş Sınavı) konusunda uzman bir öğretmensin.
Sayısal ve Sözel bölümlerde yardımcı olursun.
Sadece DGS konularıyla ilgili sorulara cevap ver.
Kısa, öz ve anlaşılır anlat.""",

    "ALES": """Sen ALES (Akademik Lisansüstü Eğitim Sınavı) konusunda uzman bir öğretmensin.
Sayısal ve Sözel bölümlerde yardımcı olursun.
Sadece ALES konularıyla ilgili sorulara cevap ver.
Kısa, öz ve anlaşılır anlat.""",

    "DIGER": """Sen tüm ÖSYM sınavları konusunda uzman bir öğretmensin.
YDT, LGS, MSÜ ve diğer sınavlarda yardımcı olursun.
Sadece sınav konularıyla ilgili sorulara cevap ver.
Kısa, öz ve anlaşılır anlat.""",
}

# ───────────────────────────────────────────
# INTENT FILTER
# ───────────────────────────────────────────

def intent_kontrol(mesaj: str) -> bool:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": f"""Sen bir sınav asistanısın (YKS/KPSS/DGS/ALES/ÖSYM).
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

def ai_cevap_al(mesaj: str, sinav_turu: str, sohbet_gecmisi: list, abone_mi: bool = False) -> str:
    sistem = SISTEM_PROMPTLARI.get(sinav_turu, SISTEM_PROMPTLARI["DIGER"])
    mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]
    model = "claude-sonnet-4-5" if abone_mi else "claude-haiku-4-5"

    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=sistem,
        messages=mesajlar
    )
    return response.content[0].text


# ───────────────────────────────────────────
# SORU HAZIRLA
# ───────────────────────────────────────────

def soru_hazirla(konu: str, ders: str, sinav_turu: str, abone_mi: bool = False) -> str:
    model = "claude-sonnet-4-5" if abone_mi else "claude-haiku-4-5"

    response = client.messages.create(
        model=model,
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": f"""{sinav_turu} sınavı {ders} dersi için {konu} konusunda 1 çoktan seçmeli soru hazırla.

ÖNEMLİ KURALLAR:
1. Önce soruyu çöz ve doğru cevabı bul
2. Doğru cevabın şıklarda olduğundan %100 emin ol
3. Her adımı iki kez kontrol et
4. Eğer doğru cevap şıklarda yoksa soruyu baştan yaz
5. Gerçek {sinav_turu} sınav tarzında, zorluk seviyesinde olsun

Format:
❓ Soru: ...
A) ...
B) ...
C) ...
D) ...
E) ...
DOGRU_CEVAP: (sadece harf)"""
        }]
    )
    return response.content[0].text


def konu_dogrula(konu: str, ders: str, sinav_turu: str) -> bool:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"""{sinav_turu} sınavının {ders} dersinde "{konu}" konusu var mı?
Sadece "EVET" veya "HAYIR" yaz."""
        }]
    )
    return response.content[0].text.strip().upper() == "EVET"


def calisma_plani_olustur(gun: int, saat: int, sinav_turu: str, abone_mi: bool = False) -> str:
    model = "claude-sonnet-4-5" if abone_mi else "claude-haiku-4-5"

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""{sinav_turu} sınavına {gun} gün kaldı. Günde {saat} saat çalışabiliyorum.

Bana haftalık detaylı çalışma programı hazırla:
- Her gün hangi ders kaç saat
- Hangi konular önce çalışılmalı
- Tekrar günleri
- Deneme sınavı günleri

Kısa ve uygulanabilir olsun, madde madde yaz."""
        }]
    )
    return response.content[0].text