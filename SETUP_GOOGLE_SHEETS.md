# Setup Sinkronisasi Google Sheets

Dengan ini, status & catatan kunjungan tersimpan di **satu Google Sheet bersama**, sehingga
seluruh tim melihat data yang sama (bukan lagi tersimpan terpisah di tiap browser).

Cukup dilakukan **sekali** oleh satu orang (admin). Setelah dapat URL, anggota lain tinggal
menempelkan URL itu di peta.

---

## Langkah 1 — Buat Google Sheet

1. Buka <https://sheets.google.com> → buat spreadsheet baru.
2. Beri nama, misalnya **"Kunjungan Sekolah SORA"**.
   (Tab/worksheet bernama `Kunjungan` akan dibuat otomatis oleh skrip — tidak perlu dibuat manual.)

## Langkah 2 — Tempel skrip

1. Di spreadsheet itu: menu **Extensions → Apps Script**.
2. Hapus semua kode contoh (`function myFunction() {}`).
3. Buka file [google-apps-script/Code.gs](google-apps-script/Code.gs) di project ini,
   salin **seluruh isinya**, lalu tempel ke editor Apps Script.
4. Klik ikon **Save** (💾).

## Langkah 3 — Deploy sebagai Web App

1. Klik tombol biru **Deploy → New deployment**.
2. Di sebelah "Select type", klik ikon gerigi ⚙️ → pilih **Web app**.
3. Isi:
   - **Description**: bebas (mis. "API kunjungan v1")
   - **Execute as**: **Me** (email Anda)
   - **Who has access**: **Anyone**  ← penting, agar peta bisa baca/tulis tanpa login
4. Klik **Deploy**.
5. Akan muncul permintaan izin → **Authorize access** → pilih akun Anda →
   pada layar "Google hasn't verified this app" klik **Advanced → Go to … (unsafe)** → **Allow**.
   (Aman: ini skrip milik Anda sendiri.)
6. Salin **Web app URL** yang muncul. Bentuknya:
   `https://script.google.com/macros/s/AKfyc..../exec`

## Langkah 4 — Hubungkan dari peta

1. Buka `schools_map.html` (lokal maupun yang sudah di-deploy).
2. Di sidebar, bagian **Sinkronisasi (Google Sheets)** → tempel URL tadi → klik **Hubungkan**.
3. Selesai. Status berubah jadi **● Terhubung**. Mulai sekarang setiap perubahan status/catatan
   otomatis tersimpan ke Google Sheet, dan tombol **🔄 Sinkron** menarik data terbaru dari tim.

> **Bagikan URL ini ke anggota tim.** Mereka cukup menempelkannya sekali di peta masing-masing.

---

## Pertanyaan umum

**Apakah data lama di browser ikut terbawa?**
Ya. Saat pertama kali Hubungkan / Sinkron, data yang sudah ada di browser Anda akan
diunggah (push) ke Sheet, lalu digabung dengan data tim. Penggabungan memakai waktu
"updated" terbaru — perubahan yang paling baru menang.

**Tetap jalan tanpa internet?**
Ya. Data tetap disimpan di browser (localStorage) sebagai cadangan. Saat offline,
perubahan diantrekan dan otomatis dikirim begitu online + tekan Sinkron.

**Mau ganti/redeploy skrip?**
Gunakan **Deploy → Manage deployments → ✏️ Edit → Version: New version → Deploy**
agar **URL tetap sama**. Kalau membuat "New deployment", URL-nya berubah dan harus
ditempel ulang di peta.

**Siapa yang bisa lihat datanya?**
Siapa pun yang membuka spreadsheet (atur lewat tombol Share di Sheet seperti biasa).
Web app "Anyone" hanya berarti peta boleh memanggil API, bukan berarti Sheet-nya publik.
