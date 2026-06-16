/* aeat docs interaction layer: broadcast dismiss, header active-link
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
    var strip = document.querySelector(".aeat-broadcast");
    if (!strip) return null;
    return "aeat:broadcast:" + strip.textContent.replace(/\s+/g, " ").trim().slice(0, 120);
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
      document.documentElement.classList.add("aeat-broadcast-dismissed");
    }
    var button = document.querySelector("[data-aeat-broadcast-dismiss]");
    if (!button) return;
    button.addEventListener("click", function () {
      document.documentElement.classList.add("aeat-broadcast-dismissed");
      try {
        window.localStorage.setItem(key, "1");
      } catch (e) {
        /* non-persistent dismissal is fine */
      }
    });
  }

  /* ── Header active-link highlighting ───────────────────────────────── */

  function initNavActive() {
    var links = document.querySelectorAll(".aeat-header-nav-link");
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
      ranges.push([commandStart, commandStart + match[3].length, "aeat-tok-cmd"]);
    }
    FLAG.lastIndex = 0;
    while ((match = FLAG.exec(text)) !== null) {
      var flagStart = match.index + match[1].length;
      ranges.push([flagStart, flagStart + match[2].length, "aeat-tok-flag"]);
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

  function initPalette() {
    var triggers = document.querySelectorAll("[data-aeat-search]");
    if (!triggers.length || typeof HTMLDialogElement === "undefined") return;
    var searchUrl = triggers[0].getAttribute("data-aeat-search-url") || "search.html";

    document.querySelectorAll("[data-aeat-search-kbd]").forEach(function (kbd) {
      kbd.textContent = IS_MAC ? "⌘ K" : "Ctrl K";
    });

    var dialog = document.createElement("dialog");
    dialog.className = "aeat-palette";
    dialog.setAttribute("aria-label", "Search documentation");
    dialog.innerHTML =
      '<div class="aeat-palette-head">' +
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001q.044.06.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1 1 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0"/></svg>' +
      '<input class="aeat-palette-input" type="text" placeholder="Search docs…" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Search query">' +
      '<kbd class="aeat-palette-esc">esc</kbd>' +
      "</div>" +
      '<ul class="aeat-palette-list" role="listbox"></ul>' +
      '<div class="aeat-palette-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div>';
    document.body.appendChild(dialog);

    var input = dialog.querySelector(".aeat-palette-input");
    var list = dialog.querySelector(".aeat-palette-list");
    var entries = null;
    var rows = [];
    var selected = 0;
    var queryToken = 0;

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

    /* Per-kind ranking tier (ADR D5: term cards first, navigation second,
     * full text third). Higher sorts first. The injected `weight` meta is the
     * fine axis within a kind. */
    var KIND_TIER = { concept: 4, cli: 3, casilla: 2, page: 1 };
    var KIND_LABEL = {
      concept: "Term",
      cli: "Command",
      casilla: "Casilla",
      page: "Page",
    };

    function cardFromPagefind(meta, fallbackTitle, url, excerpt) {
      var kind = (meta && meta.kind) || "page";
      var title = (meta && meta.title) || fallbackTitle || url;
      var crumbParts = [KIND_LABEL[kind] || "Result"];
      if (meta && meta.modelo && meta.number) {
        crumbParts.push("Modelo " + meta.modelo + " · " + meta.number);
      } else if (meta && meta.command_path) {
        crumbParts.push(meta.command_path);
      } else if (meta && meta.domain) {
        crumbParts.push(meta.domain);
      }
      var weight = meta && meta.weight ? parseFloat(meta.weight) : 0;
      if (isNaN(weight)) weight = 0;
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
        tierRank: (KIND_TIER[kind] || 1) * 10 + weight,
      };
    }

    function dataToCards(results, limit) {
      return Promise.all(
        results.slice(0, limit).map(function (result) {
          return result.data();
        })
      ).then(function (datas) {
        return datas.map(function (data) {
          return cardFromPagefind(
            data.meta,
            data.meta && data.meta.title,
            data.url,
            data.excerpt
          );
        });
      });
    }

    /* The injected term/casilla/CLI records and the docs pages share one index
     * (the injection files every record under the page language with combined
     * multilingual content, so a Spanish term is found from an English page,
     * and stamps a `weight` sort key on every record). Two passes compose the
     * ADR-D5 ladder reliably:
     *   1. a search SORTED by `weight` returns ONLY the injected records (the
     *      docs pages carry no `weight` key, so Pagefind drops them) ordered by
     *      tier weight (concept 1.0 > cli 0.8 > casilla 0.7) - these are the
     *      term-card tiers, guaranteed above the full text;
     *   2. a normal relevance search yields the full-text page hits (third
     *      tier). A page that is also a card is deduped away in compose(). */
    function searchPagefind(query) {
      return loadPagefind()
        .then(function (pf) {
          if (!pf || typeof pf.search !== "function") return [];
          /* Run the two passes SEQUENTIALLY. Two concurrent searches on one
           * Pagefind instance make the first supersede-cancel the other -
           * Pagefind keeps only the latest in-flight search and resolves the
           * rest to null - which silently emptied the card pass while a reader
           * was still typing. Awaiting each pass in turn removes the
           * self-supersede so both reliably return. */
          return Promise.resolve(
            pf.search(query, { sort: { weight: "desc" } })
          ).then(function (cardRes) {
            return Promise.resolve(pf.search(query)).then(function (pageRes) {
              var cardResults = cardRes && cardRes.results ? cardRes.results : [];
              var pageResults = pageRes && pageRes.results ? pageRes.results : [];
              /* The weight-sorted pass ties every concept card at the flat
               * tier-one weight, so capture each url's relevance rank from the
               * textual pass and carry it onto the card; compose() breaks
               * within-tier ties by it, floating the best textual match to the
               * top of its tier while cards still sit above full-text pages. */
              var relRank = {};
              pageResults.forEach(function (r, i) {
                if (relRank[r.url] === undefined) relRank[r.url] = i;
              });
              return dataToCards(cardResults, 12).then(function (cards) {
                return dataToCards(pageResults, 6).then(function (pages) {
                  var all = cards.concat(pages);
                  all.forEach(function (item) {
                    item.relRank =
                      relRank[item.href] !== undefined
                        ? relRank[item.href]
                        : Number.MAX_SAFE_INTEGER;
                  });
                  return all;
                });
              });
            });
          });
        })
        .catch(function () {
          /* A Pagefind failure degrades to nav-only; it never breaks the
           * palette or leaves an unhandled rejection. */
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
      var ordered = [];
      var cards = (pagefindCards || []).slice().sort(function (a, b) {
        /* Primary axis: the tier rank (concept > cli > casilla > page), so cards
         * always sit above full-text pages. Secondary: an exact/prefix title
         * match, so the concept the operator literally typed leads its tier (the
         * IVA concept for "iva", not VIES). Tertiary: the relevance rank, which
         * orders the remaining within-tier ties and the cross-lingual matches
         * (e.g. "pro rata" -> prorrata) whose title is in another language. */
        if (b.tierRank !== a.tierRank) return b.tierRank - a.tierRank;
        var ma = titleMatch(a.title, query);
        var mb = titleMatch(b.title, query);
        if (mb !== ma) return mb - ma;
        return (a.relRank || 0) - (b.relRank || 0);
      });
      cards.forEach(function (card) {
        if (seenHref[card.href]) return;
        seenHref[card.href] = true;
        ordered.push(card);
      });
      navMatches(query).forEach(function (entry) {
        if (seenHref[entry.href]) return;
        seenHref[entry.href] = true;
        ordered.push(entry);
      });
      ordered.push(fullSearchEntry(query));
      return ordered.slice(0, 18);
    }

    function paint(items) {
      list.textContent = "";
      rows = items.map(function (entry, index) {
        var item = document.createElement("li");
        item.className = "aeat-palette-item";
        if (entry.kind) item.classList.add("aeat-palette-item--" + entry.kind);
        item.setAttribute("role", "option");
        var link = document.createElement("a");
        link.href = entry.href;
        var title = document.createElement("span");
        title.className = "aeat-palette-item-title";
        title.textContent = entry.title;
        link.appendChild(title);
        if (entry.crumb) {
          var crumb = document.createElement("span");
          crumb.className = "aeat-palette-item-crumb";
          crumb.textContent = entry.crumb;
          link.appendChild(crumb);
        }
        if (entry.excerpt) {
          var ex = document.createElement("span");
          ex.className = "aeat-palette-item-excerpt";
          ex.textContent = entry.excerpt;
          link.appendChild(ex);
        }
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
        paint(compose("", []));
        return;
      }
      /* Keep the current results painted until the new query resolves, then
       * swap - so a keystroke never blanks the palette to the bare fallback
       * (the old eager repaint did, and on a transiently-empty Pagefind pass it
       * stuck there). */
      searchPagefind(query)
        .then(function (cards) {
          if (token !== queryToken) return; /* a newer keystroke superseded this */
          paint(compose(query, cards));
        })
        .catch(function () {
          if (token !== queryToken) return;
          paint(compose(query, []));
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

    function open() {
      if (dialog.open) return;
      dialog.showModal();
      input.value = "";
      render("");
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
        render(q);
      }, 130);
    });

    dialog.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        select(selected + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        select(selected - 1);
      } else if (event.key === "Enter") {
        var row = rows[selected];
        var link = row && row.querySelector("a");
        if (link) {
          event.preventDefault();
          window.location.assign(link.href);
        }
      }
    });

    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
  }

  ready(function () {
    initBroadcast();
    initNavActive();
    initCommandBlocks();
    initPalette();
  });
})();
