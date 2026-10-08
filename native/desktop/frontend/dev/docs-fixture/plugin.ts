// A stand-in documentation site for browser development, served only while
// the Vite development server runs. Its pages load the real desktop bridge
// script, so the shell talks to them exactly as it talks to the packaged
// documentation: across origins, through postMessage.
//
// It listens on a port of its own beside the development server, on the same
// address. The same host name with another port is another origin, and it is
// reachable from wherever the development server is, so the fixture works on
// the machine itself and from another device alike. The port is assigned by
// the operating system and handed to the development entry through the
// `virtual:docs-fixture` module.
//
// It is a fixture: a few static pages and a search that answers from a fixed
// list. It carries no documentation content and proves nothing about the
// packaged documentation or the `cadrumo-docs` scheme.
import { readFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../../scripts/build-paths.mjs";
import type { Plugin } from "vite";

export const DOCS_FIXTURE_LANGUAGES = ["en", "es", "ca", "hu"] as const;

type Language = (typeof DOCS_FIXTURE_LANGUAGES)[number];
type PageName = "index" | "guide" | "glossary";

const MODULE = "virtual:docs-fixture";
const RESOLVED = `\0${MODULE}`;

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

const STATIC = new Map<string, { file: string; type: string }>([
  [
    "bridge.js",
    {
      file: here("../../../../../docs/_static/cadrumo-desktop-bridge.js"),
      type: "text/javascript",
    },
  ],
  ["fixture.js", { file: here("./fixture.js"), type: "text/javascript" }],
  ["fixture.css", { file: here("./fixture.css"), type: "text/css" }],
  [
    "palette.css",
    {
      file: resolve(buildPath("desktop_frontend_generated"), "palette.css"),
      type: "text/css",
    },
  ],
]);

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

// English sits at the root and the other languages under their code, as the
// packaged documentation is laid out.
const root = (language: Language) =>
  language === "en" ? "/" : `/${language}/`;

function page(language: Language, name: PageName) {
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
<link rel="stylesheet" href="/_static/palette.css">
<link rel="stylesheet" href="/_static/fixture.css">
<script src="/_static/bridge.js"></script>
<script src="/_static/fixture.js"></script>
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
  const language = (DOCS_FIXTURE_LANGUAGES as readonly string[]).includes(
    parts[0] ?? "",
  )
    ? (parts.shift() as Language)
    : "en";
  const file = parts.length === 0 ? "index.html" : parts.join("/");
  const name = /^(index|guide|glossary)\.html$/.exec(file)?.[1];
  return name ? page(language, name as PageName) : null;
}

function answer(path: string): { type: string; body: string } | null {
  const asset = /^\/_static\/([\w.-]+)$/.exec(path)?.[1];
  if (asset) {
    const entry = STATIC.get(asset);
    return entry
      ? { type: entry.type, body: readFileSync(entry.file, "utf8") }
      : null;
  }
  const body = resolvePage(path);
  return body === null ? null : { type: "text/html", body };
}

function listen(host: string | undefined): {
  server: Server;
  port: Promise<number>;
} {
  const server = createServer((request, response) => {
    const found =
      request.method === "GET" || request.method === "HEAD"
        ? answer(new URL(request.url ?? "/", "http://fixture").pathname)
        : null;
    if (!found) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "Content-Type": `${found.type}; charset=utf-8`,
      "Cache-Control": "no-store",
    });
    response.end(request.method === "HEAD" ? undefined : found.body);
  });
  const port = new Promise<number>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, host, () =>
      resolve((server.address() as AddressInfo).port),
    );
  });
  return { server, port };
}

export function docsFixture(): Plugin {
  let port: Promise<number> | null = null;
  return {
    name: "development-docs-fixture",
    // The fixture exists only beside a development server. A build of the
    // development entry gets no port, and so no documentation.
    configureServer(vite) {
      const configured = vite.config.server.host;
      const fixture = listen(
        typeof configured === "string" ? configured : undefined,
      );
      port = fixture.port;
      vite.httpServer?.once("close", () => fixture.server.close());
    },
    resolveId(id) {
      if (id === MODULE) return RESOLVED;
    },
    async load(id) {
      if (id !== RESOLVED) return;
      return `export const port = ${port ? await port : null};`;
    },
  };
}
