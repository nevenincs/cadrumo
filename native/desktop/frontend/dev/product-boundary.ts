// The product build's boundary: development-only modules must not be in it.
// The scenario host fabricates host answers, sign-in included, and the
// catalogue's stories and the documentation fixture are tooling. A production
// build that bundles any of them is refused, whatever imported them.
import { relative, sep } from "node:path";
import type { Plugin } from "vite";

const DEVELOPMENT = [
  /^src\/dev\//,
  /^dev\//,
  /^\.storybook\//,
  /\.stories\.[jt]sx?$/,
];

/** The module ids, relative to `root`, that belong to development tooling. */
export function developmentModules(
  ids: Iterable<string>,
  root: string,
): string[] {
  const found: string[] = [];
  for (const id of ids) {
    // Virtual modules and query suffixes are not files of this project.
    const file = id.split("?")[0] ?? id;
    if (file.startsWith("\0")) continue;
    const path = relative(root, file).split(sep).join("/");
    if (path.startsWith("..")) continue;
    if (DEVELOPMENT.some((pattern) => pattern.test(path))) found.push(path);
  }
  return found;
}

export function productBoundary(root: string): Plugin {
  return {
    name: "product-boundary",
    apply: "build",
    generateBundle(_options, bundle) {
      const leaked = Object.values(bundle).flatMap((output) =>
        output.type === "chunk"
          ? developmentModules(output.moduleIds, root).map(
              (path) => `${path} in ${output.fileName}`,
            )
          : [],
      );
      if (leaked.length)
        this.error(
          `Development-only modules reached the product build: ${leaked.join(", ")}`,
        );
    },
  };
}
