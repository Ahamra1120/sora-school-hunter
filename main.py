"""
Entry point: jalankan semua fase scraping secara berurutan.

Penggunaan:
  python main.py           # semua fase (default: koordinat dari kemendikdasmen)
  python main.py --google  # fase 2 pakai Google Places API (butuh API key)
  python main.py --fase 1  # hanya fase 1 (daftar sekolah dari kemendikdasmen)
  python main.py --fase 2  # hanya fase 2 (koordinat dari kemendikdasmen, GRATIS)
  python main.py --fase 3  # hanya fase 3 (scrape SPP dari website sekolah)
"""
import argparse


def main():
    parser = argparse.ArgumentParser(description="Scraper sekolah swasta Jakarta + SPP")
    parser.add_argument(
        "--fase", type=int, choices=[1, 2, 3], default=0,
        help="Jalankan fase tertentu saja (default: semua)"
    )
    parser.add_argument(
        "--google", action="store_true",
        help="Fase 2: gunakan Google Places API (dapat website & koordinat, butuh API key)"
    )
    args = parser.parse_args()

    if args.fase in (0, 1):
        print("\n" + "="*55)
        print("FASE 1: Scraping daftar sekolah dari kemendikdasmen")
        print("="*55)
        import fase1_dapodik
        fase1_dapodik.run()

    if args.fase in (0, 2):
        if args.google:
            print("\n" + "="*55)
            print("FASE 2: Enrichment via Google Places API (butuh API key)")
            print("="*55)
            import fase2_enrich
            fase2_enrich.run()
        else:
            print("\n" + "="*55)
            print("FASE 2: Koordinat dari kemendikdasmen.go.id (GRATIS)")
            print("="*55)
            import fase2_geocode_free
            fase2_geocode_free.run()

    if args.fase in (0, 3):
        print("\n" + "="*55)
        print("FASE 3: Scraping SPP dari website sekolah")
        print("="*55)
        import fase3_scrape_spp
        fase3_scrape_spp.run()

    print("\nSelesai! Cek folder data/ untuk hasil.")


if __name__ == "__main__":
    main()
