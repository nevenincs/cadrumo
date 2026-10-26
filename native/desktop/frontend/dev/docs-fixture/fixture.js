/* The documentation fixture's page script: the pieces of cadrumo-docs.js and
 * Furo that the desktop bridge relies on, reduced to fixed answers. It loads
 * after the real bridge script, as cadrumo-docs.js does.
 *
 * The search mode comes from the entry URL (?search=results|empty|slow|failed)
 * and is kept for the session, so it survives navigation between pages. */
(function () {
  "use strict";

  var MODE_KEY = "docs-fixture-search";
  var requested = new URLSearchParams(window.location.search).get("search");
  try {
    if (requested) window.sessionStorage.setItem(MODE_KEY, requested);
  } catch {
    /* Storage unavailable: the mode holds for this page only. */
  }
  function mode() {
    try {
      return window.sessionStorage.getItem(MODE_KEY) || requested || "results";
    } catch {
      return requested || "results";
    }
  }

  var base = new URL("./", document.baseURI).href;
  var RECORDS = [
    {
      kind: "concept",
      title: "Modelo",
      href: base + "glossary.html#term-modelo",
      excerpt: "A modelo is one official form. This entry is a fixture.",
      crumb: "Term",
    },
    {
      kind: "casilla",
      title: "Casilla 01",
      href: base + "index.html#text",
      excerpt: "Casilla 01 total, the first field of the fixture modelo.",
      crumb: "Casilla · Modelo fixture · 01",
    },
    {
      kind: "cli",
      title: "config sign-in-status",
      href: base + "guide.html",
      excerpt: "Reports whether a sign-in is present. Fixture command entry.",
      crumb: "Command",
    },
    {
      kind: "page",
      title: "Stand-in documentation",
      href: base + "index.html",
      excerpt:
        "This page is a development <mark>fixture</mark>: it stands in for the packaged documentation.",
      excerptIsMarkup: true,
      crumb: "",
    },
    {
      kind: "page",
      title: "Second page",
      href: base + "guide.html",
      excerpt:
        "The second page exists so back, forward and home have somewhere to go.",
      crumb: "",
    },
    {
      kind: "legal",
      title: "A result kind the shell does not name",
      href: base + "guide.html",
      excerpt:
        "An unknown kind still lists, without a kind label. Fixture entry.",
      crumb: "",
    },
  ];

  function matches(record, words) {
    var text = (
      record.title +
      " " +
      record.excerpt +
      " " +
      record.crumb
    ).toLowerCase();
    return words.every(function (word) {
      return text.indexOf(word) !== -1;
    });
  }

  function search(query) {
    var current = mode();
    if (current === "failed") return new Promise(function () {});
    var words = String(query).toLowerCase().split(/\s+/).filter(Boolean);
    var found =
      current === "empty"
        ? []
        : RECORDS.filter(function (record) {
            return matches(record, words);
          });
    return new Promise(function (resolve) {
      window.setTimeout(
        function () {
          resolve(found);
        },
        current === "slow" ? 1500 : 60,
      );
    });
  }

  window.CadrumoDocs = {
    search: search,
    openSearch: function () {
      var note = document.querySelector(".fixture-note");
      if (note) note.textContent = "the page's own search was asked to open";
    },
  };

  /* Furo's theme model: body[data-theme] is auto, light or dark, remembered in
   * localStorage.theme. The palette keys on [data-scheme], so mirror it. */
  var dark = window.matchMedia("(prefers-color-scheme: dark)");

  function savedTheme() {
    try {
      return window.localStorage.getItem("theme");
    } catch {
      return null;
    }
  }

  function applyScheme() {
    var theme = document.body.dataset.theme;
    var scheme =
      theme === "light" || theme === "dark"
        ? theme
        : dark.matches
          ? "dark"
          : "light";
    document.documentElement.dataset.scheme = scheme;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var saved = savedTheme();
    if (saved === "light" || saved === "dark" || saved === "auto")
      document.body.dataset.theme = saved;
    applyScheme();
    new MutationObserver(applyScheme).observe(document.body, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    dark.addEventListener("change", applyScheme);
    var toggle = document.querySelector(".theme-toggle");
    if (toggle)
      toggle.addEventListener("click", function () {
        var order = ["auto", "light", "dark"];
        var next =
          order[
            (order.indexOf(document.body.dataset.theme) + 1) % order.length
          ];
        document.body.dataset.theme = next;
        try {
          window.localStorage.setItem("theme", next);
        } catch {
          /* The theme holds for this page only. */
        }
      });
  });
})();
