import { build } from "esbuild";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../../scripts/build-paths.mjs";
import { catalogue } from "./strings";

/** The shell's generated inputs a component may import, by the names it
 * imports them under, as vite.config.ts serves them from this build. */
const GENERATED: Record<string, string> = {
  "virtual:operational-settings": "operational-settings.ts",
  "virtual:desktop-provider-icons": "provider-icons.json",
  "virtual:desktop-navigation": "navigation.json",
};

/** A component drawn to markup with the props it is given. */
export type Draw<Props> = (props: Props) => string;

/**
 * Compile the component `name` exported by `source` (a path under `src/`)
 * with the project's own JSX setting and the generated chrome strings, and
 * return a function that renders it to static markup. The test runner
 * replaces JSX in the files it loads, so a component is bundled here rather
 * than imported.
 */
export async function markupOf<Props>(
  source: string,
  name: string,
): Promise<Draw<Props>> {
  const root = fileURLToPath(new URL("../..", import.meta.url));
  const component = fileURLToPath(
    new URL(`../../src/${source}`, import.meta.url),
  );
  const built = await build({
    stdin: {
      contents: `
        import { createElement } from "react";
        import { renderToStaticMarkup } from "react-dom/server";
        import { ${name} as Component } from ${JSON.stringify(component)};
        export const draw = (props) =>
          renderToStaticMarkup(createElement(Component, props));
      `,
      resolveDir: root,
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
  const module = { exports: {} as { draw: Draw<Props> } };
  new Function(
    "module",
    "exports",
    "require",
    built.outputFiles.map((file) => file.text).join(""),
  )(module, module.exports, createRequire(import.meta.url));
  return module.exports.draw;
}
