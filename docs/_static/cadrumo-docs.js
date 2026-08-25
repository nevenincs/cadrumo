/* Cadrumo docs interaction layer: broadcast dismiss, header active-link
 * highlighting, and a Ctrl/Cmd-K command palette over the navigation tree
 * with a full-text search fallback. No framework, no dependencies. */
(function () {
  "use strict";

  var IS_MAC = /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent);

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  /* ── Broadcast dismiss ─────────────────────────────────────────────── */

  function broadcastKey() {
    var strip = document.querySelector(".cadrumo-broadcast");
    if (!strip) return null;
    return "cadrumo:broadcast:" + strip.textContent.replace(/\s+/g, " ").trim().slice(0, 120);
  }

  function initBroadcast() {
    var key = broadcastKey();
    if (!key) return;
    var stored = null;
    try {
      stored = window.localStorage.getItem(key);
    } catch (e) {
      /* storage unavailable (private mode); strip stays visible */
    }
    if (stored) {
      document.documentElement.classList.add("cadrumo-broadcast-dismissed");
    }
    var button = document.querySelector("[data-cadrumo-broadcast-dismiss]");
    if (!button) return;
    button.addEventListener("click", function () {
      document.documentElement.classList.add("cadrumo-broadcast-dismissed");
      try {
        window.localStorage.setItem(key, "1");
      } catch (e) {
        /* non-persistent dismissal is fine */
      }
    });
  }

  /* ── Header active-link highlighting ───────────────────────────────── */

  function initNavActive() {
    var links = document.querySelectorAll(".cadrumo-header-nav-link");
    var here = window.location.pathname;
    var best = null;
    var bestLength = 0;
    links.forEach(function (link) {
      var url;
      try {
        url = new URL(link.href, window.location.href);
      } catch (e) {
        return;
      }
      var dir = url.pathname.replace(/index\.html?$/, "");
      if (here === url.pathname || here.indexOf(dir) === 0) {
        if (dir.length > bestLength) {
          best = link;
          bestLength = dir.length;
        }
      }
    });
    if (best) {
      best.classList.add("is-active");
      best.setAttribute("aria-current", "page");
    }
  }

  /* ── Command-block decoration ──────────────────────────────────────────
   * Pygments tokenizes bash strings/numbers but leaves command words and
   * --flags as plain text. Wrap those in spans so shell transcripts read
   * like a modern terminal. Only text nodes are touched, so the copy
   * button's textContent-based extraction is unaffected. */

  var COMMAND_HEAD = /(^|\n)((?:\$ |PS> )?)(aeat(?:\s+[a-z][\w-]*)*)/g;
  var FLAG = /(^|[\s=])(--?[A-Za-z][\w-]*)(?=[\s=,)"']|$)/g;

  function decorateTextNode(node) {
    var text = node.nodeValue;
    var ranges = [];
    var match;
    COMMAND_HEAD.lastIndex = 0;
    while ((match = COMMAND_HEAD.exec(text)) !== null) {
      var commandStart = match.index + match[1].length + match[2].length;
      ranges.push([commandStart, commandStart + match[3].length, "cadrumo-tok-cmd"]);
    }
    FLAG.lastIndex = 0;
    while ((match = FLAG.exec(text)) !== null) {
      var flagStart = match.index + match[1].length;
      ranges.push([flagStart, flagStart + match[2].length, "cadrumo-tok-flag"]);
    }
    if (!ranges.length) return;
    ranges.sort(function (a, b) {
      return a[0] - b[0];
    });
    var fragment = document.createDocumentFragment();
    var pos = 0;
    ranges.forEach(function (range) {
      if (range[0] < pos) return;
      if (range[0] > pos) {
        fragment.appendChild(document.createTextNode(text.slice(pos, range[0])));
      }
      var span = document.createElement("span");
      span.className = range[2];
      span.textContent = text.slice(range[0], range[1]);
      fragment.appendChild(span);
      pos = range[1];
    });
    if (pos < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(pos)));
    }
    node.parentNode.replaceChild(fragment, node);
  }

  function initCommandBlocks() {
    var selector = [
      'div[class*="highlight-bash"] pre',
      'div[class*="highlight-console"] pre',
      'div[class*="highlight-shell"] pre',
      'div[class*="highlight-sh"] pre',
      'div[class*="highlight-default"] pre',
      'div[class*="highlight-text"] pre',
      'div[class*="highlight-powershell"] pre',
    ].join(", ");
    document.querySelectorAll(selector).forEach(function (pre) {
      // Pygments wraps whitespace runs in <span class="w">, splitting the
      // text into single-word nodes; unwrap them so command runs are
      // contiguous text the decorators can see.
      pre.querySelectorAll("span.w").forEach(function (ws) {
        ws.replaceWith(document.createTextNode(ws.textContent));
      });
      pre.normalize();
      Array.prototype.slice.call(pre.childNodes).forEach(function (node) {
        if (node.nodeType === Node.TEXT_NODE) decorateTextNode(node);
      });
    });
  }

  /* ── Command palette ───────────────────────────────────────────────── */

  function navIndex() {
    var seen = Object.create(null);
    var entries = [];

    function crumbFor(anchor) {
      var parts = [];
      var li = anchor.closest("li");
      li = li ? li.parentElement.closest("li") : null;
      while (li) {
        var parentAnchor = li.querySelector(":scope > a");
        if (parentAnchor) parts.unshift(parentAnchor.textContent.trim());
        li = li.parentElement.closest("li");
      }
      var topUl = anchor.closest("ul");
      while (topUl && topUl.parentElement.closest("ul")) {
        topUl = topUl.parentElement.closest("ul");
      }
      var caption = topUl ? topUl.previousElementSibling : null;
      if (caption && caption.classList.contains("caption")) {
        parts.unshift(caption.textContent.trim());
      }
      return parts.join(" / ");
    }

    document.querySelectorAll(".sidebar-tree a.reference").forEach(function (anchor) {
      var href = anchor.href;
      var title = anchor.textContent.replace(/\s+/g, " ").trim();
      if (!title || seen[href]) return;
      seen[href] = true;
      entries.push({ title: title, href: href, crumb: crumbFor(anchor) });
    });

    document.querySelectorAll(".toc-tree a.reference").forEach(function (anchor) {
      var href = anchor.href;
      var title = anchor.textContent.replace(/\s+/g, " ").trim();
      if (!title || seen[href]) return;
      seen[href] = true;
      entries.push({ title: title, href: href, crumb: "On this page" });
    });

    return entries;
  }

  function score(entry, query) {
    var title = entry.title.toLowerCase();
    var crumb = entry.crumb.toLowerCase();
    var tokens = query.split(/\s+/).filter(Boolean);
    var total = 0;
    for (var i = 0; i < tokens.length; i++) {
      var token = tokens[i];
      if (title.indexOf(token) === 0) {
        total += 100;
      } else if (title.indexOf(" " + token) >= 0) {
        total += 60;
      } else if (title.indexOf(token) >= 0) {
        total += 40;
      } else if (crumb.indexOf(token) >= 0) {
        total += 12;
      } else {
        return -1;
      }
    }
    return total - Math.min(entry.title.length, 40) / 10;
  }

  /* ── Search controller ─────────────────────────────────────────────────
   * The full search behaviour (Pagefind loading, the two-pass card/page
   * search, the ADR-D5 compose ladder, the PERF-003 relevance tie-break,
   * dedupe, painting, keyboard selection, and the busy-state machine) is
   * host-agnostic. It is parameterised on a node set — a `root` for the busy
   * class, an `input`, a result `list`, and a screen-reader `status` node —
   * plus small behavioural flags, so the exact same core drives two surfaces:
   * the Ctrl-K modal palette (`initPalette`) and the inline search page
   * (`initSearchPage`). Nothing here reaches for a dialog-scoped variable;
   * every host node arrives through `opts` (ADR D5).
   *
   * opts:
   *   root          element the busy `is-busy` class toggles on
   *   input, list, status  the surface's three inner nodes
   *   searchUrl     page-relative path used to resolve the pagefind bundle
   *                 and, when `handoffRow` is on, the full-text escape row
   *   handoffRow    append the "Search the docs for …" navigation row
   *                 (modal only; the inline page already shows full text)
   *   navOnEmpty    an empty query paints the nav index (modal) vs clears
   *                 to nothing (the inline page is a pure search surface) */
  function createSearchController(opts) {
    var root = opts.root;
    var input = opts.input;
    var list = opts.list;
    var status = opts.status;
    var searchUrl = opts.searchUrl || "search.html";
    var handoffRow = opts.handoffRow !== false;
    var navOnEmpty = opts.navOnEmpty === true;

    var entries = null;
    var rows = [];
    var selected = 0;
    var queryToken = 0;

    /* ── Busy state ───────────────────────────────────────────────────────
     * Pagefind resolves asynchronously (a lazy index import on first open,
     * then two sequential passes), and render() deliberately keeps the
     * PREVIOUS results painted until the new query resolves. Without a busy
     * signal that combination is indistinguishable from a dead palette: the
     * reader types and nothing changes. The signal is therefore additive -
     * the stale rows stay, and the head says a newer answer is coming.
     *
     * Shown only after BUSY_DELAY_MS still pending: a steady-state Pagefind
     * hit resolves in a few ms, and flashing a spinner for one frame reads as
     * jank, not as progress. The first open (which pays the index import) is
     * the slow case this exists for.
     *
     * Ownership follows the queryToken supersede guard: only the resolve of
     * the LATEST query clears the state. A superseded resolve returns before
     * clearing, so it cannot switch off a signal that a newer in-flight query
     * still owns. Every search path settles (searchPagefind swallows failure
     * and resolves []), so the degraded no-index path clears too and never
     * spins forever. */
    var BUSY_DELAY_MS = 120;
    var busyTimer = null;
    var isBusy = false;

    function setBusy(on) {
      if (isBusy === on) return;
      isBusy = on;
      root.classList.toggle("is-busy", on);
      list.setAttribute("aria-busy", on ? "true" : "false");
      /* A screen reader gets told the search is working rather than sitting in
       * silence on unchanged (stale) rows; the settled count replaces it. */
      if (on) status.textContent = "Searching…";
    }

    function beginBusy() {
      if (busyTimer) clearTimeout(busyTimer);
      busyTimer = setTimeout(function () {
        busyTimer = null;
        setBusy(true);
      }, BUSY_DELAY_MS);
    }

    function endBusy(resultCount) {
      if (busyTimer) {
        clearTimeout(busyTimer);
        busyTimer = null;
      }
      setBusy(false);
      /* No count means there was no search to report (the empty-query reset, or
       * a reopen): drop any stale announcement rather than leave the live region
       * asserting a count for results the reader is no longer looking at. */
      status.textContent =
        typeof resultCount !== "number"
          ? ""
          : resultCount === 1
            ? "1 result"
            : String(resultCount) + " results";
    }

    /* ── Pagefind tier (term cards / full text) ───────────────────────── */
    /* Pagefind ships a chunked index under <site>/pagefind/ when the docs
     * build runs the post-build index pass. The palette lazy-loads it on
     * first open and queries it for the injected term/casilla/CLI cards and
     * the full-text page hits. When the index is absent (a dev preview built
     * without the pass), the palette silently keeps its nav-only behaviour. */
    var pagefindPromise = null;
    /* Resolve the index URL against the page so the dynamic import gets an
     * absolute specifier: a bare/relative one (e.g. "pagefind/pagefind.js")
     * is treated as a package name and fails. searchUrl is page-relative
     * (e.g. "search.html" or "../search.html"); strip its filename and append
     * the pagefind bundle, resolved against the document base. */
    var pagefindBase = new URL(
      searchUrl.replace(/[^/]*$/, "") + "pagefind/",
      document.baseURI
    ).href;

    function loadPagefind() {
      if (pagefindPromise) return pagefindPromise;
      pagefindPromise = import(pagefindBase + "pagefind.js")
        .then(function (pf) {
          if (pf && typeof pf.options === "function") {
            pf.options({ excerptLength: 24 });
          }
          return pf;
        })
        .catch(function () {
          return null;
        });
      return pagefindPromise;
    }

    /* A structured address is deliberately resolved from shipped Pagefind
     * metadata, not from a JavaScript copy of the registry. Numeric matching
     * ignores presentation zero-padding and locale casing; a segmented
     * modelo must name its segment, or remain on the ordinary ladder when the
     * address is not unique. */
    function normalizeStructuredText(value) {
      var text = String(value || "").trim();
      if (typeof text.normalize === "function") {
        text = text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
      }
      return text.toLowerCase();
    }

    function normalizeStructuredValue(value) {
      var text = normalizeStructuredText(value);
      return /^\d+$/.test(text) ? text.replace(/^0+(?=\d)/, "") : text;
    }

    function parseStructuredCasillaQuery(query) {
      var text = normalizeStructuredText(query)
        .replace(/[^\w\s:.-]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      var match = text.match(
        /^(?:modelo|model|form)\s+([0-9]+)\s+(?:casilla|casella|box|field)\s+([a-z0-9][a-z0-9._:-]*)$/
      );
      if (!match) return null;

      var casilla = match[2];
      var separator = casilla.indexOf(":");
      var segmento = "";
      var number = casilla;
      if (separator >= 0) {
        if (separator === 0 || separator === casilla.length - 1) return null;
        segmento = casilla.slice(0, separator);
        number = casilla.slice(separator + 1);
      }
      var casillaId = normalizeStructuredText(casilla);
      return {
        modelo: normalizeStructuredValue(match[1]),
        casillaId: casillaId,
        number: normalizeStructuredValue(number),
        segmento: segmento ? normalizeStructuredValue(segmento) : null,
      };
    }

    function isStructuredCasillaMatch(data, address) {
      var meta = data && data.meta;
      if (!meta || meta.kind !== "casilla") return false;
      if (normalizeStructuredValue(meta.modelo) !== address.modelo) return false;
      if (normalizeStructuredText(meta.casilla_id) === address.casillaId) return true;
      if (normalizeStructuredValue(meta.number) !== address.number) return false;
      return !address.segmento || normalizeStructuredValue(meta.segmento) === address.segmento;
    }

    function searchStructuredCasilla(pf, query) {
      var address = parseStructuredCasillaQuery(query);
      if (!address) return Promise.resolve([]);

      return Promise.resolve(
        pf.search(query, { filters: { kind: ["casilla"] } })
      )
        .then(function (response) {
          var results = response && response.results ? response.results : [];
          return Promise.all(
            results.map(function (result) {
              return Promise.resolve(result.data()).then(function (data) {
                return { data: data, result: result };
              });
            })
          );
        })
        .then(function (items) {
          var seenHref = {};
          var matches = [];
          items.forEach(function (item) {
            var href = item.data && item.data.url;
            if (!href || seenHref[href] || !isStructuredCasillaMatch(item.data, address)) {
              return;
            }
            seenHref[href] = true;
            matches.push({ data: item.data, href: href });
          });
          if (matches.length !== 1) return [];

          var match = matches[0];
          return [
            cardFromPagefind(
              match.data.meta,
              match.data.meta && match.data.meta.title,
              match.href,
              match.data.excerpt,
              true
            ),
          ];
        })
        .catch(function () {
          /* A malformed/older index falls through to the normal ladder. */
          return [];
        });
    }

    /* Result iconography + ranking authority (ADR 2026-07-15 D7/D8). The Python
     * injection seam ships a closed `display_class` on every injected record
     * (`casilla`/`modelo`/`cli`/`technical`/`doc`) plus a `weight` already
     * placed on the one user-first ladder (doc 1.0 > modelo 0.9 > casilla 0.8 >
     * cli 0.7 > technical 0.5). This renderer READS that class verbatim for the
     * icon and RANKS on that shipped weight; it NEVER re-derives the class from
     * kind/URL heuristics (the exact duplicated-structural-fact failure that
     * silently rotted the CLI targets — ADR Axis-6 O6b/O6c).
     *
     * Hand-authored inline SVG, one per display class, matching the file's
     * existing 16×16 stroke/viewBox idiom (magnifier, chevron, copy). No
     * icon-font, no external asset (`aeat-documentation`). Full-text
     * page hits carry a path-derived class too (build-side page-meta stamping,
     * ADR D8); a record with no shipped class (a nav title, or an older index)
     * degrades to no icon rather than a guessed one. */
    var DISPLAY_CLASS_ICONS = {
      casilla:
        '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
        '<rect x="2.5" y="2.5" width="11" height="11" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.3"/>' +
        '<path d="M5.4 8.2l1.9 1.9 3.3-3.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      modelo:
        '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
        '<path d="M4 2.2h5l3 3v8.6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3.2a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>' +
        '<path d="M9 2.4v3h3M5.6 8.6h4.8M5.6 10.8h4.8" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
      cli:
        '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
        '<rect x="2.3" y="3" width="11.4" height="10" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.3"/>' +
        '<path d="M4.8 6.6l2 1.7-2 1.7M8.6 10.4h3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      technical:
        '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
        '<path d="M6 4.5L2.6 8 6 11.5M10 4.5L13.4 8 10 11.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      doc:
        '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
        '<circle cx="8" cy="8" r="5.6" fill="none" stroke="currentColor" stroke-width="1.3"/>' +
        '<path d="M6.4 6.4a1.7 1.7 0 0 1 3.2.6c0 1.1-1.5 1.4-1.6 2.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>' +
        '<circle cx="8" cy="11.3" r="0.65" fill="currentColor"/></svg>',
    };

    /* Crumb category label, keyed on the shipped display class where present,
     * falling back to the record kind for a full-text page hit (no class). */
    var DISPLAY_CLASS_LABEL = {
      casilla: "Casilla",
      modelo: "Modelo",
      legal: "Legal",
      cli: "Command",
      technical: "Reference",
      doc: "Docs",
    };
    var KIND_LABEL = {
      concept: "Term",
      cli: "Command",
      casilla: "Casilla",
      page: "Page",
    };

    /* Intra-band rank for a full-text PAGE hit, keyed on its shipped
     * `display_class` (ADR D8). A page carries NO `weight` meta (Trap 1: that
     * would pollute the weight-sorted card pass), so this JS-side map is how a
     * user-doc page (`doc`) floats above a dev-machinery page (`technical`)
     * WITHIN the full-text band. Every value sits in (0, 1) — comfortably below
     * the card band (tierRank 1 + weight, ≥ 1.7) — so cards always lead; the
     * order mirrors the shipped weight ladder (doc > modelo > casilla > legal >
     * cli > technical). This CONSUMES the shipped class; it never re-derives it. */
    var PAGE_BAND_RANK = {
      doc: 0.4,
      modelo: 0.35,
      casilla: 0.3,
      legal: 0.28,
      cli: 0.25,
      technical: 0.2,
    };

    function cardFromPagefind(meta, fallbackTitle, url, excerpt, fromCardPass) {
      var kind = (meta && meta.kind) || "page";
      var displayClass = (meta && meta.display_class) || "";
      var title = (meta && meta.title) || fallbackTitle || url;
      var crumbParts = [DISPLAY_CLASS_LABEL[displayClass] || KIND_LABEL[kind] || "Result"];
      if (meta && meta.modelo && meta.number) {
        /* Casilla crumb: modelo + official number, plus the segmento the Python
         * seam now ships so sibling casillas of a segmented modelo (M200
         * `DP200014:00562`) read apart at a glance (ADR D6). */
        var casillaCrumb = "Modelo " + meta.modelo + " · " + meta.number;
        if (meta.segmento) casillaCrumb += " · " + meta.segmento;
        crumbParts.push(casillaCrumb);
      } else if (meta && meta.command_path) {
        crumbParts.push(meta.command_path);
      } else if (meta && meta.domain) {
        crumbParts.push(meta.domain);
      }
      /* Rank on the shipped user-first weight (D8): the Python ladder already
       * encodes doc>modelo>casilla>cli>technical, so consuming `weight` keeps a
       * single ranking authority instead of the retired local KIND_TIER (which
       * re-keyed on kind and still ordered cli above casilla). An injected card
       * carries a weight (0.7–1.0); a full-text page hit carries none, so it
       * sits below every card — the retained RankingTier coarse axis (term/nav
       * cards first, full text last) is the +1 card band; PERF-003's relevance
       * tie-break within a band is preserved in compose(). */
      var weight = meta && meta.weight ? parseFloat(meta.weight) : 0;
      if (isNaN(weight)) weight = 0;
      /* `isCard` is PASS-ORIGIN, not class-presence (Trap 2): the weight-sorted
       * card pass yields only injected records, the relevance pass yields
       * full-text pages. Since pages now ALSO carry a `display_class`, keying
       * `isCard` on `displayClass !== ""` would wrongly promote every page into
       * the card band. Threading which pass produced the row keeps cards above
       * pages while pages still carry a class for their intra-band order + icon. */
      var isCard = !!fromCardPass;
      /* Injected term/casilla/CLI records carry a clean single-language
       * `summary`; show that, never Pagefind's auto-excerpt of the record,
       * which is the cross-lingual token blob (title + every alias + all four
       * descriptions). Full-text page hits carry no summary, so they keep their
       * real Pagefind snippet. */
      var summary = meta && meta.summary ? meta.summary : "";
      return {
        title: title,
        href: url,
        crumb: crumbParts.join(" · "),
        excerpt: summary || excerpt || "",
        kind: kind,
        displayClass: displayClass,
        /* The weight-sorted Pagefind pass contains only injected records. Keep
         * this as a pass-origin marker, not a direct-identity signal: Pagefind
         * can reach a card through its description as well as its title or
         * declared aliases. The compose ladder uses title/direct-match
         * strength for identity precedence. */
        isLexicalCard: isCard,
        /* Newer injection payloads may carry the opaque id. Older Pagefind
         * records remain valid and dedupe by their href below. */
        recordId: meta && meta.record_id ? meta.record_id : null,
        /* Card band: 1 + shipped weight (≥ 1.7). Full-text band: the class's
         * intra-band rank in (0, 1), so a `doc` page outranks a `technical`
         * page while every page stays below every card. */
        tierRank: isCard ? 1 + weight : PAGE_BAND_RANK[displayClass] || 0,
      };
    }

    function dataToCards(results, limit, fromCardPass) {
      return Promise.all(
        results.slice(0, limit).map(function (result) {
          return Promise.resolve(result.data()).then(function (data) {
            var card = cardFromPagefind(
              data.meta,
              data.meta && data.meta.title,
              data.url,
              data.excerpt,
              fromCardPass
            );
            card.pagefindId = result.id;
            return card;
          });
        })
      );
    }

    /* The injected term/casilla/CLI records and the docs pages share one index
     * (the injection files every record under the page language with combined
     * multilingual content, so a Spanish term is found from an English page,
     * and stamps a `weight` sort key on every record). Two passes compose the
     * ADR-D5 ladder reliably:
     *   1. a search SORTED by `weight` returns ONLY the injected records (the
     *      docs pages carry no `weight` key, so Pagefind drops them) ordered by
     *      the D8 display-class ladder (doc 1.0 > modelo 0.9 > casilla 0.8 > cli
     *      0.7) - these are the term/navigation card tiers, guaranteed above the
     *      full text;
     *   2. a normal relevance search yields the full-text page hits (third
     *      tier). Each page carries a path-derived `display_class` (but NO
     *      `weight` key, so pass 1 still drops it), which orders pages within
     *      the full-text band (user docs above dev machinery; ADR D8). A page
     *      that is also a card is deduped away in compose(). */
    function searchPagefind(query) {
      return loadPagefind()
        .then(function (pf) {
          if (!pf || typeof pf.search !== "function") return { cards: [], structured: false };
          /* Run the two passes SEQUENTIALLY. Two concurrent searches on one
           * Pagefind instance make the first supersede-cancel the other -
           * Pagefind keeps only the latest in-flight search and resolves the
           * rest to null - which silently emptied the card pass while a reader
           * was still typing. Awaiting each pass in turn removes the
           * self-supersede so both reliably return. */
          return searchStructuredCasilla(pf, query).then(function (structured) {
            if (structured.length) return { cards: structured, structured: true };
            return Promise.resolve(
              pf.search(query, { sort: { weight: "desc" } })
            ).then(function (cardRes) {
              return Promise.resolve(pf.search(query)).then(function (pageRes) {
                var cardResults = cardRes && cardRes.results ? cardRes.results : [];
                var pageResults = pageRes && pageRes.results ? pageRes.results : [];
                /* The weight-sorted pass ties every concept card at the flat
                 * tier-one weight, so join its rows to the textual pass by
                 * Pagefind's ephemeral result id; compose() breaks within-tier
                 * ties by that rank, floating the best textual match to the top
                 * of its tier while cards still sit above full-text pages. */
                var relRank = {};
                pageResults.forEach(function (r, i) {
                  if (relRank[r.id] === undefined) relRank[r.id] = i;
                });
                return dataToCards(cardResults, 12, true).then(function (cards) {
                  return dataToCards(pageResults, 6, false).then(function (pages) {
                    var all = cards.concat(pages);
                    all.forEach(function (item) {
                      item.relRank =
                        relRank[item.pagefindId] !== undefined
                          ? relRank[item.pagefindId]
                          : Number.MAX_SAFE_INTEGER;
                    });
                    return { cards: all, structured: false };
                  });
                });
              });
            });
          });
        })
        .catch(function () {
          /* Pagefind is optional; its absence degrades to the nav ladder. */
          return { cards: [], structured: false };
        })
        .then(function (result) {
          return result.cards;
        })
        .catch(function () {
          /* Any earlier controller failure degrades to the ordinary
           * nav/Pagefind ladder; it never breaks the palette or leaves an
           * unhandled rejection. */
          return [];
        });
    }

    function fullSearchEntry(query) {
      return {
        title: query ? 'Search the docs for “' + query + '”' : "Open full-text search",
        href: searchUrl + (query ? "?q=" + encodeURIComponent(query) : ""),
        crumb: "Full-text search",
      };
    }

    function navMatches(query) {
      if (entries === null) entries = navIndex();
      if (!query) return entries.slice(0, 9);
      return entries
        .map(function (entry) {
          return { entry: entry, value: score(entry, query.toLowerCase()) };
        })
        .filter(function (item) {
          return item.value >= 0;
        })
        .sort(function (a, b) {
          return b.value - a.value;
        })
        .slice(0, 9)
        .map(function (item) {
          return item.entry;
        });
    }

    /* Compose the ADR-D5 progressive ladder: Pagefind term/casilla/CLI cards
     * first (ordered by injected tier+weight), navigation titles second, the
     * full-text handoff third. Dedupe by href across tiers: a hit that is both
     * a term card and a nav/full-text result shows once, in its higher tier. */
    /* How well a card's own title matches the query: an exact title match is a
     * strong, DETERMINISTIC signal that this card is THE answer, independent of
     * Pagefind's BM25 (which, for a short common token like "iva" diluted across
     * many multilingual card descriptions, does not reliably float the exact
     * concept). 3 exact, 2 prefix, 1 substring, 0 none. */
    function titleMatch(title, query) {
      if (!title || !query) return 0;
      var t = String(title).toLowerCase();
      var q = String(query).toLowerCase().trim();
      if (!q) return 0;
      if (t === q) return 3;
      if (t.indexOf(q) === 0) return 2;
      if (t.indexOf(q) >= 0) return 1;
      return 0;
    }

    function compose(query, pagefindCards) {
      var seenHref = {};
      var seenRecordId = {};
      var ordered = [];
      var cards = (pagefindCards || []).slice().sort(function (a, b) {
        /* A declared lexical identity (including an exact title or alias
         * returned by Pagefind) orders ahead of a weaker match. The card-pass
         * marker is deliberately not identity: a description hit is lexical
         * provenance, not a direct answer. Display-class bands rank first, then
         * direct-match strength, then Pagefind's own relevance order.
         *
         * The semantic tie-breaks that once sat between these steps were
         * removed with the static-embedding tier. They were unreachable
         * without a card carrying a semanticScore, so their removal is a
         * subtraction: this comparator orders lexical cards exactly as before. */
        var ma = typeof a.directMatchStrength === "number" ? a.directMatchStrength : titleMatch(a.title, query);
        var mb = typeof b.directMatchStrength === "number" ? b.directMatchStrength : titleMatch(b.title, query);
        if (b.tierRank !== a.tierRank) return b.tierRank - a.tierRank;
        if (mb !== ma) return mb - ma;
        return (a.relRank || 0) - (b.relRank || 0);
      });
      cards.forEach(function (card) {
        if (seenHref[card.href] || (card.recordId && seenRecordId[card.recordId])) return;
        seenHref[card.href] = true;
        if (card.recordId) seenRecordId[card.recordId] = true;
        ordered.push(card);
      });
      navMatches(query).forEach(function (entry) {
        if (seenHref[entry.href] || (entry.recordId && seenRecordId[entry.recordId])) return;
        seenHref[entry.href] = true;
        if (entry.recordId) seenRecordId[entry.recordId] = true;
        ordered.push(entry);
      });
      if (handoffRow) ordered.push(fullSearchEntry(query));
      return ordered.slice(0, 18);
    }

    function paint(items) {
      list.textContent = "";
      rows = items.map(function (entry, index) {
        var item = document.createElement("li");
        item.className = "cadrumo-palette-item";
        if (entry.kind) item.classList.add("cadrumo-palette-item--" + entry.kind);
        item.setAttribute("role", "option");
        var link = document.createElement("a");
        link.href = entry.href;
        /* Per-class result icon (ADR D7/D8): the shipped `display_class`, read
         * verbatim, selects one hand-authored inline SVG. Full-text page hits
         * now also ship a class (build-side page-meta stamping), so they render
         * an icon too; a row with no shipped class (nav title, handoff) gets no
         * icon rather than a guessed one — never re-derive the class here. */
        if (entry.displayClass && DISPLAY_CLASS_ICONS[entry.displayClass]) {
          var icon = document.createElement("span");
          icon.className =
            "cadrumo-palette-item-icon cadrumo-palette-item-icon--" + entry.displayClass;
          icon.setAttribute("aria-hidden", "true");
          icon.innerHTML = DISPLAY_CLASS_ICONS[entry.displayClass]; // static SVG markup, no user data
          link.appendChild(icon);
        }
        var body = document.createElement("span");
        body.className = "cadrumo-palette-item-body";
        var title = document.createElement("span");
        title.className = "cadrumo-palette-item-title";
        title.textContent = entry.title;
        body.appendChild(title);
        if (entry.crumb) {
          var crumb = document.createElement("span");
          crumb.className = "cadrumo-palette-item-crumb";
          crumb.textContent = entry.crumb;
          body.appendChild(crumb);
        }
        if (entry.excerpt) {
          var ex = document.createElement("span");
          ex.className = "cadrumo-palette-item-excerpt";
          ex.textContent = entry.excerpt;
          body.appendChild(ex);
        }
        link.appendChild(body);
        item.appendChild(link);
        item.addEventListener("mousemove", function () {
          select(index);
        });
        list.appendChild(item);
        return item;
      });
      select(0);
    }

    function render(query) {
      var token = ++queryToken;
      if (!query) {
        /* An empty query settles synchronously - there is nothing in flight to
         * report. The modal answers it from the nav index (a launcher shows
         * suggestions on open); the inline search page is a pure query surface,
         * so it clears to nothing rather than list every nav title unprompted. */
        endBusy();
        if (navOnEmpty) {
          paint(compose("", []));
        } else {
          list.textContent = "";
          rows = [];
          selected = 0;
        }
        return;
      }
      /* Keep the current results painted until the new query resolves, then
       * swap - so a keystroke never blanks the palette to the bare fallback
       * (the old eager repaint did, and on a transiently-empty Pagefind pass it
       * stuck there). The busy signal is what tells the reader those rows are
       * the OLD answer and a newer one is on its way. */
      beginBusy();
      searchPagefind(query)
        .then(function (cards) {
          if (token !== queryToken) return; /* a newer keystroke superseded this */
          var items = compose(query, cards);
          endBusy(items.length);
          paint(items);
        })
        .catch(function () {
          if (token !== queryToken) return;
          var items = compose(query, []);
          endBusy(items.length);
          paint(items);
        });
    }

    function select(index) {
      if (!rows.length) return;
      selected = Math.max(0, Math.min(index, rows.length - 1));
      rows.forEach(function (row, i) {
        row.classList.toggle("is-selected", i === selected);
        row.setAttribute("aria-selected", i === selected ? "true" : "false");
      });
      rows[selected].scrollIntoView({ block: "nearest" });
    }

    return {
      render: render,
      moveSelection: function (delta) {
        select(selected + delta);
      },
      /* The href of the currently-selected row, or null when nothing is
       * selectable — the host decides whether to preventDefault and navigate. */
      selectedHref: function () {
        var row = rows[selected];
        var link = row && row.querySelector("a");
        return link ? link.href : null;
      },
    };
  }

  /* ── Command palette (modal host) ──────────────────────────────────────── */

  function initPalette() {
    var triggers = document.querySelectorAll("[data-cadrumo-search]");
    if (!triggers.length || typeof HTMLDialogElement === "undefined") return;
    var searchUrl = triggers[0].getAttribute("data-cadrumo-search-url") || "search.html";

    document.querySelectorAll("[data-cadrumo-search-kbd]").forEach(function (kbd) {
      kbd.textContent = IS_MAC ? "⌘ K" : "Ctrl K";
    });

    var dialog = document.createElement("dialog");
    dialog.className = "cadrumo-palette";
    dialog.setAttribute("aria-label", "Search documentation");
    dialog.innerHTML =
      '<div class="cadrumo-palette-head">' +
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001q.044.06.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1 1 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0"/></svg>' +
      '<input class="cadrumo-palette-input" type="text" placeholder="Search docs…" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Search query">' +
      '<span class="cadrumo-palette-spin" aria-hidden="true"></span>' +
      '<kbd class="cadrumo-palette-esc">esc</kbd>' +
      "</div>" +
      '<ul class="cadrumo-palette-list" role="listbox" aria-busy="false"></ul>' +
      '<p class="cadrumo-palette-status" role="status" aria-live="polite"></p>' +
      '<div class="cadrumo-palette-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div>';
    document.body.appendChild(dialog);

    var input = dialog.querySelector(".cadrumo-palette-input");
    var controller = createSearchController({
      root: dialog,
      input: input,
      list: dialog.querySelector(".cadrumo-palette-list"),
      status: dialog.querySelector(".cadrumo-palette-status"),
      searchUrl: searchUrl,
      handoffRow: true,
      navOnEmpty: true,
    });

    function open() {
      if (dialog.open) return;
      dialog.showModal();
      input.value = "";
      controller.render("");
      input.focus();
    }

    triggers.forEach(function (trigger) {
      trigger.addEventListener("click", function (event) {
        event.preventDefault();
        open();
      });
    });

    document.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === "k") {
        event.preventDefault();
        if (dialog.open) {
          dialog.close();
        } else {
          open();
        }
      }
    });

    var searchDebounce = null;
    input.addEventListener("input", function () {
      var q = input.value.trim();
      if (searchDebounce) clearTimeout(searchDebounce);
      /* Coalesce fast typing into one search: firing a Pagefind pass per
       * keystroke is what raced them into the supersede-empty state. */
      searchDebounce = setTimeout(function () {
        controller.render(q);
      }, 130);
    });

    dialog.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        controller.moveSelection(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        controller.moveSelection(-1);
      } else if (event.key === "Enter") {
        var href = controller.selectedHref();
        if (href) {
          event.preventDefault();
          window.location.assign(href);
        }
      }
    });

    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
  }

  /* ── Search page (inline host) ─────────────────────────────────────────
   * The shipped search page (docs/_templates/search.html) is a bare
   * `#pagefind-search` mount; the same controller that drives the Ctrl-K modal
   * renders inline here so the page inherits the D5 tier ladder, the PERF-003
   * tie-break, and dedupe instead of a second, divergent implementation (the
   * retired PagefindUI drop). The page reads `?q=` to seed a shareable search
   * and rewrites the URL as the query changes. */

  function initSearchPage() {
    var mount = document.getElementById("pagefind-search");
    if (!mount) return;

    mount.classList.add("cadrumo-search-page");
    var head = document.createElement("div");
    head.className = "cadrumo-search-page-head";
    head.innerHTML =
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001q.044.06.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1 1 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0"/></svg>' +
      '<input class="cadrumo-palette-input cadrumo-search-page-input" type="search" placeholder="Search docs…" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Search query">' +
      '<span class="cadrumo-palette-spin" aria-hidden="true"></span>';
    var list = document.createElement("ul");
    list.className = "cadrumo-palette-list cadrumo-search-page-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-busy", "false");
    var status = document.createElement("p");
    status.className = "cadrumo-palette-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    mount.appendChild(head);
    mount.appendChild(list);
    mount.appendChild(status);

    var input = head.querySelector(".cadrumo-search-page-input");
    var controller = createSearchController({
      root: mount,
      input: input,
      list: list,
      status: status,
      /* The page IS search.html, so the pagefind bundle resolves against this
       * document's own directory; the full-text handoff row is dropped because
       * the page already renders full-text results inline. */
      searchUrl: "",
      handoffRow: false,
      navOnEmpty: false,
    });

    function queryFromUrl() {
      /* URLSearchParams decodes BOTH `+` and %20 to a space; the two encodings
       * both reach this page (the palette emits %20 via encodeURIComponent, the
       * casilla records emit `+`). decodeURIComponent would leave `+` literal —
       * the reported `?q=130+10` failure — so it must not be used here. */
      return new URLSearchParams(window.location.search).get("q") || "";
    }

    function syncUrl(query) {
      var url = new URL(window.location.href);
      if (query) {
        url.searchParams.set("q", query);
      } else {
        url.searchParams.delete("q");
      }
      /* replaceState, not pushState: a shareable URL per settled query without
       * flooding the back button with one entry per keystroke. */
      window.history.replaceState(null, "", url.toString());
    }

    var initial = queryFromUrl();
    if (initial) {
      input.value = initial;
      controller.render(initial);
    }

    var searchDebounce = null;
    input.addEventListener("input", function () {
      var q = input.value.trim();
      if (searchDebounce) clearTimeout(searchDebounce);
      searchDebounce = setTimeout(function () {
        syncUrl(q);
        controller.render(q);
      }, 130);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        controller.moveSelection(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        controller.moveSelection(-1);
      } else if (event.key === "Enter") {
        var href = controller.selectedHref();
        if (href) {
          event.preventDefault();
          window.location.assign(href);
        }
      }
    });

    input.focus();
  }

  /* ── CLI sequence playhead ─────────────────────────────────────────────
   * Progressive enhancement over the server-rendered div.cadrumo-sequence
   * transcript (ADR D5; presentation revised per operator review). The frames
   * are already in the DOM as div.cadrumo-frame with full token highlighting;
   * without this script the reader sees the complete highlighted transcript.
   *
   * When it runs, the widget is a PLAYHEAD over a rundown: every command line
   * stays visible at all times. Exactly one command is active — highlighted,
   * with its output shown beneath it. Commands after the playhead are dimmed
   * with their highlighting and output suppressed (JS-applied classes the CSS
   * keys on — never a DOM rewrite). Prev/next (and arrow keys) move the
   * playhead; there is no autonomous or timed advance. The widget only toggles
   * state classes and never injects or removes frame content. Each sequence on
   * a page keeps its own independent state. */

  function unescapePayload(text) {
    // The directive escapes </ as <\/ so the inline JSON cannot break out of
    // its script element; reverse that before parsing.
    return text.replace(/<\\\//g, "</");
  }

  function parseSequencePayload(root) {
    var script = root.querySelector("script.cadrumo-sequence-payload");
    if (!script) return null;
    try {
      return JSON.parse(unescapePayload(script.textContent));
    } catch (e) {
      /* A malformed payload never breaks the widget; the playhead is driven by
       * the DOM frames, and the static transcript stays intact. */
      return null;
    }
  }

  function setupSequence(root) {
    // The playhead runs over every frame in document order — setup frames are
    // ordinary steppable frames (no collapsed disclosure); the position
    // indicator counts them too.
    var frames = Array.prototype.slice.call(root.querySelectorAll(".cadrumo-frame"));
    if (frames.length < 2) return; // a single frame is nothing to step through

    // The inline payload is the sequence's build-time contract. If it is absent
    // or malformed, leave the static transcript unenhanced rather than driving a
    // playhead over a sequence whose contract we cannot validate.
    if (parseSequencePayload(root) === null) return;

    var total = frames.length;
    var current = 0;

    /* Output disclosure: each frame's output/stderr block is toggleable by the
     * reader and ONLY by the reader — stepping the playhead never opens or
     * closes an output. The verification caption and its checks stay visible
     * (they are narration, not output). The toggle is a real labelled button
     * with an SVG chevron icon; it is JS-created, so a no-JS reader sees
     * everything. */
    var OUTPUT_SELECTOR = ".cadrumo-frame-output, .cadrumo-frame-stderr";
    var CHEVRON_SVG =
      '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
      '<path d="M5 3l6 5-6 5" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round"/></svg>';

    function setOutputOpen(frame, open) {
      frame.classList.toggle("is-output-open", open);
      var toggle = frame.querySelector(".cadrumo-output-toggle");
      if (toggle) {
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        var label = toggle.querySelector(".cadrumo-output-toggle-label");
        if (label) label.textContent = open ? "Hide output" : "Show output";
      }
    }

    frames.forEach(function (frame) {
      if (!frame.querySelector(OUTPUT_SELECTOR)) return;
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "cadrumo-output-toggle";
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = CHEVRON_SVG; // static icon markup, no user data
      var label = document.createElement("span");
      label.className = "cadrumo-output-toggle-label";
      label.textContent = "Show output";
      toggle.appendChild(label);
      var command = frame.querySelector(".cadrumo-frame-command");
      if (command && command.parentNode === frame) {
        frame.insertBefore(toggle, command.nextSibling);
      } else {
        frame.appendChild(toggle);
      }
      toggle.addEventListener("click", function () {
        setOutputOpen(frame, !frame.classList.contains("is-output-open"));
      });
    });

    var controls = document.createElement("div");
    controls.className = "cadrumo-sequence-controls";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", "Command rundown");

    function button(kind, label, glyph) {
      var el = document.createElement("button");
      el.type = "button";
      el.className = "cadrumo-sequence-btn cadrumo-sequence-btn--" + kind;
      el.setAttribute("aria-label", label);
      el.innerHTML = glyph;
      return el;
    }

    var prevBtn = button("prev", "Previous command", "&#8592;");
    var nextBtn = button("next", "Next command", "&#8594;");

    var indicator = document.createElement("span");
    indicator.className = "cadrumo-sequence-position";
    indicator.setAttribute("aria-live", "polite");
    indicator.setAttribute("aria-atomic", "true");

    controls.appendChild(prevBtn);
    controls.appendChild(indicator);
    controls.appendChild(nextBtn);

    function render() {
      frames.forEach(function (frame, index) {
        // Commands are always visible; only the playhead state changes. The CSS
        // keys on these classes to dim future commands (and drop their
        // highlighting). Output disclosure is entirely the reader's: stepping
        // neither opens nor closes any output.
        frame.classList.toggle("is-active", index === current);
        frame.classList.toggle("is-past", index < current);
        frame.classList.toggle("is-future", index > current);
      });
      indicator.textContent = current + 1 + " / " + total;
      prevBtn.disabled = current === 0;
      nextBtn.disabled = current === total - 1;
    }

    var stepped = null;

    function goTo(index) {
      current = Math.max(0, Math.min(index, total - 1));
      render();
      if (stepped) stepped(current);
    }

    prevBtn.addEventListener("click", function () {
      goTo(current - 1);
    });
    nextBtn.addEventListener("click", function () {
      goTo(current + 1);
    });

    // Place the controls after the final frame so the rundown reads
    // top-to-bottom with its stepper beneath it.
    var anchor = frames[total - 1];
    if (anchor.parentNode) {
      anchor.parentNode.insertBefore(controls, anchor.nextSibling);
    } else {
      root.appendChild(controls);
    }
    root.classList.add("cadrumo-sequence--enhanced");
    render();

    // The page-level keyboard loop drives this block through the controller;
    // button-driven steps report back so the loop cursor stays in sync.
    return {
      count: total,
      goTo: goTo,
      frameAt: function (index) {
        return frames[Math.max(0, Math.min(index, total - 1))];
      },
      onStep: function (callback) {
        stepped = callback;
      },
    };
  }

  /* ── Shell switcher ─────────────────────────────────────────────────────
   * Each command frame carries one div.cadrumo-cmd-variant[data-shell] per
   * declared shell, server-rendered with that shell's wrapping and continuation
   * marker. The CSS shows only the variant matching the root's data-cadrumo-shell
   * (set at build to the default shell, so the correct variant shows without JS).
   * This adds a segmented control that updates data-cadrumo-shell — per-sequence
   * state, no global persistence. A sequence declaring a single shell gets no
   * switcher. */
  function setupShellSwitcher(root) {
    var variants = root.querySelectorAll(".cadrumo-cmd-variant[data-shell]");
    if (!variants.length) return;
    var shells = [];
    Array.prototype.forEach.call(variants, function (variant) {
      var shell = variant.getAttribute("data-shell");
      if (shell && shells.indexOf(shell) === -1) shells.push(shell);
    });
    if (shells.length < 2) return; // one shell — nothing to switch between
    if (!root.getAttribute("data-cadrumo-shell")) {
      root.setAttribute("data-cadrumo-shell", shells[0]);
    }

    var switcher = document.createElement("div");
    switcher.className = "cadrumo-shell-switcher";
    switcher.setAttribute("role", "group");
    switcher.setAttribute("aria-label", "Terminal shell");

    var buttons = shells.map(function (shell) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cadrumo-shell-btn";
      btn.setAttribute("data-shell", shell);
      btn.textContent = shell;
      btn.setAttribute(
        "aria-pressed",
        root.getAttribute("data-cadrumo-shell") === shell ? "true" : "false"
      );
      btn.addEventListener("click", function () {
        selectShell(shell);
      });
      switcher.appendChild(btn);
      return btn;
    });

    function selectShell(shell) {
      root.setAttribute("data-cadrumo-shell", shell);
      buttons.forEach(function (btn) {
        btn.setAttribute(
          "aria-pressed",
          btn.getAttribute("data-shell") === shell ? "true" : "false"
        );
      });
    }

    // Home the switcher in a slim block header bar at the TOP of the sequence,
    // right-aligned; the bottom controls row keeps only prev/next + position.
    var bar = document.createElement("div");
    bar.className = "cadrumo-sequence-bar";
    bar.appendChild(switcher);
    root.insertBefore(bar, root.firstChild);
  }

  /* ── Copy command ───────────────────────────────────────────────────────
   * Every command/result frame carries data-command-line: the single-line
   * authored command (placeholders intact, no prompt, no continuation chars).
   * This adds a copy icon-button that writes it to the clipboard — enhancement
   * only (JS-created), so a no-JS reader still sees the full command. */
  var COPY_SVG =
    '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
    '<rect x="5.4" y="5.4" width="8.1" height="8.1" rx="1.3" fill="none" stroke="currentColor" stroke-width="1.3"/>' +
    '<path d="M3.5 10.5h-.6a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v.6" fill="none" ' +
    'stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var COPIED_MS = 1500;

  function fallbackCopy(text) {
    try {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "absolute";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(area);
      return ok;
    } catch (e) {
      return false;
    }
  }

  function writeClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () {
          return true;
        },
        function () {
          return fallbackCopy(text);
        }
      );
    }
    return Promise.resolve(fallbackCopy(text));
  }

  function setupCopyButtons(root) {
    var frames = root.querySelectorAll(".cadrumo-frame[data-command-line]");
    Array.prototype.forEach.call(frames, function (frame) {
      // Every frame is a visible command the reader can copy (setup frames are
      // no longer folded away).
      var button = document.createElement("button");
      button.type = "button";
      button.className = "cadrumo-copy-btn";
      button.setAttribute("aria-label", "Copy command");
      button.innerHTML = COPY_SVG; // static icon markup, no user data
      var label = document.createElement("span");
      label.className = "cadrumo-copy-label";
      label.setAttribute("aria-hidden", "true");
      button.appendChild(label);

      var timer = null;
      button.addEventListener("click", function () {
        var command = frame.getAttribute("data-command-line") || "";
        writeClipboard(command).then(function (ok) {
          button.classList.add("is-copied");
          label.textContent = ok ? "Copied" : "Copy failed";
          if (timer) window.clearTimeout(timer);
          timer = window.setTimeout(function () {
            button.classList.remove("is-copied");
            label.textContent = "";
          }, COPIED_MS);
        });
      });
      frame.appendChild(button);
    });
  }

  /* Keyboard navigation spans EVERY sequence on the page as one continuous
   * loop: ArrowRight/ArrowLeft step through all frames of all blocks in page
   * order, wrapping from the last frame of the last block back to the first
   * (and the reverse). Typing surfaces and open dialogs are left alone; the
   * loop's active frame is scrolled into view as it moves. */
  function initSequences() {
    var blocks = [];
    document.querySelectorAll("[data-cadrumo-sequence]").forEach(function (root) {
      var controller = setupSequence(root);
      setupShellSwitcher(root);
      setupCopyButtons(root);
      if (controller) blocks.push(controller);
    });
    if (!blocks.length) return;

    var cursor = { block: 0, frame: 0 };

    blocks.forEach(function (block, blockIndex) {
      block.onStep(function (frameIndex) {
        cursor = { block: blockIndex, frame: frameIndex };
      });
    });

    function stepPage(delta) {
      var b = cursor.block;
      var f = cursor.frame + delta;
      if (f >= blocks[b].count) {
        b = (b + 1) % blocks.length;
        f = 0;
      } else if (f < 0) {
        b = (b - 1 + blocks.length) % blocks.length;
        f = blocks[b].count - 1;
      }
      blocks[b].goTo(f);
      cursor = { block: b, frame: f };
      var frame = blocks[b].frameAt(f);
      if (frame && frame.scrollIntoView) {
        frame.scrollIntoView({ block: "nearest" });
      }
    }

    document.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      var target = event.target;
      if (
        target &&
        (target.isContentEditable ||
          /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName || ""))
      ) {
        return;
      }
      if (document.querySelector("dialog[open]")) return;
      event.preventDefault();
      stepPage(event.key === "ArrowRight" ? 1 : -1);
    });
  }

  /* ── CLI token hover help ───────────────────────────────────────────────
   * A verb/option token in a sequence carries a data-command-path key that
   * indexes the build-emitted cli-tree.json help projection (ADR D5). On hover
   * or focus the token opens a popover with that command's live help, usage,
   * and parameters. The projection is fetched once per page, lazily on the
   * first hover intent, over a same-origin relative URL derived from this
   * script's own src; a fetch failure degrades to no hover help (no console
   * noise) and leaves the static transcript untouched. */

  function cliTreeUrl() {
    // Derive _static/cli-tree.json from this script's own src, so the fetch is
    // same-origin and page-depth-independent without hard-coding a path.
    var script = document.querySelector('script[src*="cadrumo-docs.js"]');
    if (!script || !script.src) return null;
    try {
      return new URL("cli-tree.json", script.src).href;
    } catch (e) {
      return null;
    }
  }

  function initHoverHelp() {
    var tokens = document.querySelectorAll(
      ".cadrumo-sequence .cli-tok[data-command-path]"
    );
    if (!tokens.length) return;
    var url = cliTreeUrl();
    if (!url) return;

    var treePromise = null;
    function loadTree() {
      if (treePromise) return treePromise;
      treePromise = fetch(url, { credentials: "same-origin" })
        .then(function (response) {
          return response.ok ? response.json() : null;
        })
        .catch(function () {
          /* Absent projection (e.g. a dev preview built without the emit hook):
           * hover help is simply unavailable, silently. */
          return null;
        });
      return treePromise;
    }

    var popover = document.createElement("div");
    popover.className = "cadrumo-cli-popover";
    popover.id = "cadrumo-cli-popover";
    popover.setAttribute("role", "tooltip");
    popover.hidden = true;
    document.body.appendChild(popover);

    var activeToken = null;
    var intended = null;
    var pinned = false;

    function hide() {
      popover.hidden = true;
      pinned = false;
      if (activeToken) {
        activeToken.removeAttribute("aria-describedby");
        activeToken = null;
      }
    }

    function appendLine(className, text) {
      if (!text) return;
      var el = document.createElement("p");
      el.className = className;
      el.textContent = text;
      popover.appendChild(el);
    }

    function appendParam(param) {
      var li = document.createElement("li");
      var name = document.createElement("span");
      name.className = "cadrumo-cli-popover-param-name";
      name.textContent = (param.names || []).join(", ");
      li.appendChild(name);
      if (param.required) {
        var req = document.createElement("span");
        req.className = "cadrumo-cli-popover-param-req";
        req.textContent = "required";
        li.appendChild(req);
      }
      if (param.help) {
        var help = document.createElement("span");
        help.className = "cadrumo-cli-popover-param-help";
        help.textContent = param.help;
        li.appendChild(help);
      }
      return li;
    }

    function renderNode(node, optionName, isPinned) {
      popover.textContent = "";
      if (isPinned) {
        // A clicked-open popup carries its own explicit close control.
        var close = document.createElement("button");
        close.type = "button";
        close.className = "cadrumo-cli-popover-close";
        close.setAttribute("aria-label", "Close help");
        close.textContent = "×";
        close.addEventListener("click", function () {
          intended = null;
          hide();
        });
        popover.appendChild(close);
      }
      appendLine("cadrumo-cli-popover-path", (node.path || []).join(" "));
      appendLine("cadrumo-cli-popover-usage", node.usage);
      appendLine("cadrumo-cli-popover-help", node.help);
      var params = node.params || [];
      // When the token is a specific option, lead with just that option's
      // parameter; otherwise list the command's parameters.
      var shown = params;
      if (optionName) {
        shown = params.filter(function (param) {
          return (param.names || []).indexOf(optionName) >= 0;
        });
        if (!shown.length) shown = params;
      }
      if (shown.length) {
        var list = document.createElement("ul");
        list.className = "cadrumo-cli-popover-params";
        shown.slice(0, 12).forEach(function (param) {
          list.appendChild(appendParam(param));
        });
        popover.appendChild(list);
      }
    }

    function positionNear(token) {
      var rect = token.getBoundingClientRect();
      var margin = 8;
      var doc = document.documentElement;
      var pw = popover.offsetWidth;
      var ph = popover.offsetHeight;
      var left = rect.left + window.pageXOffset;
      var maxLeft = window.pageXOffset + doc.clientWidth - pw - margin;
      if (left > maxLeft) left = maxLeft;
      if (left < window.pageXOffset + margin) left = window.pageXOffset + margin;
      var top = rect.bottom + window.pageYOffset + 6;
      if (rect.bottom + ph + 12 > doc.clientHeight && rect.top - ph - 6 > 0) {
        top = rect.top + window.pageYOffset - ph - 6;
      }
      popover.style.left = Math.round(left) + "px";
      popover.style.top = Math.round(top) + "px";
    }

    function show(token, pin) {
      var key = token.getAttribute("data-command-path");
      if (!key) return;
      intended = token;
      loadTree().then(function (tree) {
        if (!tree || intended !== token) return; // pointer/focus moved on
        var node = tree[key];
        if (!node) return;
        renderNode(node, token.getAttribute("data-option"), pin === true);
        popover.hidden = false;
        pinned = pin === true;
        activeToken = token;
        token.setAttribute("aria-describedby", popover.id);
        positionNear(token);
        // The popup must always be fully visible: when the viewport-clamped
        // position still leaves it partly off-canvas, scroll it into view.
        popover.scrollIntoView({ block: "nearest", inline: "nearest" });
      });
    }

    tokens.forEach(function (token) {
      if (!token.hasAttribute("tabindex")) token.setAttribute("tabindex", "0");
      // Hover/focus give a transient preview; click PINS the popup until its
      // close button, Escape, an outside click, or another token's pin.
      token.addEventListener("mouseenter", function () {
        if (!pinned) show(token, false);
      });
      token.addEventListener("mouseleave", function () {
        if (!pinned) {
          intended = null;
          hide();
        }
      });
      token.addEventListener("focus", function () {
        if (!pinned) show(token, false);
      });
      token.addEventListener("blur", function () {
        if (!pinned) {
          intended = null;
          hide();
        }
      });
      token.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (pinned && activeToken === token) {
          intended = null;
          hide();
        } else {
          show(token, true);
        }
      });
    });

    // An outside click dismisses a pinned popup (clicks inside it stay).
    document.addEventListener("click", function (event) {
      if (pinned && !popover.hidden && !popover.contains(event.target)) {
        intended = null;
        hide();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !popover.hidden) {
        intended = null;
        hide();
      }
    });
  }

  /* ── Download cards (progressive enhancement) ───────────────────────────
   * The Tier-1 generated table in download.md is the floor: it always renders
   * the channel matrix offline. When a release publishes download-latest.json
   * beside this script, initDownloadCards() fetches it and fills the
   * [data-cadrumo-downloads] mount with the release version and direct asset
   * links. The file is derived from this script's own src (same-origin,
   * page-depth-independent, like cliTreeUrl); a fetch failure or absent file
   * degrades silently and leaves the Tier-1 table untouched. */

  function downloadLatestUrl() {
    var script = document.querySelector('script[src*="cadrumo-docs.js"]');
    if (!script || !script.src) return null;
    try {
      return new URL("download-latest.json", script.src).href;
    } catch (e) {
      return null;
    }
  }

  function renderDownloadCards(mount, data) {
    if (!data || !Array.isArray(data.assets) || !data.assets.length) return;
    while (mount.firstChild) mount.removeChild(mount.firstChild);

    var heading = document.createElement("p");
    heading.className = "cadrumo-downloads-heading";
    heading.textContent = "Direct downloads for the latest release" +
      (data.version ? " (v" + data.version + ")" : "");
    mount.appendChild(heading);

    var list = document.createElement("ul");
    list.className = "cadrumo-downloads-list";
    data.assets.forEach(function (asset) {
      if (!asset || !asset.filename) return;
      var item = document.createElement("li");
      if (asset.url) {
        var link = document.createElement("a");
        link.href = asset.url;
        link.rel = "noopener";
        link.textContent = asset.filename;
        item.appendChild(link);
      } else {
        item.textContent = asset.filename;
      }
      if (asset.kind) {
        var kind = document.createElement("span");
        kind.className = "cadrumo-downloads-kind";
        kind.textContent = " — " + asset.kind;
        item.appendChild(kind);
      }
      list.appendChild(item);
    });
    if (!list.childNodes.length) return;
    mount.appendChild(list);
    mount.hidden = false;
  }

  function initDownloadCards() {
    var mount = document.querySelector("[data-cadrumo-downloads]");
    if (!mount) return;
    var url = downloadLatestUrl();
    if (!url) return;
    fetch(url, { credentials: "same-origin" })
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        renderDownloadCards(mount, data);
      })
      .catch(function () {
        /* Absent payload (dev preview or a build without the emit hook): the
         * Tier-1 table remains the floor. Silently degrade. */
      });
  }

  // Language switcher: close the native details dropdown on outside click or
  // Escape (progressive enhancement; the disclosure works without script).
  function initLanguageSwitcher() {
    var switcher = document.querySelector("details[data-cadrumo-lang]");
    if (!switcher) {
      return;
    }
    document.addEventListener("click", function (event) {
      if (switcher.open && !switcher.contains(event.target)) {
        switcher.open = false;
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && switcher.open) {
        switcher.open = false;
      }
    });
  }

  /* ── Accessibility repairs on theme-generated markup ───────────────── */

  /* Two defects that live in markup this project does not author -- Furo's
   * sidebar captions and the CLI frames' output blocks -- and that no
   * stylesheet can reach, because both are attributes rather than
   * presentation.
   *
   * 1. Sphinx renders a sidebar caption as <p class="caption" role="heading">
   *    with no aria-level. role="heading" REQUIRES aria-level, so a screen
   *    reader gets a heading of undefined rank; axe reports it as a critical
   *    aria-required-attr failure, eight per page. The captions sit above
   *    top-level nav groups inside a <nav>, so level 2 is their real rank.
   *
   * 2. A command frame's output is a <pre> that scrolls, and a block that
   *    scrolls with nothing focusable inside it cannot be reached or panned
   *    by keyboard at all (WCAG 2.1.1). tabindex="0" makes it a stop; a
   *    scrollable region also needs an accessible name once it is focusable,
   *    and role="group" plus a label is the least invasive way to give it
   *    one without inventing visible text.
   *
   * Both are applied at runtime rather than patched into the theme so a Furo
   * upgrade cannot silently drop them. */
  function initA11yRepairs() {
    var captions = document.querySelectorAll('.sidebar-tree .caption[role="heading"]:not([aria-level])');
    Array.prototype.forEach.call(captions, function (caption) {
      caption.setAttribute("aria-level", "2");
    });

    /* Deferred a frame: whether a block overflows is a layout question, and
     * at DOMContentLoaded the web fonts have not necessarily swapped in, so
     * measuring here would sometimes decide a block fits when it will not. */
    requestAnimationFrame(markScrollableOutputs);
  }

  function markScrollableOutputs() {
    var outputs = document.querySelectorAll(".cadrumo-frame-output, .cadrumo-frame-stderr");
    Array.prototype.forEach.call(outputs, function (output) {
      if (output.scrollWidth <= output.clientWidth && output.scrollHeight <= output.clientHeight) return;
      if (!output.hasAttribute("tabindex")) output.setAttribute("tabindex", "0");
      if (!output.hasAttribute("role")) output.setAttribute("role", "group");
      if (!output.hasAttribute("aria-label")) {
        output.setAttribute("aria-label", output.classList.contains("cadrumo-frame-stderr") ? "Command error output" : "Command output");
      }
    });
  }

  ready(function () {
    initBroadcast();
    initNavActive();
    initLanguageSwitcher();
    initCommandBlocks();
    initPalette();
    initSearchPage();
    initSequences();
    initHoverHelp();
    initDownloadCards();
    initA11yRepairs();
  });
})();
