"""
Dashboard Flask: Peta Interaktif Sekolah Swasta Jakarta + SPP
Jalankan: python dashboard.py
Akses:    http://localhost:5000
"""
import os
import math
import pandas as pd
from flask import Flask, jsonify, render_template, request
from config import OUTPUT_CSV, OUTPUT_RAW, SPP_SEGMENTS

app = Flask(__name__)

_cache: dict = {}


def load_data() -> pd.DataFrame:
    """Load data sekolah dari CSV. Prioritas: final CSV → raw CSV."""
    if "df" in _cache:
        return _cache["df"]

    if os.path.exists(OUTPUT_CSV):
        df = pd.read_csv(OUTPUT_CSV, dtype=str).fillna("")
    elif os.path.exists(OUTPUT_RAW):
        df = pd.read_csv(OUTPUT_RAW, dtype=str).fillna("")
        # Tambah kolom yang belum ada
        for col in ["website", "telepon", "rating_google", "spp", "segmen", "lat", "lng", "akreditasi"]:
            if col not in df.columns:
                df[col] = ""
    else:
        return pd.DataFrame()

    _cache["df"] = df
    return df


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/schools")
def api_schools():
    df = load_data()
    if df.empty:
        return jsonify({"error": "Data belum tersedia. Jalankan scraper dulu.", "schools": []})

    # Filter opsional dari query params
    jenjang_filter = request.args.getlist("jenjang")   # ?jenjang=SD&jenjang=SMP
    segmen_filter = request.args.getlist("segmen")
    kecamatan_filter = request.args.get("kecamatan", "").strip()

    filtered = df.copy()
    if jenjang_filter:
        filtered = filtered[filtered["jenjang"].isin(jenjang_filter)]
    if segmen_filter:
        filtered = filtered[filtered["segmen"].isin(segmen_filter)]
    if kecamatan_filter:
        filtered = filtered[filtered["kecamatan"].str.contains(kecamatan_filter, case=False, na=False)]

    schools = []
    for _, row in filtered.iterrows():
        lat = _safe_float(row.get("lat", ""))
        lng = _safe_float(row.get("lng", ""))
        spp = _safe_float(row.get("spp", ""))

        schools.append({
            "npsn":         row.get("npsn", ""),
            "nama":         row.get("nama_sekolah", ""),
            "jenjang":      row.get("jenjang", ""),
            "alamat":       row.get("alamat", ""),
            "kecamatan":    row.get("kecamatan", ""),
            "kota":         row.get("kota", ""),
            "akreditasi":   row.get("akreditasi", ""),
            "website":      row.get("website", ""),
            "telepon":      row.get("telepon", ""),
            "rating":       row.get("rating_google", ""),
            "spp":          spp,
            "segmen":       row.get("segmen", "Tidak Diketahui") or "Tidak Diketahui",
            "lat":          lat,
            "lng":          lng,
        })

    return jsonify({"total": len(schools), "schools": schools})


@app.route("/api/stats")
def api_stats():
    df = load_data()
    if df.empty:
        return jsonify({"error": "Data belum tersedia."})

    total = len(df)
    spp_filled = int((df["spp"].replace("", pd.NA).notna()).sum()) if "spp" in df.columns else 0

    # Distribusi per segmen
    if "segmen" in df.columns:
        per_segmen = df["segmen"].replace("", "Tidak Diketahui").fillna("Tidak Diketahui").value_counts().to_dict()
    else:
        per_segmen = {}

    # Distribusi per jenjang
    per_jenjang = df["jenjang"].value_counts().to_dict() if "jenjang" in df.columns else {}

    # Daftar kecamatan unik untuk dropdown
    kecamatan_list = sorted(df["kecamatan"].dropna().unique().tolist()) if "kecamatan" in df.columns else []
    kecamatan_list = [k for k in kecamatan_list if k]

    return jsonify({
        "total":          total,
        "spp_filled":     spp_filled,
        "spp_pct":        round(spp_filled / total * 100, 1) if total else 0,
        "per_segmen":     per_segmen,
        "per_jenjang":    per_jenjang,
        "kecamatan_list": kecamatan_list,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
