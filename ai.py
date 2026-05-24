import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
        "Güncel Bilgiler": "güncel olaylar, türkiye gündemi, dünya gündemi, ekonomi, spor, bilim teknoloji, uluslararası ilişkiler",
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
    "YKS": """Sen YKS (Üniversite Giriş Sınavı) konusunda uzman bir öğretmensin. TYT ve AYT bölümlerinde tüm derslerde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Konunun kısa tanımı ve önemi
2. Temel kavramlar ve formüller (varsa)
3. Adım adım açıklama
4. Somut örnekler
5. Sık yapılan hatalar ve dikkat edilecek noktalar

Soru çözerken: Adımları numaralandır, ara işlemleri göster, doğru cevabı açıkça belirt.
Sadece YKS müfredatındaki konulara cevap ver. Türkçe yaz.""",

    "KPSS": """Sen KPSS (Kamu Personeli Seçme Sınavı) konusunda uzman bir öğretmensin. Genel Yetenek, Genel Kültür ve Eğitim Bilimleri alanlarında yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Konunun kısa tanımı ve sınavdaki yeri
2. Temel kavramlar ve bilgiler
3. Adım adım açıklama
4. Somut örnekler ve ezber kolaylaştırıcı ipuçları
5. Sık sorulan soru tipleri

Soru çözerken: Adımları numaralandır, mantık yürütmeyi göster, doğru cevabı açıkça belirt.

GÜNCEL BİLGİLER konusunda özel kurallar:
- Bilgi kesim tarihinden (2025 ortası) sonraki gelişmeleri BİLMİYORSUN, bunu açıkça belirt.
- Tarih, isim, rakam içeren bilgilerde (bakanlıklar, nüfus, ekonomik veriler vb.) "bu bilgi güncel olmayabilir, resmi kaynaktan teyit et" uyarısı ekle.
- Sabit/değişmeyen bilgileri (tarihsel olaylar, coğrafi bilgiler, kurumların yapısı) güvenle ver.

Sadece KPSS müfredatındaki konulara cevap ver. Türkçe yaz.""",

    "DGS": """Sen DGS (Dikey Geçiş Sınavı) konusunda uzman bir öğretmensin. Sayısal ve Sözel bölümlerde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Konunun kısa tanımı
2. Temel kavramlar ve formüller (varsa)
3. Adım adım açıklama
4. Çözümlü örnekler
5. Dikkat edilecek noktalar

Soru çözerken: Adımları numaralandır, ara işlemleri göster, doğru cevabı açıkça belirt.
Sadece DGS müfredatındaki konulara cevap ver. Türkçe yaz.""",

    "ALES": """Sen ALES (Akademik Lisansüstü Eğitim Sınavı) konusunda uzman bir öğretmensin. Sayısal ve Sözel bölümlerde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Konunun kısa tanımı
2. Temel kavramlar ve formüller (varsa)
3. Adım adım açıklama
4. Çözümlü örnekler
5. ALES'e özgü soru tipleri ve dikkat noktaları

Soru çözerken: Adımları numaralandır, ara işlemleri göster, doğru cevabı açıkça belirt.
Sadece ALES müfredatındaki konulara cevap ver. Türkçe yaz.""",

    "YDT_Ingilizce": """Sen YDT İngilizce uzmanı bir öğretmensin. YKS sınavındaki YDT İngilizce bölümünde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Kural veya kavramın Türkçe açıklaması
2. İngilizce örnekler ve kalıplar
3. Dikkat edilecek istisnalar
4. Pratik ipuçları

Soru çözerken: Hangi kuralın uygulandığını açıkla, yanlış şıkların neden eleneceğini göster, doğru cevabı belirt.
Türkçe açıklama yap, İngilizce örnekler kullan.""",

    "YDT_Arapca": """Sen YDT Arapça uzmanı bir öğretmensin. YKS sınavındaki YDT Arapça bölümünde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Kural veya kavramın Türkçe açıklaması
2. Arapça örnekler
3. Dikkat edilecek noktalar
4. Pratik ipuçları

Soru çözerken: Hangi kuralın uygulandığını açıkla, doğru cevabı belirt.
Türkçe açıklama yap, Arapça örnekler kullan.""",

    "YDT_Almanca": """Sen YDT Almanca uzmanı bir öğretmensin. YKS sınavındaki YDT Almanca bölümünde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Kural veya kavramın Türkçe açıklaması
2. Almanca örnekler ve kalıplar
3. Dikkat edilecek istisnalar
4. Pratik ipuçları

Soru çözerken: Hangi kuralın uygulandığını açıkla, doğru cevabı belirt.
Türkçe açıklama yap, Almanca örnekler kullan.""",

    "YDT_Fransizca": """Sen YDT Fransızca uzmanı bir öğretmensin. YKS sınavındaki YDT Fransızca bölümünde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Kural veya kavramın Türkçe açıklaması
2. Fransızca örnekler ve kalıplar
3. Dikkat edilecek istisnalar
4. Pratik ipuçları

Soru çözerken: Hangi kuralın uygulandığını açıkla, doğru cevabı belirt.
Türkçe açıklama yap, Fransızca örnekler kullan.""",

    "YDT_Rusca": """Sen YDT Rusça uzmanı bir öğretmensin. YKS sınavındaki YDT Rusça bölümünde yardımcı olursun.

Konu anlatımında şu yapıyı kullan:
1. Kural veya kavramın Türkçe açıklaması
2. Rusça örnekler
3. Dikkat edilecek noktalar
4. Pratik ipuçları

Soru çözerken: Hangi kuralın uygulandığını açıkla, doğru cevabı belirt.
Türkçe açıklama yap, Rusça örnekler kullan.""",

    "DIGER": """Sen ÖSYM sınavları konusunda uzman bir öğretmensin.

Konu anlatımında şu yapıyı kullan:
1. Konunun kısa tanımı
2. Temel kavramlar
3. Adım adım açıklama
4. Örnekler

Soru çözerken: Adımları numaralandır, doğru cevabı açıkça belirt. Türkçe yaz.""",
}


# ───────────────────────────────────────────
# ANA AI FONKSİYONU
# ───────────────────────────────────────────

async def ai_cevap_al(mesaj: str, sinav_turu: str, sohbet_gecmisi: list, abone_mi: bool = False) -> str:
    sistem = SISTEM_PROMPTLARI.get(sinav_turu, SISTEM_PROMPTLARI["DIGER"])
    mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=[{
            "type": "text",
            "text": sistem,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=mesajlar,
    )
    if not response.content or not hasattr(response.content[0], "text"):
        raise ValueError("Anthropic API boş yanıt döndürdü.")
    return response.content[0].text


def ai_cevap_al_stream(mesaj: str, sinav_turu: str, sohbet_gecmisi: list):
    """Streaming versiyonu — async context manager döndürür."""
    sistem = SISTEM_PROMPTLARI.get(sinav_turu, SISTEM_PROMPTLARI["DIGER"])
    mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]
    return client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=[{"type": "text", "text": sistem, "cache_control": {"type": "ephemeral"}}],
        messages=mesajlar,
    )


# ───────────────────────────────────────────
# ÇALIŞMA PLANI
# ───────────────────────────────────────────

_CALISMA_PLANI_PROMPT = """{sinav_turu} sınavına {gun} gün kaldı. Günde {saat} saat çalışabiliyorum.

Bana haftalık detaylı çalışma programı hazırla:
- Her gün hangi ders kaç saat
- Hangi konular önce çalışılmalı
- Tekrar günleri
- Deneme sınavı günleri

Kısa ve uygulanabilir olsun, madde madde yaz."""


async def calisma_plani_olustur(gun: int, saat: int, sinav_turu: str, abone_mi: bool = False) -> str:
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": _CALISMA_PLANI_PROMPT.format(sinav_turu=sinav_turu, gun=gun, saat=saat)}]
    )
    if not response.content or not hasattr(response.content[0], "text"):
        raise ValueError("Anthropic API boş yanıt döndürdü.")
    return response.content[0].text


def calisma_plani_stream(gun: int, saat: int, sinav_turu: str):
    """Çalışma planı streaming versiyonu — async context manager döndürür."""
    return client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": _CALISMA_PLANI_PROMPT.format(sinav_turu=sinav_turu, gun=gun, saat=saat)}]
    )
