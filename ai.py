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
    "Sayısal - Matematik": "matematik, sayılar, cebir, problemler",
    "Sayısal - Geometri": "geometri, alan, hacim, açılar",
    "Sözel - Türkçe": "türkçe, dil bilgisi, paragraf",
    "Sözel - Anlam Bilgisi": "anlam bilgisi, kelime, deyim",
    "Sözel - Mantık": "mantık, akıl yürütme",
    },
    "ALES": {
        "Sayısal Matematik": "matematik, sayısal",
        "Sözel Türkçe": "türkçe, sözel, anlam",
    },
    "YDT_Ingilizce": {
        "Dilbilgisi": "grammar, tenses, prepositions, conjunctions",
        "Kelime Bilgisi": "vocabulary, synonyms, antonyms, word forms",
        "Okuma Anlama": "reading comprehension, main idea, inference",
        "Cloze Test": "fill in the blanks, context clues",
    },
    "YDT_Arapca": {
        "Dilbilgisi": "arapça gramer, sarf, nahiv",
        "Kelime Bilgisi": "arapça kelimeler, eş anlamlı, zıt anlamlı",
        "Okuma Anlama": "arapça metin anlama",
        "Çeviri": "türkçe-arapça çeviri",
    },
    "YDT_Almanca": {
        "Dilbilgisi": "deutsche grammatik, zeitformen, kasus",
        "Kelime Bilgisi": "vokabular, synonyme, antonyme",
        "Okuma Anlama": "leseverstehen, textverständnis",
        "Cloze Test": "lückentext, ergänzungsaufgaben",
    },
    "YDT_Fransizca": {
        "Dilbilgisi": "grammaire française, conjugaison, temps",
        "Kelime Bilgisi": "vocabulaire, synonymes, antonymes",
        "Okuma Anlama": "compréhension écrite, lecture",
        "Cloze Test": "texte à trous, complétion",
    },
    "YDT_Rusca": {
        "Dilbilgisi": "русская грамматика, падежи, глаголы",
        "Kelime Bilgisi": "словарный запас, синонимы",
        "Okuma Anlama": "чтение и понимание текста",
        "Çeviri": "türkçe-rusça çeviri",
    },
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

    "YDT_Ingilizce": """Sen YDT İngilizce uzmanı bir öğretmensin.
YKS sınavındaki YDT İngilizce bölümünde yardımcı olursun.
Dilbilgisi, kelime bilgisi, okuma anlama ve cloze test konularında uzman.
Türkçe açıklama yap, İngilizce örnekler kullan.
Kısa, öz ve anlaşılır anlat.""",

    "YDT_Arapca": """Sen YDT Arapça uzmanı bir öğretmensin.
YKS sınavındaki YDT Arapça bölümünde yardımcı olursun.
Türkçe açıklama yap, Arapça örnekler kullan.
Kısa, öz ve anlaşılır anlat.""",

    "YDT_Almanca": """Sen YDT Almanca uzmanı bir öğretmensin.
YKS sınavındaki YDT Almanca bölümünde yardımcı olursun.
Türkçe açıklama yap, Almanca örnekler kullan.
Kısa, öz ve anlaşılır anlat.""",

    "YDT_Fransizca": """Sen YDT Fransızca uzmanı bir öğretmensin.
YKS sınavındaki YDT Fransızca bölümünde yardımcı olursun.
Türkçe açıklama yap, Fransızca örnekler kullan.
Kısa, öz ve anlaşılır anlat.""",

    "YDT_Rusca": """Sen YDT Rusça uzmanı bir öğretmensin.
YKS sınavındaki YDT Rusça bölümünde yardımcı olursun.
Türkçe açıklama yap, Rusça örnekler kullan.
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
                "content": f"""Sen bir sınav asistanısın (YKS/KPSS/DGS/ALES/YDT/ÖSYM).
Kullanıcının mesajı sınav konularıyla, derslerle veya öğrenmek istediği bir şeyle ilgili mi?
Eğitim, ders, konu, soru içeriyorsa EVET de.
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
            "content": f"""{sinav_turu} sınavının {ders} dersinde "{konu}" konusu veya buna benzer bir konu var mı?
Geniş yorumla, İngilizce kelimeler de olabilir.
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