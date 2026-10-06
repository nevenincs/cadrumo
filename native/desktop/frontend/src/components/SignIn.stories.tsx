import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { accountFixture, refused, SIGNED_OUT } from "@/dev/fixtures/account";
import type { SignInController } from "../shell/signIn";
import { useStrings } from "../shell/strings";
import { Account, SignedOut, SignInDialog } from "./SignIn";

// Stories take a controller in a fixed state, so every state of the screen
// can be looked at without a host. They prove presentation only.
const controller = accountFixture;

function Screen({ account }: { account: SignInController }) {
  const button = useRef<HTMLButtonElement>(null);
  return (
    <div className="flex min-h-dvh bg-background" data-scheme="dark">
      <SignedOut
        account={account}
        onSignIn={() => undefined}
        onOpenTui={() => undefined}
        signInButton={button}
      />
      <SignInDialog
        account={account}
        open
        onOpenChange={() => undefined}
        onClosed={() => button.current?.focus()}
        onOpenTui={() => undefined}
      />
    </div>
  );
}

const meta = {
  title: "Shell/Sign-in",
  parameters: { fill: true },
  args: { account: controller() },
  render: (args: { account: SignInController }) => <Screen {...args} />,
} satisfies Meta<{ account: SignInController }>;
export default meta;
type Story = StoryObj<typeof meta>;

export const SignedOutState: Story = { name: "Signed out" };

export const SigningIn: Story = {
  args: { account: controller({ busy: true }) },
};

export const WrongPassword: Story = {
  args: { account: controller({ refusal: refused("CREDENTIAL_REJECTED") }) },
};

export const Throttled: Story = {
  args: {
    account: controller({
      refusal: refused("THROTTLED", 30),
      retrySeconds: 18,
    }),
  },
};

export const ProfileLocked: Story = {
  args: { account: controller({ refusal: refused("PROFILE_LOCKED") }) },
};

const SERVICES_DOWN = {
  supported: true,
  state: "unknown",
  active_profile: null,
  runtimeAvailable: false,
  refusal: null,
} as const;
const NO_PROFILE = { ...SIGNED_OUT, active_profile: null };
const UNKNOWN = {
  ...SIGNED_OUT,
  state: "unknown",
  refusal: refused("timed_out"),
} as const;
const PRESENT = { ...SIGNED_OUT, state: "present" } as const;

export const NoProfile: Story = {
  name: "No active profile",
  args: { account: controller({ status: NO_PROFILE }) },
};

export const RuntimeUnavailable: Story = {
  name: "Services not running",
  args: { account: controller({ status: SERVICES_DOWN }) },
};

export const UnnamedFailure: Story = {
  args: { account: controller({ refusal: refused("timed_out") }) },
};

export const StateUnknown: Story = {
  name: "State unknown",
  args: { account: controller({ status: UNKNOWN }) },
};

// The TUI pane alone, as it stands once the dialog is put aside: one for
// every phase that withholds the TUI.
function Pane({ account }: { account: SignInController }) {
  return (
    <div className="flex min-h-dvh bg-background" data-scheme="dark">
      <SignedOut
        account={account}
        onSignIn={() => undefined}
        onOpenTui={() => undefined}
        signInButton={{ current: null }}
      />
    </div>
  );
}

// The same gate in a second pane beside the TUI's, as the calendar shows
// it: its own sentence for what signing in gives, and quiet actions, so the
// window has one filled button and not two.
function Beside({ account }: { account: SignInController }) {
  const t = useStrings();
  return (
    <div className="grid min-h-dvh grid-cols-2">
      <div className="flex bg-background">
        <SignedOut
          account={account}
          lead={t("desktop.calendar.signed_out")}
          quiet
          onSignIn={() => undefined}
          onOpenTui={() => undefined}
        />
      </div>
      <div className="flex bg-background" data-scheme="dark">
        <SignedOut
          account={account}
          onSignIn={() => undefined}
          onOpenTui={() => undefined}
        />
      </div>
    </div>
  );
}

export const PaneChecking: Story = {
  name: "Pane: checking",
  render: () => <Pane account={controller({ status: null })} />,
};

export const PaneSignedOut: Story = {
  name: "Pane: signed out",
  render: () => <Pane account={controller()} />,
};

export const PaneNoProfile: Story = {
  name: "Pane: no active profile",
  render: () => <Pane account={controller({ status: NO_PROFILE })} />,
};

export const PaneServicesDown: Story = {
  name: "Pane: services not running",
  render: () => <Pane account={controller({ status: SERVICES_DOWN })} />,
};

export const PaneUnknown: Story = {
  name: "Pane: state unknown",
  render: () => <Pane account={controller({ status: UNKNOWN })} />,
};

export const PaneLocked: Story = {
  name: "Pane: profile locked",
  render: () => (
    <Pane account={controller({ refusal: refused("PROFILE_LOCKED") })} />
  ),
};

export const BesideSignedOut: Story = {
  name: "Two panes: signed out",
  render: () => <Beside account={controller()} />,
};

export const BesideLocked: Story = {
  name: "Two panes: profile locked",
  render: () => (
    <Beside account={controller({ refusal: refused("PROFILE_LOCKED") })} />
  ),
};

export const BesideNoProfile: Story = {
  name: "Two panes: no active profile",
  render: () => <Beside account={controller({ status: NO_PROFILE })} />,
};

// The account in settings, in every phase: the profile and its sign-in say
// the same thing the rest of the window does.
const present = controller({ status: PRESENT });
const SECTIONS: [string, SignInController][] = [
  ["Signed in", present],
  ["Signing out", { ...present, busy: true }],
  ["Sign-out refused", { ...present, signOutFailure: refused("timed_out") }],
  [
    "Signed out, agent access left on",
    controller({
      remaining: {
        remainingAccess: { automationEnabled: true, automationRevoked: false },
      },
    }),
  ],
  ["No active profile", controller({ status: NO_PROFILE })],
  ["Services not running", controller({ status: SERVICES_DOWN })],
  ["State unknown", controller({ status: UNKNOWN })],
  ["Profile locked", controller({ refusal: refused("PROFILE_LOCKED") })],
  ["Continuing in the TUI", controller({ handover: true })],
];

export const AccountSection: Story = {
  name: "Account in settings",
  parameters: { fill: false, surface: "card" },
  render: () => (
    <div className="grid max-w-settings gap-8">
      {SECTIONS.map(([name, account]) => (
        <Specimen key={name} title={name} className="grid gap-3">
          <Account
            account={account}
            onSignIn={() => undefined}
            onSignOut={() => undefined}
            onOpenTui={() => undefined}
          />
        </Specimen>
      ))}
    </div>
  ),
};
