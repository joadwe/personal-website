/* ============================================================
   extra.js — Scroll Reveal Animations & Typing Effect
   Compatible with MkDocs Material instant navigation.
   ============================================================ */

function jwInitExtra() {
  /* ----------------------------------------------------------
     1. SCROLL REVEAL (IntersectionObserver)
     ---------------------------------------------------------- */
  const revealEls = document.querySelectorAll(".jw-reveal:not(.jw-reveal--visible)");
  if (revealEls.length > 0) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("jw-reveal--visible");
            observer.unobserve(entry.target); // animate once
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => observer.observe(el));
  }

  /* ----------------------------------------------------------
     2. ANIMATED COUNTERS
     ---------------------------------------------------------- */
  const counters = document.querySelectorAll("[data-jw-count]:not([data-jw-counted])");
  if (counters.length > 0) {
    const counterObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            counterObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.5 }
    );
    counters.forEach((el) => counterObserver.observe(el));
  }

  function animateCounter(el) {
    el.setAttribute("data-jw-counted", "true");
    const target = parseInt(el.getAttribute("data-jw-count"), 10);
    const suffix = el.getAttribute("data-jw-suffix") || "";
    const duration = 1500;
    const startTime = performance.now();

    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * target);
      el.textContent = current.toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
  }

  /* ----------------------------------------------------------
     3. TYPING EFFECT
     ---------------------------------------------------------- */
  const typeEl = document.querySelector("[data-jw-typing]");
  if (typeEl && !typeEl.hasAttribute("data-jw-typing-active")) {
    typeEl.setAttribute("data-jw-typing-active", "true");
    const phrases = JSON.parse(typeEl.getAttribute("data-jw-typing"));
    let phraseIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    const typeSpeed = 60;
    const deleteSpeed = 35;
    const pauseEnd = 2000;
    const pauseStart = 500;

    function type() {
      // Stop if element is no longer in the DOM (navigated away)
      if (!document.body.contains(typeEl)) return;

      const current = phrases[phraseIndex];
      if (isDeleting) {
        typeEl.textContent = current.substring(0, charIndex - 1);
        charIndex--;
      } else {
        typeEl.textContent = current.substring(0, charIndex + 1);
        charIndex++;
      }

      let delay = isDeleting ? deleteSpeed : typeSpeed;

      if (!isDeleting && charIndex === current.length) {
        delay = pauseEnd;
        isDeleting = true;
      } else if (isDeleting && charIndex === 0) {
        isDeleting = false;
        phraseIndex = (phraseIndex + 1) % phrases.length;
        delay = pauseStart;
      }

      setTimeout(type, delay);
    }

    // Start after hero animation completes
    setTimeout(type, 1200);
  }

  /* ----------------------------------------------------------
     4. DYNAMIC TALK SECTION COUNTS
     ---------------------------------------------------------- */
  document.querySelectorAll(".jw-talk-count").forEach(function (badge) {
    var heading = badge.closest("h3");
    if (!heading) return;

    // Walk forward from the heading to find the next <ol>
    var sibling = heading.nextElementSibling;
    while (sibling && sibling.tagName !== "OL" && sibling.tagName !== "H3" && sibling.tagName !== "H2") {
      sibling = sibling.nextElementSibling;
    }

    if (sibling && sibling.tagName === "OL") {
      badge.textContent = sibling.querySelectorAll("li").length;
    }
  });
}

// Run on initial load
document.addEventListener("DOMContentLoaded", jwInitExtra);

// Re-run on MkDocs Material instant navigation
if (typeof document$ !== "undefined") {
  document$.subscribe(function () { jwInitExtra(); });
} else {
  // Fallback: listen for the location change event used by instant loading
  document.addEventListener("DOMContentSwitch", jwInitExtra);
}
