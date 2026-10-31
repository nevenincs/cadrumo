import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { expect, userEvent, waitFor } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import { SEED_ELEMENTS } from "@/dev/assetsSeed";
import { ledgerClassOf } from "@/dev/ledgerClassesFixture";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort } from "../../../shell/ledger";
import { PausedBanner, usePagePause, WritePauseContext } from "../WritePause";
import { AssetForm, type ActProps } from "./AssetForm";
import { BajaForm } from "./BajaForm";
import { ClaimFlow } from "./ClaimFlow";
import { CorrectForm } from "./CorrectForm";
import { DescribeForm } from "./DescribeForm";
import { ASSET_KEYS } from "./assetsWords";
import { translator } from "../../../shell/strings";

// The forms of the Assets tab over the scenario ledger: adding an element,
// describing it, correcting it, recording its dotación and giving it a baja,
// and changing or removing one. The choices of a field are the ones the
// backend serves. Each write state has its story: in flight, done, already
// recorded, refused with what was typed kept, sent with fields missing, which
// marks them and lists them under the button, a dotación that overlaps
// another and the way to correct it, an element with no plan for the year, a
// baja waiting for its confirmation, failed, and a write whose settlement was
// not seen or whose answer was lost, which holds the page's writes behind its
// banner.

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

/** Chooses the choice the options served for `key` under `value`. */
const chosenValue = async (root: Root, key: string, value: string) => {
  const select = await drawn<HTMLSelectElement>(
    root,
    `[data-field="${key}"] select`,
  );
  await waitFor(
    () => {
      if (!select.querySelector(`option[value="${value}"]`))
        throw new Error(`${key} does not offer ${value} yet`);
    },
    { timeout: 5000 },
  );
  await userEvent.selectOptions(select, value);
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
  await chosen(root, "amortization.authority_class_key", 0);
  await chosen(root, "acquisition", 0);
  await chosenValue(root, "acquired_condition", "new");
  await chosenValue(root, "basis_stage", "taxpayer_owned");
  await chosenValue(root, "opening_status", "missing");
  await typed(root, "basis_amount", "900.00");
  await typed(root, "business_use_share", "100");
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
  name: "Add element, sent with fields missing: marked and listed",
  play: steps(submit),
});
export const AddElementOutsideLedger: Story = adding({
  name: "Add element, bought outside the ledger: date, activity and document",
  play: steps(
    (root) => chosen(root, "asset_kind", 1),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosen(root, "acquisition_shape", 1),
    (root) => typed(root, "declared_acquisition_date", "2024-11-05"),
    (root) => chosen(root, "declared_activity", 0),
    (root) => typed(root, "acquisition_reference", "Factura 2024-118"),
  ),
});
export const AddElementOutsideLedgerLaterPayment: Story = adding({
  name: "Add element, bought outside the ledger, with a later payment from the ledger",
  play: steps(
    (root) => chosen(root, "asset_kind", 1),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosen(root, "acquisition_shape", 1),
    (root) => typed(root, "declared_acquisition_date", "2024-11-05"),
    (root) => chosen(root, "declared_activity", 0),
    (root) => typed(root, "acquisition_reference", "Factura 2024-118"),
    (root) => chosen(root, "further_purchase", 0),
    (root) => chosen(root, "further_shape", 0),
  ),
});
export const AddElementWholeProperty: Story = adding({
  name: "Add element, whole property: its parts",
  play: steps(
    (root) => chosen(root, "asset_kind", 0),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosenValue(root, "basis_stage", "whole_property"),
  ),
});
export const AddElementUsedBuilding: Story = adding({
  name: "Add element, bought used: the date the building was built",
  play: steps(
    (root) => chosen(root, "asset_kind", 0),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosenValue(root, "acquired_condition", "used"),
    (root) => chosenValue(root, "basis_stage", "whole_property"),
  ),
});
export const AddElementOpeningKnown: Story = adding({
  name: "Add element, opening history known: the facts it can state",
  play: steps(
    (root) => chosen(root, "asset_kind", 0),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosenValue(root, "opening_status", "known"),
  ),
});
/** The control a field is drawn on: a calendar for a day, a percent box for a
 * share, numeric entry for an amount and a year, plain text for a name. */
const drawnOn = async (root: Root, key: string) => {
  const field = await drawn<HTMLElement>(root, `[data-field="${key}"]`);
  const input = field.querySelector<HTMLInputElement>("input")!;
  return {
    date: field.querySelector('[data-slot="date-editor"]') !== null,
    percent: field.querySelector('[data-slot="percent-editor"]') !== null,
    inputMode: input.inputMode,
  };
};

export const AddElementEditors: Story = adding({
  name: "Add element, opening known: each field on its own editor, with no writing hint",
  play: async (context) => {
    const root = context.canvasElement;
    await steps(
      (found) => chosen(found, "asset_kind", 0),
      (found) => chosenValue(found, "basis_stage", "taxpayer_owned"),
      (found) => chosenValue(found, "opening_status", "known"),
    )(context);
    await expect(await drawnOn(root, "in_service_date")).toMatchObject({
      date: true,
      percent: false,
    });
    await expect(await drawnOn(root, "business_use_share")).toMatchObject({
      date: false,
      percent: true,
      inputMode: "decimal",
    });
    await expect(await drawnOn(root, "basis_amount")).toMatchObject({
      date: false,
      percent: false,
      inputMode: "decimal",
    });
    await expect(await drawnOn(root, "opening_through")).toMatchObject({
      date: false,
      percent: false,
      inputMode: "numeric",
    });
    await expect(await drawnOn(root, "name")).toMatchObject({
      date: false,
      percent: false,
      inputMode: "",
    });
    const writing = [
      "Year-month-day",
      "Write 70 for 70%",
      "Dot decimal",
      "Four digits",
    ];
    for (const hint of writing)
      await expect(root.textContent).not.toContain(hint);
  },
});
export const AddElementUsedOriginalPrice: Story = adding({
  name: "Add element, bought used on the linear method: the originating price beside the building date",
  play: steps(
    (root) => chosen(root, "asset_kind", 0),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosenValue(root, "method", "linear"),
    (root) => chosenValue(root, "acquired_condition", "used"),
    (root) =>
      drawn(
        root,
        '[data-field="amortization.used_original_price.original_price"]',
      ).then(noop),
  ),
});
export const AddElementNewHidesUsedFacts: Story = adding({
  name: "Add element, bought new: neither the building date nor the originating price is asked",
  play: steps(
    (root) => chosen(root, "asset_kind", 0),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosenValue(root, "method", "linear"),
    (root) => chosenValue(root, "acquired_condition", "new"),
    async (root) => {
      for (const key of [
        "building_construction_date",
        "amortization.used_original_price.original_price",
      ])
        if (root.querySelector(`[data-field="${key}"]`))
          throw new Error(`${key} is asked of an element bought new`);
    },
  ),
});
export const AddElementVehicle: Story = adding({
  name: "Add element, a class that requires a vehicle declaration: it opens as required, with no question",
  play: steps(
    (root) => chosen(root, "asset_kind", 1),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosen(root, "method", 0),
    (root) =>
      chosenValue(
        root,
        "amortization.authority_class_key",
        "transporte-externo",
      ),
    (root) => drawn(root, '[data-field="vehicle_category"]').then(noop),
    async (root) => {
      if (root.querySelector('[data-field="vehicle_declared"]'))
        throw new Error("the declaration is asked as a question");
    },
  ),
});
export const AddElementClassWithoutVehicle: Story = adding({
  name: "Add element, a class that needs no vehicle declaration: nothing is drawn",
  play: steps(
    (root) => chosen(root, "asset_kind", 1),
    (root) => typed(root, "in_service_date", "2026-06-15"),
    (root) => chosen(root, "method", 0),
    (root) =>
      chosenValue(root, "amortization.authority_class_key", "maquinaria"),
  ),
});
export const AddElementDone: Story = adding({
  name: "Add element, done",
  play: sendElement,
});
export const AddElementAlreadyThere: Story = adding({
  name: "Add element, sent again: the same element, recorded once",
  play: steps(fillElement, submit, async (root) => {
    await drawn(root, ".ledger-asset-saved");
    await submit(root);
    // The register answers an identical send with the element it holds, so the
    // line stays the one for a landed write and nothing is refused.
    await waitFor(
      () => {
        if (
          root.querySelector(".ledger-asset-refused, .ledger-asset-incomplete")
        )
          throw new Error("the second send was refused");
        if (!root.querySelector(".ledger-asset-saved"))
          throw new Error("the line for the landed write is gone");
      },
      { timeout: 5000 },
    );
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

/** The year the page stands on when a baja is given: one the registry serves
 * options for, whenever the element came into service. */
const BAJA_YEAR = 2026;

const disposing = (assetId: string, extra: Partial<Story> = {}) =>
  form(
    (props) => <BajaForm {...props} assetId={assetId} taxYear={BAJA_YEAR} />,
    extra,
  );

const fillBaja = (date: string) => async (root: Root) => {
  await typed(root, "date", date);
  await chosen(root, "reason", 0);
  await typed(root, "proceeds", "9000.00");
  await typed(root, "transmission_costs", "150.00");
  await submit(root);
};
const confirm = (root: Root) => pressed(root, ".ledger-asset-confirm-yes");
/** A baja filled in, sent, and confirmed. */
const dispose = (date: string) => steps(fillBaja(date), confirm);

/** The baja an element is given before its form opens, to change or remove. */
const recorded = {
  disposal_date: "2026-03-31",
  reason: "sale",
  proceeds: { decimal: "9000.00" },
  transmission_costs: { decimal: "150.00" },
  market_value: null,
  prior_free_depreciation_regime: null,
  later_affectation_on: null,
};

/** Draws its child once the element has a baja, as an element does that was
 * given one earlier. */
function AfterBaja({
  port,
  assetId,
  children,
}: {
  port: LedgerPort;
  assetId: string;
  children: ReactNode;
}) {
  const [given, setGiven] = useState(false);
  const [refused, setRefused] = useState<Error | null>(null);
  useEffect(() => {
    void port
      .submit("ledger.actividad-asset.dispose", {
        asset_id: assetId,
        disposal: recorded,
      })
      .then((outcome) => {
        if (outcome.kind === "settled") setGiven(true);
        else
          setRefused(
            new Error(
              `the baja given before the form opened was ${outcome.kind}`,
            ),
          );
      })
      .catch((error: unknown) =>
        setRefused(error instanceof Error ? error : new Error(String(error))),
      );
  }, [port, assetId]);
  // A story that depends on a baja already being there fails if it is not.
  if (refused !== null) throw refused;
  return given ? children : null;
}

const changing = (assetId: string, extra: Partial<Story> = {}) =>
  form(
    (props) => (
      <AfterBaja port={props.port} assetId={assetId}>
        <BajaForm {...props} assetId={assetId} taxYear={BAJA_YEAR} />
      </AfterBaja>
    ),
    extra,
  );

export const Baja: Story = disposing("plotter", { name: "Baja" });
export const BajaDone: Story = disposing("furgoneta", {
  name: "Baja, done",
  play: dispose("2026-12-31"),
});
export const BajaIncomplete: Story = disposing("plotter", {
  name: "Baja, sent with fields missing: marked and listed",
  play: steps(submit),
});
export const BajaConfirmation: Story = disposing("furgoneta", {
  name: "Baja, waiting for the person to confirm: nothing sent yet",
  play: steps(fillBaja("2026-12-31")),
});
export const BajaBeforeService: Story = disposing("plotter", {
  name: "Baja, before the element entered service: refused",
  play: dispose("1990-01-31"),
});
export const BajaInFlight: Story = disposing("plotter", {
  name: "Baja, in flight",
  args: { hold: "in_flight" },
  play: dispose("2026-03-31"),
});
export const BajaNotSeen: Story = disposing("plotter", {
  name: "Baja, settlement not seen: held",
  args: { shape: "unknown" },
  play: dispose("2026-03-31"),
});
export const BajaChange: Story = changing("plotter", {
  name: "Baja recorded: change or remove it",
});
export const BajaChangeDone: Story = changing("plotter", {
  name: "Baja recorded, changed: done",
  play: steps((root) => typed(root, "date", "2026-06-30"), submit, confirm),
});
export const BajaRemoveConfirmation: Story = changing("plotter", {
  name: "Baja recorded, removal waiting for the person to confirm",
  play: steps((root) => pressed(root, ".ledger-asset-remove")),
});
export const BajaRemoved: Story = changing("plotter", {
  name: "Baja recorded, removed: done",
  play: steps((root) => pressed(root, ".ledger-asset-remove"), confirm),
});
export const CorrectKeepsBaja: Story = form(
  (props) => (
    <AfterBaja port={props.port} assetId="plotter">
      <CorrectForm {...props} assetId="plotter" />
    </AfterBaja>
  ),
  {
    name: "Correct an element with a baja: the baja stays",
    play: steps((root) => typed(root, "residual_value", "10"), submit),
  },
);

// ---- Recording depreciation ---------------------------------------------------------

/** Each story opens on the year it names: the latest year the plan leaves
 * open is a later one, which the registry has no edition for yet. */
const claiming = (
  assetId: string,
  taxYear: number,
  extra: Partial<Story> = {},
  more: { initialYear?: number; supersedes?: string } = {},
) =>
  form(
    (props) => (
      <ClaimFlow
        {...props}
        assetId={assetId}
        taxYear={taxYear}
        initialYear={more.initialYear ?? taxYear}
        supersedes={more.supersedes}
      />
    ),
    extra,
  );

/** The dotación the plan of an element holds for a year. */
const claimOf = (assetId: string, year: number) =>
  SEED_ELEMENTS.find((seed) => seed.id === assetId)!
    .rows.find((row) => row.tax_year === year)!
    .claims.find((found) => found.effective)!.claim_id;

const forecast = (root: Root) => pressed(root, ".ledger-asset-forecast");
const claim = (root: Root) => pressed(root, ".ledger-asset-claim");
/** A span that overlaps the half year already recorded. */
const overlap = async (root: Root) => {
  await typed(root, "covered_from", "2026-01-01");
  await forecast(root);
};

export const Claim: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, a year not claimed",
});
export const ClaimOpensOnTheServedYear: Story = form(
  (props) => <ClaimFlow {...props} assetId="cristaleria" taxYear={2026} />,
  {
    name: "Record dotación, opens on the year the register names for the element, not the page's",
    play: steps(async (root) => {
      const select = await drawn<HTMLSelectElement>(
        root,
        ".ledger-asset-form-claim select",
      );
      await waitFor(() => {
        if (select.value !== "2025")
          throw new Error("the form did not open on the served year");
      });
    }),
  },
);
export const ClaimForecast: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, forecast shown first",
  play: steps(forecast),
});
export const ClaimForecastEarlierEnd: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, a last day typed before the span's end",
  play: steps((root) => typed(root, "covered_through", "2026-09-30"), forecast),
});
export const ClaimDone: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, done",
  play: steps(forecast, claim),
});
export const ClaimAlreadyRecorded: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, sent again: already recorded",
  play: steps(forecast, claim, async (root) => {
    await drawn(root, ".ledger-asset-saved");
    await claim(root);
  }),
});
export const ClaimConflict: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, overlaps one recorded: refused, offers to correct it",
  play: steps(overlap),
});
export const ClaimConflictCorrectThat: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, overlaps one recorded: switched to correcting it",
  play: steps(overlap, (root) => pressed(root, ".ledger-asset-correct-that")),
});
export const ClaimCorrecting: Story = claiming(
  "furgoneta",
  2026,
  { name: "Correct a dotación, opened from the plan" },
  { initialYear: 2026, supersedes: claimOf("furgoneta", 2026) },
);
export const ClaimCorrectingDone: Story = claiming(
  "furgoneta",
  2026,
  {
    name: "Correct a dotación, done",
    play: steps(forecast, claim),
  },
  { initialYear: 2026, supersedes: claimOf("furgoneta", 2026) },
);
export const ClaimNoPlanForTheYear: Story = claiming(
  "furgoneta",
  2026,
  { name: "Record dotación, the element has no plan for the year" },
  { initialYear: 2040 },
);
export const ClaimFreeMethodWithoutAmount: Story = claiming("impresora", 2026, {
  name: "Record dotación, free method without an amount: incomplete",
  play: steps(forecast),
});
export const ClaimProjectedYear: Story = claiming("furgoneta", 2027, {
  name: "Record dotación, a year on projected tables: marked estimated, forecast offered with the note",
  play: async (context) => {
    await steps(forecast)(context);
    const root = context.canvasElement;
    await drawn(root, ".ledger-asset-forecast-result");
    const t = translator(String(context.globals.locale ?? "en"));
    await waitFor(() => {
      if (!root.textContent?.includes(t(ASSET_KEYS.year_estimated_note)))
        throw new Error("the estimated note is not drawn");
    });
  },
});
export const ClaimNothingOpen: Story = claiming("cristaleria", 2026, {
  name: "Record dotación, nothing open in the year: the reason is said above the dates",
  play: steps(async (root) => {
    await drawn(root, ".ledger-asset-nothing-open");
  }),
});
export const ClaimPeriodElapsed: Story = claiming("cristaleria", 2026, {
  name: "Record dotación, maximum period elapsed: refused with its date",
  play: steps(
    (root) => typed(root, "covered_from", "2026-01-01"),
    (root) => typed(root, "covered_through", "2026-12-31"),
    forecast,
  ),
});
export const ClaimInFlight: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, in flight",
  args: { hold: "in_flight" },
  play: steps(forecast, claim),
});
export const ClaimFailed: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, failed: nothing saved",
  args: { hold: "unavailable" },
  play: steps(forecast, claim),
});
export const ClaimNotSeen: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, settlement not seen: held",
  args: { shape: "unknown" },
  play: steps(forecast, claim),
});
export const ClaimAnswerLost: Story = claiming("furgoneta", 2026, {
  name: "Record dotación, saved but the answer was lost: held",
  play: async (context) => {
    window.__scenarioLedger?.nextWrites(["saved_unread"]);
    await steps(forecast, claim)(context);
  },
});
