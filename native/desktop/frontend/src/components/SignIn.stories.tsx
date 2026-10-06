import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { accountFixture, refused } from "@/dev/fixtures/account";
import type { SignInController } from "../shell/signIn";
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
        signInButton={button}
      />
      <SignInDialog
        account={account}
        open
        onOpenChange={() => undefined}
        onClosed={() => button.current?.focus()}
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
      <Account
        account={present}
        onSignIn={() => undefined}
        onSignOut={() => undefined}
      />
      <Account
        account={{ ...present, busy: true }}
        onSignIn={() => undefined}
        onSignOut={() => undefined}
      />
      <Account
        account={controller({
          remaining: {
            remainingAccess: {
              automationEnabled: true,
              automationRevoked: false,
            },
          },
        })}
        onSignIn={() => undefined}
        onSignOut={() => undefined}
      />
      <Account
        account={{ ...present, signOutFailure: refused("timed_out") }}
        onSignIn={() => undefined}
        onSignOut={() => undefined}
      />
    </div>
  ),
};
