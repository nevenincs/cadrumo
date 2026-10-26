import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { DEFAULT_PREFS, type Prefs } from "../shell/layout";
import { useStrings } from "../shell/strings";
import { Rail } from "./Rail";
import { Settings } from "./Settings";

// Settings beside the rail it opens from, over preferences held by the story.
const noop = () => undefined;

function Screen({
  initial,
  initialLanguage = "en",
  languages,
}: {
  initial: Prefs;
  initialLanguage?: string;
  languages: readonly string[];
}) {
  const t = useStrings();
  const [prefs, setPrefs] = useState(initial);
  const [language, setLanguage] = useState(initialLanguage);
  return (
    <div className="grid h-dvh grid-cols-[auto_1fr] bg-chrome">
      <Rail
        label={t("desktop.rail.label")}
        top={[
          {
            id: "search",
            icon: "search",
            label: t("desktop.rail.search"),
            onClick: noop,
          },
        ]}
        bottom={[
          {
            id: "settings",
            icon: "settings",
            label: t("desktop.rail.settings"),
            pressed: true,
            onClick: noop,
          },
        ]}
      />
      <div className="bg-background" />
      <Settings
        prefs={prefs}
        setPrefs={setPrefs}
        language={{ value: language, languages, onChange: setLanguage }}
        onReset={() => setPrefs(initial)}
        close={noop}
      />
    </div>
  );
}

const meta = {
  title: "Shell/Settings",
  parameters: { fill: true },
  args: { initial: DEFAULT_PREFS, languages: ["en", "es", "ca", "hu"] },
  render: (args: {
    initial: Prefs;
    initialLanguage?: string;
    languages: readonly string[];
  }) => <Screen {...args} />,
} satisfies Meta<{
  initial: Prefs;
  initialLanguage?: string;
  languages: readonly string[];
}>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Defaults: Story = {};

export const EveryChoiceChanged: Story = {
  args: {
    initialLanguage: "ca",
    initial: {
      appearance: "dark",
      terminals: "dark",
      orientation: "column",
      order: "tui",
      fontSize: "x-large",
    },
  },
};

export const OneLanguage: Story = {
  name: "One bundled language",
  args: { languages: ["en"] },
};
