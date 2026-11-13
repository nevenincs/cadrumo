import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import type { ModeloFormStepState } from "../../../shell/modeloContract/modeloWorkForm";
import { translator } from "../../../shell/strings";
import { JourneySteps } from "./JourneySteps";

// The steps of filing a declaration as the read model serves them: the
// states a story shows are served values, and the component only draws them.

const meta: Meta = {
  title: "Modelo/Journey steps",
  decorators: [
    (Story) => (
      <div className="p-6">
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj;

const FILLING: ModeloFormStepState[] = [
  { step: "fill", status: "current" },
  { step: "calculate", status: "pending" },
  { step: "review", status: "pending" },
  { step: "file", status: "pending" },
];
const BLOCKED: ModeloFormStepState[] = [
  { step: "fill", status: "done" },
  { step: "calculate", status: "done" },
  { step: "review", status: "blocked" },
  { step: "file", status: "pending" },
];
const HELD: ModeloFormStepState[] = [
  { step: "fill", status: "current" },
  { step: "calculate", status: "pending" },
  { step: "review", status: "pending" },
  { step: "file", status: "pending" },
];
const RECORDED: ModeloFormStepState[] = [
  { step: "fill", status: "done" },
  { step: "calculate", status: "done" },
  { step: "review", status: "done" },
  { step: "file", status: "done" },
];

async function expectServed(
  canvasElement: HTMLElement,
  locale: unknown,
  served: ModeloFormStepState[],
) {
  const t = translator(String(locale));
  const items = within(canvasElement).getAllByRole("listitem");
  expect(items).toHaveLength(served.length);
  served.forEach(({ step, status }, index) => {
    expect(items[index]).toHaveAttribute("data-step", step);
    expect(items[index]).toHaveAttribute("data-status", status);
    expect(items[index]).toHaveTextContent(t(`workspace.modelo.step.${step}`));
    if (status === "current")
      expect(items[index]).toHaveAttribute("aria-current", "step");
    else expect(items[index]).not.toHaveAttribute("aria-current");
  });
}

export const Filling: Story = {
  name: "Steps · filling in",
  render: () => <JourneySteps steps={FILLING} />,
  play: ({ canvasElement, globals }) =>
    expectServed(canvasElement, globals.locale, FILLING),
};

export const Blocked: Story = {
  name: "Steps · the check is blocked",
  render: () => <JourneySteps steps={BLOCKED} />,
  play: ({ canvasElement, globals }) =>
    expectServed(canvasElement, globals.locale, BLOCKED),
};

export const ChangesHeld: Story = {
  name: "Steps · while changes are held, nothing is done",
  render: () => <JourneySteps steps={HELD} />,
  play: ({ canvasElement, globals }) =>
    expectServed(canvasElement, globals.locale, HELD),
};

export const Recorded: Story = {
  name: "Steps · recorded as filed",
  render: () => <JourneySteps steps={RECORDED} />,
  play: ({ canvasElement, globals }) =>
    expectServed(canvasElement, globals.locale, RECORDED),
};
