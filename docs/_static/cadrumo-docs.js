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

  /* ── Rung-2 static semantic seam (source-only, fail closed) ────────────
   * Update 6 authorises a browser reader for a future, measured artifact. It
   * does not author a default URL, a threshold, a model download, or a second
   * result authority. The only enablement surface is the explicit
   * `window.__CADRUMO_SEARCH_RUNG2__` configuration emitted beside a future
   * build. With no configuration, or with any incomplete/tampered payload,
   * this seam returns no candidates and the existing Pagefind ladder remains
   * authoritative.
   *
   * Config v1 shape (all values are required before the tier can run):
   *   {
   *     schema_version: "cadrumo.docs-search.rung2-config.v1",
   *     enabled: true,
   *     normalization_version: RUNG2_NORMALIZATION_VERSION,
   *     bundle_url, bundle_sha256,
   *     acceptance: {
   *       approved: true,
   *       minimum_coverage_ratio, cosine_floor, runner_up_margin,
   *       maximum_quantization_drift, measured_quantization_drift,
   *       payload_bytes, quantization_accepted, held_out_top_five_loss,
   *       held_out_miss_rate, no_locale_or_kind_regression,
   *     },
   *   }
   *
   * The bundle is the schema-v1 Rung2SearchBundle emitted by _rung2_bridge.py:
   * it contains the schema-v3 matrix, hash-linked bridge, and authoritative
   * record manifest under one measured byte bound. URLs are consumed only
   * from that manifest; this code never parses an id or constructs a target. */
  var RUNG2_CONFIG_SCHEMA = "cadrumo.docs-search.rung2-config.v1";
  var RUNG2_NORMALIZATION_VERSION = "unicode-word-runs-nfkc-lower-v1";
  var RUNG2_BUNDLE_SCHEMA_VERSION = 1;
  var RUNG2_MATRIX_SCHEMA_VERSION = 3;
  var RUNG2_MODEL_REPOSITORY = "minishlab/potion-multilingual-128M";
  var RUNG2_MODEL_REVISION = "e7421cd79c75fc506b88bb75723ae0a234994720";
  var RUNG2_MODEL_LICENSE = "MIT";
  var RUNG2_DIMENSION = 256;
  var RUNG2_MAX_PAYLOAD_BYTES = 3000000;
  var RUNG2_QUANTIZATION = "symmetric-per-row-int8-f32-v1";
  var RUNG2_ROW_ORDER = "canonical-utf8-byte-order-v1";
  var RUNG2_HEX40 = /^[0-9a-f]{40}$/;
  var RUNG2_HEX64 = /^[0-9a-f]{64}$/;
  var RUNG2_TOKEN_PATTERN = null;
  try {
    /* Property escapes are part of the pinned browser algorithm. An older
     * engine therefore disables Rung 2 instead of silently changing recall. */
    RUNG2_TOKEN_PATTERN = new RegExp("[\\p{L}\\p{N}][\\p{L}\\p{N}\\p{M}]*", "gu");
  } catch (e) {
    RUNG2_TOKEN_PATTERN = null;
  }
  var RUNG2_BUNDLE_PROMISE = null;

  function rung2Has(value, key) {
    return Object.prototype.hasOwnProperty.call(value, key);
  }

  function rung2Object(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error(label + " must be an object");
    }
    return value;
  }

  function rung2Keys(value, allowed, label) {
    var keys = Object.keys(value);
    for (var i = 0; i < keys.length; i++) {
      if (allowed.indexOf(keys[i]) < 0) {
        throw new Error(label + " contains an unknown field");
      }
    }
  }

  function rung2RequiredString(value, key, label) {
    if (!rung2Has(value, key) || typeof value[key] !== "string" || !value[key]) {
      throw new Error(label + "." + key + " is required");
    }
    return value[key];
  }

  function rung2Hex(value, label) {
    if (typeof value !== "string" || !RUNG2_HEX64.test(value)) {
      throw new Error(label + " must be a lowercase SHA-256 hex digest");
    }
    return value;
  }

  function rung2Finite(value, label) {
    if (typeof value !== "number" || !isFinite(value)) {
      throw new Error(label + " must be finite");
    }
    return value;
  }

  function rung2Bounded(value, minimum, maximum, label) {
    rung2Finite(value, label);
    if (value < minimum || value > maximum) {
      throw new Error(label + " is outside its approved range");
    }
    return value;
  }

  function rung2Integer(value, minimum, maximum, label) {
    if (typeof value !== "number" || !isFinite(value) || Math.floor(value) !== value) {
      throw new Error(label + " must be an integer");
    }
    if (value < minimum || value > maximum) {
      throw new Error(label + " is outside its approved range");
    }
    return value;
  }

  function rung2Normalize(value) {
    if (typeof value !== "string" || !RUNG2_TOKEN_PATTERN || typeof value.normalize !== "function") {
      return null;
    }
    var normalized = value.normalize("NFKC").toLowerCase();
    if (Array.from(normalized).length > 160) return null;
    var tokens = normalized.match(RUNG2_TOKEN_PATTERN) || [];
    return { text: tokens.join(" "), tokens: tokens };
  }

  function rung2NormalizeTerm(value) {
    var normalized = rung2Normalize(value);
    return normalized && normalized.text ? normalized.text : null;
  }

  function rung2Utf8Bytes(value) {
    var bytes = [];
    for (var i = 0; i < value.length; i++) {
      var codePoint = value.charCodeAt(i);
      if (codePoint >= 0xd800 && codePoint <= 0xdbff) {
        var low = value.charCodeAt(i + 1);
        if (low >= 0xdc00 && low <= 0xdfff) {
          codePoint = 0x10000 + ((codePoint - 0xd800) << 10) + (low - 0xdc00);
          i += 1;
        } else {
          throw new Error("unpaired surrogate in UTF-8 value");
        }
      } else if (codePoint >= 0xdc00 && codePoint <= 0xdfff) {
        throw new Error("unpaired surrogate in UTF-8 value");
      }
      if (codePoint <= 0x7f) {
        bytes.push(codePoint);
      } else if (codePoint <= 0x7ff) {
        bytes.push(0xc0 | (codePoint >> 6), 0x80 | (codePoint & 0x3f));
      } else if (codePoint <= 0xffff) {
        bytes.push(
          0xe0 | (codePoint >> 12),
          0x80 | ((codePoint >> 6) & 0x3f),
          0x80 | (codePoint & 0x3f)
        );
      } else {
        bytes.push(
          0xf0 | (codePoint >> 18),
          0x80 | ((codePoint >> 12) & 0x3f),
          0x80 | ((codePoint >> 6) & 0x3f),
          0x80 | (codePoint & 0x3f)
        );
      }
    }
    return bytes;
  }

  function rung2Utf8Compare(left, right) {
    var a = rung2Utf8Bytes(left);
    var b = rung2Utf8Bytes(right);
    var length = Math.min(a.length, b.length);
    for (var i = 0; i < length; i++) {
      if (a[i] !== b[i]) return a[i] - b[i];
    }
    return a.length - b.length;
  }

  function rung2Sha256(bytes) {
    if (!window.crypto || !window.crypto.subtle) return Promise.reject(new Error("Web Crypto unavailable"));
    return window.crypto.subtle.digest("SHA-256", bytes).then(function (digest) {
      var view = new Uint8Array(digest);
      var hex = "";
      for (var i = 0; i < view.length; i++) hex += view[i].toString(16).padStart(2, "0");
      return hex;
    });
  }

  function rung2FetchJson(url) {
    if (typeof TextDecoder === "undefined") return Promise.reject(new Error("TextDecoder unavailable"));
    return fetch(url, { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) throw new Error("Rung-2 payload unavailable");
      return response.arrayBuffer();
    }).then(function (buffer) {
      var bytes = new Uint8Array(buffer);
      var text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      var payload = JSON.parse(text);
      return { bytes: bytes, text: text, payload: payload };
    });
  }

  function rung2SameOriginUrl(value) {
    if (typeof value !== "string" || !value) throw new Error("Rung-2 URL is required");
    var url = new URL(value, document.baseURI);
    if (url.origin !== window.location.origin) throw new Error("Rung-2 URL must be same-origin");
    return url.href;
  }

  function rung2ValidateConfig(config) {
    rung2Object(config, "Rung-2 config");
    rung2Keys(config, [
      "schema_version", "enabled", "normalization_version", "bundle_url", "bundle_sha256", "acceptance",
    ], "Rung-2 config");
    if (config.schema_version !== RUNG2_CONFIG_SCHEMA || config.enabled !== true) {
      throw new Error("Rung-2 config is not explicitly enabled");
    }
    if (config.normalization_version !== RUNG2_NORMALIZATION_VERSION) {
      throw new Error("Rung-2 normalization version mismatch");
    }
    var bundleUrl = rung2SameOriginUrl(rung2RequiredString(config, "bundle_url", "Rung-2 config"));
    var bundleSha = rung2Hex(rung2RequiredString(config, "bundle_sha256", "Rung-2 config"), "bundle_sha256");
    var acceptance = rung2Object(config.acceptance, "Rung-2 acceptance");
    rung2Keys(acceptance, [
      "approved", "minimum_coverage_ratio", "cosine_floor", "runner_up_margin",
      "maximum_quantization_drift", "measured_quantization_drift", "payload_bytes",
      "quantization_accepted", "held_out_top_five_loss", "held_out_miss_rate",
      "no_locale_or_kind_regression",
    ], "Rung-2 acceptance");
    if (acceptance.approved !== true || acceptance.quantization_accepted !== true ||
        acceptance.held_out_top_five_loss !== false || acceptance.no_locale_or_kind_regression !== true) {
      throw new Error("Rung-2 acceptance is incomplete");
    }
    rung2Bounded(acceptance.minimum_coverage_ratio, Number.MIN_VALUE, 1, "minimum_coverage_ratio");
    rung2Bounded(acceptance.cosine_floor, -1, 1, "cosine_floor");
    rung2Bounded(acceptance.runner_up_margin, 0, 2, "runner_up_margin");
    rung2Bounded(acceptance.maximum_quantization_drift, 0, 2, "maximum_quantization_drift");
    if (rung2Finite(acceptance.measured_quantization_drift, "measured_quantization_drift") >
        acceptance.maximum_quantization_drift) {
      throw new Error("Rung-2 quantization drift exceeds acceptance");
    }
    rung2Bounded(acceptance.held_out_miss_rate, 0, 0.1, "held_out_miss_rate");
    rung2Integer(acceptance.payload_bytes, 1, RUNG2_MAX_PAYLOAD_BYTES, "payload_bytes");
    return {
      bundleUrl: bundleUrl,
      bundleSha: bundleSha,
      acceptance: acceptance,
    };
  }

  function rung2ValidateInt8Row(row, dimension, label, tokenKey, queryRow) {
    rung2Object(row, label);
    var keys = [tokenKey, "scale", "values"];
    if (queryRow) keys.push("model_token_ids", "token_count");
    rung2Keys(row, keys, label);
    rung2RequiredString(row, tokenKey, label);
    rung2Finite(row.scale, label + ".scale");
    if (row.scale <= 0 || Math.fround(row.scale) !== row.scale) {
      throw new Error(label + ".scale is not an exact positive float32");
    }
    if (!Array.isArray(row.values) || row.values.length !== dimension || !row.values.some(function (value) { return value !== 0; })) {
      throw new Error(label + ".values has the wrong dimension or is zero");
    }
    row.values.forEach(function (value) {
      rung2Integer(value, -127, 127, label + ".values");
    });
    if (queryRow) {
      rung2Integer(row.token_count, 1, Number.MAX_SAFE_INTEGER, label + ".token_count");
      rung2ValidateTokenIds(row.model_token_ids, row.token_count, label + ".model_token_ids");
    }
  }

  function rung2ValidateTokenIds(value, expectedCount, label) {
    if (!Array.isArray(value) || value.length !== expectedCount || !value.length) {
      throw new Error(label + " must contain the complete token-id tuple");
    }
    value.forEach(function (tokenId) {
      rung2Integer(tokenId, 0, Number.MAX_SAFE_INTEGER, label);
    });
  }

  function rung2ValidateMatrix(matrix) {
    rung2Object(matrix, "Rung-2 matrix");
    rung2Keys(matrix, [
      "schema_version", "model", "vocabulary_sha256", "vocabulary_count", "query_token_sha256",
      "query_token_count", "dimension", "quantization_algorithm", "row_order", "token_inventory",
      "rows", "query_token_rows", "serialized_bytes", "artifact_sha256",
    ], "Rung-2 matrix");
    if (matrix.schema_version !== RUNG2_MATRIX_SCHEMA_VERSION || matrix.quantization_algorithm !== RUNG2_QUANTIZATION ||
        matrix.row_order !== RUNG2_ROW_ORDER || matrix.dimension !== RUNG2_DIMENSION) {
      throw new Error("Rung-2 matrix schema or model dimension mismatch");
    }
    var model = rung2Object(matrix.model, "Rung-2 matrix.model");
    rung2Keys(model, ["repository", "revision", "spdx_license", "dimension", "provider", "tokenizer"], "Rung-2 matrix.model");
    if (model.repository !== RUNG2_MODEL_REPOSITORY || model.revision !== RUNG2_MODEL_REVISION ||
        model.spdx_license !== RUNG2_MODEL_LICENSE || model.dimension !== RUNG2_DIMENSION) {
      throw new Error("Rung-2 model provenance mismatch");
    }
    rung2RequiredString(model, "repository", "Rung-2 matrix.model");
    if (!RUNG2_HEX40.test(model.revision)) throw new Error("Rung-2 model revision is not immutable");
    rung2Integer(model.dimension, 1, Number.MAX_SAFE_INTEGER, "Rung-2 model.dimension");
    var provider = rung2Object(model.provider, "Rung-2 matrix.model.provider");
    rung2Keys(provider, ["package", "version", "source_sha256"], "Rung-2 matrix.model.provider");
    rung2RequiredString(provider, "package", "Rung-2 matrix.model.provider");
    rung2RequiredString(provider, "version", "Rung-2 matrix.model.provider");
    rung2Hex(provider.source_sha256, "Rung-2 provider.source_sha256");
    var tokenizer = rung2Object(model.tokenizer, "Rung-2 matrix.model.tokenizer");
    rung2Keys(tokenizer, ["package", "version", "repository", "revision", "vocabulary_sha256", "config_sha256", "normalization"], "Rung-2 matrix.model.tokenizer");
    rung2RequiredString(tokenizer, "package", "Rung-2 matrix.model.tokenizer");
    rung2RequiredString(tokenizer, "version", "Rung-2 matrix.model.tokenizer");
    rung2RequiredString(tokenizer, "repository", "Rung-2 matrix.model.tokenizer");
    if (!RUNG2_HEX40.test(rung2RequiredString(tokenizer, "revision", "Rung-2 matrix.model.tokenizer"))) {
      throw new Error("Rung-2 tokenizer revision is not immutable");
    }
    rung2Hex(tokenizer.vocabulary_sha256, "Rung-2 tokenizer.vocabulary_sha256");
    rung2Hex(tokenizer.config_sha256, "Rung-2 tokenizer.config_sha256");
    var normalization = rung2Object(tokenizer.normalization, "Rung-2 tokenizer.normalization");
    rung2Keys(normalization, ["algorithm", "unicode_form", "case_mapping", "accent_policy", "token_boundaries", "separator_policy"], "Rung-2 tokenizer.normalization");
    if (normalization.algorithm !== RUNG2_NORMALIZATION_VERSION || normalization.unicode_form !== "NFKC" ||
        normalization.case_mapping !== "lower" || normalization.accent_policy !== "preserve" ||
        normalization.token_boundaries !== "unicode-letter-number-runs-v1" ||
        normalization.separator_policy !== "collapse-to-boundary-v1") {
      throw new Error("Rung-2 tokenizer normalization contract mismatch");
    }
    rung2Hex(matrix.vocabulary_sha256, "vocabulary_sha256");
    rung2Hex(matrix.query_token_sha256, "query_token_sha256");
    rung2Hex(matrix.artifact_sha256, "artifact_sha256");
    rung2Integer(matrix.vocabulary_count, 1, Number.MAX_SAFE_INTEGER, "vocabulary_count");
    rung2Integer(matrix.query_token_count, 1, Number.MAX_SAFE_INTEGER, "query_token_count");
    rung2Integer(matrix.serialized_bytes, 1, RUNG2_MAX_PAYLOAD_BYTES, "serialized_bytes");
    if (!Array.isArray(matrix.rows) || matrix.rows.length !== matrix.vocabulary_count ||
        !Array.isArray(matrix.token_inventory) || matrix.token_inventory.length !== matrix.vocabulary_count ||
        !Array.isArray(matrix.query_token_rows) || matrix.query_token_rows.length !== matrix.query_token_count) {
      throw new Error("Rung-2 matrix counts do not match rows");
    }

    var terms = [];
    var termSet = Object.create(null);
    matrix.rows.forEach(function (row, index) {
      rung2ValidateInt8Row(row, matrix.dimension, "Rung-2 matrix.rows[" + index + "]", "term", false);
      var canonical = rung2NormalizeTerm(row.term);
      if (canonical !== row.term || termSet[row.term]) throw new Error("Rung-2 terms are not canonical and unique");
      termSet[row.term] = true;
      terms.push(row.term);
      if (index && rung2Utf8Compare(terms[index - 1], row.term) >= 0) throw new Error("Rung-2 terms are not UTF-8 ordered");
    });
    matrix.token_inventory.forEach(function (entry, index) {
      rung2Object(entry, "Rung-2 token_inventory[" + index + "]");
      rung2Keys(entry, ["term", "token_ids", "token_count"], "Rung-2 token_inventory[" + index + "]");
      if (entry.term !== terms[index]) throw new Error("Rung-2 token inventory order mismatch");
      rung2Integer(entry.token_count, 1, Number.MAX_SAFE_INTEGER, "Rung-2 token_count");
      rung2ValidateTokenIds(entry.token_ids, entry.token_count, "Rung-2 token_inventory token_ids");
    });

    var queryTokens = [];
    var querySet = Object.create(null);
    var queryRows = Object.create(null);
    matrix.query_token_rows.forEach(function (row, index) {
      rung2ValidateInt8Row(row, matrix.dimension, "Rung-2 query_token_rows[" + index + "]", "token", true);
      var normalized = rung2Normalize(row.token);
      if (!normalized || normalized.tokens.length !== 1 || normalized.tokens[0] !== row.token || querySet[row.token]) {
        throw new Error("Rung-2 query tokens are not canonical and unique");
      }
      querySet[row.token] = true;
      queryTokens.push(row.token);
      queryRows[row.token] = row;
      if (index && rung2Utf8Compare(queryTokens[index - 1], row.token) >= 0) throw new Error("Rung-2 query tokens are not UTF-8 ordered");
    });
    return { matrix: matrix, terms: terms, queryTokens: queryTokens, queryRows: queryRows, termRows: matrix.rows };
  }

  function rung2ValidateManifest(manifest) {
    rung2Object(manifest, "Rung-2 record manifest");
    rung2Keys(manifest, ["schema_version", "row_order", "record_count", "records", "records_sha256", "serialized_bytes"], "Rung-2 record manifest");
    if (manifest.schema_version !== 1 || manifest.row_order !== RUNG2_ROW_ORDER) {
      throw new Error("Rung-2 record manifest schema mismatch");
    }
    rung2Integer(manifest.record_count, 1, Number.MAX_SAFE_INTEGER, "Rung-2 record_count");
    rung2Hex(manifest.records_sha256, "Rung-2 records_sha256");
    rung2Integer(manifest.serialized_bytes, 1, RUNG2_MAX_PAYLOAD_BYTES, "Rung-2 manifest.serialized_bytes");
    if (!Array.isArray(manifest.records) || manifest.records.length !== manifest.record_count) {
      throw new Error("Rung-2 record manifest count mismatch");
    }
    var records = Object.create(null);
    manifest.records.forEach(function (record, index) {
      rung2Object(record, "Rung-2 records[" + index + "]");
      rung2Keys(record, ["record_id", "kind", "display_class", "title", "target", "ranking_weight"], "Rung-2 records[" + index + "]");
      var id = rung2RequiredString(record, "record_id", "Rung-2 record");
      if (records[id]) throw new Error("Rung-2 manifest contains duplicate record_id");
      rung2RequiredString(record, "title", "Rung-2 record");
      rung2RequiredString(record, "target", "Rung-2 record");
      var kind = rung2RequiredString(record, "kind", "Rung-2 record");
      if (["concept", "casilla", "cli", "page", "legal"].indexOf(kind) < 0) throw new Error("Rung-2 record has an invalid kind");
      var displayClass = rung2RequiredString(record, "display_class", "Rung-2 record");
      if (["casilla", "modelo", "cli", "technical", "doc"].indexOf(displayClass) < 0) throw new Error("Rung-2 record has an invalid display class");
      rung2Bounded(record.ranking_weight, 0, 1, "Rung-2 record.ranking_weight");
      if (index && rung2Utf8Compare(manifest.records[index - 1].record_id, id) >= 0) {
        throw new Error("Rung-2 manifest records are not UTF-8 ordered");
      }
      records[id] = record;
    });
    return {
      records: records,
      recordsSha256: manifest.records_sha256,
      serializedBytes: manifest.serialized_bytes,
    };
  }

  function rung2ValidateBridge(bridge, matrix, manifest) {
    rung2Object(bridge, "Rung-2 bridge");
    rung2Keys(bridge, [
      "schema_version", "row_order", "matrix_vocabulary_sha256", "record_manifest_sha256",
      "term_count", "entries", "artifact_sha256", "serialized_bytes",
    ], "Rung-2 bridge");
    if (bridge.schema_version !== 1 || bridge.row_order !== RUNG2_ROW_ORDER ||
        bridge.matrix_vocabulary_sha256 !== matrix.vocabulary_sha256 ||
        bridge.record_manifest_sha256 !== manifest.recordsSha256) {
      throw new Error("Rung-2 bridge hash link mismatch");
    }
    rung2Integer(bridge.term_count, 1, Number.MAX_SAFE_INTEGER, "Rung-2 bridge.term_count");
    rung2Hex(bridge.artifact_sha256, "Rung-2 bridge.artifact_sha256");
    rung2Integer(bridge.serialized_bytes, 1, RUNG2_MAX_PAYLOAD_BYTES, "Rung-2 bridge.serialized_bytes");
    if (!Array.isArray(bridge.entries) || bridge.entries.length !== bridge.term_count || bridge.entries.length !== matrix.rows.length) {
      throw new Error("Rung-2 bridge counts are invalid");
    }
    var terms = Object.create(null);
    bridge.entries.forEach(function (entry, index) {
      rung2Object(entry, "Rung-2 bridge.entries[" + index + "]");
      rung2Keys(entry, ["term", "targets", "targets_sha256"], "Rung-2 bridge entry");
      rung2Hex(entry.targets_sha256, "Rung-2 bridge.targets_sha256");
      if (entry.term !== matrix.rows[index].term || terms[entry.term] || !Array.isArray(entry.targets) || !entry.targets.length) {
        throw new Error("Rung-2 bridge term order or targets are invalid");
      }
      var targetIds = Object.create(null);
      terms[entry.term] = entry.targets.map(function (target, targetIndex) {
        rung2Object(target, "Rung-2 bridge target");
        rung2Keys(target, ["record_id", "ranking_weight"], "Rung-2 bridge target");
        var recordId = rung2RequiredString(target, "record_id", "Rung-2 target");
        if (!manifest.records[recordId]) throw new Error("Rung-2 target has no manifest record");
        if (targetIds[recordId]) throw new Error("Rung-2 term has duplicate record_id targets");
        targetIds[recordId] = true;
        rung2Bounded(target.ranking_weight, 0, 1, "Rung-2 target.ranking_weight");
        if (targetIndex && (entry.targets[targetIndex - 1].ranking_weight < target.ranking_weight ||
            entry.targets[targetIndex - 1].ranking_weight === target.ranking_weight &&
            rung2Utf8Compare(entry.targets[targetIndex - 1].record_id, recordId) > 0)) {
          throw new Error("Rung-2 targets are not deterministically ordered");
        }
        return { recordId: recordId, rankingWeight: target.ranking_weight };
      });
    });
    return { terms: terms, records: manifest.records, serializedBytes: bridge.serialized_bytes };
  }

  function rung2ValidateBundle(bundle) {
    rung2Object(bundle, "Rung-2 bundle");
    rung2Keys(bundle, ["schema_version", "matrix", "bridge", "record_manifest", "serialized_bytes", "artifact_sha256"], "Rung-2 bundle");
    if (bundle.schema_version !== RUNG2_BUNDLE_SCHEMA_VERSION) throw new Error("Rung-2 bundle schema mismatch");
    rung2Hex(bundle.artifact_sha256, "Rung-2 bundle.artifact_sha256");
    rung2Integer(bundle.serialized_bytes, 1, RUNG2_MAX_PAYLOAD_BYTES, "Rung-2 bundle.serialized_bytes");
    var matrix = rung2ValidateMatrix(bundle.matrix);
    var manifest = rung2ValidateManifest(bundle.record_manifest);
    var bridge = rung2ValidateBridge(bundle.bridge, matrix.matrix, manifest);
    if (bridge.terms && Object.keys(bridge.terms).length !== matrix.terms.length) {
      throw new Error("Rung-2 bundle bridge vocabulary mismatch");
    }
    return {
      matrix: matrix.matrix,
      queryRows: matrix.queryRows,
      termRows: matrix.termRows,
      bridge: bridge,
      termVectors: rung2BuildRows(matrix),
    };
  }

  function rung2Dequantize(row, dimension) {
    var vector = new Float32Array(dimension);
    for (var i = 0; i < dimension; i++) vector[i] = Math.fround(row.values[i] * row.scale);
    var normSquared = Math.fround(0);
    for (var j = 0; j < dimension; j++) normSquared = Math.fround(normSquared + Math.fround(vector[j] * vector[j]));
    var norm = Math.sqrt(normSquared);
    if (!isFinite(norm) || norm <= 0) throw new Error("Rung-2 vector is zero or non-finite");
    return { vector: vector, norm: norm };
  }

  function rung2BuildRows(bundle) {
    var rows = Object.create(null);
    bundle.termRows.forEach(function (row) {
      rows[row.term] = rung2Dequantize(row, bundle.matrix.dimension);
    });
    return rows;
  }

  function loadRung2Bundle() {
    if (RUNG2_BUNDLE_PROMISE) return RUNG2_BUNDLE_PROMISE;
    var rawConfig = window.__CADRUMO_SEARCH_RUNG2__;
    if (!rawConfig) return (RUNG2_BUNDLE_PROMISE = Promise.resolve(null));
    RUNG2_BUNDLE_PROMISE = Promise.resolve().then(function () {
      var config = rung2ValidateConfig(rawConfig);
      return rung2FetchJson(config.bundleUrl).then(function (payload) {
        if (payload.bytes.byteLength !== config.acceptance.payload_bytes || payload.bytes.byteLength > RUNG2_MAX_PAYLOAD_BYTES) {
          throw new Error("Rung-2 payload is outside the measured bound");
        }
        if (payload.bytes.byteLength !== payload.payload.serialized_bytes) {
          throw new Error("Rung-2 serialized byte stamps do not match");
        }
        return rung2Sha256(payload.bytes.buffer).then(function (hash) {
          if (hash !== config.bundleSha) throw new Error("Rung-2 payload hash mismatch");
          var bundle = rung2ValidateBundle(payload.payload);
          return Promise.all([
            rung2Sha256(new TextEncoder().encode(bundle.matrix.rows.map(function (row) { return row.term; }).join("\n")).buffer),
            rung2Sha256(new TextEncoder().encode(bundle.matrix.query_token_rows.map(function (row) { return row.token; }).join("\n")).buffer),
          ]).then(function (fingerprints) {
            if (fingerprints[0] !== bundle.matrix.vocabulary_sha256 || fingerprints[1] !== bundle.matrix.query_token_sha256) {
              throw new Error("Rung-2 vocabulary fingerprint mismatch");
            }
            bundle.config = config;
            return bundle;
          });
        });
      });
    }).catch(function () {
      /* Missing config, malformed data, unavailable crypto, or any acceptance
       * mismatch is a deliberate no-semantic-result outcome. */
      return null;
    });
    return RUNG2_BUNDLE_PROMISE;
  }

  function rung2SemanticCandidates(bundle, query) {
    if (!bundle || !Math.fround) return [];
    var normalized = rung2Normalize(query);
    if (!normalized || !normalized.tokens.length) return [];
    var covered = 0;
    var dimension = bundle.matrix.dimension;
    var queryVector = new Float32Array(dimension);
    normalized.tokens.forEach(function (token) {
      var row = bundle.queryRows[token];
      if (!row) return;
      covered += 1;
      for (var i = 0; i < dimension; i++) {
        queryVector[i] = Math.fround(queryVector[i] + Math.fround(row.values[i] * row.scale));
      }
    });
    if (!covered || covered / normalized.tokens.length < bundle.config.acceptance.minimum_coverage_ratio) return [];
    for (var j = 0; j < dimension; j++) if (!isFinite(queryVector[j])) return [];
    for (var k = 0; k < dimension; k++) queryVector[k] = Math.fround(queryVector[k] / covered);
    var queryNormSquared = Math.fround(0);
    for (var n = 0; n < dimension; n++) queryNormSquared = Math.fround(queryNormSquared + Math.fround(queryVector[n] * queryVector[n]));
    var queryNorm = Math.sqrt(queryNormSquared);
    if (!isFinite(queryNorm) || queryNorm <= 0) return [];
    var scored = bundle.termRows.map(function (row) {
      var termVector = bundle.termVectors[row.term];
      var dot = Math.fround(0);
      for (var i = 0; i < dimension; i++) dot = Math.fround(dot + Math.fround(queryVector[i] * termVector.vector[i]));
      var score = dot / (queryNorm * termVector.norm);
      return { term: row.term, score: score };
    }).filter(function (candidate) {
      return isFinite(candidate.score) && candidate.score >= bundle.config.acceptance.cosine_floor;
    }).sort(function (left, right) {
      if (right.score !== left.score) return right.score - left.score;
      return rung2Utf8Compare(left.term, right.term);
    });
    if (!scored.length) return [];
    if (scored.length > 1 && scored[0].score - scored[1].score < bundle.config.acceptance.runner_up_margin) return [];
    var byRecord = Object.create(null);
    scored.forEach(function (candidate) {
      (bundle.bridge.terms[candidate.term] || []).forEach(function (target) {
        var prior = byRecord[target.recordId];
        if (!prior || candidate.score > prior.semanticScore ||
            candidate.score === prior.semanticScore && target.rankingWeight > prior.semanticRankingWeight) {
          byRecord[target.recordId] = {
            recordId: target.recordId,
            semanticScore: candidate.score,
            semanticRankingWeight: target.rankingWeight,
          };
        }
      });
    });
    return Object.keys(byRecord).map(function (recordId) {
      var candidate = byRecord[recordId];
      var record = bundle.bridge.records[recordId];
      return {
        title: record.title,
        href: record.target,
        crumb: "",
        excerpt: "",
        kind: record.kind,
        displayClass: record.display_class,
        tierRank: 1 + record.ranking_weight,
        recordId: candidate.recordId,
        semanticScore: candidate.semanticScore,
        semanticRankingWeight: candidate.semanticRankingWeight,
        directMatchStrength: 0,
      };
    }).sort(function (left, right) {
      if (right.semanticScore !== left.semanticScore) return right.semanticScore - left.semanticScore;
      if (right.semanticRankingWeight !== left.semanticRankingWeight) return right.semanticRankingWeight - left.semanticRankingWeight;
      return rung2Utf8Compare(left.recordId, right.recordId);
    }).slice(0, 5);
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
      return {
        modelo: normalizeStructuredValue(match[1]),
        number: normalizeStructuredValue(number),
        segmento: segmento ? normalizeStructuredValue(segmento) : null,
      };
    }

    function isStructuredCasillaMatch(data, address) {
      var meta = data && data.meta;
      if (!meta || meta.kind !== "casilla") return false;
      if (normalizeStructuredValue(meta.modelo) !== address.modelo) return false;
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
     * icon-font, no external asset (`shipped-search-licence-clean`). Full-text
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
     * order mirrors the shipped weight ladder (doc > modelo > casilla > cli >
     * technical). This CONSUMES the shipped class; it never re-derives it. */
    var PAGE_BAND_RANK = {
      doc: 0.4,
      modelo: 0.35,
      casilla: 0.3,
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
        /* The weight-sorted Pagefind pass contains only injected records. A
         * hit there is therefore a declared lexical surface match, including
         * a search_aliases hit, even when its title is not the query. Keep the
         * flag separate from titleMatch so exact titles retain their stronger
         * score inside the lexical band. */
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
          return result.data();
        })
      ).then(function (datas) {
        return datas.map(function (data) {
          return cardFromPagefind(
            data.meta,
            data.meta && data.meta.title,
            data.url,
            data.excerpt,
            fromCardPass
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
                 * tier-one weight, so capture each url's relevance rank from the
                 * textual pass and carry it onto the card; compose() breaks
                 * within-tier ties by it, floating the best textual match to the
                 * top of its tier while cards still sit above full-text pages. */
                var relRank = {};
                pageResults.forEach(function (r, i) {
                  if (relRank[r.url] === undefined) relRank[r.url] = i;
                });
                return dataToCards(cardResults, 12, true).then(function (cards) {
                  return dataToCards(pageResults, 6, false).then(function (pages) {
                    var all = cards.concat(pages);
                    all.forEach(function (item) {
                      item.relRank =
                        relRank[item.href] !== undefined
                          ? relRank[item.href]
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
          /* Pagefind is optional; its absence must not prevent a separately
           * validated semantic bundle from being considered. */
          return { cards: [], structured: false };
        })
        .then(function (result) {
          if (result.structured) return result.cards;
          /* The semantic tier is an additive source inside this controller.
           * It never replaces the structured casilla first-refusal above and
           * it can only hydrate records from the validated bridge. */
          return loadRung2Bundle().then(function (bundle) {
            var semantic = rung2SemanticCandidates(bundle, query);
            return result.cards.concat(semantic);
          }).catch(function () {
            /* A malformed or unavailable semantic payload disables only that
             * optional tier; already-resolved Pagefind cards remain visible. */
            return result.cards;
          });
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
         * returned by Pagefind) precedes a semantic fallback. Once both rows
         * are in the same source class, retain the existing display-class
         * ladder and its relevance tie-break; semantic rows therefore never
         * become a second display-class authority. */
        var ma = typeof a.directMatchStrength === "number" ? a.directMatchStrength : titleMatch(a.title, query);
        var mb = typeof b.directMatchStrength === "number" ? b.directMatchStrength : titleMatch(b.title, query);
        var aSemantic = typeof a.semanticScore === "number";
        var bSemantic = typeof b.semanticScore === "number";
        if (aSemantic !== bSemantic) {
          var aDirect = !!a.isLexicalCard || ma > 0;
          var bDirect = !!b.isLexicalCard || mb > 0;
          if (aDirect !== bDirect) return aDirect ? -1 : 1;
          if (aDirect && bDirect && mb !== ma) return mb - ma;
          /* With no direct identity/title/alias signal, fall through to the
           * existing display-class band. This keeps semantic results above
           * ordinary full-text pages while direct lexical answers still win. */
        }
        if (b.tierRank !== a.tierRank) return b.tierRank - a.tierRank;
        if (mb !== ma) return mb - ma;
        if (aSemantic && bSemantic) {
          if (b.semanticScore !== a.semanticScore) return b.semanticScore - a.semanticScore;
          if ((b.semanticRankingWeight || 0) !== (a.semanticRankingWeight || 0)) {
            return (b.semanticRankingWeight || 0) - (a.semanticRankingWeight || 0);
          }
          if (a.recordId && b.recordId) return rung2Utf8Compare(a.recordId, b.recordId);
        }
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
  });
})();
