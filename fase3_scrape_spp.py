"""
Fase 3: Scrape nominal SPP dengan pendekatan bertingkat (tiered fallback).

  Tier 1 — Website resmi sekolah
            httpx langsung → Playwright (JS render) jika perlu

  Tier 2 — DuckDuckGo Search
            Search "{nama_sekolah} SPP biaya bulanan {kota}"
            Parse snippet + fetch URL teratas
            Gratis, tanpa API key

  Tier 3 — Tandai perlu_verifikasi_manual

Resume-safe: setiap baris langsung ditulis ke CSV (append mode).
Jalankan ulang kapanpun → otomatis lanjut dari terakhir.
"""
import os
import csv
import time
import asyncio
import requests
import pandas as pd
from datetime import date
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    OUTPUT_ENRICHED, OUTPUT_XLSX, OUTPUT_CSV, DATA_DIR, SPP_SEGMENTS,
    REQUEST_HEADERS,
)
from utils.parser import extract_spp_from_html, extract_spp_from_text, has_spp_keyword
from utils.browser import fetch_with_js, close_browser

TIMEOUT = 12

KOLOM_FINAL = [
    "npsn", "nama_sekolah", "jenjang", "status", "alamat",
    "kecamatan", "kota", "akreditasi", "website", "telepon",
    "lat", "lng",
    "spp", "spp_confidence", "sumber_spp", "tier_spp", "segmen",
]

# Event loop persisten agar Playwright tidak buka/tutup browser tiap call
_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def label_segmen(spp_val) -> str:
    try:
        spp = int(float(spp_val))
    except (TypeError, ValueError):
        return "Tidak Diketahui"
    for nama, (low, high) in SPP_SEGMENTS.items():
        if low <= spp < high:
            return nama
    return "Tidak Diketahui"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=6),
       retry=retry_if_exception_type(requests.RequestException))
def _get(url: str) -> str:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _load_done_npsn() -> set[str]:
    if not os.path.exists(OUTPUT_CSV):
        return set()
    try:
        done = pd.read_csv(OUTPUT_CSV, dtype=str, usecols=["npsn"]).fillna("")
        return set(done["npsn"].tolist())
    except Exception:
        return set()


def _append_row(row_dict: dict, write_header: bool):
    cols = KOLOM_FINAL + [k for k in row_dict if k not in KOLOM_FINAL]
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row_dict)


# ─── Tier 1: Website ──────────────────────────────────────────────────────────

def scrape_website(url: str) -> tuple[int | None, str]:
    html = ""
    try:
        html = _get(url)
    except Exception:
        pass

    spp, src = extract_spp_from_html(html)
    if spp:
        return spp, f"website:{src}"

    # Fallback Playwright jika HTML kosong atau tampak butuh JS
    if not html or len(html) < 1500 or has_spp_keyword(html):
        try:
            html_js = _run(fetch_with_js(url))
            spp, spp_src = extract_spp_from_html(html_js)
            if spp:
                return spp, f"playwright:{spp_src}"
        except Exception:
            pass

    return None, ""


# ─── Tier 2: DuckDuckGo Search ───────────────────────────────────────────────

def search_ddg_spp(nama: str, kota: str) -> tuple[int | None, str]:
    queries = [
        f"{nama} SPP biaya bulanan {kota}",
        f"{nama} biaya sekolah SPP",
    ]
    MAX_MONTHLY = 10_000_000  # SPP bulanan realistis maks Rp 10 juta

    for query in queries:
        try:
            from ddgs import DDGS  # noqa: PLC0415
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
        except Exception:
            continue

        for r in results:
            snippet = r.get("body", "") + " " + r.get("title", "")

            spp, _ = extract_spp_from_text(snippet)
            if spp and spp <= MAX_MONTHLY:
                return spp, f"ddg_snippet:{r.get('href', '')}"

            if any(kw in snippet.lower() for kw in ["spp", "biaya", "iuran"]):
                try:
                    html = _get(r["href"])
                    spp, _ = extract_spp_from_html(html)
                    if spp and spp <= MAX_MONTHLY:
                        return spp, f"ddg_page:{r['href']}"
                except Exception:
                    pass
                time.sleep(0.5)

    return None, ""


# ─── Orchestrator ────────────────────────────────────────────────────────────

def process_school(school: dict) -> dict:
    result = {**school, "spp": None, "sumber_spp": "perlu_verifikasi_manual",
              "tier_spp": 3, "spp_confidence": "rendah"}
    website = school.get("website", "").strip()
    nama    = school.get("nama_sekolah", "")
    kota    = school.get("kota", "Jakarta")

    # ── Tier 1: Website ──────────────────────────────────
    if website and website.startswith("http"):
        spp, src = scrape_website(website)
        if spp:
            result.update(spp=spp, sumber_spp=src, tier_spp=1, spp_confidence="tinggi")
            return result
        time.sleep(1)

    # ── Tier 2: DuckDuckGo ───────────────────────────────
    spp, src = search_ddg_spp(nama, kota)
    if spp:
        result.update(spp=spp, sumber_spp=src, tier_spp=2, spp_confidence="menengah")
        return result

    # ── Tier 3: Perlu verifikasi manual ──────────────────
    return result


# ─── Export Excel ─────────────────────────────────────────────────────────────

def export_excel():
    df = pd.read_csv(OUTPUT_CSV, dtype=str).fillna("")
    df["spp_num"] = pd.to_numeric(df["spp"], errors="coerce")
    df["last_verified"] = str(date.today())

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Semua Sekolah", index=False)

        for nama_segmen, (low, high) in SPP_SEGMENTS.items():
            subset = df[(df["spp_num"] >= low) & (df["spp_num"] < high)]
            if not subset.empty:
                subset.to_excel(writer, sheet_name=nama_segmen[:31], index=False)

        for tier, label in [(1, "Tier1-Website"), (2, "Tier2-Search")]:
            subset = df[df["tier_spp"] == str(tier)]
            if not subset.empty:
                subset.to_excel(writer, sheet_name=label, index=False)

        manual = df[df["sumber_spp"] == "perlu_verifikasi_manual"]
        if not manual.empty:
            manual.to_excel(writer, sheet_name="Perlu Verifikasi", index=False)

    print(f"Excel disimpan: {OUTPUT_XLSX}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def run():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(OUTPUT_ENRICHED):
        print(f"ERROR: {OUTPUT_ENRICHED} tidak ditemukan. Jalankan fase2 dulu.")
        return

    df = pd.read_csv(OUTPUT_ENRICHED, dtype=str).fillna("")

    done_npsn = _load_done_npsn()
    is_new    = len(done_npsn) == 0
    remaining = df[~df["npsn"].isin(done_npsn)]

    if done_npsn:
        print(f"Resume: {len(done_npsn)} sudah diproses, {len(remaining)} tersisa")
    if remaining.empty:
        print("Semua sekolah sudah diproses.")
        export_excel()
        return

    total = len(remaining)
    print("=== FASE 3: Scraping SPP (tiered fallback) ===")
    print(f"Total sekolah : {total}")
    print(f"Tier 1        : Website langsung + Playwright fallback")
    print(f"Tier 2        : DuckDuckGo Search")
    print(f"Tier 3        : Perlu verifikasi manual")
    print(f"Resume-safe   : setiap baris langsung disimpan\n")

    stats = {1: 0, 2: 0, 3: 0}

    for i, (_, row) in enumerate(remaining.iterrows()):
        result = process_school(row.to_dict())
        result["segmen"] = label_segmen(result.get("spp"))
        _append_row(result, write_header=(is_new and i == 0))

        tier = result["tier_spp"]
        stats[tier] = stats.get(tier, 0) + 1
        found_total = stats[1] + stats[2]

        pct = found_total / (i + 1) * 100
        tier_icon = {1: "WEB", 2: "DDG", 3: "---"}.get(tier, "?")
        print(
            f"  [{i+1:>4}/{total}] {row.get('nama_sekolah','')[:38]:<38}"
            f" [{tier_icon}]"
            f" SPP:{str(result.get('spp') or '--'):>10}"
            f" hit:{pct:.0f}%",
            end="\r",
        )

    _run(close_browser())

    print(f"\n\n=== RINGKASAN ===")
    final = pd.read_csv(OUTPUT_CSV, dtype=str)
    spp_found = final["spp"].replace("", pd.NA).notna().sum()
    print(f"Total         : {len(final)} sekolah")
    print(f"SPP ditemukan : {spp_found} ({spp_found/len(final)*100:.1f}%)")
    print(f"  Tier 1 (web): {stats[1]}")
    print(f"  Tier 2 (ddg): {stats[2]}")
    print(f"  Tier 3 (man): {stats[3]}")
    print()
    final["segmen"] = final["spp"].apply(label_segmen)
    print(final["segmen"].value_counts().to_string())

    export_excel()
    print(f"\nCSV : {OUTPUT_CSV}")


if __name__ == "__main__":
    run()
