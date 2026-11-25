import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { ProvisioningStage, type StagedStart } from "../dev/ProvisioningStage";
import type { SetupShape } from "../dev/setupFixture";
import { DEFAULT_PREFS, type Prefs } from "../shell/layout";
import { useStrings } from "../shell/strings";
import { Rail } from "./Rail";
import { Settings } from "./Settings";

// Settings beside the rail it opens from, over preferences held by the story
// and the scenario host's synthetic setup: its one provisioning section says
// whether Cadrumo is set up and opens the one provisioning panel. Nothing is
// downloaded.
const noop = () => undefined;

type Args = {
  initial: Prefs;
  initialLanguage?: string;
  languages: readonly string[];
  shape: SetupShape;
  starts: StagedStart[];
};

function Screen({
  initial,
  initialLanguage = "en",
  languages,
  shape,
  starts,
}: Args) {
  const t = useStrings();
  const [prefs, setPrefs] = useState(initial);
  const [language, setLanguage] = useState(initialLanguage);
  return (
    <ProvisioningStage shape={shape} latencyMs={900} starts={starts}>
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
    </ProvisioningStage>
  );
}

const meta = {
  title: "Shell/Settings",
  parameters: { fill: true },
  args: {
    initial: DEFAULT_PREFS,
    languages: ["en", "es", "ca", "hu"],
    shape: "ready",
    starts: [],
  },
  render: (args: Args) => <Screen {...args} />,
} satisfies Meta<Args>;
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

/** Every component is set up. */
export const SetUp: Story = {};

/** Some component is not set up yet. */
export const NotComplete: Story = { args: { shape: "fresh" } };

/** A component is setting up now: the section says so and still opens the
 * panel. */
export const SettingUp: Story = {
  args: { shape: "fresh", starts: [{ item: "browser", approve: true }] },
};

/** The status cannot be read. */
export const Unavailable: Story = { args: { shape: "unavailable" } };
