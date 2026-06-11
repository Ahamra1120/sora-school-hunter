"""
Fase 2 (GRATIS): Ambil koordinat + akreditasi + website + telepon
dari halaman detail resmi kemendikdasmen per NPSN.

Sumber: https://referensi.data.kemendikdasmen.go.id/pendidikan/npsn/{npsn}
- Koordinat dari Leaflet map script (lat/lon)
- Akreditasi, website, telepon dari tabel profil sekolah
- Tidak butuh API key, tidak ada biaya
- Rate limit: 1 req/detik (sopan ke server pemerintah)

Resume-safe: setiap baris langsung ditulis ke CSV (append).
Jika stop kapanpun → jalankan ulang, otomatis lanjut dari terakhir.
"""
import os
import csv
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import REQUEST_HEADERS, OUTPUT_RAW, OUTPUT_ENRICHED, DATA_DIR

BASE_NPSN_URL = "https://referensi.data.kemendikdasmen.go.id/pendidikan/npsn"

# Pola koordinat di Leaflet script
_LAT_RE = re.compile(r"lat\s*:\s*(-?\d+\.\d+)")
_LON_RE = re.compile(r"lon\s*:\s*(-?\d+\.\d+)")

OUTPUT_COLUMNS = [
    "npsn", "nama_sekolah", "jenjang", "status", "alamat",
    "kelurahan", "kecamatan", "kota",
    "akreditasi", "website", "telepon",
    "lat", "lng", "koordinat_sumber",
]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
)
def fetch_npsn_page(npsn: str) -> requests.Response:
    url = f"{BASE_NPSN_URL}/{npsn}"
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp


def _parse_table_field(soup: BeautifulSoup, label: str) -> str:
    """Ambil nilai dari tabel profil berformat: ['', 'Label', ':', 'Nilai']."""
    for tr in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
        # Format kolom: ['', 'Nama Field', ':', 'Nilai']
        if len(cells) >= 4 and cells[1] == label:
            return cells[3]
    return ""


def scrape_npsn(npsn: str) -> dict:
    """
    Fetch halaman detail NPSN dan ekstrak:
    - lat, lng  (dari Leaflet script)
    - akreditasi, website, telepon  (dari tabel profil)
    """
    result = {
        "lat": "", "lng": "", "koordinat_sumber": "",
        "akreditasi": "", "website": "", "telepon": "",
    }

    try:
        resp  = fetch_npsn_page(npsn)
        html  = resp.text
        soup  = BeautifulSoup(html, "lxml")

        # Koordinat dari Leaflet script
        lat_m = _LAT_RE.search(html)
        lon_m = _LON_RE.search(html)
        if lat_m and lon_m:
            result["lat"] = lat_m.group(1)
            result["lng"] = lon_m.group(1)
            result["koordinat_sumber"] = "kemendikdasmen"

        # Akreditasi, website, telepon dari tabel
        result["akreditasi"] = _parse_table_field(soup, "Akreditasi")
        result["telepon"]    = _parse_table_field(soup, "Telepon")
        website              = _parse_table_field(soup, "Website")
        # Bersihkan double-protocol seperti "http://https://..."
        website = re.sub(r"^https?://(https?://)", r"\1", website)
        result["website"] = website if website.startswith("http") else ""

    except Exception as e:
        result["koordinat_sumber"] = f"error:{e}"

    return result


def _load_done_npsn() -> set[str]:
    if not os.path.exists(OUTPUT_ENRICHED):
        return set()
    try:
        done = pd.read_csv(OUTPUT_ENRICHED, dtype=str, usecols=["npsn"]).fillna("")
        return set(done["npsn"].tolist())
    except Exception:
        return set()


def _append_row(row_dict: dict, write_header: bool):
    cols = OUTPUT_COLUMNS + [k for k in row_dict if k not in OUTPUT_COLUMNS]
    with open(OUTPUT_ENRICHED, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row_dict)


def run():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(OUTPUT_RAW):
        print(f"ERROR: {OUTPUT_RAW} tidak ditemukan. Jalankan fase1_dapodik.py dulu.")
        return

    df = pd.read_csv(OUTPUT_RAW, dtype=str).fillna("")

    done_npsn = _load_done_npsn()
    is_new    = len(done_npsn) == 0
    remaining = df[~df["npsn"].isin(done_npsn)]

    if done_npsn:
        print(f"Resume: {len(done_npsn)} sudah diproses, {len(remaining)} tersisa")
    if remaining.empty:
        print("Semua sekolah sudah di-enrich.")
        return

    total = len(remaining)
    print("=== FASE 2: Ambil koordinat dari kemendikdasmen.go.id ===")
    print(f"Total  : {total} sekolah")
    print(f"Sumber : referensi.data.kemendikdasmen.go.id/pendidikan/npsn/{{npsn}}")
    print(f"Est.   : ~{total // 60} menit ({total} detik)")
    print(f"Data   : koordinat + akreditasi + website + telepon")
    print(f"Safety : setiap baris langsung disimpan, aman jika stop kapanpun\n")

    found_coord = 0
    found_web   = 0

    for i, (_, row) in enumerate(remaining.iterrows()):
        npsn  = row.get("npsn", "")
        extra = scrape_npsn(npsn)

        # Gabung data asal + data baru
        merged = {**row.to_dict(), **extra}

        # Tulis langsung ke CSV
        _append_row(merged, write_header=(is_new and i == 0))

        if extra["lat"]:
            found_coord += 1
        if extra["website"]:
            found_web += 1

        pct_coord = found_coord / (i + 1) * 100
        status    = "OK " if extra["lat"] else "-- "
        print(
            f"  [{i+1:>4}/{total}] {row.get('nama_sekolah','')[:38]:<38}"
            f" {status}"
            f" koordinat:{found_coord:>4} ({pct_coord:.0f}%)",
            end="\r",
        )

        time.sleep(1.0)  # 1 req/detik

    print(f"\n\nSelesai!")
    final       = pd.read_csv(OUTPUT_ENRICHED)
    n_coord     = (final["lat"].replace("", pd.NA).notna()).sum()
    n_web       = (final["website"].replace("", pd.NA).notna()).sum()
    n_akr       = (final["akreditasi"].replace("", pd.NA).notna()).sum()
    print(f"Total sekolah   : {len(final)}")
    print(f"Punya koordinat : {n_coord} ({n_coord/len(final)*100:.1f}%)")
    print(f"Punya website   : {n_web}  ({n_web/len(final)*100:.1f}%)")
    print(f"Punya akreditasi: {n_akr}  ({n_akr/len(final)*100:.1f}%)")
    print(f"Disimpan ke     : {OUTPUT_ENRICHED}")


if __name__ == "__main__":
    run()
