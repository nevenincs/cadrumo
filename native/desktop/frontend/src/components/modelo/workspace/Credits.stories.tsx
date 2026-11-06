import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { expect, fn, userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import type { LedgerErrorDetail } from "../../../shell/ledger";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { byName } from "@/dev/globByName";

// The withholdings a register supplies and the estimate from the quarterly
// declarations, in the real workspace over the envelopes the application read
// for synthetic filers: the Modelo 100 of 2025, whose credits come from the
// withholding register. Nothing here is typed into; a credit is corrected in
// the register, which the workspace opens.

const UNIT = "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4";

const refusals = byName(
  import.meta.glob<LedgerErrorDetail>(
    "@fixtures/modelo/refusal-project-quarter-incomplete-*.json",
    { import: "default" },
  ),
);

/** The refusal the application recorded for the quarter that cannot yet give
 * its result, in `locale`. */
async function incomplete(locale: OutputLanguage): Promise<LedgerErrorDetail> {
  const load = refusals[`refusal-project-quarter-incomplete-${locale}`];
  if (!load) throw new Error("No refusal is stored for the incomplete quarter");
  return load();
}

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Credits({
  shape,
  locale,
  onOpenSurface = () => undefined,
  onOpenWork,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
  onOpenSurface?: (surface: string) => void;
  /** Opens another declaration, as the shell does; without it the estimate
   * offers no step that opens one. */
  onOpenWork?: (workUnitId: string) => void;
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
        onOpenWork={onOpenWork}
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

export const Dependents: Story = {
  name: "The boxes the application works out from the credits, apart from the credits",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await credits(canvasElement);
    const region = canvasElement.querySelector<HTMLElement>(
      "section:has([data-credit]) ~ section:has([data-credit])",
    );
    if (!region)
      throw new Error("the boxes worked out from the credits are not drawn");
    const boxes = (root: ParentNode) =>
      [...root.querySelectorAll<HTMLElement>("[data-credit]")].map(
        (row) => row.dataset.credit,
      );
    const dependents = boxes(region);
    expect(dependents.length).toBeGreaterThan(0);
    // A credit is listed as a credit, never again among the boxes read from it.
    const all = boxes(canvasElement);
    const listedCredits = all.slice(0, all.length - dependents.length);
    for (const box of dependents) expect(listedCredits).not.toContain(box);
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

/** The step button a refusal offers, once the estimate has answered. */
const offeredStep = (canvasElement: HTMLElement, kind: string) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>(
        `[data-estimate-step=${kind}]`,
      );
      if (!found) throw new Error(`the ${kind} step is not offered yet`);
      return found;
    },
    { timeout: 15_000 },
  );

/** The estimate is asked for again: no refusal stands and the ask is on
 * offer. */
const askedAgain = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const button = canvasElement.querySelector<HTMLButtonElement>(
        "[data-estimate-ask]",
      );
      if (!button || button.disabled)
        throw new Error("the estimate cannot be asked for again yet");
      if (canvasElement.querySelector("[data-estimate] [role=status]"))
        throw new Error("the refusal still stands");
      expect(canvasElement.querySelector("[data-estimate-step]")).toBeNull();
    },
    { timeout: 15_000 },
  );

export const EstimateOffersCreation: Story = {
  name: "Estimate: no quarterly declaration, creating the first quarter is offered in the application's words",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await ask(canvasElement);
    const step = await offeredStep(canvasElement, "create_work");
    // The sentence on the button is the application's, never an action
    // identifier or a command.
    expect(step.textContent?.trim()).not.toBe("");
    expect(step.textContent).not.toMatch(/operator\.|`|--/);
    expect(canvasElement.querySelector("[data-estimate-result]")).toBeNull();
  },
};

const openedWork = fn();

/** Steps the first quarter from not created to calculated without its
 * answers, asking for the estimate again after each, and asks once more. */
const reachTheIncompleteQuarter = async (canvasElement: HTMLElement) => {
  await ask(canvasElement);
  await userEvent.click(await offeredStep(canvasElement, "create_work"));
  await askedAgain(canvasElement);
  await userEvent.click(
    canvasElement.querySelector<HTMLElement>("[data-estimate-ask]")!,
  );
  // The declaration just created is the one to calculate.
  await userEvent.click(await offeredStep(canvasElement, "calculate_work"));
  await askedAgain(canvasElement);
  await userEvent.click(
    canvasElement.querySelector<HTMLElement>("[data-estimate-ask]")!,
  );
};

export const EstimateOffersCalculation: Story = {
  name: "Estimate: the first quarter created, calculating it is offered, and the estimate is asked for again after each step",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await reachTheIncompleteQuarter(canvasElement);
    // What the quarter still lacks is the application's to say, and with no
    // shell to open another declaration in, it names no step to take here.
    await waitFor(
      () =>
        expect(
          canvasElement.querySelector("[data-estimate] [role=status]"),
        ).not.toBeNull(),
      { timeout: 15_000 },
    );
    expect(canvasElement.querySelector("[data-estimate-step]")).toBeNull();
    expect(canvasElement.querySelector("[data-estimate-result]")).toBeNull();
  },
};

export const EstimateOffersOpeningTheQuarter: Story = {
  name: "Estimate: the quarter calculated without its earlier-filing answers, its open boxes are named and opening it is offered",
  render: (_, { globals }) => (
    <Credits shape="renta" locale={language(globals)} onOpenWork={openedWork} />
  ),
  play: async ({ canvasElement, globals }) => {
    openedWork.mockClear();
    await reachTheIncompleteQuarter(canvasElement);
    const step = await offeredStep(canvasElement, "open_work");
    // Both the sentence and the button are the application's words: the open
    // boxes are named in the sentence, never an amount, and the button names
    // no action identifier or command.
    const sentence = canvasElement.querySelector<HTMLElement>(
      "[data-estimate] [role=status]",
    );
    expect(sentence?.textContent?.trim()).not.toBe("");
    // The sentence is the one the application served, and it names the open
    // inputs the refusal carries.
    const served = await incomplete(language(globals));
    expect(sentence?.textContent?.trim()).toBe(served.refusal_words);
    const inputs = served.context.find((fact) => fact.key === "inputs");
    expect(String(inputs?.value)).not.toBe("");
    expect(sentence?.textContent).toContain(String(inputs?.value));
    expect(step.textContent?.trim()).not.toBe("");
    expect(step.textContent).not.toMatch(/operator\.|`|--/);
    expect(canvasElement.querySelector("[data-estimate-result]")).toBeNull();
    await userEvent.click(step);
    // The shell is asked to open the declaration the step addresses; nothing
    // was sent to the application.
    expect(openedWork).toHaveBeenCalledTimes(1);
    expect(openedWork).toHaveBeenCalledWith(
      expect.stringMatching(/^[0-9a-f]{64}$/),
    );
  },
};
