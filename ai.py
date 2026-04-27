import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────
# INTENT FILTER
# ───────────────────────────────────────────

def intent_kontrol(mesaj: str) -> bool:
    try:
        response = client.messages.create(
            model="claude-4-5-haiku-20251001",
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
    except Exception as e:
        print(f"Intent Filtre Hatası: {e}")
        return True


# ───────────────────────────────────────────
# ANA AI FONKSİYONU
# ───────────────────────────────────────────

SISTEM_PROMPTLARI = {
    "YKS": "Sen YKS uzmanı bir öğretmensin. Türkçe, Matematik, Fen ve Sosyal konularında kısa, öz ve formül odaklı yardımcı olursun.",
    "KPSS": "Sen KPSS uzmanı bir öğretmensin. Genel Yetenek, Kültür ve Eğitim Bilimleri konularında önemli noktaları vurgularsın.",
    "DGS": "Sen DGS uzmanı bir öğretmensin. Sayısal ve Sözel mantık konularında temel kavramları vurgularsın.",
    "ALES": "Sen ALES uzmanı bir öğretmensin. Akademik seviyede sayısal ve sözel mantık analizi yaparsın.",
    "DIGER": "Sen tüm ÖSYM sınavları konusunda uzman bir öğretmensin. Müfredata uygun kısa ve öz anlatım yaparsın."
}

def ai_cevap_al(mesaj: str, sinav_turu: str, sohbet_gecmisi: list, abone_mi: bool = False) -> str:
    # Hatayı düzelten kısım: Değişkenleri tanımlıyoruz
    sistem = SISTEM_PROMPTLARI.get(sinav_turu, SISTEM_PROMPTLARI["YKS"])
    mesajlar = sohbet_gecmisi + [{"role": "user", "content": mesaj}]

    # 🚨 Ücretsizlere Haiku 4.5, Abonelere Sonnet 4.5
    model_adi = "claude-4-5-sonnet-20251001" if abone_mi else "claude-4-5-haiku-20251001"

    response = client.messages.create(
        model=model_adi,
        max_tokens=1000,
        system=sistem,
        messages=mesajlar
    )
    return response.content[0].text


# ───────────────────────────────────────────
# SORU HAZIRLA (Profesyonel ÖSYM Modu)
# ───────────────────────────────────────────

def soru_hazirla(sinav_turu: str, ders: str, konu: str, adet: int, abone_mi: bool = False) -> str:
    # 🚨 Soru hazırlarken de aynı denge geçerli
    model_adi = "claude-4-5-sonnet-20251001" if abone_mi else "claude-4-5-haiku-20251001"

    prompt = f"""Sen profesyonel bir {sinav_turu} uzmanısın.
Lütfen {sinav_turu} müfredatına uygun olarak, {ders} dersinin {konu} konusundan tam {adet} adet çoktan seçmeli soru hazırla.

ÖNEMLİ KURALLAR:
1. Sorular yeni nesil ÖSYM formatında olsun.
2. Önce soruyu ver, şıkları (A, B, C, D, E) sırala.
3. Her sorunun hemen altında detaylı "Çözüm" ve "Doğru Cevap" bulunsun."""

    response = client.messages.create(
        model=model_adi,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
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