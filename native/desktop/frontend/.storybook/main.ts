import type { StorybookConfig } from "@storybook/react-vite";
import { fileURLToPath } from "node:url";

// What the catalogue's server may read: this project, and the documentation's
// own static files, which hold the shell's typefaces and mark.
const frontend = fileURLToPath(new URL("..", import.meta.url));
const docsStatic = fileURLToPath(
  new URL("../../../../docs/_static", import.meta.url),
);

// The catalogue renders the application's own components with the
// application's own Vite configuration, theme and generated strings. Two of
// that configuration's plugins are not for it: the product boundary, which
// refuses stories in a build, and the documentation fixture server.
const NOT_FOR_THE_CATALOGUE = new Set([
  "product-boundary",
  "development-docs-fixture",
]);

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.tsx"],
  addons: ["@storybook/addon-a11y"],
  framework: { name: "@storybook/react-vite", options: {} },
  core: {
    disableTelemetry: true,
    enableCrashReports: false,
    disableWhatsNewNotifications: true,
  },
  viteFinal(base) {
    return {
      ...base,
      plugins: (base.plugins ?? [])
        .flat()
        .filter(
          (plugin) =>
            !(
              plugin &&
              typeof plugin === "object" &&
              "name" in plugin &&
              NOT_FOR_THE_CATALOGUE.has(plugin.name)
            ),
        ),
      build: { ...base.build, rolldownOptions: undefined },
      server: {
        ...base.server,
        fs: {
          ...base.server?.fs,
          allow: [...(base.server?.fs?.allow ?? []), frontend, docsStatic],
        },
      },
    };
  },
};

export default config;
