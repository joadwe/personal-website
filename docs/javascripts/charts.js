/* ============================================================
   charts.js — Publication Timeline Chart (Chart.js)
   Compatible with MkDocs Material instant navigation.
   ============================================================ */

var jwPubChart = null; // Store chart instance for cleanup

function jwInitCharts() {
  const canvas = document.getElementById("jw-pub-chart");
  if (!canvas) return;

  // Destroy previous chart instance if it exists
  if (jwPubChart) {
    jwPubChart.destroy();
    jwPubChart = null;
  }

  // Parse data from the element's data attribute, or fall back to defaults
  let labels, data;
  try {
    const raw = JSON.parse(canvas.getAttribute("data-jw-chart"));
    labels = raw.labels;
    data = raw.values;
  } catch (e) {
    labels = ["2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"];
    data = [1, 4, 6, 5, 8, 6, 5, 4, 3, 2];
  }

  // Detect dark mode
  const isDark =
    document.body.getAttribute("data-md-color-scheme") === "slate" ||
    document.querySelector("[data-md-color-scheme='slate']") !== null;

  const gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";
  const textColor = isDark ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.6)";

  // Gradient fill
  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, "rgba(0, 121, 107, 0.6)");
  gradient.addColorStop(1, "rgba(92, 107, 192, 0.1)");

  jwPubChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Publications",
          data: data,
          backgroundColor: gradient,
          borderColor: "rgba(0, 121, 107, 0.9)",
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false,
          hoverBackgroundColor: "rgba(0, 121, 107, 0.8)",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: {
        duration: 1200,
        easing: "easeOutQuart",
      },
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: isDark ? "#37474f" : "#fff",
          titleColor: isDark ? "#fff" : "#333",
          bodyColor: isDark ? "#ccc" : "#666",
          borderColor: "rgba(0,121,107,0.3)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: function (context) {
              const val = context.parsed.y;
              return val + (val === 1 ? " publication" : " publications");
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: textColor, font: { size: 12 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { size: 12 },
            stepSize: 2,
          },
        },
      },
    },
  });
}

// Run on initial load
document.addEventListener("DOMContentLoaded", jwInitCharts);

// Re-run on MkDocs Material instant navigation
if (typeof document$ !== "undefined") {
  document$.subscribe(function () { jwInitCharts(); });
} else {
  document.addEventListener("DOMContentSwitch", jwInitCharts);
}
