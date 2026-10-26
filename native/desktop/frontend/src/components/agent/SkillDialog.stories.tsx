import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import {
  FIXTURE_SKILLS,
  fixtureSkillDetail,
  fixtureSkillVerification,
} from "@/dev/fixtures/agentSkills";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { SkillDialog } from "./SkillDialog";

// Appearance only: the skills are the scenario host's made-up ones, read at
// once, and nothing is asked of an agent.

type Args = ComponentProps<typeof SkillDialog>;

const known = (name: string) => {
  const held = FIXTURE_SKILLS.find((skill) => skill.name === name);
  return held
    ? Promise.resolve(held)
    : Promise.reject(
        Object.assign(new Error(name), {
          code: "agent_gateway_skill_not_found",
        }),
      );
};

const meta = {
  title: "Shell/Agent/Skill dialog",
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    locale: "en",
    command: { kind: "review", name: "cadrumo-iva-trimestral" },
    review: (name) => known(name).then(fixtureSkillDetail),
    verify: (name) => known(name).then(fixtureSkillVerification),
    onClose: NOOP,
  },
  render: (args: Args, { globals }) => (
    <SkillDialog
      key={`${args.command.kind}:${args.command.name}`}
      {...args}
      locale={String(globals.locale)}
    />
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Review: Story = {};

export const VerifyClean: Story = {
  name: "Verify: every check passes",
  args: { command: { kind: "verify", name: "cadrumo-calendario" } },
};

export const VerifyWarned: Story = {
  name: "Verify: passes with a warning",
  args: { command: { kind: "verify", name: "cadrumo-facturas" } },
};

export const VerifyFailed: Story = {
  name: "Verify: fails",
  args: { command: { kind: "verify", name: "cadrumo-revision-fuentes" } },
};

export const Unknown: Story = {
  name: "No such skill",
  args: { command: { kind: "review", name: "cadrumo-no-existe" } },
};
