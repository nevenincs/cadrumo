// A stand-in documentation site for browser development, served only while
// the Vite development server runs, or the preview server of the built
// scenarios (`--mode scenarios`). Its pages load the real desktop bridge
// script, so the shell talks to them exactly as it talks to the packaged
// documentation: across origins, through postMessage.
//
// It listens on a port of its own beside the server, on the same address. The
// same host name with another port is another origin, and it is reachable
// from wherever the server is, so the fixture works on the machine itself and
// from another device alike. The fixed port comes from the development server
// contract and is handed to the development entry through the
// `virtual:docs-fixture` module. The development server writes it into that
// module; a built page is static, so the preview server hands it the port in
// the page it serves and an entry served any other way gets none.
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
import { server as serverConfiguration } from "../../../scripts/configuration.mjs";
import { testRunPorts } from "../../scripts/test-run-directory.mjs";
import type { Plugin } from "vite";

export const DOCS_FIXTURE_LANGUAGES = ["en", "es", "ca", "hu"] as const;

type Language = (typeof DOCS_FIXTURE_LANGUAGES)[number];
type PageName = "index" | "guide" | "glossary";

const MODULE = "virtual:docs-fixture";
const RESOLVED = `\0${MODULE}`;
// Where a built entry finds the fixture's port, set by the page that carries it.
const PAGE_PORT = "__docsFixturePort";

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
<nav aria-label="Languages">${DOCS_FIXTURE_LANGUAGES.map((code) => `<a class="cadrumo-header-lang-item" lang="${code}" href="${root(code)}${name}.html">${code}</a>`).join(" ")}</nav>
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

function listen(
  host: string | undefined,
  fixedPort: number,
  owner?: string,
): {
  server: Server;
  port: Promise<number>;
} {
  const server = createServer((request, response) => {
    if (owner && request.url === "/__cadrumo_test_owner") {
      response.writeHead(200, { "Cache-Control": "no-store" }).end(owner);
      return;
    }
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
    server.listen(fixedPort, host, () =>
      resolve((server.address() as AddressInfo).port),
    );
  });
  return { server, port };
}

export function docsFixture(): Plugin {
  let port: Promise<number> | null = null;
  let building = false;
  return {
    name: "development-docs-fixture",
    configResolved(config) {
      building = config.command === "build";
    },
    // The fixture exists only beside a development server or the preview
    // server of the built scenarios. The test server that exercises Vite's hot
    // reload (mode scenarios) needs no documentation, so it has none.
    async configureServer(vite) {
      if (vite.config.mode === "scenarios") return;
      const configured = vite.config.server.host;
      const fixture = listen(
        typeof configured === "string" ? configured : undefined,
        serverConfiguration().docsPort,
      );
      port = fixture.port;
      vite.httpServer?.once("close", () => fixture.server.close());
      await port;
    },
    // The built scenario page is static, so the server that runs the fixture
    // hands the page its port. Any other host of the build, such as the
    // benchmark's, serves the page as it is and the shell has no documentation.
    async configurePreviewServer(preview) {
      if (preview.config.mode !== "scenarios") return;
      const configured = preview.config.preview.host;
      const testPorts = testRunPorts(buildPath("desktop_results"));
      const fixture = listen(
        typeof configured === "string" ? configured : undefined,
        (testPorts ?? serverConfiguration()).scenariosDocsPort,
        testPorts?.token,
      );
      preview.httpServer.once("close", () => fixture.server.close());
      const fixturePort = await fixture.port;
      const entry = resolve(preview.config.build.outDir, "scenarios.html");
      preview.middlewares.use((request, response, next) => {
        const path = new URL(request.url ?? "/", "http://preview").pathname;
        const method = request.method ?? "";
        if (path !== "/scenarios.html" || !["GET", "HEAD"].includes(method)) {
          next();
          return;
        }
        try {
          const page = readFileSync(entry, "utf8");
          if (!page.includes("</head>"))
            throw new Error("The built scenario page has no head to extend.");
          response.writeHead(200, {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store",
          });
          response.end(
            method === "HEAD"
              ? undefined
              : page.replace(
                  "</head>",
                  `<script>globalThis.${PAGE_PORT}=${fixturePort}</script></head>`,
                ),
          );
        } catch (error) {
          next(error);
        }
      });
    },
    resolveId(id) {
      if (id === MODULE) return RESOLVED;
    },
    async load(id) {
      if (id !== RESOLVED) return;
      if (building)
        return `export const port = globalThis.${PAGE_PORT} ?? null;`;
      return `export const port = ${port ? await port : null};`;
    },
  };
}
