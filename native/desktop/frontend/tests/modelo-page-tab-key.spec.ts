import { expect, test } from "@playwright/test";
import { build } from "esbuild";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import type { PageTabPage } from "../src/components/modelo/form/PageTab";
import { catalogue, label } from "./support/strings";

// A form page the application could name only by its registry path is served
// that path with the disclosure `technical`, and its tab draws the path as
// the key it is: carried in `data-key` and glossed by the window's words for
// a technical name. No scenario world serves such a page heading, because
// every supported year's pages are named in words, so the tab is drawn here
// on its own with served heading objects that carry no tax facts. A page
// served in words beside it is drawn as words, never as a key.

const LANGUAGES_UNDER_TEST = ["en", "es"] as const;

/** The shell's generated inputs a component may import, by the names it
 * imports them under, as vite.config.ts serves them from this build. */
const GENERATED: Record<string, string> = {
  "virtual:operational-settings": "operational-settings.ts",
  "virtual:desktop-provider-icons": "provider-icons.json",
  "virtual:desktop-navigation": "navigation.json",
};

type Draw = (props: { pages: PageTabPage[]; language: string }) => string;

/** The tabs of `pages` in a tab list, in the window language `language`,
 * rendered to static markup. The component is compiled here with the
 * project's own JSX setting because the test runner replaces JSX in the
 * files it loads, and the tab needs the tab list it belongs to. */
async function compiled(): Promise<Draw> {
  const source = (path: string) =>
    JSON.stringify(fileURLToPath(new URL(`../src/${path}`, import.meta.url)));
  const built = await build({
    stdin: {
      contents: `
        import { createElement as h } from "react";
        import { renderToStaticMarkup } from "react-dom/server";
        import { PageTab } from ${source("components/modelo/form/PageTab.tsx")};
        import { Tabs, TabsList } from ${source("components/ui/tabs.tsx")};
        import { StringsContext, translator } from ${source("shell/strings.ts")};
        export const draw = ({ pages, language }) =>
          renderToStaticMarkup(
            h(
              StringsContext.Provider,
              { value: translator(language) },
              h(
                Tabs,
                { value: pages[0].id },
                h(
                  TabsList,
                  { "aria-label": "pages" },
                  pages.map((page) =>
                    h(PageTab, { key: page.id, page, panel: "panel" }),
                  ),
                ),
              ),
            ),
          );
      `,
      resolveDir: fileURLToPath(new URL("..", import.meta.url)),
      loader: "js",
    },
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    logLevel: "silent",
    plugins: [
      {
        name: "desktop-strings",
        setup(plugin) {
          plugin.onResolve({ filter: /^virtual:desktop-strings$/ }, () => ({
            path: "desktop-strings",
            namespace: "stub",
          }));
          plugin.onResolve({ filter: /^virtual:/ }, ({ path }) => {
            const name = GENERATED[path];
            return name === undefined
              ? undefined
              : {
                  path: resolve(buildPath("desktop_frontend_generated"), name),
                };
          });
          plugin.onLoad({ filter: /.*/, namespace: "stub" }, () => ({
            contents: `export default ${JSON.stringify(catalogue)};`,
            loader: "js",
          }));
        },
      },
    ],
  });
  const module = { exports: {} as { draw: Draw } };
  new Function(
    "module",
    "exports",
    "require",
    built.outputFiles.map((file) => file.text).join(""),
  )(module, module.exports, createRequire(import.meta.url));
  return module.exports.draw;
}

/** A page served only its registry path, and one served in words. */
const keyOnly: PageTabPage = {
  id: "page-key",
  heading: { text: "page-key", disclosure: "technical" },
  applies: true,
  counts: null,
};
const worded: PageTabPage = {
  id: "page-words",
  heading: { text: "Served words", disclosure: "localized" },
  applies: true,
  counts: null,
};

for (const language of LANGUAGES_UNDER_TEST) {
  test(`a page tab served only a registry path draws it as a key (${language})`, async ({
    page: target,
  }) => {
    const draw = await compiled();
    await target.setContent(draw({ pages: [keyOnly, worded], language }));
    const tabs = target
      .getByRole("tablist", { name: "pages" })
      .getByRole("tab");
    await expect(tabs).toHaveCount(2);

    const keyTab = tabs.nth(0);
    await expect(keyTab).toHaveAttribute(
      "data-heading-disclosure",
      "technical",
    );
    const key = keyTab.locator("[data-key]");
    await expect(key).toHaveCount(1);
    await expect(key).toHaveAttribute("data-key", keyOnly.heading.text);
    await expect(key).toHaveText(keyOnly.heading.text);
    await expect(key).toHaveAttribute(
      "title",
      label("workspace.modelo.disclosure.technical", {}, language),
    );
    await expect(keyTab).toHaveText(keyOnly.heading.text);

    const wordTab = tabs.nth(1);
    await expect(wordTab).toHaveAttribute(
      "data-heading-disclosure",
      "localized",
    );
    await expect(wordTab.locator("[data-key]")).toHaveCount(0);
    await expect(wordTab).toHaveText(worded.heading.text);
  });
}
