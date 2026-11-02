import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { expect, fn, userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract";
import { WorkspaceScreen } from "./WorkspaceScreen";

// The withholdings a register supplies and the estimate from the quarterly
// declarations, in the real workspace over the envelopes the application read
// for synthetic filers: the Modelo 100 of 2025, whose credits come from the
// withholding register. Nothing here is typed into; a credit is corrected in
// the register, which the workspace opens.

const UNIT = "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4";

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Credits({
  shape,
  locale,
  onOpenSurface = () => undefined,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
  onOpenSurface?: (surface: string) => void;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: () => undefined,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={UNIT}
        language={locale}
        locale={locale}
        onBack={() => undefined}
        onOpenSurface={onOpenSurface}
        canOpenSurface={() => true}
        openLink={() => undefined}
        initialView="credits"
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Withholdings",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

/** The credits view, once the workspace has read the declaration. */
const credits = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>("[data-credit]");
      if (!found) throw new Error("the credits are not drawn yet");
      return found;
    },
    { timeout: 15_000 },
  );

/** Asks for the estimate and waits for it to answer. */
const ask = async (canvasElement: HTMLElement) => {
  await credits(canvasElement);
  const button = canvasElement.querySelector<HTMLElement>(
    "[data-estimate-ask]",
  );
  if (!button) throw new Error("the estimate is not offered");
  await userEvent.click(button);
};

export const Unresolved: Story = {
  name: "Salaried, no payer record: unresolved, never zero",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await credits(canvasElement);
    const rows = canvasElement.querySelectorAll<HTMLElement>("[data-credit]");
    expect(rows.length).toBeGreaterThanOrEqual(3);
    // A credit without a figure shows the application's words for why, and
    // no row offers a field to type into.
    for (const row of rows) {
      expect(row).toHaveAttribute("data-origin", expect.any(String));
      expect(row.textContent).not.toMatch(/\b0[.,]00/);
    }
    expect(canvasElement.querySelector("input, textarea")).toBeNull();
  },
};

export const FromRegister: Story = {
  name: "Salaried, certificate in the register: the credit from the register",
  render: (_, { globals }) => (
    <Credits shape="renta-pay" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await credits(canvasElement);
    const row = canvasElement.querySelector<HTMLElement>("[data-credit]");
    expect(row?.querySelector("[data-figure]")).not.toBeNull();
    expect(canvasElement.querySelector("input, textarea")).toBeNull();
  },
};

const opened = fn();

export const RoutesToTheRegister: Story = {
  name: "Open the withholding register to correct a credit",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} onOpenSurface={opened} />
  ),
  play: async ({ canvasElement }) => {
    await credits(canvasElement);
    opened.mockClear();
    const open = canvasElement.querySelector<HTMLElement>(
      "[data-open-surface=withholding]",
    );
    if (!open) throw new Error("the way to the register is not offered");
    await userEvent.click(open);
    await waitFor(() => expect(opened).toHaveBeenCalledWith("withholding"));
  },
};

export const EstimateUnresolved: Story = {
  name: "Estimate: the credit and the totals that read it left without a figure",
  render: (_, { globals }) => (
    <Credits shape="renta-projected" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await ask(canvasElement);
    await waitFor(
      () =>
        expect(
          canvasElement.querySelector("[data-estimate-result]"),
        ).not.toBeNull(),
      { timeout: 15_000 },
    );
    expect(
      canvasElement.querySelectorAll("[data-unresolved-credit]").length,
    ).toBeGreaterThan(0);
    expect(
      canvasElement.querySelectorAll("[data-unresolved-box]").length,
    ).toBeGreaterThan(0);
    // No box without a figure is given one in the estimate.
    expect(canvasElement.querySelector("[data-estimate-box]")).toBeNull();
  },
};

export const EstimateResolved: Story = {
  name: "Estimate: every credit from the register, nothing left without a figure",
  render: (_, { globals }) => (
    <Credits shape="renta-credited" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await ask(canvasElement);
    await waitFor(
      () =>
        expect(
          canvasElement.querySelector("[data-estimate-result]"),
        ).not.toBeNull(),
      { timeout: 15_000 },
    );
    expect(canvasElement.querySelector("[data-unresolved-credit]")).toBeNull();
    expect(canvasElement.querySelector("[data-unresolved-box]")).toBeNull();
    expect(canvasElement.querySelector("[data-estimate-box]")).not.toBeNull();
    expect(canvasElement.querySelector("[data-in-estimate]")).not.toBeNull();
  },
};

export const EstimateRefused: Story = {
  name: "Estimate: no quarterly declaration, refused in the application's words",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await ask(canvasElement);
    await waitFor(
      () =>
        expect(
          canvasElement.querySelector("[data-estimate] [role=status]"),
        ).not.toBeNull(),
      { timeout: 15_000 },
    );
    expect(canvasElement.querySelector("[data-estimate-result]")).toBeNull();
  },
};
