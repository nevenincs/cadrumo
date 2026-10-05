import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import type { SignInRefusal } from "../ipc/contract";
import type { SignInController } from "../shell/signIn";
import { Account, SignedOut, SignInDialog } from "./SignIn";

// Stories take a controller in a fixed state, so every state of the screen
// can be looked at without a host. They prove presentation only.
function controller(change: Partial<SignInController> = {}): SignInController {
  return {
    status: {
      supported: true,
      state: "absent",
      active_profile: "Demo profile",
      runtimeAvailable: true,
      refusal: null,
    },
    refusal: null,
    retrySeconds: 0,
    busy: false,
    remaining: null,
    gated: true,
    submit: async () => undefined,
    signOut: async () => undefined,
    openTui: () => undefined,
    tuiExited: () => undefined,
    ...change,
  };
}

const refused = (code: string, retryAfterSeconds: number | null = null) =>
  ({ code, retryAfterSeconds }) satisfies SignInRefusal;

function Screen({ account }: { account: SignInController }) {
  const button = useRef<HTMLButtonElement>(null);
  return (
    <div className="flex min-h-dvh bg-background" data-scheme="dark">
      <SignedOut
        account={account}
        onSignIn={() => undefined}
        signInButton={button}
      />
      <SignInDialog
        account={account}
        open
        onOpenChange={() => undefined}
        returnFocus={button}
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

export const RuntimeUnavailable: Story = {
  args: {
    account: controller({
      status: {
        supported: true,
        state: "unknown",
        active_profile: null,
        runtimeAvailable: false,
        refusal: null,
      },
    }),
  },
};

export const UnnamedFailure: Story = {
  args: { account: controller({ refusal: refused("timed_out") }) },
};

export const Checking: Story = {
  render: () => {
    const account = controller({ status: null });
    return (
      <div className="flex min-h-dvh bg-background" data-scheme="dark">
        <SignedOut
          account={account}
          onSignIn={() => undefined}
          signInButton={{ current: null }}
        />
      </div>
    );
  },
};

export const Dismissed: Story = {
  render: () => (
    <div className="flex min-h-dvh bg-background" data-scheme="dark">
      <SignedOut
        account={controller()}
        onSignIn={() => undefined}
        signInButton={{ current: null }}
      />
    </div>
  ),
};

const present = controller({
  gated: false,
  status: {
    supported: true,
    state: "present",
    active_profile: "Demo profile",
    runtimeAvailable: true,
    refusal: null,
  },
});

export const AccountSection: Story = {
  name: "Account",
  parameters: { fill: false, surface: "card" },
  render: () => (
    <div className="grid max-w-settings gap-6">
      <Account account={present} onSignOut={() => undefined} />
      <Account
        account={{ ...present, busy: true }}
        onSignOut={() => undefined}
      />
      <Account
        account={controller({
          gated: true,
          remaining: {
            remainingAccess: {
              automationEnabled: true,
              automationRevoked: false,
            },
          },
        })}
        onSignOut={() => undefined}
      />
      <Account
        account={{ ...present, refusal: refused("timed_out") }}
        onSignOut={() => undefined}
      />
    </div>
  ),
};
