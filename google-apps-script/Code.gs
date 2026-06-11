/**
 * Backend Google Sheets untuk Peta Sebaran Sekolah (SORA marketing).
 * Menyimpan status & catatan kunjungan agar bisa dipakai bersama satu tim.
 *
 * Cara pakai: lihat SETUP_GOOGLE_SHEETS.md di folder project.
 * Deploy sebagai Web App  ->  Execute as: Me  ->  Who has access: Anyone.
 */

var SHEET_NAME = 'Kunjungan';
var HEADERS = ['npsn', 'nama_sekolah', 'jenjang', 'kecamatan', 'kota', 'status', 'note', 'updated'];

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
  }
  return sh;
}

/** Baca semua kunjungan. Dipanggil saat peta dimuat / sinkron. */
function doGet(e) {
  var sh = getSheet_();
  var values = sh.getDataRange().getValues();
  values.shift(); // buang header
  var out = {};
  values.forEach(function (r) {
    var npsn = String(r[0]).trim();
    if (!npsn) return;
    out[npsn] = {
      status: r[5] || 'none',
      note: r[6] || '',
      updated: r[7] ? new Date(r[7]).getTime() : null
    };
  });
  return json_({ ok: true, visits: out });
}

/** Simpan/perbarui satu atau banyak record kunjungan. */
function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(25000);
  } catch (err) {
    return json_({ ok: false, error: 'sibuk, coba lagi' });
  }
  try {
    var body = JSON.parse(e.postData.contents);
    var records = body.records || (body.npsn ? [body] : []);
    var sh = getSheet_();
    var data = sh.getDataRange().getValues();

    // peta npsn -> nomor baris
    var rowByNpsn = {};
    for (var i = 1; i < data.length; i++) rowByNpsn[String(data[i][0]).trim()] = i + 1;

    records.forEach(function (rec) {
      var npsn = String(rec.npsn || '').trim();
      if (!npsn) return;
      var row = [
        npsn,
        rec.nama_sekolah || '',
        rec.jenjang || '',
        rec.kecamatan || '',
        rec.kota || '',
        rec.status || 'none',
        rec.note || '',
        rec.updated ? new Date(rec.updated) : new Date()
      ];
      if (rowByNpsn[npsn]) {
        sh.getRange(rowByNpsn[npsn], 1, 1, row.length).setValues([row]);
      } else {
        sh.appendRow(row);
        rowByNpsn[npsn] = sh.getLastRow();
      }
    });

    return json_({ ok: true, count: records.length });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
