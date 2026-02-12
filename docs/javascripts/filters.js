/* ============================================================
   filters.js — Publication Search & Filter
   Compatible with MkDocs Material instant navigation.
   ============================================================ */

function jwInitFilters() {
  const searchInput = document.getElementById("jw-pub-search");
  const filterBtns = document.querySelectorAll(".jw-filter-btn[data-jw-filter]");
  const countEl = document.getElementById("jw-filter-count");
  const pubItems = document.querySelectorAll(".jw-pub-item");

  if (!searchInput || pubItems.length === 0) return;

  let activeFilter = "all";

  // Remove old listeners by cloning the search input
  const newSearchInput = searchInput.cloneNode(true);
  searchInput.parentNode.replaceChild(newSearchInput, searchInput);
  newSearchInput.addEventListener("input", applyFilters);

  // Clone filter buttons to remove stale listeners
  filterBtns.forEach((btn) => {
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    newBtn.addEventListener("click", function () {
      document.querySelectorAll(".jw-filter-btn[data-jw-filter]").forEach((b) =>
        b.classList.remove("jw-filter-btn--active")
      );
      this.classList.add("jw-filter-btn--active");
      activeFilter = this.getAttribute("data-jw-filter");
      applyFilters();
    });
  });

  function applyFilters() {
    const currentSearch = document.getElementById("jw-pub-search");
    const query = currentSearch ? currentSearch.value.toLowerCase().trim() : "";
    let visible = 0;

    pubItems.forEach((item) => {
      const text = item.textContent.toLowerCase();
      const type = item.getAttribute("data-jw-type") || "publication";
      const year = item.getAttribute("data-jw-year") || "";

      const matchesSearch = !query || text.includes(query);
      const matchesFilter =
        activeFilter === "all" ||
        type === activeFilter ||
        year === activeFilter;

      if (matchesSearch && matchesFilter) {
        item.classList.remove("jw-pub-item--hidden");
        visible++;
      } else {
        item.classList.add("jw-pub-item--hidden");
      }
    });

    const currentCount = document.getElementById("jw-filter-count");
    if (currentCount) {
      currentCount.textContent =
        visible + " of " + pubItems.length + " shown";
    }

    updateYearHeadings();
  }

  /**
   * Hide year headings (h2) when all items in that year are filtered out.
   */
  function updateYearHeadings() {
    const content = document.querySelector(".md-content__inner");
    if (!content) return;

    const headings = content.querySelectorAll("h2");
    headings.forEach(function (h2) {
      var sibling = h2.nextElementSibling;
      var items = [];

      while (sibling && sibling.tagName !== "H2") {
        if (sibling.classList && sibling.classList.contains("jw-pub-item")) {
          items.push(sibling);
        }
        var nested = sibling.querySelectorAll
          ? sibling.querySelectorAll(".jw-pub-item")
          : [];
        nested.forEach(function (n) { items.push(n); });
        sibling = sibling.nextElementSibling;
      }

      if (items.length === 0) return;

      var allHidden = items.every(function (item) {
        return item.classList.contains("jw-pub-item--hidden");
      });

      h2.style.display = allHidden ? "none" : "";
    });
  }

  // Initialize count
  const initCount = document.getElementById("jw-filter-count");
  if (initCount) {
    initCount.textContent = pubItems.length + " of " + pubItems.length + " shown";
  }
}

// Run on initial load
document.addEventListener("DOMContentLoaded", jwInitFilters);

// Re-run on MkDocs Material instant navigation
if (typeof document$ !== "undefined") {
  document$.subscribe(function () { jwInitFilters(); });
} else {
  document.addEventListener("DOMContentSwitch", jwInitFilters);
}
