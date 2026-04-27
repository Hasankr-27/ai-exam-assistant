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
        model="claude-4-5-haiku", # Maliyeti düşük olması için Haiku kullanıyoruz
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

    "ALES": """Sen ALES (Akademik Lisansüstü Eğitim Sınavı) konusunda uzman bir öğretmensin.
Sayısal ve Sözel bölüm konularında yardımcı olursun.
Konu anlatımlarını kısa ve öz tut. Önemli noktaları vurgula.
Sadece ALES ile ilgili sorulara cevap ver.""",

"DIGER": """Sen tüm ÖSYM sınavları konusunda uzman bir öğretmensin.
YDT, AGS, LGS, MSÜ ve diğer tüm ÖSYM sınavlarında yardımcı olursun.
Konu anlatımlarını kısa ve öz tut. Önemli noktaları vurgula.
Sadece sınav konularıyla ilgili sorulara cevap ver."""

}


def ai_cevap_al(mesaj: str, sinav_turu: str, sohbet_gecmisi: list, abone_mi: bool = False) -> str:
    """
    Kullanıcının mesajına AI cevabı üretir.
    sohbet_gecmisi: [{"role": "user/assistant", "content": "..."}]
    """
    sistem = SISTEM_PROMPTLARI.get(sinav_turu, SISTEM_PROMPTLARI["YKS"])
    mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]

    # Abonelere 4.5 Sonnet, ücretsizlere 4.5 Haiku
    model = "claude-4-5-sonnet" if abone_mi else "claude-4-5-haiku"

    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=sistem,
        messages=mesajlar
    )

    return response.content[0].text


# ───────────────────────────────────────────
# YENİ SORU HAZIRLA (Profesyonel ÖSYM Modu)
# ───────────────────────────────────────────

def soru_hazirla(sinav_turu: str, ders: str, konu: str, adet: int, abone_mi: bool = False) -> str:
    """
    Kullanıcının seçtiği sınav, ders, konu ve adete göre soru üretir.
    """
    # Abonelere 4.5 Sonnet, ücretsizlere 4.5 Haiku
    model_adi = "claude-4-5-sonnet" if abone_mi else "claude-4-5-haiku"

    prompt = f"""Sen profesyonel bir {sinav_turu} uzmanısın.
Lütfen {sinav_turu} müfredatına uygun olarak, {ders} dersinin {konu} konusundan tam {adet} adet farklı çoktan seçmeli soru hazırla.

ÖNEMLİ KURALLAR:
1. Sorular ne çok kolay ne de gereksiz zor olsun, tam ÖSYM sınav formatında olsun.
2. Önce soruyu ver, şıkları (A, B, C, D, E) sırala.
3. Her sorunun hemen altında adım adım, açıklayıcı bir "Çözüm" ve "Doğru Cevap" bulunsun.
4. Sadece soruları ve çözümleri ver, gereksiz sohbete girme."""

    response = client.messages.create(
        model=model_adi,
        max_tokens=2500,  # 5 soru isteyebileceği için limiti yüksek tuttuk
        messages=[
            {
                "role": "user",
                "content": prompt
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
    # Parametreleri yeni fonksiyona göre güncelledim
    soru = soru_hazirla("YKS", "Matematik", "Türev", 1, abone_mi=True)
    print(soru)