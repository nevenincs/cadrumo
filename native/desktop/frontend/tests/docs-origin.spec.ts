import { expect, test } from "@playwright/test";
import { onDocsOrigin } from "../src/shell/docsOrigin";

test("macOS documentation URLs keep their exact custom-scheme authority", () => {
  const origin = "cadrumo-docs://localhost";
  // WHATWG URL.origin is "null" for all these custom-scheme URLs.
  expect(new URL(`${origin}/es/index.html`).origin).toBe("null");
  expect(onDocsOrigin(new URL(`${origin}/es/index.html#casilla`), origin)).toBe(
    true,
  );
  expect(
    onDocsOrigin(new URL("other-docs://localhost/es/index.html"), origin),
  ).toBe(false);
  expect(
    onDocsOrigin(new URL("cadrumo-docs://other/es/index.html"), origin),
  ).toBe(false);
  expect(
    onDocsOrigin(
      new URL("cadrumo-docs://localhost:8080/es/index.html"),
      origin,
    ),
  ).toBe(false);
  expect(
    onDocsOrigin(
      new URL("cadrumo-docs://user@localhost/es/index.html"),
      origin,
    ),
  ).toBe(false);
});

test("Windows and development documentation URLs keep their transport and port", () => {
  const origin = "https://cadrumo-docs.localhost";
  expect(onDocsOrigin(new URL(`${origin}/index.html`), origin)).toBe(true);
  expect(
    onDocsOrigin(new URL("http://cadrumo-docs.localhost/index.html"), origin),
  ).toBe(false);
  expect(
    onDocsOrigin(
      new URL("https://cadrumo-docs.localhost.evil/index.html"),
      origin,
    ),
  ).toBe(false);
  const devOrigin = "http://localhost:15372";
  expect(onDocsOrigin(new URL(`${devOrigin}/en/guide.html`), devOrigin)).toBe(
    true,
  );
  expect(
    onDocsOrigin(new URL("http://localhost:15373/en/guide.html"), devOrigin),
  ).toBe(false);
});

test("an invalid or path-bearing claimed origin grants no documentation URL", () => {
  const url = new URL("cadrumo-docs://localhost/index.html");
  expect(onDocsOrigin(url, "null")).toBe(false);
  expect(onDocsOrigin(url, "cadrumo-docs://localhost/other")).toBe(false);
  expect(onDocsOrigin(url, "cadrumo-docs://user@localhost")).toBe(false);
});
