import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
REQUESTS_PER_SECOND   = float(os.getenv("REQUESTS_PER_SECOND", "1"))

DATA_DIR = "data"
OUTPUT_RAW = f"{DATA_DIR}/schools_raw.csv"
OUTPUT_ENRICHED = f"{DATA_DIR}/schools_enriched.csv"
OUTPUT_XLSX = f"{DATA_DIR}/sekolah_jakarta_spp.xlsx"
OUTPUT_CSV = f"{DATA_DIR}/sekolah_jakarta_spp.csv"

JENJANG_LIST = ["SD", "SMP", "SMA"]

# Kata kunci pencarian SPP di HTML
SPP_KEYWORDS = [
    "spp", "biaya pendidikan", "biaya sekolah", "uang sekolah",
    "iuran", "investasi pendidikan", "biaya bulanan", "cicilan",
    "per bulan", "perbulan", "uang pangkal", "biaya masuk",
]

# Segmentasi SPP untuk marketing
SPP_SEGMENTS = {
    "Budget": (0, 500_000),
    "Menengah": (500_000, 1_500_000),
    "Premium": (1_500_000, 3_000_000),
    "Ultra Premium": (3_000_000, float("inf")),
}

# Headers HTTP umum
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}
