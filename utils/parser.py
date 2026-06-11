import re
from bs4 import BeautifulSoup
from config import SPP_KEYWORDS

# Pola harga: Rp 1.500.000 / Rp1500000 / 1.500.000/bulan
_PRICE_RE = re.compile(
    r"Rp\.?\s?[\d.,]{3,}|[\d.,]{4,}\s*/?\s*bulan|[\d.,]{4,}\s*per\s*bulan",
    re.IGNORECASE,
)

# Keyword lebih spesifik ke SPP bulanan (bukan uang pangkal)
_SPP_MONTHLY_KEYWORDS = [
    "spp bulanan", "spp per bulan", "spp perbulan",
    "iuran bulanan", "biaya bulanan", "uang sekolah per bulan",
]

# Keyword yang menandakan ini BUKAN SPP bulanan — hindari
_SKIP_CONTEXT = ["uang pangkal", "biaya masuk", "uang masuk", "daftar ulang", "dp sekolah"]


def _normalize_price(raw: str) -> int | None:
    """Ubah string harga menjadi integer rupiah."""
    cleaned = re.sub(r"[^\d]", "", raw)
    if len(cleaned) < 4:
        return None
    value = int(cleaned)
    # SPP bulanan: Rp 50.000 – Rp 15.000.000
    if value < 50_000 or value > 15_000_000:
        return None
    return value


def _extract_from_text(text: str) -> tuple[int | None, str]:
    """Cari harga SPP bulanan dalam dua tahap: keyword spesifik → umum."""
    # Tahap 1: keyword spesifik "spp bulanan", "iuran bulanan", dll.
    # Tidak pakai skip-context karena keywordnya sudah cukup spesifik.
    # Window kecil (10 sebelum, 150 sesudah) agar harga di baris selanjutnya yang diambil.
    for kw in _SPP_MONTHLY_KEYWORDS:
        idx = text.find(kw)
        if idx == -1:
            continue
        window = text[max(0, idx - 10): idx + 150]
        for m in _PRICE_RE.findall(window):
            price = _normalize_price(m)
            if price:
                return price, f"keyword:{kw}"

    # Tahap 2: keyword umum — lebih ketat soal konteks uang pangkal.
    # Window lebih kecil (5 sebelum) agar tidak menangkap harga dari baris sebelumnya.
    for kw in SPP_KEYWORDS:
        idx = text.find(kw)
        if idx == -1:
            continue
        window = text[max(0, idx - 5): idx + 200]
        # Skip jika kata pangkal/masuk muncul DEKAT keyword (bukan di baris lain)
        nearby = text[max(0, idx - 40): idx + 40]
        if any(skip in nearby for skip in _SKIP_CONTEXT):
            continue
        for m in _PRICE_RE.findall(window):
            price = _normalize_price(m)
            if price:
                return price, f"keyword:{kw}"

    return None, "keyword_ditemukan_tapi_harga_tidak_terparsing"


def extract_spp_from_html(html: str) -> tuple[int | None, str]:
    """Parsing HTML untuk mencari nominal SPP bulanan."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True).lower()

    if not any(kw in text for kw in SPP_KEYWORDS):
        return None, "tidak_ada_keyword"

    return _extract_from_text(text)


def extract_spp_from_text(text: str) -> tuple[int | None, str]:
    """Parsing plain text (caption IG, snippet search) untuk mencari nominal SPP bulanan."""
    text_lower = text.lower()
    if not any(kw in text_lower for kw in SPP_KEYWORDS):
        return None, "tidak_ada_keyword"
    return _extract_from_text(text_lower)


def has_spp_keyword(html: str) -> bool:
    """Cek cepat apakah halaman mengandung kata kunci SPP."""
    text = html.lower()
    return any(kw in text for kw in SPP_KEYWORDS)
