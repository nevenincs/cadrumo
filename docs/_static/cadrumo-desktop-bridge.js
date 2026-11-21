/* Cadrumo desktop frame bridge.
 *
 * Loaded only by the desktop documentation flavor, before cadrumo-docs.js.
 * In the desktop application every page runs inside the window's documentation
 * frame, on its own origin; this script is the one channel between the page
 * and the window that hosts it. It exchanges window.postMessage envelopes
 *
 *   {channel: "cadrumo-desktop", version: 1, type: <string>, ...fields}
 *
 * with exactly one peer: the parent window, which must be the top window. Its
 * origin is the one the browser reports for the embedding window
 * (location.ancestorOrigins), so the page never names or trusts an origin of
 * its own choosing; which windows may embed the page at all is the
 * documentation server's frame-ancestors policy. Every message is addressed to
 * that exact origin, and an incoming message is read only when its source is
 * the parent window and its origin is that origin. Opened any other way, the
 * script does nothing.
 *
 * Page to window: ready {url, title, lang, theme, features, entry, traversed},
 * location {url, title, entry, traversed}, theme {theme}, shortcut {id}, open-external {url},
 * context-menu {x, y, selection, link: {href, external} | null, pointer},
 * search-progress {id} while the accepted request is active, then
 * search-results {id, results: [{kind, title, url, excerpt, ranges, crumb}]}.
 * Window to page: keymap {chords: [{id, code, ctrlKey, shiftKey, altKey,
 * metaKey}]}, command {name: back | forward | open-search | home} and
 * command {name: navigate, url}, zoom {factor: 0.5 to 2.0},
 * search {id, query, limit}, appearance {theme: auto | light | dark}.
 *
 * entry is the place of the page's history entry in the frame's own history,
 * counted from 0 for the first page the frame showed; traversed is true when
 * the page came back to an entry it already had (a Back, a Forward or a
 * reload), and false for a new entry, which drops every entry that lay ahead.
 * The window cannot read the frame's history across origins, so this is how
 * it knows whether Back and Forward can move the page, whoever moved it. The
 * place is kept in the entry's own history.state and, for the next page the
 * frame opens, in the frame's window.name, which a new frame starts empty. A
 * page script that replaces the entry's state (Sphinx does on every page
 * load) keeps the place, and one that pushes a new entry reports it.
 *
 * `features` in ready lists exactly the later additions this page can serve:
 * "search" when cadrumo-docs.js has exposed its search, "navigate", "home"
 * when the page links its language root, and "appearance".
 *
 * Search answers with the ranked rows of the page's own search controller
 * (cadrumo-docs.js), in its order, cut to `limit`. A query holds at most 256
 * characters and a limit is an integer from 1 to 50; an id is a string of at
 * most 64 characters with at most one search in flight under it, and at most
 * eight searches are in flight at once. A blank query is answered with no
 * results. Each result's excerpt is plain text and `ranges` lists its matches
 * as [start, end) offsets in UTF-16 code units, the indices String.slice
 * takes: Pagefind's own <mark> matches for a page excerpt, and the
 * case-insensitive occurrences of the query's words for a card summary. Only
 * results on this page's own origin are sent.
 *
 * navigate goes only to an absolute URL on this page's own origin. home goes
 * to the root of the language this page belongs to, which is the target of
 * the page's own brand link: every page renders it from Sphinx's
 * pathto(master_doc), the same computation the language switcher uses. The
 * docs manifest the window reads is not available inside the page, and that
 * link is the entry the manifest records for this language.
 *
 * appearance applies a theme the way Furo's own toggle does, through
 * document.body.dataset.theme and localStorage.theme, and is echoed by one
 * theme report; "auto" hands the choice back to the page's toggle.
 *
 * Ctrl or Cmd+K inside the page, and a click on the page's own search
 * trigger, are relayed as shortcut {id: "palette.open"} so the window's
 * palette is the only one; the page's palette does not open.
 *
 * language {language, entry} follows the host choice through the generated
 * switcher link, preserving the fragment; entry is the same-origin fallback.
 * A switcher click sends language-change {language} and waits for that choice.
 *
 * An unknown type is ignored. A known channel with another version, or a
 * malformed message of a known type, is refused and logged without its
 * contents. The bridge carries the fields above and nothing else: it never
 * reads, keeps or forwards any other field of a message it receives. */
(function () {
  "use strict";

  var CHANNEL = "cadrumo-desktop";
  var VERSION = 1;
  var SEARCH_PROGRESS_MS = 2000;
  var MAX_SELECTION = 65536;
  var MAX_CHORDS = 64;
  var MAX_CHORD_ID = 64;
  var MAX_CHORD_CODE = 32;
  var MIN_ZOOM = 0.5;
  var MAX_ZOOM = 2.0;
  var MAX_URL = 4096;
  var MAX_SEARCH_ID = 64;
  var MAX_QUERY = 256;
  var MAX_SEARCH_LIMIT = 50;
  var MAX_SEARCHES_IN_FLIGHT = 8;
  var PALETTE_SHORTCUT = "palette.open";
  var SEARCH_TRIGGER = "[data-cadrumo-search]";
  /* Both links are rendered from pathto(master_doc): Cadrumo's header brand
   * and Furo's own page-header brand, which every Furo page carries. */
  var LANGUAGE_ROOT_LINK = "a.cadrumo-header-brand[href], .header-center > a[href]";
  var LOG_PREFIX = "cadrumo-desktop-bridge: ";
  var ENTRY_STATE = "cadrumoEntry";
  var ENTRY_NAME = "cadrumo-docs-entry:";

  if (window.parent === window) return;
  if (window.parent !== window.top) {
    console.warn(LOG_PREFIX + "inactive: the page is not framed directly by the top window");
    return;
  }
  var ancestors = window.location.ancestorOrigins;
  var shellOrigin = ancestors && ancestors.length ? ancestors[0] : null;
  if (!shellOrigin || shellOrigin === "null") {
    console.warn(LOG_PREFIX + "inactive: the browser reports no origin for the embedding window");
    return;
  }
  var shell = window.parent;

  function post(type, fields) {
    var message = { channel: CHANNEL, version: VERSION, type: type };
    for (var key in fields) {
      if (Object.prototype.hasOwnProperty.call(fields, key)) message[key] = fields[key];
    }
    shell.postMessage(message, shellOrigin);
  }

  function refuse(reason) {
    console.warn(LOG_PREFIX + "refused message: " + reason);
  }

  function currentTheme() {
    var theme = document.body ? document.body.dataset.theme : null;
    return theme === "light" || theme === "dark" ? theme : "auto";
  }

  /* Compared by scheme and host rather than URL.origin, which is "null" for
   * every non-special scheme, so a documentation URL on a custom scheme would
   * otherwise compare equal to any other opaque URL. */
  function onThisOrigin(url) {
    var here = window.location;
    return !!here.host && url.protocol === here.protocol && url.host === here.host;
  }

  /* A URL on this page's own origin, or null. Without `base`, only an
   * absolute URL parses. */
  function documentationUrl(value, base) {
    if (typeof value !== "string" || value.length > MAX_URL) return null;
    var url;
    try {
      url = base === undefined ? new URL(value) : new URL(value, base);
    } catch (e) {
      return null;
    }
    return onThisOrigin(url) ? url : null;
  }

  function languageRoot() {
    var link = document.querySelector(LANGUAGE_ROOT_LINK);
    var url = link ? documentationUrl(link.getAttribute("href"), document.baseURI) : null;
    if (url) url.hash = "";
    return url;
  }

  /* Generated switcher links already know which pages exist in each root. */
  function languageLink(language) {
    var links = document.querySelectorAll("a.cadrumo-header-lang-item[lang][href]");
    for (var i = 0; i < links.length; i++) {
      if (links[i].getAttribute("lang") === language) return links[i];
    }
    return null;
  }

  function applyLanguage(data) {
    var language = data.language;
    if (typeof language !== "string" || !/^[a-z]{2,3}$/.test(language)) return refuse("invalid language");
    if (document.documentElement.lang === language) return;
    var link = languageLink(language);
    var target = link ? documentationUrl(link.getAttribute("href"), document.baseURI) : documentationUrl(data.entry);
    if (!target) return refuse("language has no documentation target");
    if (!target.hash) target.hash = window.location.hash;
    if (target.href !== window.location.href) window.location.assign(target.href);
  }

  function searchFunction() {
    var docs = window.CadrumoDocs;
    return docs && typeof docs.search === "function" ? docs.search : null;
  }

  /* ── Window to page ─────────────────────────────────────────────────── */

  var chords = [];

  function readChord(entry) {
    if (!entry || typeof entry !== "object") return null;
    var id = entry.id;
    var code = entry.code;
    if (typeof id !== "string" || !id || id.length > MAX_CHORD_ID) return null;
    if (typeof code !== "string" || !code || code.length > MAX_CHORD_CODE) return null;
    var chord = { id: id, code: code };
    var modifiers = ["ctrlKey", "shiftKey", "altKey", "metaKey"];
    for (var i = 0; i < modifiers.length; i++) {
      var value = entry[modifiers[i]];
      if (value === undefined) value = false;
      if (typeof value !== "boolean") return null;
      chord[modifiers[i]] = value;
    }
    return chord;
  }

  function applyKeymap(data) {
    var list = data.chords;
    if (!Array.isArray(list) || list.length > MAX_CHORDS) return refuse("keymap chords are not a bounded list");
    var next = [];
    for (var i = 0; i < list.length; i++) {
      var chord = readChord(list[i]);
      if (chord === null) return refuse("keymap holds a malformed chord");
      next.push(chord);
    }
    chords = next;
  }

  function applyCommand(data) {
    var name = data.name;
    if (name === "back") {
      window.history.back();
    } else if (name === "forward") {
      window.history.forward();
    } else if (name === "open-search") {
      var docs = window.CadrumoDocs;
      if (docs && typeof docs.openSearch === "function") {
        window.focus();
        docs.openSearch();
      } else {
        refuse("this page has no search palette");
      }
    } else if (name === "navigate") {
      var target = documentationUrl(data.url);
      if (target === null) return refuse("navigate URL is not on the documentation origin");
      window.location.assign(target.href);
    } else if (name === "home") {
      var root = languageRoot();
      if (root === null) return refuse("this page links no language root");
      window.location.assign(root.href);
    } else {
      refuse("unknown command");
    }
  }

  function applyZoom(data) {
    var factor = data.factor;
    if (typeof factor !== "number" || !isFinite(factor) || factor < MIN_ZOOM || factor > MAX_ZOOM) {
      return refuse("zoom factor outside 0.5 to 2.0");
    }
    document.documentElement.style.zoom = factor === 1 ? "" : String(factor);
  }

  var lastTheme = null;

  function reportTheme(always) {
    var theme = currentTheme();
    if (!always && theme === lastTheme) return;
    lastTheme = theme;
    post("theme", { theme: theme });
  }

  function applyAppearance(data) {
    var theme = data.theme;
    if (theme !== "auto" && theme !== "light" && theme !== "dark") {
      return refuse("appearance theme is not auto, light or dark");
    }
    document.body.dataset.theme = theme;
    try {
      window.localStorage.setItem("theme", theme);
    } catch (e) {
      /* Storage unavailable: the theme holds for this page only. */
    }
    reportTheme(true);
  }

  /* ── Search ─────────────────────────────────────────────────────────── */

  function mergeRanges(ranges) {
    ranges.sort(function (a, b) {
      return a[0] - b[0];
    });
    var merged = [];
    for (var i = 0; i < ranges.length; i++) {
      var last = merged[merged.length - 1];
      if (last && ranges[i][0] <= last[1]) {
        if (ranges[i][1] > last[1]) last[1] = ranges[i][1];
      } else {
        merged.push([ranges[i][0], ranges[i][1]]);
      }
    }
    return merged;
  }

  /* Pagefind's excerpt is markup: words with entities and <mark> matches.
   * DOMParser builds an inert document, so nothing in it runs or loads; only
   * its text is kept, with each run inside a <mark> recorded as a range. */
  function excerptFromMarkup(markup) {
    var body = new DOMParser().parseFromString(markup, "text/html").body;
    var text = "";
    var ranges = [];
    function walk(node, marked) {
      for (var child = node.firstChild; child; child = child.nextSibling) {
        if (child.nodeType === 3) {
          var start = text.length;
          text += child.nodeValue;
          if (marked && text.length > start) ranges.push([start, text.length]);
        } else if (child.nodeType === 1) {
          walk(child, marked || child.tagName === "MARK");
        }
      }
    }
    if (body) walk(body, false);
    return { text: text, ranges: mergeRanges(ranges) };
  }

  /* A card summary is plain text; its ranges are where the query's words
   * occur in it, ignoring case. */
  function excerptFromText(text, query) {
    var words = query.split(/\s+/);
    var ranges = [];
    for (var i = 0; i < words.length; i++) {
      if (!words[i]) continue;
      var pattern = new RegExp(words[i].replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&"), "giu");
      var match;
      while ((match = pattern.exec(text)) !== null) {
        ranges.push([match.index, match.index + match[0].length]);
      }
    }
    return { text: text, ranges: mergeRanges(ranges) };
  }

  function searchResults(items, query, limit) {
    var results = [];
    if (!Array.isArray(items)) return results;
    for (var i = 0; i < items.length && results.length < limit; i++) {
      var item = items[i];
      if (!item || typeof item.title !== "string" || typeof item.href !== "string") continue;
      var url = documentationUrl(item.href, document.baseURI);
      if (url === null) continue;
      var raw = typeof item.excerpt === "string" ? item.excerpt : "";
      var excerpt = item.excerptIsMarkup === true ? excerptFromMarkup(raw) : excerptFromText(raw, query);
      results.push({
        kind: typeof item.kind === "string" && item.kind ? item.kind : "page",
        title: item.title,
        url: url.href,
        excerpt: excerpt.text,
        ranges: excerpt.ranges,
        crumb: typeof item.crumb === "string" ? item.crumb : "",
      });
    }
    return results;
  }

  var searchesInFlight = Object.create(null);
  var searchCount = 0;

  function applySearch(data) {
    var id = data.id;
    var query = data.query;
    var limit = data.limit;
    if (typeof id !== "string" || !id || id.length > MAX_SEARCH_ID) return refuse("search id is not a bounded string");
    if (typeof query !== "string" || query.length > MAX_QUERY) return refuse("search query is not a bounded string");
    if (typeof limit !== "number" || Math.floor(limit) !== limit || limit < 1 || limit > MAX_SEARCH_LIMIT) {
      return refuse("search limit outside 1 to 50");
    }
    var search = searchFunction();
    if (search === null) return refuse("this page has no search");
    if (searchesInFlight[id] === true) return refuse("a search with this id is in flight");
    var words = query.trim();
    if (!words) return post("search-results", { id: id, results: [] });
    if (searchCount >= MAX_SEARCHES_IN_FLIGHT) return refuse("too many searches in flight");
    searchesInFlight[id] = true;
    searchCount += 1;
    // A cold Pagefind load and its sequential ranking passes can exceed the
    // shell's silence deadline. Report that this accepted request is still
    // alive without changing the one final search-results answer.
    post("search-progress", { id: id });
    var heartbeat = window.setInterval(function () {
      post("search-progress", { id: id });
    }, SEARCH_PROGRESS_MS);
    Promise.resolve()
      .then(function () {
        return search(words);
      })
      .then(
        function (items) {
          return searchResults(items, words, limit);
        },
        function () {
          return [];
        }
      )
      .then(function (results) {
        delete searchesInFlight[id];
        searchCount -= 1;
        window.clearInterval(heartbeat);
        post("search-results", { id: id, results: results });
      }, function () {
        delete searchesInFlight[id];
        searchCount -= 1;
        window.clearInterval(heartbeat);
        post("search-results", { id: id, results: [] });
      });
  }

  var HANDLERS = {
    keymap: applyKeymap,
    command: applyCommand,
    zoom: applyZoom,
    search: applySearch,
    appearance: applyAppearance,
    language: applyLanguage,
  };

  window.addEventListener("message", function (event) {
    if (event.source !== shell || event.origin !== shellOrigin) return;
    var data = event.data;
    if (!data || typeof data !== "object" || data.channel !== CHANNEL) return;
    if (data.version !== VERSION) return refuse("unsupported version");
    var type = data.type;
    if (typeof type !== "string" || !Object.prototype.hasOwnProperty.call(HANDLERS, type)) return;
    HANDLERS[type](data);
  });

  /* ── Page to window ─────────────────────────────────────────────────── */

  function relayShortcut(event, id) {
    event.preventDefault();
    event.stopImmediatePropagation();
    post("shortcut", { id: id });
  }

  /* Registered on the window in the capture phase, before any page script
   * runs, so a shell chord is taken before a listener on the document or any
   * element sees the key. The shell's chords come first; Ctrl or Cmd+K, the
   * page palette's own key, is relayed whether or not the shell sent it. */
  window.addEventListener(
    "keydown",
    function (event) {
      if (event.isComposing) return;
      for (var i = 0; i < chords.length; i++) {
        var chord = chords[i];
        if (
          chord.code === event.code &&
          chord.ctrlKey === event.ctrlKey &&
          chord.shiftKey === event.shiftKey &&
          chord.altKey === event.altKey &&
          chord.metaKey === event.metaKey
        ) {
          return relayShortcut(event, chord.id);
        }
      }
      if ((event.ctrlKey || event.metaKey) && (event.code === "KeyK" || String(event.key).toLowerCase() === "k")) {
        relayShortcut(event, PALETTE_SHORTCUT);
      }
    },
    true
  );

  function elementOf(target) {
    return target && target.nodeType === 1 ? target : target && target.parentElement;
  }

  /* The page's search trigger opens the window's palette instead of its own. */
  window.addEventListener(
    "click",
    function (event) {
      var element = elementOf(event.target);
      if (element && element.closest && element.closest(SEARCH_TRIGGER)) {
        relayShortcut(event, PALETTE_SHORTCUT);
      }
    },
    true
  );

  /* The canonical host choice settles before any cross-language navigation. */
  window.addEventListener("click", function (event) {
    var element = elementOf(event.target);
    var anchor = element && element.closest ? element.closest("a.cadrumo-header-lang-item[lang][href]") : null;
    if (!anchor) return;
    var language = anchor.getAttribute("lang");
    var target = documentationUrl(anchor.getAttribute("href"), document.baseURI);
    if (!target || !/^[a-z]{2,3}$/.test(language)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    post("language-change", { language: language });
  }, true);

  function linkFor(target) {
    var element = elementOf(target);
    var anchor = element && element.closest ? element.closest("a[href]") : null;
    if (!anchor) return null;
    var url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (e) {
      return null;
    }
    if (url.protocol === "javascript:") return null;
    return { href: url.href, external: !onThisOrigin(url) };
  }

  /* A link that leaves this origin opens outside the window; the window
   * decides which schemes it accepts. */
  function interceptExternal(event) {
    if (event.type === "auxclick" && event.button !== 1) return;
    var link = linkFor(event.target);
    if (!link || !link.external) return;
    event.preventDefault();
    post("open-external", { url: link.href });
  }

  window.addEventListener("click", interceptExternal, true);
  window.addEventListener("auxclick", interceptExternal, true);

  function selectedText() {
    var active = document.activeElement;
    if (active && /^(INPUT|TEXTAREA)$/.test(active.tagName) && typeof active.selectionStart === "number") {
      return active.value.substring(active.selectionStart, active.selectionEnd);
    }
    var selection = window.getSelection();
    return selection ? String(selection) : "";
  }

  /* A menu opened from the keyboard (Shift+F10 or the menu key) rather than
   * by a pointer. Chromium reports such an event with pointerType "mouse" and
   * detail 0, exactly as it does a right-click, and tells them apart only by
   * button: -1 from the keyboard, the pressed button from a pointer. An empty
   * pointerType is the Pointer Events form of the same fact. */
  function openedByKeyboard(event) {
    return event.pointerType === "" || event.button === -1;
  }

  /* Coordinates are in this frame's viewport pixels, whatever the page zoom,
   * so the window adds only the frame's own position. */
  window.addEventListener(
    "contextmenu",
    function (event) {
      event.preventDefault();
      post("context-menu", {
        x: Math.round(event.clientX),
        y: Math.round(event.clientY),
        selection: selectedText().slice(0, MAX_SELECTION),
        link: linkFor(event.target),
        pointer: !openedByKeyboard(event),
      });
    },
    true
  );

  /* A state with the entry's place added, without changing the caller's own. */
  function withPlace(state, place) {
    var next = {};
    if (state && typeof state === "object") {
      for (var key in state) {
        if (Object.prototype.hasOwnProperty.call(state, key)) next[key] = state[key];
      }
    }
    next[ENTRY_STATE] = place;
    return next;
  }

  /* The place this document's script last read or stamped. */
  var currentPlace = null;
  var nativeReplaceState = window.history.replaceState;
  var nativePushState = window.history.pushState;
  function replaceKeepingPlace(state, title, url) {
    var kept = currentPlace === null ? state : withPlace(state, currentPlace.entry);
    return nativeReplaceState.call(window.history, kept, title, url);
  }
  window.history.replaceState = replaceKeepingPlace;
  window.history.pushState = function (state, title, url) {
    var place = currentPlace === null ? 0 : currentPlace.entry + 1;
    var result = nativePushState.call(window.history, withPlace(state, place), title, url);
    window.name = ENTRY_NAME + place;
    currentPlace = { entry: place, traversed: false };
    reportLocation(currentPlace);
    return result;
  };

  /* The place of the current history entry. An entry this bridge already
   * stamped is one the frame came back to; any other is new, one past the
   * entry the frame was on, and is stamped now so a later return knows it. */
  function placeEntry() {
    var state = window.history.state;
    var stamped = state && typeof state === "object" ? state[ENTRY_STATE] : undefined;
    var place;
    var traversed = typeof stamped === "number" && stamped >= 0 && Math.floor(stamped) === stamped;
    if (traversed) {
      place = stamped;
    } else {
      var name = typeof window.name === "string" ? window.name : "";
      var before = name.indexOf(ENTRY_NAME) === 0 ? Number(name.slice(ENTRY_NAME.length)) : NaN;
      place = before >= 0 && Math.floor(before) === before ? before + 1 : 0;
      nativeReplaceState.call(window.history, withPlace(state, place), "");
    }
    window.name = ENTRY_NAME + place;
    currentPlace = { entry: place, traversed: traversed };
    return currentPlace;
  }

  /* Read now, before any page script replaces the state on load. */
  placeEntry();

  /* One fragment navigation can fire both popstate and hashchange; the shell
   * hears about each address once. A page restored from the back-forward
   * cache runs no script again, so its return is reported as well. */
  var lastUrl = window.location.href;

  function reportLocation(known) {
    var url = window.location.href;
    if (url === lastUrl) return;
    lastUrl = url;
    var place = known && typeof known.entry === "number" ? known : placeEntry();
    post("location", { url: url, title: document.title, entry: place.entry, traversed: place.traversed });
  }

  window.addEventListener("hashchange", reportLocation);
  window.addEventListener("popstate", reportLocation);
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    lastUrl = null;
    reportLocation();
  });

  function features() {
    var list = [];
    if (searchFunction() !== null) list.push("search");
    list.push("navigate");
    if (languageRoot() !== null) list.push("home");
    list.push("appearance");
    list.push("language");
    return list;
  }

  function announce() {
    lastUrl = window.location.href;
    lastTheme = currentTheme();
    var place = currentPlace;
    post("ready", {
      url: window.location.href,
      title: document.title,
      lang: document.documentElement.lang || "",
      theme: lastTheme,
      features: features(),
      entry: place.entry,
      traversed: place.traversed,
    });
    new MutationObserver(function () {
      reportTheme(false);
    }).observe(document.body, { attributes: true, attributeFilter: ["data-theme"] });
  }

  /* cadrumo-docs.js loads after this script and exposes its search while it
   * evaluates, so the announcement waits until every page script has run. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", announce);
  } else {
    window.setTimeout(announce, 0);
  }
})();
