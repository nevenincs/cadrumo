import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import type { SignInController } from "../shell/signIn";
import { DEFAULT_PREFS, type Prefs } from "../shell/layout";
import { useStrings } from "../shell/strings";
import { Rail } from "./Rail";
import { Settings } from "./Settings";
import { Account } from "./SignIn";

// Settings beside the rail it opens from, over preferences held by the story.
const noop = () => undefined;

const account: SignInController = {
  status: {
    supported: true,
    state: "present",
    active_profile: "Demo profile",
    runtimeAvailable: true,
    refusal: null,
  },
  refusal: null,
  retrySeconds: 0,
  busy: false,
  remaining: null,
  signOutFailure: null,
  gated: false,
  submit: async () => undefined,
  signOut: async () => undefined,
  openTui: noop,
  tuiExited: noop,
};

function Screen({
  initial,
  languages,
}: {
  initial: Prefs;
  languages: readonly string[];
}) {
  const t = useStrings();
  const [prefs, setPrefs] = useState(initial);
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
        languages={languages}
        onReset={() => setPrefs(initial)}
        close={noop}
        account={<Account account={account} onSignOut={noop} />}
      />
    </div>
  );
}

const meta = {
  title: "Shell/Settings",
  parameters: { fill: true },
  args: { initial: DEFAULT_PREFS, languages: ["en", "es", "ca", "hu"] },
  render: (args: { initial: Prefs; languages: readonly string[] }) => (
    <Screen {...args} />
  ),
} satisfies Meta<{ initial: Prefs; languages: readonly string[] }>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Defaults: Story = {};

export const EveryChoiceChanged: Story = {
  args: {
    initial: {
      appearance: "dark",
      language: "ca",
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
