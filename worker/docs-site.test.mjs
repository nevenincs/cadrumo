import assert from "node:assert/strict";
import { test } from "node:test";

import worker, { RELEASE_HEADER, keyTail, route } from "./docs-site.mjs";

const ENV = {
  RELEASE_ID: "v1.2.3-20260923T000000Z",
  CANONICAL_HOST: "cadrumo.neve.md",
  CANONICAL_MOUNT: "/docs",
  MIRROR_HOST: "neve.md",
  MIRROR_MOUNT: "/cadrumo/docs",
};

/* An in-memory bucket with the slice of the R2 binding the Worker uses. */
function bucket(objects) {
  const entry = (key) => {
    if (!(key in objects)) return null;
    const { body, contentType } = objects[key];
    return {
      size: body.length,
      httpEtag: `"${key}"`,
      writeHttpMetadata(headers) {
        headers.set("content-type", contentType);
        headers.set("cache-control", "public, max-age=300, must-revalidate");
      },
      body: new Response(body).body,
    };
  };
  return { get: async (key) => entry(key), head: async (key) => entry(key) };
}

const release = (tail) => `releases/${ENV.RELEASE_ID}${tail}`;
const SITE = bucket({
  [release("/index.html")]: { body: "apex", contentType: "text/html; charset=utf-8" },
  [release("/es/index.html")]: { body: "es", contentType: "text/html; charset=utf-8" },
  [release("/404.html")]: { body: "missing", contentType: "text/html; charset=utf-8" },
  [release("/pagefind/pagefind.js")]: { body: "js", contentType: "text/javascript; charset=utf-8" },
});

const fetchFrom = (url, init) => worker.fetch(new Request(url, init), { ...ENV, SITE });

test("both mounts map onto the same release path", () => {
  assert.deepEqual(route(new URL("https://cadrumo.neve.md/docs/es/"), ENV), { kind: "serve", path: "/es/" });
  assert.deepEqual(route(new URL("https://neve.md/cadrumo/docs/es/"), ENV), { kind: "serve", path: "/es/" });
});

test("a bare mount redirects to its directory and keeps the query", () => {
  assert.deepEqual(route(new URL("https://cadrumo.neve.md/docs?q=1"), ENV), { kind: "redirect", location: "/docs/?q=1" });
  assert.deepEqual(route(new URL("https://neve.md/cadrumo/docs"), ENV), { kind: "redirect", location: "/cadrumo/docs/" });
});

test("paths outside a mount and undeclared hosts are not served", () => {
  for (const url of [
    "https://cadrumo.neve.md/",
    "https://cadrumo.neve.md/docsfoo",
    "https://neve.md/docs/",
    "https://neve.md/cadrumo/docsfoo",
    "https://example.com/docs/",
  ]) {
    assert.deepEqual(route(new URL(url), ENV), { kind: "not-found" }, url);
  }
});

test("dot segments and undecodable paths address nothing", () => {
  assert.equal(keyTail("/../secret"), null);
  assert.equal(keyTail("/%2e%2e/secret"), null);
  assert.equal(keyTail("/%E0%A4%A"), null);
  assert.equal(keyTail("/es/"), "/es/index.html");
});

test("a page is served from the configured release with the release header", async () => {
  for (const url of ["https://cadrumo.neve.md/docs/es/", "https://neve.md/cadrumo/docs/es/"]) {
    const response = await fetchFrom(url);
    assert.equal(response.status, 200, url);
    assert.equal(await response.text(), "es");
    assert.equal(response.headers.get(RELEASE_HEADER), ENV.RELEASE_ID);
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  }
});

test("a directory without its slash redirects to the directory", async () => {
  const response = await fetchFrom("https://cadrumo.neve.md/docs/es");
  assert.equal(response.status, 301);
  assert.equal(response.headers.get("location"), "/docs/es/");
});

test("a missing page is the release's 404 page with status 404", async () => {
  const response = await fetchFrom("https://cadrumo.neve.md/docs/nowhere.html");
  assert.equal(response.status, 404);
  assert.equal(await response.text(), "missing");
  assert.equal(response.headers.get(RELEASE_HEADER), ENV.RELEASE_ID);
});

test("HEAD answers headers without a body", async () => {
  const response = await fetchFrom("https://cadrumo.neve.md/docs/pagefind/pagefind.js", { method: "HEAD" });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-length"), "2");
  assert.equal(await response.text(), "");
});

test("writes are refused and an unconfigured release is unavailable", async () => {
  assert.equal((await fetchFrom("https://cadrumo.neve.md/docs/", { method: "POST" })).status, 405);
  const response = await worker.fetch(new Request("https://cadrumo.neve.md/docs/"), { ...ENV, RELEASE_ID: " ", SITE });
  assert.equal(response.status, 503);
});
