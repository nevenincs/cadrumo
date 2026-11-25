import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { AgentAccess, type AgentCredential } from "./AgentAccess";
import { fixtureInstant } from "@/dev/fixtureDates";

// Appearance only: the keys of a made-up profile in each standing they can be
// in. Issuing and revoking do nothing here, and no key is stored or shown.

type Args = ComponentProps<typeof AgentAccess>;

const NOOP = () => undefined;

const KEYS: AgentCredential[] = [
  {
    id: "3f9a1c2e-71b4-4d58-a9c0-6e2d8b14f7a3",
    standing: "active",
    issuedAt: fixtureInstant(7, 14, "09:12:00Z"),
    expiresAt: fixtureInstant(7, 14, "09:12:00Z", 1),
    lastUsedAt: fixtureInstant(10, 12, "16:40:00Z"),
    categories: ["profile_values", "operation_metadata", "tax_values"],
    allOperations: true,
  },
  {
    id: "b7c4e2d9-0a13-4f6b-8e75-1c9d3a5f2b60",
    standing: "active",
    issuedAt: fixtureInstant(10, 1, "10:00:00Z"),
    expiresAt: fixtureInstant(10, 1, "10:00:00Z", 1),
    categories: ["profile_values", "operation_metadata"],
    allOperations: true,
  },
  {
    id: "9d2f6a41-c8e3-4b07-a5d1-7f0e4c8b3a29",
    standing: "suspended",
    issuedAt: fixtureInstant(8, 14, "08:30:00Z"),
    expiresAt: fixtureInstant(8, 14, "08:30:00Z", 1),
    lastUsedAt: fixtureInstant(9, 22, "12:05:00Z"),
    categories: ["profile_values", "operation_metadata"],
    allOperations: true,
  },
  {
    id: "5e0c7b18-2d4a-4f93-b6a1-8c3d9e0f1a52",
    standing: "pending",
    issuedAt: fixtureInstant(10, 13, "07:55:00Z"),
    expiresAt: fixtureInstant(10, 13, "07:55:00Z", 1),
    categories: ["profile_values", "operation_metadata"],
    allOperations: false,
  },
  {
    id: "2a8e5c70-d4b9-4136-8f2a-5e7c1b9d0f44",
    standing: "expired",
    issuedAt: fixtureInstant(9, 2, "10:00:00Z", -1),
    expiresAt: fixtureInstant(9, 2, "10:00:00Z"),
    lastUsedAt: fixtureInstant(8, 19, "18:20:00Z"),
    categories: ["profile_values", "operation_metadata"],
    allOperations: true,
  },
  {
    id: "6c0b9e83-f1a5-47d2-b8c4-3a6e9d2f7015",
    standing: "revoked",
    issuedAt: fixtureInstant(6, 10, "10:00:00Z"),
    expiresAt: fixtureInstant(6, 10, "10:00:00Z", 1),
    lastUsedAt: fixtureInstant(7, 1, "11:00:00Z"),
    categories: ["profile_values", "operation_metadata", "tax_values"],
    allOperations: true,
  },
];

const meta = {
  title: "Shell/Settings/Agent API keys",
  parameters: { surface: "chrome" },
  args: {
    credentials: KEYS,
    locale: "en",
    onIssue: NOOP,
    onCloseIssue: NOOP,
    onRevoke: NOOP,
    onRefresh: NOOP,
  },
  render: (args: Args, { globals }) => (
    <div className="w-settings max-w-full">
      <AgentAccess {...args} locale={String(globals.locale)} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Keys: Story = {
  name: "Keys in each standing",
};

export const NoKeys: Story = {
  name: "No keys yet",
  args: { credentials: [] },
};

export const Revoking: Story = {
  args: { busyId: KEYS[0]?.id ?? null },
};

export const Issuing: Story = {
  name: "Issuing a key",
  args: { issuing: true },
};

export const IssueRefused: Story = {
  name: "Issuing refused",
  args: { issueRefusal: "profile_locked" },
};

export const IssueNotAvailable: Story = {
  name: "Issuing not available yet",
  args: { issueRefusal: "issue_unavailable" },
};

export const Issued: Story = {
  name: "A key just issued",
  args: {
    issued: { reference: "0b4d7e21-93c5-4a8f-b160-52e7a9c3d8f4" },
    onCopy: () => Promise.resolve(),
  },
};

export const Outcomes: Story = {
  name: "Revoked with cleanup pending, and refused",
  args: {
    outcomes: {
      [KEYS[1]?.id ?? ""]: { kind: "revoked_cleanup_pending" },
      [KEYS[2]?.id ?? ""]: { kind: "refused", code: "profile_locked" },
      [KEYS[0]?.id ?? ""]: { kind: "refused", code: "outcome_unknown" },
    },
  },
};
