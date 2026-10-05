// A stand-in documentation site for browser development, served by the Vite
// development server only. Its pages load the real desktop bridge script, so
// the shell talks to them exactly as it talks to the packaged documentation:
// across origins, through postMessage. The shell reaches it on the other
// loopback name (localhost when the shell is on 127.0.0.1, and the reverse),
// which makes it a different origin on the same server.
//
// It is a fixture: a few static pages and a search that answers from a fixed
// list. It carries no documentation content and proves nothing about the
// packaged documentation or the `cadrumo-docs` scheme.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

export const DOCS_FIXTURE_BASE = "/docs-fixture";
export const DOCS_FIXTURE_LANGUAGES = ["en", "es", "ca", "hu"] as const;

type Language = (typeof DOCS_FIXTURE_LANGUAGES)[number];

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

const STATIC: Record<string, { file: string; type: string }> = {
  "bridge.js": {
    file: here("../../../../../docs/_static/cadrumo-desktop-bridge.js"),
    type: "text/javascript",
  },
  "fixture.js": { file: here("./fixture.js"), type: "text/javascript" },
  "fixture.css": { file: here("./fixture.css"), type: "text/css" },
  "palette.css": {
    file: here("../../src/generated/palette.css"),
    type: "text/css",
  },
};

const TITLES: Record<Language, { site: string; home: string; guide: string }> =
  {
    en: {
      site: "Documentation fixture",
      home: "Stand-in documentation",
      guide: "Second page",
    },
    es: {
      site: "Documentación de prueba",
      home: "Documentación de sustitución",
      guide: "Segunda página",
    },
    ca: {
      site: "Documentació de prova",
      home: "Documentació de substitució",
      guide: "Segona pàgina",
    },
    hu: {
      site: "Próbadokumentáció",
      home: "Helyettesítő dokumentáció",
      guide: "Második oldal",
    },
  };

const root = (language: Language) =>
  language === "en"
    ? `${DOCS_FIXTURE_BASE}/`
    : `${DOCS_FIXTURE_BASE}/${language}/`;

function page(language: Language, name: "index" | "guide" | "glossary") {
  const titles = TITLES[language];
  const home = `${root(language)}index.html`;
  const heading =
    name === "index"
      ? titles.home
      : name === "guide"
        ? titles.guide
        : "Glossary";
  const body =
    name === "index"
      ? `<p id="text">Casilla 01 total. This page is a development fixture: it stands in for the packaged documentation so the bridge can be exercised in a browser.</p>
<p><a id="internal" href="guide.html">${titles.guide}</a> · <a href="glossary.html">Glossary</a> · <a id="external" href="https://example.org/">External link</a></p>
${Array.from({ length: 12 }, (_, index) => `<p>Filler paragraph ${index + 1}, so the page scrolls and zoom has something to scale.</p>`).join("\n")}`
      : name === "guide"
        ? `<p>The second page exists so back, forward and home have somewhere to go.</p><p><a href="index.html">${titles.home}</a></p>`
        : `<dl><dt id="term-modelo">Modelo</dt><dd>A fixture glossary entry.</dd><dt id="term-casilla">Casilla</dt><dd>Another fixture glossary entry.</dd></dl>`;
  return `<!doctype html>
<html lang="${language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${heading}</title>
<link rel="stylesheet" href="${DOCS_FIXTURE_BASE}/_static/palette.css">
<link rel="stylesheet" href="${DOCS_FIXTURE_BASE}/_static/fixture.css">
<script src="${DOCS_FIXTURE_BASE}/_static/bridge.js"></script>
<script src="${DOCS_FIXTURE_BASE}/_static/fixture.js"></script>
</head>
<body data-theme="auto">
<header>
<a class="cadrumo-header-brand" href="${home}">${titles.site}</a>
<span class="fixture-note">development fixture</span>
<button type="button" data-cadrumo-search>Search</button>
<button type="button" class="theme-toggle">Theme</button>
</header>
<main>
<h1>${heading}</h1>
${body}
</main>
</body>
</html>
`;
}

function resolvePage(path: string): string | null {
  const parts = path.split("/").filter(Boolean);
  const first = parts[0];
  const language = (DOCS_FIXTURE_LANGUAGES as readonly string[]).includes(
    first ?? "",
  )
    ? (parts.shift() as Language)
    : "en";
  const file = parts.length === 0 ? "index.html" : parts.join("/");
  const name = /^(index|guide|glossary)\.html$/.exec(file)?.[1];
  return name ? page(language, name as "index" | "guide" | "glossary") : null;
}

export function docsFixture(): Plugin {
  return {
    name: "development-docs-fixture",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(DOCS_FIXTURE_BASE, (request, response, next) => {
        const path = new URL(request.url ?? "/", "http://fixture").pathname;
        const asset = /^\/_static\/([\w.-]+)$/.exec(path)?.[1];
        const entry = asset ? STATIC[asset] : undefined;
        let type = "text/html";
        let body: string | null;
        if (entry) {
          type = entry.type;
          body = readFileSync(entry.file, "utf8");
        } else {
          body = asset ? null : resolvePage(path);
        }
        if (body === null) {
          next();
          return;
        }
        response.statusCode = 200;
        response.setHeader("Content-Type", `${type}; charset=utf-8`);
        response.setHeader("Cache-Control", "no-store");
        response.end(body);
      });
    },
  };
}
