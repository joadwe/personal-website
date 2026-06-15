/* ============================================================
   scholar-dashboard.js — Light Scholar metrics enhancements
   Compatible with MkDocs Material instant navigation.
   ============================================================ */

function jwInitScholarDashboard() {
  var root = document.getElementById("jw-scholar-dashboard");
  if (!root) return;

  linkPublicationItems();

  var dataSrc = root.getAttribute("data-jw-scholar-src") || "../data/scholar-dashboard.json";
  root.innerHTML = '<div class="jw-scholar-loading">Loading Scholar metrics...</div>';

  fetch(dataSrc, { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("Could not load Scholar data");
      return response.json();
    })
    .then(function (data) {
      window.jwScholarPublicationLookup = buildPublicationLookup(data.publications || []);
      renderScholarSummary(root, data);
      enhancePublicationItems(data.publications || []);
      if (typeof jwSetCitationChartData === "function") {
        jwSetCitationChartData(data.citation_history || [], data.publications || []);
      }
    })
    .catch(function (error) {
      root.innerHTML = '<div class="jw-scholar-error">Scholar metrics are unavailable right now.</div>';
      if (window.console) console.warn(error);
    });
}

function renderScholarSummary(root, data) {
  var profile = data.profile || {};
  var listedItems = document.querySelectorAll(".jw-pub-item").length;

  var metrics = [
    { label: "Total citations", value: profile.total_citations },
    { label: "h-index", value: profile.h_index },
    { label: "i10-index", value: profile.i10_index },
    { label: "Documents", value: listedItems },
  ];

  root.innerHTML = [
    '<div class="jw-scholar-metrics">',
    metrics.map(function (metric) {
      return [
        '<div class="jw-scholar-metric">',
        '  <div class="jw-scholar-metric__label">' + escapeHtml(metric.label) + '</div>',
        '  <div class="jw-scholar-metric__value">' + formatNumber(metric.value) + '</div>',
        '</div>',
      ].join("");
    }).join(""),
    '</div>',
  ].join("");
}

function enhancePublicationItems(publications) {
  var citationLookup = window.jwScholarPublicationLookup || buildPublicationLookup(publications);

  document.querySelectorAll(".jw-pub-item").forEach(function (item) {
    var existingBadges = item.querySelector(".jw-pub-badges");
    if (existingBadges) existingBadges.remove();

    var type = item.getAttribute("data-jw-type") || "publication";
    var title = extractPublicationTitle(item);
    var doi = extractDoi(item.textContent);
    var matchedPublication = doi ? citationLookup[normalizeDoi(doi)] : null;
    if (!matchedPublication && title) {
      matchedPublication = citationLookup[normalizeTitle(title)] || findTitleMatch(title, publications);
    }
    var citations = matchedPublication ? matchedPublication.total_citations : null;
    if (matchedPublication) {
      item.setAttribute("data-jw-scholar-key", getPublicationLookupKey(matchedPublication));
    }

    var target = item.querySelector("li") || item.querySelector("p") || item;
    linkPublicationText(target);

    var badges = document.createElement("span");
    badges.className = "jw-pub-badges";
    badges.appendChild(makeBadge(formatType(type), "type", type));

    if (citations > 0) {
      badges.appendChild(makeBadge(formatNumber(citations) + " citations", "citations"));
    }

    target.appendChild(document.createTextNode(" "));
    target.appendChild(badges);
  });
}

function linkPublicationItems() {
  document.querySelectorAll(".jw-pub-item").forEach(function (item) {
    var target = item.querySelector("li") || item.querySelector("p") || item;
    linkPublicationText(target);
  });
}

function linkPublicationText(target) {
  if (target.querySelector(".jw-pub-item__link")) return;

  var websiteLink = Array.prototype.slice.call(target.querySelectorAll("a[href]")).find(function (link) {
    return link.textContent.trim().toLowerCase() === "website";
  });
  if (!websiteLink) return;

  var previousNode = websiteLink.previousSibling;
  if (previousNode && previousNode.nodeType === Node.TEXT_NODE) {
    previousNode.textContent = previousNode.textContent.replace(/(?:,\s*)?\[\s*$/, "");
  }
  var nextNode = websiteLink.nextSibling;
  if (nextNode && nextNode.nodeType === Node.TEXT_NODE) {
    nextNode.textContent = nextNode.textContent.replace(/^\s*\]/, "");
  }

  var link = document.createElement("a");
  link.className = "jw-pub-item__link";
  link.href = websiteLink.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  websiteLink.remove();

  while (target.firstChild) {
    link.appendChild(target.firstChild);
  }
  target.appendChild(link);
}

function buildPublicationLookup(publications) {
  return publications.reduce(function (lookup, publication) {
    if (publication.title) {
      lookup[normalizeTitle(publication.title)] = publication;
    }
    if (publication.doi) {
      lookup[normalizeDoi(publication.doi)] = publication;
    }
    return lookup;
  }, {});
}

function getPublicationLookupKey(publication) {
  if (publication.doi) return normalizeDoi(publication.doi);
  return normalizeTitle(publication.title);
}

function findTitleMatch(title, publications) {
  var normalizedTitle = normalizeTitle(title);
  if (!normalizedTitle) return null;
  return publications.find(function (publication) {
    var candidate = normalizeTitle(publication.title);
    return candidate && (
      candidate.indexOf(normalizedTitle) !== -1 ||
      normalizedTitle.indexOf(candidate) !== -1
    );
  }) || null;
}

function extractPublicationTitle(item) {
  var titleEl = item.querySelector("strong");
  return titleEl ? titleEl.textContent.trim() : "";
}

function makeBadge(label, kind, type) {
  var badge = document.createElement("span");
  badge.className = "jw-pub-badge jw-pub-badge--" + kind;
  if (type) badge.className += " jw-pub-badge--" + type;
  badge.textContent = label;
  return badge;
}

function formatNumber(value) {
  if (value == null || value === "") return "-";
  return Number(value).toLocaleString();
}

function formatType(type) {
  if (type === "publication" || type === "manuscript") return "Paper";
  return String(type || "Publication").replace(/\b\w/g, function (char) { return char.toUpperCase(); });
}

function normalizeTitle(title) {
  return String(title || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function extractDoi(text) {
  var match = String(text || "").match(/10\.\d{4,9}\/[^\s\]\)"'>]+/i);
  return match ? match[0] : "";
}

function normalizeDoi(doi) {
  return String(doi || "")
    .toLowerCase()
    .replace(/[.,;]+$/g, "")
    .replace(/\.abstract$/g, "");
}

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", jwInitScholarDashboard);

if (typeof document$ !== "undefined") {
  document$.subscribe(function () { jwInitScholarDashboard(); });
} else {
  document.addEventListener("DOMContentSwitch", jwInitScholarDashboard);
}
