"""
Fase 2: Enrichment data sekolah dengan website & telepon via Google Places API.
Input:  data/schools_raw.csv
Output: data/schools_enriched.csv

Butuh GOOGLE_PLACES_API_KEY di .env
Dokumentasi: https://developers.google.com/maps/documentation/places/web-service/text-search

Resume-safe: setiap baris langsung ditulis ke CSV (append mode).
Jika stop di tengah, jalankan ulang — baris yang sudah ada di-skip otomatis.
"""
import os
import csv
import time
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import (
    GOOGLE_PLACES_API_KEY, REQUEST_HEADERS,
    OUTPUT_RAW, OUTPUT_ENRICHED, DATA_DIR,
)

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"

# Kolom output final — urutan tetap agar CSV konsisten
OUTPUT_COLUMNS = [
    "npsn", "nama_sekolah", "jenjang", "status", "alamat",
    "kelurahan", "kecamatan", "kota", "akreditasi",
    "website", "telepon", "rating_google", "place_id", "lat", "lng",
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10),
       retry=retry_if_exception_type(requests.RequestException))
def text_search(query: str) -> dict:
    params = {
        "query": query,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "id",
        "region": "id",
    }
    resp = requests.get(PLACES_TEXT_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10),
       retry=retry_if_exception_type(requests.RequestException))
def place_details(place_id: str) -> dict:
    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,website,formatted_address,rating,geometry",
        "key": GOOGLE_PLACES_API_KEY,
        "language": "id",
    }
    resp = requests.get(PLACES_DETAILS_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def enrich_school(row: pd.Series) -> dict:
    """Cari website + telepon untuk satu sekolah via Google Places."""
    nama = row.get("nama_sekolah", "")
    kota = row.get("kota", "Jakarta")
    query = f"{nama} {kota} sekolah"

    result = {
        "website": "", "telepon": "", "rating_google": "",
        "place_id": "", "lat": "", "lng": "",
    }

    try:
        data = text_search(query)
        candidates = data.get("results", [])
        if not candidates:
            return result

        place = candidates[0]
        place_id = place.get("place_id", "")
        if not place_id:
            return result

        result["place_id"]      = place_id
        result["rating_google"] = place.get("rating", "")

        detail_data = place_details(place_id)
        detail = detail_data.get("result", {})
        result["website"] = detail.get("website", "")
        result["telepon"] = detail.get("formatted_phone_number", "")
        loc = detail.get("geometry", {}).get("location", {})
        result["lat"] = loc.get("lat", "")
        result["lng"] = loc.get("lng", "")

    except Exception as e:
        result["error_fase2"] = str(e)

    return result


def _load_done_npsn() -> set[str]:
    """Baca NPSN yang sudah ada di OUTPUT_ENRICHED."""
    if not os.path.exists(OUTPUT_ENRICHED):
        return set()
    try:
        done = pd.read_csv(OUTPUT_ENRICHED, dtype=str, usecols=["npsn"]).fillna("")
        return set(done["npsn"].tolist())
    except Exception:
        return set()


def _append_row(row_dict: dict, write_header: bool):
    """Tulis satu baris ke CSV (append). Thread-safe karena single-process."""
    cols = OUTPUT_COLUMNS + [k for k in row_dict if k not in OUTPUT_COLUMNS]
    with open(OUTPUT_ENRICHED, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row_dict)


def run():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not GOOGLE_PLACES_API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY belum di-set di .env")
        print("Salin .env.example ke .env dan isi API key.")
        return

    if not os.path.exists(OUTPUT_RAW):
        print(f"ERROR: {OUTPUT_RAW} tidak ditemukan. Jalankan fase1_dapodik.py dulu.")
        return

    df = pd.read_csv(OUTPUT_RAW, dtype=str).fillna("")

    done_npsn  = _load_done_npsn()
    is_new     = len(done_npsn) == 0
    remaining  = df[~df["npsn"].isin(done_npsn)]

    if done_npsn:
        print(f"Resume: {len(done_npsn)} sudah diproses, {len(remaining)} tersisa")
    if remaining.empty:
        print("Semua sekolah sudah di-enrich.")
        return

    total = len(remaining)
    print(f"=== FASE 2: Enrichment via Google Places API ===")
    print(f"Total yang akan diproses: {total}")
    print(f"Setiap baris langsung disimpan — aman jika stop kapanpun.\n")

    found = 0
    for i, (_, row) in enumerate(remaining.iterrows()):
        extra   = enrich_school(row)
        merged  = {**row.to_dict(), **extra}

        # Tulis langsung ke CSV setelah tiap baris berhasil diproses
        _append_row(merged, write_header=(is_new and i == 0))

        if extra.get("lat"):
            found += 1

        pct = found / (i + 1) * 100
        print(
            f"  [{i+1}/{total}] {row.get('nama_sekolah','')[:40]:<40}"
            f" lat={'ok' if extra.get('lat') else '--'}"
            f" web={'ok' if extra.get('website') else '--'}"
            f" ({pct:.0f}% hit)",
            end="\r",
        )

        time.sleep(1.0)  # ~1 req/detik

    print(f"\n\nSelesai!")
    final = pd.read_csv(OUTPUT_ENRICHED)
    punya_website = (final["website"].replace("", pd.NA).notna()).sum()
    punya_koordinat = (final["lat"].replace("", pd.NA).notna()).sum()
    print(f"Total   : {len(final)} sekolah")
    print(f"Website : {punya_website} ({punya_website/len(final)*100:.1f}%)")
    print(f"Koordinat: {punya_koordinat} ({punya_koordinat/len(final)*100:.1f}%)")
    print(f"Disimpan : {OUTPUT_ENRICHED}")


if __name__ == "__main__":
    run()
