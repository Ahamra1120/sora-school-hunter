"""
Fase 1: Ambil daftar sekolah swasta SD/SMP/SMA di Jakarta.
Sumber: https://referensi.data.kemendikdasmen.go.id
Struktur URL:
  /pendidikan/{jenjang_path}/010000/1  → Provinsi DKI Jakarta
  /pendidikan/{jenjang_path}/{kode}/2  → Kota/Kabupaten
  /pendidikan/{jenjang_path}/{kode}/3  → Kecamatan → tabel sekolah

Output: data/schools_raw.csv
"""
import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import REQUEST_HEADERS, DATA_DIR, OUTPUT_RAW

BASE_URL = "https://referensi.data.kemendikdasmen.go.id"
KODE_DKI  = "010000"

# dikdas = SD/MI/SMP/MTs  |  dikmen = SMA/MA/SMK
JENJANG_PATHS = ["dikdas", "dikmen"]


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(requests.RequestException),
)
def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def get_links_from_table(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Ambil semua (teks, href) dari link di dalam tabel."""
    table = soup.find("table")
    if not table:
        return []
    return [(a.get_text(strip=True), a["href"])
            for a in table.find_all("a", href=True)]


def infer_jenjang(nama: str, jenjang_path: str = "") -> str:
    """Tebak jenjang dari nama sekolah (prefix-first agar lebih akurat)."""
    import re
    n = nama.upper().strip()

    # Prefix lengkap (urutan: lebih spesifik dulu)
    prefix_sma = ["SMAS ", "SMAI ", "SMAIT ", "SMAN ", "SMA ", "MAS ", "MA "]
    prefix_smk = ["SMKS ", "SMKI ", "SMKIT ", "SMKN ", "SMK "]
    prefix_smp = ["SMPS ", "SMPI ", "SMPIT ", "SMPN ", "SMP ",
                  "MTSS ", "MTSI ", "MTS ", "MTS."]
    prefix_sd  = ["SDS ", "SDI ", "SDIT ", "SDIN ", "SDN ", "SD ",
                  "MIS ", "MIN ", "MI ", "MI.", "SDIT."]

    for p in prefix_sma:
        if n.startswith(p): return "SMA"
    for p in prefix_smk:
        if n.startswith(p): return "SMK"
    for p in prefix_smp:
        if n.startswith(p): return "SMP"
    for p in prefix_sd:
        if n.startswith(p): return "SD"

    # Fallback word-boundary
    patterns = [
        ("SMA", r'\b(SMA|ALIYAH|MENENGAH ATAS)\b'),
        ("SMK", r'\b(SMK|KEJURUAN)\b'),
        ("SMP", r'\b(SMP|TSANAWIYAH|MENENGAH PERTAMA)\b'),
        ("SD",  r'\b(SD|IBTIDAIYAH|SEKOLAH DASAR)\b'),
    ]
    for jenjang, pattern in patterns:
        if re.search(pattern, n):
            return jenjang

    # Fallback dari konteks URL: dikmen → asumsi SMA, dikdas → tidak bisa tentukan pasti
    if jenjang_path == "dikmen":
        return "SMA"

    return ""


def parse_school_table(soup: BeautifulSoup, kecamatan: str, kota: str, jenjang_path: str = "") -> list[dict]:
    """Parse tabel sekolah di halaman level-3 (kecamatan)."""
    table = soup.find("table")
    if not table:
        return []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not cells:
            continue

        # Mapping kolom fleksibel
        row: dict = {"kecamatan": kecamatan, "kota": kota}
        for i, cell in enumerate(cells):
            if i >= len(headers):
                break
            h = headers[i]
            if "npsn" in h:
                row["npsn"] = cell
            elif "nama" in h:
                row["nama_sekolah"] = cell
            elif "alamat" in h:
                row["alamat"] = cell
            elif "kelurahan" in h or "desa" in h:
                row["kelurahan"] = cell
            elif "status" in h:
                row["status"] = cell

        # Hanya ambil sekolah swasta
        if row.get("status", "").upper() != "SWASTA":
            continue

        nama = row.get("nama_sekolah", "")
        row["jenjang"] = infer_jenjang(nama, jenjang_path)

        if row.get("npsn") and nama:
            rows.append(row)

    return rows


def scrape_jenjang_path(jenjang_path: str) -> list[dict]:
    """Scrape semua sekolah swasta untuk satu jenjang path (dikdas / dikmen)."""
    all_schools: list[dict] = []

    # Level 1: Provinsi DKI Jakarta → ambil link kota
    url_prov = f"{BASE_URL}/pendidikan/{jenjang_path}/{KODE_DKI}/1"
    print(f"  [{jenjang_path}] Level 1 (provinsi): {url_prov}")
    try:
        soup = fetch(url_prov)
    except Exception as e:
        print(f"  [{jenjang_path}] GAGAL level 1: {e}")
        return []

    kota_links = get_links_from_table(soup)
    print(f"  [{jenjang_path}] Ditemukan {len(kota_links)} kota/kab")

    for kota_nama, kota_url in kota_links:
        time.sleep(0.8)

        # Level 2: Kota → ambil link kecamatan
        try:
            soup_kota = fetch(kota_url)
        except Exception as e:
            print(f"    GAGAL kota {kota_nama}: {e}")
            continue

        kec_links = get_links_from_table(soup_kota)

        for kec_nama, kec_url in kec_links:
            time.sleep(0.8)

            # Level 3: Kecamatan → tabel sekolah
            try:
                soup_kec = fetch(kec_url)
            except Exception as e:
                print(f"      GAGAL kec {kec_nama}: {e}")
                continue

            schools = parse_school_table(soup_kec, kecamatan=kec_nama, kota=kota_nama, jenjang_path=jenjang_path)
            all_schools.extend(schools)
            print(f"      {kota_nama} / {kec_nama}: {len(schools)} swasta", end="\r")

    print()
    return all_schools


def run():
    os.makedirs(DATA_DIR, exist_ok=True)
    all_schools: list[dict] = []

    print("=== FASE 1: Scraping dari referensi.data.kemendikdasmen.go.id ===\n")

    for jenjang_path in JENJANG_PATHS:
        schools = scrape_jenjang_path(jenjang_path)
        all_schools.extend(schools)
        print(f"  [{jenjang_path}] Subtotal: {len(schools)} sekolah\n")

    if not all_schools:
        print("GAGAL: Tidak ada data yang berhasil diambil.")
        return

    df = pd.DataFrame(all_schools)

    # Kolom standar
    kolom = ["npsn", "nama_sekolah", "jenjang", "status", "alamat",
             "kelurahan", "kecamatan", "kota", "akreditasi"]
    for k in kolom:
        if k not in df.columns:
            df[k] = ""

    df = (df[kolom]
          .drop_duplicates(subset=["npsn"])
          .reset_index(drop=True))

    # Ringkasan
    print(f"\nTotal sekolah swasta: {len(df)}")
    print("\nBreakdown jenjang:")
    print(df["jenjang"].value_counts().to_string())
    print("\nBreakdown kota:")
    print(df["kota"].value_counts().to_string())

    df.to_csv(OUTPUT_RAW, index=False, encoding="utf-8-sig")
    print(f"\nDisimpan ke: {OUTPUT_RAW}")


if __name__ == "__main__":
    run()
