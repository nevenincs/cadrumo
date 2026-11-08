import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect } from "storybook/test";
import calculation from "@fixtures/modelo/calculate-130.json" with { type: "json" };
import type { ModeloWorkCalculatePublicResultV3 } from "../../../shell/modeloContract/modeloWork";
import { UnresolvedFindings } from "./UnresolvedFindings";

// What the calculation of a Modelo 130 could give no value for, as the
// application served it with the result: each input and box in its own
// words, and no figure beside a box that has none.

const served = calculation as unknown as ModeloWorkCalculatePublicResultV3;

const meta: Meta<typeof UnresolvedFindings> = {
  title: "Modelo/Calculation without a value",
  component: UnresolvedFindings,
  args: {
    bindings: served.unresolved_bindings,
    casillas: served.unresolved_casillas,
    bindingsTitle: "Inputs without a value",
    casillasTitle: "Boxes without a figure",
    boxName: (row) => <span className="font-mono">{row.box}</span>,
  },
  decorators: [
    (Story) => (
      <div className="flex max-w-3xl flex-col gap-3 p-6">
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof UnresolvedFindings>;

/** Every input and box the result lists is drawn with the application's
 * words, and none is drawn as an amount. */
export const Unresolved: Story = {
  name: "Unresolved inputs and boxes, never a zero",
  play: async ({ canvasElement }) => {
    for (const row of served.unresolved_bindings) {
      const line = canvasElement.querySelector(
        `[data-unresolved-credit="${row.casilla_id}"]`,
      );
      expect(line?.textContent).toContain(row.words);
    }
    for (const row of served.unresolved_casillas) {
      expect(
        canvasElement.querySelector(
          `[data-unresolved-box="${row.casilla_id}"]`,
        ),
      ).not.toBeNull();
      expect(canvasElement.textContent).toContain(row.reason_words);
    }
    expect(canvasElement.textContent).not.toMatch(/\d+[.,]\d{2}\b/);
  },
};

/** A calculation that left nothing without a value draws nothing. */
export const Nothing: Story = {
  args: { bindings: [], casillas: [] },
  play: async ({ canvasElement }) => {
    expect(canvasElement.querySelector("section")).toBeNull();
  },
};
