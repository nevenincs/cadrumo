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

    function fullSearchEntry(query) {
      return {
        title: query ? 'Search the docs for “' + query + '”' : "Open full-text search",
        href: searchUrl + (query ? "?q=" + encodeURIComponent(query) : ""),
        crumb: "Full-text search",
      };
    }

    function render(query) {
      if (entries === null) entries = navIndex();
      var matches;
      if (!query) {
        matches = entries.slice(0, 9);
      } else {
        matches = entries
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
      matches = matches.concat([fullSearchEntry(query)]);

      list.textContent = "";
      rows = matches.map(function (entry, index) {
        var item = document.createElement("li");
        item.className = "aeat-palette-item";
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
        item.appendChild(link);
        item.addEventListener("mousemove", function () {
          select(index);
        });
        list.appendChild(item);
        return item;
      });
      select(0);
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

    input.addEventListener("input", function () {
      render(input.value.trim());
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
