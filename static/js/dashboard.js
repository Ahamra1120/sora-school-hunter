/* ── Config ── */
const COLORS = {
  "Budget":          "#3b82f6",
  "Menengah":        "#22c55e",
  "Premium":         "#eab308",
  "Ultra Premium":   "#ef4444",
  "Tidak Diketahui": "#9ca3af",
};

const JAKARTA_CENTER = [-6.2088, 106.8456];
const JAKARTA_ZOOM   = 11;

/* ── State ── */
let map, clusterLayer;
let allSchools  = [];
let allMarkers  = [];
let sppChart    = null;

/* ── Init ── */
document.addEventListener("DOMContentLoaded", async () => {
  initMap();
  await loadStats();
  await loadSchools();
  setupFilters();
});

/* ── Map init ── */
function initMap() {
  map = L.map("map", { zoomControl: true }).setView(JAKARTA_CENTER, JAKARTA_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);
}

/* ── Load stats & populate kecamatan dropdown + donut chart ── */
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    if (data.error) return;

    document.getElementById("statTotal").textContent =
      `${data.total.toLocaleString("id-ID")} sekolah`;
    document.getElementById("statSpp").textContent =
      `SPP: ${data.spp_pct}%`;

    // Kecamatan dropdown
    const sel = document.getElementById("filterKecamatan");
    (data.kecamatan_list || []).forEach(k => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      sel.appendChild(opt);
    });

    // Donut chart
    buildChart(data.per_segmen);
  } catch (e) {
    console.error("Stats error:", e);
  }
}

/* ── Load schools & render markers ── */
async function loadSchools() {
  showOverlay("Memuat data sekolah...");
  try {
    const res = await fetch("/api/schools");
    const data = await res.json();

    if (data.error) {
      showOverlay(data.error);
      return;
    }

    allSchools = data.schools;
    renderMarkers(allSchools);
    hideOverlay();

    const noCoord = allSchools.filter(s => !s.lat || !s.lng).length;
    document.getElementById("noCoordCount").textContent =
      `${noCoord.toLocaleString("id-ID")} sekolah tidak memiliki koordinat (tidak tampil di peta)`;
  } catch (e) {
    showOverlay("Gagal memuat data. Pastikan server berjalan dan CSV tersedia.");
    console.error(e);
  }
}

/* ── Render markers ── */
function renderMarkers(schools) {
  // Hapus layer lama
  allMarkers.forEach(m => map.removeLayer(m));
  allMarkers = [];

  let visible = 0;
  schools.forEach(school => {
    if (!school.lat || !school.lng) return;
    const marker = makeMarker(school);
    marker.addTo(map);
    allMarkers.push(marker);
    visible++;
  });

  document.getElementById("statFiltered").textContent =
    `Ditampilkan: ${visible.toLocaleString("id-ID")}`;
}

/* ── Build one circle marker ── */
function makeMarker(s) {
  const color = COLORS[s.segmen] || COLORS["Tidak Diketahui"];
  const marker = L.circleMarker([s.lat, s.lng], {
    radius:      6,
    fillColor:   color,
    color:       "#0f172a",
    weight:      1.5,
    opacity:     1,
    fillOpacity: 0.85,
  });

  marker.bindPopup(buildPopup(s), { maxWidth: 300 });
  return marker;
}

/* ── Build popup HTML ── */
function buildPopup(s) {
  const badgeClass = `badge-${s.jenjang}`;
  const sppText    = s.spp ? `Rp ${Number(s.spp).toLocaleString("id-ID")}/bln` : "Tidak diketahui";
  const segmenSlug = s.segmen.replace(/\s+/g, "-");
  const sppClass   = s.spp ? `spp-chip spp-${segmenSlug}` : "";

  const websiteRow = s.website
    ? `<a class="popup-link" href="${s.website}" target="_blank" rel="noopener">🌐 Kunjungi Website</a>`
    : "";

  const teleponRow = s.telepon
    ? `<div class="popup-row"><span class="popup-icon">📞</span><span>${s.telepon}</span></div>`
    : "";

  const ratingRow = s.rating
    ? `<div class="popup-row"><span class="popup-icon">⭐</span><span>${s.rating} / 5</span></div>`
    : "";

  return `
    <div class="popup-header">
      <div class="popup-nama">${escHtml(s.nama)}</div>
      <span class="popup-badge ${badgeClass}">${s.jenjang}</span>
      ${s.akreditasi ? `<span class="popup-badge" style="background:#1e293b;color:#94a3b8">Akreditasi ${escHtml(s.akreditasi)}</span>` : ""}
    </div>
    <div class="popup-body">
      <div class="popup-row">
        <span class="popup-icon">📍</span>
        <span>${escHtml(s.kecamatan)}${s.kecamatan && s.kota ? ", " : ""}${escHtml(s.kota)}</span>
      </div>
      ${teleponRow}
      ${ratingRow}
      <div class="popup-row">
        <span class="popup-icon">💰</span>
        <span>
          <span class="popup-label">SPP:</span>
          ${s.spp
            ? `<span class="${sppClass}">${sppText}</span> <span style="color:#94a3b8;font-size:11px">(${escHtml(s.segmen)})</span>`
            : `<span style="color:#6b7280">${sppText}</span>`
          }
        </span>
      </div>
      ${websiteRow}
    </div>`;
}

/* ── Filters ── */
function setupFilters() {
  document.getElementById("searchInput")
    .addEventListener("input", applyFilters);

  document.querySelectorAll(".filter-jenjang, .filter-segmen")
    .forEach(el => el.addEventListener("change", applyFilters));

  document.getElementById("filterKecamatan")
    .addEventListener("change", applyFilters);

  document.getElementById("btnReset")
    .addEventListener("click", resetFilters);
}

function applyFilters() {
  const query    = document.getElementById("searchInput").value.toLowerCase().trim();
  const jenjangs = [...document.querySelectorAll(".filter-jenjang:checked")].map(el => el.value);
  const segmens  = [...document.querySelectorAll(".filter-segmen:checked")].map(el => el.value);
  const kec      = document.getElementById("filterKecamatan").value;

  const filtered = allSchools.filter(s => {
    if (query && !s.nama.toLowerCase().includes(query)) return false;
    if (!jenjangs.includes(s.jenjang)) return false;
    const seg = s.segmen || "Tidak Diketahui";
    if (!segmens.includes(seg)) return false;
    if (kec && s.kecamatan !== kec) return false;
    return true;
  });

  renderMarkers(filtered);
}

function resetFilters() {
  document.getElementById("searchInput").value = "";
  document.querySelectorAll(".filter-jenjang, .filter-segmen")
    .forEach(el => { el.checked = true; });
  document.getElementById("filterKecamatan").value = "";
  renderMarkers(allSchools);
}

/* ── Donut Chart ── */
function buildChart(perSegmen) {
  const ctx = document.getElementById("sppChart").getContext("2d");

  const labels = Object.keys(perSegmen);
  const values = labels.map(l => perSegmen[l]);
  const colors = labels.map(l => COLORS[l] || COLORS["Tidak Diketahui"]);

  if (sppChart) sppChart.destroy();
  sppChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 1, borderColor: "#1e293b" }],
    },
    options: {
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#94a3b8", font: { size: 11 }, boxWidth: 10, padding: 8 },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString("id-ID")} sekolah`,
          },
        },
      },
      cutout: "65%",
    },
  });
}

/* ── Overlay helpers ── */
function showOverlay(msg) {
  document.getElementById("overlayMsg").textContent = msg;
  document.getElementById("mapOverlay").classList.remove("hidden");
}
function hideOverlay() {
  document.getElementById("mapOverlay").classList.add("hidden");
}

/* ── HTML escape ── */
function escHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
