import type { Decorator, Preview } from "@storybook/react-vite";
import { useEffect } from "react";
import { Frame, type Surface } from "../src/dev/catalogue/Frame";
import "../src/dev/index.css";

import "virtual:desktop-palette.css";

// Every story is drawn on a real shell surface, in the scheme and language
// chosen in the toolbar, with the application's own providers around it.
const withShell: Decorator = (Story, context) => {
  const scheme = context.globals.scheme as "light" | "dark";
  const locale = context.globals.locale as string;
  const surface = (context.parameters.surface ?? "background") as Surface;
  useEffect(() => {
    document.documentElement.dataset.scheme = scheme;
    document.documentElement.lang = locale;
  }, [scheme, locale]);
  return (
    <Frame
      surface={surface}
      locale={locale}
      fill={context.parameters.fill === true}
    >
      <Story />
    </Frame>
  );
};

const preview: Preview = {
  decorators: [withShell],
  globalTypes: {
    scheme: {
      description: "Colour scheme",
      toolbar: {
        title: "Scheme",
        icon: "mirror",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
        ],
        dynamicTitle: true,
      },
    },
    locale: {
      description: "Chrome language",
      toolbar: {
        title: "Language",
        icon: "globe",
        items: [
          { value: "en", title: "English" },
          { value: "es", title: "Español" },
          { value: "ca", title: "Català" },
          { value: "hu", title: "Magyar" },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: { scheme: "light", locale: "en" },
  parameters: {
    layout: "fullscreen",
    // Surfaces come from the theme, not from the catalogue's own backgrounds.
    backgrounds: { disable: true },
    controls: { expanded: true },
    a11y: { test: "error" },
    options: {
      storySort: {
        order: ["Foundations", "Primitives", "Shell"],
      },
    },
  },
};

export default preview;
