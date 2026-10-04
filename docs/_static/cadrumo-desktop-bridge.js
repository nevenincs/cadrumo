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
 * Page to window: ready {url, title, lang, theme}, location {url, title},
 * theme {theme}, shortcut {id}, open-external {url},
 * context-menu {x, y, selection, link: {href, external} | null}.
 * Window to page: keymap {chords: [{id, code, ctrlKey, shiftKey, altKey,
 * metaKey}]}, command {name: back | forward | open-search},
 * zoom {factor: 0.5 to 2.0}.
 *
 * An unknown type is ignored. A known channel with another version, or a
 * malformed message of a known type, is refused and logged without its
 * contents. The bridge carries the fields above and nothing else: it never
 * reads, keeps or forwards any other field of a message it receives. */
(function () {
  "use strict";

  var CHANNEL = "cadrumo-desktop";
  var VERSION = 1;
  var MAX_SELECTION = 65536;
  var MAX_CHORDS = 64;
  var MAX_CHORD_ID = 64;
  var MAX_CHORD_CODE = 32;
  var MIN_ZOOM = 0.5;
  var MAX_ZOOM = 2.0;
  var LOG_PREFIX = "cadrumo-desktop-bridge: ";

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

  var HANDLERS = { keymap: applyKeymap, command: applyCommand, zoom: applyZoom };

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

  /* Registered on the window in the capture phase, before any page script
   * runs, so a shell chord is taken before a listener on the document or any
   * element sees the key. */
  window.addEventListener(
    "keydown",
    function (event) {
      if (event.isComposing || !chords.length) return;
      for (var i = 0; i < chords.length; i++) {
        var chord = chords[i];
        if (
          chord.code === event.code &&
          chord.ctrlKey === event.ctrlKey &&
          chord.shiftKey === event.shiftKey &&
          chord.altKey === event.altKey &&
          chord.metaKey === event.metaKey
        ) {
          event.preventDefault();
          event.stopImmediatePropagation();
          post("shortcut", { id: chord.id });
          return;
        }
      }
    },
    true
  );

  function linkFor(target) {
    var element = target && target.nodeType === 1 ? target : target && target.parentElement;
    var anchor = element && element.closest ? element.closest("a[href]") : null;
    if (!anchor) return null;
    var url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (e) {
      return null;
    }
    if (url.protocol === "javascript:") return null;
    return { href: url.href, external: url.origin !== window.location.origin };
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
      });
    },
    true
  );

  /* One fragment navigation can fire both popstate and hashchange; the shell
   * hears about each address once. */
  var lastUrl = window.location.href;

  function reportLocation() {
    var url = window.location.href;
    if (url === lastUrl) return;
    lastUrl = url;
    post("location", { url: url, title: document.title });
  }

  window.addEventListener("hashchange", reportLocation);
  window.addEventListener("popstate", reportLocation);

  function announce() {
    lastUrl = window.location.href;
    post("ready", {
      url: window.location.href,
      title: document.title,
      lang: document.documentElement.lang || "",
      theme: currentTheme(),
    });
    var lastTheme = currentTheme();
    new MutationObserver(function () {
      var theme = currentTheme();
      if (theme === lastTheme) return;
      lastTheme = theme;
      post("theme", { theme: theme });
    }).observe(document.body, { attributes: true, attributeFilter: ["data-theme"] });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", announce);
  } else {
    announce();
  }
})();
