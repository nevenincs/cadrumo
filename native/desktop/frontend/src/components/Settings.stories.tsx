import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { accountFixture, SIGNED_OUT } from "@/dev/fixtures/account";
import { DEFAULT_PREFS, type Prefs } from "../shell/layout";
import { useStrings } from "../shell/strings";
import { Rail } from "./Rail";
import { Settings } from "./Settings";
import { Account } from "./SignIn";

// Settings beside the rail it opens from, over preferences held by the story.
const noop = () => undefined;

const ACCOUNTS = {
  "signed-in": accountFixture({ status: { ...SIGNED_OUT, state: "present" } }),
  "signed-out": accountFixture(),
  "no-profile": accountFixture({
    status: { ...SIGNED_OUT, active_profile: null },
  }),
} as const;

function Screen({
  initial,
  languages,
  account: phase = "signed-in",
}: {
  initial: Prefs;
  languages: readonly string[];
  account?: keyof typeof ACCOUNTS;
}) {
  const account = ACCOUNTS[phase];
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
        account={
          <Account
            account={account}
            onSignIn={noop}
            onSignOut={noop}
            onOpenTui={noop}
          />
        }
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
    languages: readonly string[];
    account?: keyof typeof ACCOUNTS;
  }) => <Screen {...args} />,
} satisfies Meta<{
  initial: Prefs;
  languages: readonly string[];
  account?: keyof typeof ACCOUNTS;
}>;
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

export const SignedOutAccount: Story = {
  name: "Signed out",
  args: { account: "signed-out" },
};

export const NoProfile: Story = {
  name: "No active profile",
  args: { account: "no-profile" },
};

export const OneLanguage: Story = {
  name: "One bundled language",
  args: { languages: ["en"] },
};
