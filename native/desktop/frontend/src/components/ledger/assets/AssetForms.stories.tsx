import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, type ReactNode } from "react";
import { userEvent, waitFor } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import { ledgerClassOf } from "@/dev/ledgerClassesFixture";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort } from "../../../shell/ledger";
import { PausedBanner, usePagePause, WritePauseContext } from "../WritePause";
import { AssetForm, type ActProps } from "./AssetForm";
import { BajaForm } from "./BajaForm";
import { ClaimFlow } from "./ClaimFlow";
import { CorrectForm } from "./CorrectForm";
import { DescribeForm } from "./DescribeForm";

// The forms of the Assets tab over the scenario ledger: adding an element,
// describing it, correcting it, recording its depreciation and giving it a
// baja. The choices of a field are the ones the backend serves. Each write
// state has its story: in flight, done, already recorded, refused with what
// was typed kept, incomplete with what to fill in, a claim that overlaps
// another, failed, and a write whose settlement was not seen or whose answer
// was lost, which holds the page's writes behind its banner.

const noop = () => undefined;

/** How the made-up ledger treats a write: it settles as the shape says, or
 * never answers, or is not reached. */
type Hold = "none" | "in_flight" | "unavailable" | "too_large";

type Args = { shape?: LedgerShape; hold?: Hold; locale: string };

/** The scenario's port, with its writes held as `hold` says. A read is
 * answered as ever. */
function useHeldPort(shape: LedgerShape | undefined, hold: Hold): LedgerPort {
  const base = useLedgerPort(shape);
  return useMemo((): LedgerPort => {
    if (hold === "none") return base;
    return {
      ...base,
      submit: (id, payload) =>
        ledgerClassOf(id) !== "write"
          ? base.submit(id, payload)
          : hold === "in_flight"
            ? new Promise(noop)
            : Promise.reject({ code: hold, operation_id: null }),
    };
  }, [base, hold]);
}

function Stage({
  shape,
  hold = "none",
  locale,
  draw,
}: Args & { draw: (props: ActProps) => ReactNode }) {
  const port = useHeldPort(shape, hold);
  const pause = usePagePause({ reader: STORY_READER, afterReread: noop });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col">
        <PausedBanner pause={pause} />
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {draw({ port, reader: STORY_READER, locale, onClose: noop })}
        </div>
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Assets/Forms",
  render: (args, { globals }) => (
    <Stage
      {...args}
      locale={String(globals.locale ?? "en")}
      draw={(props) => <AssetForm {...props} kind="element" assetId={null} />}
    />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const form = (
  draw: (props: ActProps) => ReactNode,
  extra: Partial<Story> = {},
): Story => ({
  ...extra,
  render: (args, { globals }) => (
    <Stage {...args} locale={String(globals.locale ?? "en")} draw={draw} />
  ),
});

// ---- Driving a form ---------------------------------------------------------------

type Play = NonNullable<Story["play"]>;
type Root = HTMLElement;

const drawn = <Found extends HTMLElement>(root: Root, selector: string) =>
  waitFor(
    () => {
      const found = root.querySelector<Found>(selector);
      if (!found) throw new Error(`${selector} is not drawn yet`);
      return found;
    },
    { timeout: 5000 },
  );

/** Types into the field the options named `key`. */
const typed = async (root: Root, key: string, text: string) => {
  const input = await drawn<HTMLInputElement>(
    root,
    `[data-field="${key}"] input`,
  );
  await userEvent.clear(input);
  await userEvent.type(input, text);
};

/** Chooses the `nth` of the choices the options served for `key`. */
const chosen = async (root: Root, key: string, nth: number) => {
  const select = await drawn<HTMLSelectElement>(
    root,
    `[data-field="${key}"] select`,
  );
  const option = await waitFor(
    () => {
      const found = select.querySelectorAll<HTMLOptionElement>(
        'option:not([value=""])',
      )[nth];
      if (!found) throw new Error(`${key} does not offer choice ${nth} yet`);
      return found;
    },
    { timeout: 5000 },
  );
  await userEvent.selectOptions(select, option.value);
};

const pressed = async (root: Root, selector: string) => {
  const button = await drawn<HTMLElement>(
    root,
    `${selector}:not([aria-disabled=true])`,
  );
  await userEvent.click(button);
};

const steps =
  (...all: ((root: Root) => Promise<void>)[]): Play =>
  async ({ canvasElement }) => {
    for (const step of all) await step(canvasElement);
  };

const submit = (root: Root) => pressed(root, ".ledger-asset-submit");

/** The add form filled with the first purchase, which states its figures. */
const fillElement = async (root: Root) => {
  await typed(root, "name", "Sierra de cinta");
  await typed(root, "serial_number", "SC-0412");
  await chosen(root, "asset_kind", 1);
  await typed(root, "in_service_date", "2026-06-15");
  await chosen(root, "method", 0);
  await chosen(root, "authority_class_key", 0);
  await chosen(root, "acquisition", 0);
  await typed(root, "basis_amount", "900.00");
};
const sendElement = steps(fillElement, submit);

const lostAnswer: Play = async (context) => {
  window.__scenarioLedger?.nextWrites(["saved_unread"]);
  await sendElement(context);
};

// ---- Adding an element ------------------------------------------------------------

const adding = (extra: Partial<Story> = {}) =>
  form(
    (props) => <AssetForm {...props} kind="element" assetId={null} />,
    extra,
  );

export const AddElement: Story = adding({ name: "Add element" });
export const AddElementPurchaseWithoutIva: Story = adding({
  name: "Add element, purchase that does not state the IVA",
  play: steps((root) => chosen(root, "acquisition", 1)),
});
export const AddElementIncomplete: Story = adding({
  name: "Add element, incomplete",
  play: steps(submit),
});
export const AddElementDone: Story = adding({
  name: "Add element, done",
  play: sendElement,
});
export const AddElementAlreadyThere: Story = adding({
  name: "Add element, sent again: already recorded",
  play: steps(fillElement, submit, async (root) => {
    await drawn(root, ".ledger-asset-saved");
    await submit(root);
  }),
});
export const AddElementInFlight: Story = adding({
  name: "Add element, in flight",
  args: { hold: "in_flight" },
  play: sendElement,
});
export const AddElementRefused: Story = adding({
  name: "Add element, refused: what was typed is kept",
  play: async (context) => {
    window.__scenarioLedger?.nextWrites(["refused"]);
    await sendElement(context);
  },
});
export const AddElementNotTaken: Story = adding({
  name: "Add element, the ledger takes no writes",
  args: { shape: "refused" },
  play: sendElement,
});
export const AddElementFailed: Story = adding({
  name: "Add element, failed: nothing saved",
  args: { hold: "unavailable" },
  play: sendElement,
});
export const AddElementTooLarge: Story = adding({
  name: "Add element, request too large",
  args: { hold: "too_large" },
  play: sendElement,
});
export const AddElementNotSeen: Story = adding({
  name: "Add element, settlement not seen: held",
  args: { shape: "unknown" },
  play: sendElement,
});
export const AddElementAnswerLost: Story = adding({
  name: "Add element, saved but the answer was lost: held",
  play: lostAnswer,
});

// ---- Describing an element ----------------------------------------------------------

const describing = (assetId: string, extra: Partial<Story> = {}) =>
  form((props) => <DescribeForm {...props} assetId={assetId} />, extra);

const rename = steps(
  (root) => typed(root, "name", "Plotter HP DesignJet"),
  (root) => typed(root, "description", "Plotter de gran formato"),
  submit,
);

export const Describe: Story = describing("plotter", { name: "Edit record" });
export const DescribeDone: Story = describing("plotter", {
  name: "Edit record, done",
  play: rename,
});
export const DescribeWithoutName: Story = describing("plotter", {
  name: "Edit record, name emptied: incomplete",
  play: steps((root) => typed(root, "name", " "), submit),
});
export const DescribeInFlight: Story = describing("plotter", {
  name: "Edit record, in flight",
  args: { hold: "in_flight" },
  play: rename,
});
export const DescribeNotSeen: Story = describing("plotter", {
  name: "Edit record, settlement not seen: held",
  args: { shape: "unknown" },
  play: rename,
});
export const DescribeAnswerLost: Story = describing("plotter", {
  name: "Edit record, saved but the answer was lost: held",
  play: async (context) => {
    window.__scenarioLedger?.nextWrites(["saved_unread"]);
    await rename(context);
  },
});
export const DescribeUnknownElement: Story = describing("nobody", {
  name: "Edit record, element not in the register",
});

// ---- Correcting an element ----------------------------------------------------------

const correcting = (assetId: string, extra: Partial<Story> = {}) =>
  form((props) => <CorrectForm {...props} assetId={assetId} />, extra);

const restate = steps(
  (root) => typed(root, "basis_amount", "19800.00"),
  (root) => typed(root, "non_deductible_iva", "0"),
  submit,
);

export const Correct: Story = correcting("plotter", { name: "Correct" });
export const CorrectWithStaleClaims: Story = correcting("servidor", {
  name: "Correct, claims that no longer match are offered",
});
export const CorrectDone: Story = correcting("servidor", {
  name: "Correct, done: the stale claim is recorded again in the same write",
  play: restate,
});
export const CorrectNotSeen: Story = correcting("servidor", {
  name: "Correct, settlement not seen: held",
  args: { shape: "unknown" },
  play: restate,
});

// ---- Giving an element a baja -------------------------------------------------------

const disposing = (assetId: string, extra: Partial<Story> = {}) =>
  form((props) => <BajaForm {...props} assetId={assetId} />, extra);

const dispose = (date: string) =>
  steps(
    (root) => typed(root, "date", date),
    (root) => chosen(root, "reason", 0),
    (root) => typed(root, "proceeds", "9000.00"),
    (root) => typed(root, "transmission_costs", "150.00"),
    submit,
  );

export const Baja: Story = disposing("plotter", { name: "Baja" });
export const BajaDone: Story = disposing("furgoneta", {
  name: "Baja, done",
  play: dispose("2026-12-31"),
});
export const BajaIncomplete: Story = disposing("plotter", {
  name: "Baja, incomplete",
  play: steps(submit),
});
export const BajaBeforeService: Story = disposing("plotter", {
  name: "Baja, before the element entered service: refused",
  play: dispose("1990-01-31"),
});
export const BajaInFlight: Story = disposing("plotter", {
  name: "Baja, in flight",
  args: { hold: "in_flight" },
  play: dispose("2009-03-31"),
});
export const BajaNotSeen: Story = disposing("plotter", {
  name: "Baja, settlement not seen: held",
  args: { shape: "unknown" },
  play: dispose("2009-03-31"),
});

// ---- Recording depreciation ---------------------------------------------------------

const claiming = (
  assetId: string,
  taxYear: number,
  extra: Partial<Story> = {},
) =>
  form(
    (props) => <ClaimFlow {...props} assetId={assetId} taxYear={taxYear} />,
    extra,
  );

const forecast = (root: Root) => pressed(root, ".ledger-asset-forecast");
const claim = (root: Root) => pressed(root, ".ledger-asset-claim");
/** A span that overlaps the half year already claimed. */
const overlap = async (root: Root) => {
  await typed(root, "covered_from", "2026-01-01");
  await forecast(root);
  await claim(root);
};

export const Claim: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, a year not claimed",
});
export const ClaimForecast: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, forecast shown first",
  play: steps(forecast),
});
export const ClaimDone: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, done",
  play: steps(forecast, claim),
});
export const ClaimAlreadyRecorded: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, sent again: already recorded",
  play: steps(forecast, claim, async (root) => {
    await drawn(root, ".ledger-asset-saved");
    await claim(root);
  }),
});
export const ClaimConflict: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, overlaps a claim: refused, names it",
  play: steps(overlap),
});
export const ClaimFreeMethodWithoutAmount: Story = claiming("impresora", 2026, {
  name: "Record depreciation, free method without an amount: incomplete",
  play: steps(forecast),
});
export const ClaimProjectedYear: Story = claiming("furgoneta", 2027, {
  name: "Record depreciation, a year on projected tables: forecast offered",
  play: steps(forecast),
});
export const ClaimPeriodElapsed: Story = claiming("cristaleria", 2026, {
  name: "Record depreciation, maximum period elapsed: refused with its date",
  play: steps(
    (root) => typed(root, "covered_from", "2026-01-01"),
    (root) => typed(root, "covered_until", "2027-01-01"),
    forecast,
  ),
});
export const ClaimInFlight: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, in flight",
  args: { hold: "in_flight" },
  play: steps(forecast, claim),
});
export const ClaimFailed: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, failed: nothing saved",
  args: { hold: "unavailable" },
  play: steps(forecast, claim),
});
export const ClaimNotSeen: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, settlement not seen: held",
  args: { shape: "unknown" },
  play: steps(forecast, claim),
});
export const ClaimAnswerLost: Story = claiming("furgoneta", 2026, {
  name: "Record depreciation, saved but the answer was lost: held",
  play: async (context) => {
    window.__scenarioLedger?.nextWrites(["saved_unread"]);
    await steps(forecast, claim)(context);
  },
});
