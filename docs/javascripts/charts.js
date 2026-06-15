/* ============================================================
   charts.js — Publication Timeline Chart (Chart.js)
   Compatible with MkDocs Material instant navigation.
   ============================================================ */

var jwPubChart = null; // Store chart instance for cleanup
var jwPubChartMode = "publications";
var jwPubChartBase = null;
var jwPubCitationChart = null;
window.jwCurrentPublicationFilter = { activeFilter: "all", query: "" };

function jwInitCharts() {
  const canvas = document.getElementById("jw-pub-chart");
  if (!canvas) return;

  // Destroy previous chart instance if it exists
  if (jwPubChart) {
    jwPubChart.destroy();
    jwPubChart = null;
  }
  jwPubChartMode = "publications";

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

  jwPubChartBase = { labels: labels.slice(), values: data.slice() };

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
          label: "Papers",
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
              if (jwPubChartMode === "citations") {
                return val.toLocaleString() + (val === 1 ? " citation" : " citations");
              }
              return val + (val === 1 ? " paper" : " papers");
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

  initPublicationChartToggle();
}

function initPublicationChartToggle() {
  var buttons = document.querySelectorAll(".jw-chart-mode-btn[data-jw-chart-mode]");
  if (!buttons.length) return;

  buttons.forEach(function (button) {
    button.disabled = button.getAttribute("data-jw-chart-mode") === "citations" && !jwPubCitationChart;
    button.addEventListener("click", function () {
      setPublicationChartMode(button.getAttribute("data-jw-chart-mode"));
    });
  });

  setActiveChartModeButton();
}

function setPublicationChartMode(mode) {
  if (!jwPubChart || !jwPubChartBase) return;
  if (mode === "citations" && !jwPubCitationChart) return;

  jwPubChartMode = mode === "citations" ? "citations" : "publications";
  setActiveChartModeButton();
  jwUpdatePublicationChartForFilter({ animate: true });
}

function setActiveChartModeButton() {
  document.querySelectorAll(".jw-chart-mode-btn[data-jw-chart-mode]").forEach(function (button) {
    var isActive = button.getAttribute("data-jw-chart-mode") === jwPubChartMode;
    button.classList.toggle("jw-chart-mode-btn--active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function jwSetCitationChartData(history, publications) {
  if (!Array.isArray(history) || history.length === 0) return;

  var citationsByYear = {};
  history.forEach(function (item) {
    citationsByYear[String(item.year)] = item.citations || 0;
  });

  var firstAggregateYear = Math.min.apply(null, history.map(function (item) {
    return Number(item.year);
  }));
  (publications || []).forEach(function (publication) {
    (publication.citation_history || []).forEach(function (item) {
      if (Number(item.year) >= firstAggregateYear) return;
      var year = String(item.year);
      citationsByYear[year] = (citationsByYear[year] || 0) + (item.citations || 0);
    });
  });

  var labels = Object.keys(citationsByYear).sort();
  jwPubCitationChart = {
    labels: labels,
    values: labels.map(function (year) { return citationsByYear[year] || 0; }),
  };

  document.querySelectorAll(".jw-chart-mode-btn[data-jw-chart-mode='citations']").forEach(function (button) {
    button.disabled = false;
  });

  if (jwPubChartMode === "citations") {
    jwUpdatePublicationChartForFilter({ animate: true });
  }
}

function jwUpdatePublicationChartForFilter(options) {
  if (!jwPubChart || !jwPubChartBase) return;

  var series = jwPubChartMode === "citations"
    ? buildFilteredCitationSeries()
    : buildFilteredPublicationSeries();

  jwPubChart.data.labels = series.labels;
  jwPubChart.data.datasets[0].label = series.label;
  jwPubChart.data.datasets[0].data = series.values;
  jwPubChart.options.scales.y.ticks.stepSize = jwPubChartMode === "publications" ? 2 : undefined;
  jwPubChart.update(options && options.animate ? undefined : "none");
}

function buildFilteredPublicationSeries() {
  var yearCounts = {};
  getVisiblePublicationItems().forEach(function (item) {
    var year = item.getAttribute("data-jw-year") || "";
    if (year) yearCounts[year] = (yearCounts[year] || 0) + 1;
  });

  return {
    label: "Papers",
    labels: jwPubChartBase.labels.slice(),
    values: jwPubChartBase.labels.map(function (year) { return yearCounts[year] || 0; }),
  };
}

function buildFilteredCitationSeries() {
  var filterState = window.jwCurrentPublicationFilter || { activeFilter: "all", query: "" };
  var hasActiveFilter = filterState.activeFilter !== "all" || Boolean(filterState.query);

  if (!hasActiveFilter && jwPubCitationChart) {
    return {
      label: "Citations",
      labels: jwPubCitationChart.labels.slice(),
      values: jwPubCitationChart.values.slice(),
    };
  }

  var yearCounts = {};
  var scholarLookup = window.jwScholarPublicationLookup || {};
  getVisiblePublicationItems().forEach(function (item) {
    var key = item.getAttribute("data-jw-scholar-key");
    var publication = key ? scholarLookup[key] : null;
    if (!publication || !Array.isArray(publication.citation_history)) return;
    if (publication.citation_history.length === 0) {
      if (publication.year && publication.total_citations > 0) {
        var publicationYear = String(publication.year);
        yearCounts[publicationYear] = (yearCounts[publicationYear] || 0) + publication.total_citations;
      }
      return;
    }
    publication.citation_history.forEach(function (entry) {
      var year = String(entry.year);
      yearCounts[year] = (yearCounts[year] || 0) + (entry.citations || 0);
    });
  });

  var labels = jwPubCitationChart
    ? jwPubCitationChart.labels.slice()
    : Object.keys(yearCounts).sort();
  return {
    label: "Citations",
    labels: labels,
    values: labels.map(function (year) { return yearCounts[year] || 0; }),
  };
}

function getVisiblePublicationItems() {
  return Array.prototype.slice.call(document.querySelectorAll(".jw-pub-item")).filter(function (item) {
    return !item.classList.contains("jw-pub-item--hidden");
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
