import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import {
  STORY_PERIOD,
  STORY_READER,
  useLedgerPort,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { CounterpartyAsk } from "../../../shell/counterpartyAsk";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  CounterpartyFilingName as StatedFilingName,
  CounterpartyFilingNameSlot,
  LedgerCounterpartyResult,
} from "../../../shell/ledgerClassificationSetup";
import { usePagePause, WritePauseContext } from "../WritePause";
import { CounterpartiesPane } from "./CounterpartiesPane";
import { CounterpartyFilingName } from "./CounterpartyFilingName";

// The filing-name statement under a counterparty's answer: none stated, a
// natural person, an entity with two renderings, the person stating one, the
// backend's finding about the kind in its served words, a refusal as the
// backend served it, an outcome the window did not see settle, and the
// counterparties opened from a calculation note's way out. Every name, tax
// id, edition word and sentence is synthetic.

type Outcome = "settle" | "refuse" | "unknown";

type Args = {
  stated: StatedFilingName | null;
  tax_identifier: string;
  findings?: LedgerCounterpartyResult["findings"];
  slots?: CounterpartyFilingNameSlot[];
  outcome?: Outcome;
};

const REFUSAL_WORDS = "Synthetic: a rendering is longer than its width.";
const REFUSAL_DOOR = "Synthetic: open the counterparty";
const FINDING_WORDS = "Synthetic: the kind differs from the identifier.";

const slot = (
  at: number,
  edition: string,
  width: number,
  state: Partial<CounterpartyFilingNameSlot>,
): CounterpartyFilingNameSlot => ({
  modelo: "synthetic",
  revision_id: `synthetic-${at}`,
  edition_words: edition,
  edition_words_language: "en",
  layout_id: "synthetic",
  export_record_id: "synthetic",
  export_field_id: `synthetic-${at}`,
  width,
  fits: false,
  refusal: "missing",
  composed_length: null,
  uses_rendering: false,
  ...state,
});

const UNSTATED_SLOTS = [
  slot(0, "Synthetic edition A", 40, {}),
  slot(1, "Synthetic edition B", 40, {}),
  slot(2, "Synthetic edition B", 20, {}),
];

const resultOf = (args: Args): LedgerCounterpartyResult => ({
  profile_id: "00000000-0000-4000-8000-000000000001",
  action: "view",
  tax_identifier: args.tax_identifier,
  country_code: null,
  evidenced_scope: null,
  facts: null,
  resolution: null,
  recorded: null,
  withdrawn: null,
  changed: false,
  conflict_context: null,
  provincia_code: null,
  provincia_choices: [],
  filing_name: args.stated,
  findings: args.findings ?? [],
  filing_name_slots: args.slots ?? UNSTATED_SLOTS,
  filing_name_part_limits: [
    { part: "primer_apellido", max_length: 36 },
    { part: "nombre", max_length: 36 },
    { part: "razon_social", max_length: 40 },
  ],
});

/** The served port, with its writes answered as `outcome` asks. */
function answering(served: LedgerPort, outcome: Outcome): LedgerPort {
  if (outcome === "refuse")
    return {
      ...served,
      submit: async () => ({
        kind: "refused" as const,
        operation_id: "refused",
        revision: 1,
        reason: "REFUSED_LEDGER_COUNTERPARTY_FILING_NAME_INPUT",
        detail: {
          detail_version: 1,
          kind: "refused",
          error_code: null,
          message_key: null,
          context: [],
          context_entries_omitted: 0,
          refusal_words: REFUSAL_WORDS,
          refusal_words_language: "en",
          precondition_verdict_json: JSON.stringify({
            failed_condition_id: "synthetic.filing_name.stated",
            evidence: [],
            action: { action_id: "operator.ledger.counterparty.filing_name" },
            argument_bindings: [],
            missing_argument_names: ["tax_identifier"],
            conditionality: "requires_arguments",
            action_words: REFUSAL_DOOR,
            action_words_language: "en",
            target_operation_ids: ["ledger.counterparty"],
            no_recovery_outcome: null,
          }),
        },
      }),
    };
  if (outcome === "unknown")
    return {
      ...served,
      submit: async () => {
        throw { code: "unknown", operation_id: "unknown" };
      },
    };
  return served;
}

function Stage(args: Args) {
  const served = useLedgerPort();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: () => undefined,
  });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="p-4">
        <CounterpartyFilingName
          port={answering(served, args.outcome ?? "settle")}
          result={resultOf(args)}
          country=""
          actor="Ana"
          onSaved={() => undefined}
        />
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Setup/Counterparty filing name",
  render: (args) => <Stage {...args} />,
  args: { stated: null, tax_identifier: "12345678Z" },
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const STATED_AT = "2026-11-10T09:30:00Z";

const ENTITY: StatedFilingName = {
  party_kind: "entity",
  primer_apellido: null,
  segundo_apellido: null,
  no_second_surname: false,
  nombre: null,
  razon_social: "Papelería Trazo Sociedad Limitada",
  renderings: [
    { width: 15, text: "Papelería Trazo" },
    { width: 8, text: "Trazo SL" },
  ],
  asserted_by: "Ana",
  asserted_at: STATED_AT,
};

/** Each served slot as the window shows it: the edition words, then the
 * served fields as tokens and numbers. */
const slotRows = (root: HTMLElement) =>
  [
    ...root.querySelectorAll<HTMLElement>(
      ".ledger-counterparty-filing-name-slots li",
    ),
  ].map((row) =>
    [...row.children].map((part) => part.textContent ?? "").join(" "),
  );

const MISSING = "fits=false refusal=missing uses_rendering=false";

/** Types an entity's company name into the form and saves it. */
async function stateEntity(root: HTMLElement, name: string) {
  await userEvent.selectOptions(root.querySelector("select")!, "entity");
  const input = await waitFor(() => {
    const found = root.querySelector<HTMLInputElement>("input");
    if (!found) throw new Error("not yet");
    return found;
  });
  await userEvent.type(input, name);
  await userEvent.click(
    root.querySelector(".ledger-counterparty-filing-name-save")!,
  );
}

export const NoneStated: Story = {
  name: "None stated",
  play: async ({ canvasElement }) => {
    // Every served slot as served: none filed, the refusal token verbatim.
    await expect(slotRows(canvasElement)).toEqual([
      `Synthetic edition A width=40 ${MISSING}`,
      `Synthetic edition B width=40 ${MISSING}`,
      `Synthetic edition B width=20 ${MISSING}`,
    ]);
    await expect(
      canvasElement.querySelector(
        ".ledger-counterparty-filing-name-part-limits",
      )?.textContent,
    ).toBe("primer_apellido=36nombre=36razon_social=40");
    await expect(
      within(canvasElement).getByText(/Synthetic edition A/),
    ).toBeVisible();
    await expect(
      canvasElement.querySelector(".ledger-counterparty-filing-name-stated"),
    ).toBeNull();
  },
};

export const NaturalPersonStated: Story = {
  name: "Natural person stated",
  args: {
    stated: {
      party_kind: "natural_person",
      primer_apellido: "García",
      segundo_apellido: "López",
      no_second_surname: false,
      nombre: "Marta",
      razon_social: null,
      renderings: [],
      asserted_by: "Ana",
      asserted_at: STATED_AT,
    },
    slots: [
      slot(0, "Synthetic edition A", 40, {
        fits: true,
        refusal: null,
        composed_length: 18,
      }),
      slot(1, "Synthetic edition B", 20, {
        fits: true,
        refusal: null,
        composed_length: 18,
      }),
    ],
  },
  play: async ({ canvasElement }) => {
    await expect(
      canvasElement.querySelector(".ledger-counterparty-filing-name-stated"),
    ).not.toBeNull();
    await expect(slotRows(canvasElement)).toEqual([
      "Synthetic edition A width=40 fits=true refusal=null uses_rendering=false",
      "Synthetic edition B width=20 fits=true refusal=null uses_rendering=false",
    ]);
  },
};

export const EntityWithRenderings: Story = {
  name: "Entity stated with two renderings",
  args: {
    tax_identifier: "B12345674",
    stated: ENTITY,
    slots: [
      slot(0, "Synthetic edition A", 40, {
        fits: true,
        refusal: null,
        composed_length: 33,
      }),
      slot(1, "Synthetic edition B", 15, {
        fits: true,
        refusal: null,
        composed_length: 33,
        uses_rendering: true,
      }),
      slot(2, "Synthetic edition B", 12, {
        refusal: "too_wide",
        composed_length: 33,
      }),
    ],
  },
  play: async ({ canvasElement }) => {
    // Each state is the served token or boolean, never worded here.
    await expect(slotRows(canvasElement)).toEqual([
      "Synthetic edition A width=40 fits=true refusal=null uses_rendering=false",
      "Synthetic edition B width=15 fits=true refusal=null uses_rendering=true",
      "Synthetic edition B width=12 fits=false refusal=too_wide uses_rendering=false",
    ]);
    await expect(
      canvasElement.querySelector(".ledger-counterparty-rendering-for-slot"),
    ).toBeNull();
    // The party kind is shown as served.
    await expect(
      within(canvasElement).getByText("entity", { selector: "dd" }),
    ).toBeVisible();
  },
};

export const Stating: Story = {
  name: "Stating an entity's name",
  play: async ({ canvasElement }) => {
    await stateEntity(canvasElement, "Trazo SL");
    await waitFor(() =>
      expect(
        canvasElement
          .querySelector(".ledger-counterparty-filing-name-save")
          ?.getAttribute("aria-disabled"),
      ).toBeNull(),
    );
    await expect(
      canvasElement.querySelector('[data-slot="refusal-notice"]'),
    ).toBeNull();
    await expect(canvasElement.querySelector(".setup-call-line")).toBeNull();
  },
};

export const KindContradictsIdentifier: Story = {
  name: "Kind contradicts the identifier",
  args: {
    tax_identifier: "B12345674",
    stated: {
      party_kind: "natural_person",
      primer_apellido: "García",
      segundo_apellido: null,
      no_second_surname: true,
      nombre: "Marta",
      razon_social: null,
      renderings: [],
      asserted_by: "Ana",
      asserted_at: STATED_AT,
    },
    slots: [slot(0, "Synthetic edition A", 40, { refusal: "single_surname" })],
    findings: [
      {
        code: "counterparty_filing_name_kind_contradicts_identifier_form",
        declared_kind: "natural_person",
        observed_form: "entity",
        words: FINDING_WORDS,
        words_language: "en",
      },
    ],
  },
  play: async ({ canvasElement }) => {
    // The finding reads as served, and the slot as the export refuses it.
    await expect(within(canvasElement).getByText(FINDING_WORDS)).toBeVisible();
    await expect(slotRows(canvasElement)).toEqual([
      "Synthetic edition A width=40 fits=false refusal=single_surname uses_rendering=false",
    ]);
  },
};

export const Refused: Story = {
  name: "Refused",
  args: { outcome: "refuse" },
  play: async ({ canvasElement }) => {
    await stateEntity(canvasElement, "Trazo SL");
    const notice = await waitFor(() => {
      const found = canvasElement.querySelector<HTMLElement>(
        '[data-slot="refusal-notice"]',
      );
      if (!found) throw new Error("not yet");
      return found;
    });
    // The served sentence, then the served way out in its served words.
    await expect(within(notice).getByText(REFUSAL_WORDS)).toBeVisible();
    await expect(
      within(notice).getByRole("button", { name: REFUSAL_DOOR }),
    ).toBeVisible();
  },
};

export const Unknown: Story = {
  name: "Outcome not seen to settle",
  args: { outcome: "unknown" },
  play: async ({ canvasElement }) => {
    await stateEntity(canvasElement, "Trazo SL");
    const line = await waitFor(() => {
      const found =
        canvasElement.querySelector<HTMLElement>(".setup-call-line");
      if (!found) throw new Error("not yet");
      return found;
    });
    // Unknown stays unknown: no refusal is claimed, and it is never saved
    // again from here.
    await expect(line.dataset.tone).toBe("warning");
    await expect(
      canvasElement.querySelector('[data-slot="refusal-notice"]'),
    ).toBeNull();
  },
};

/** The counterparties as a calculation note's way out opens them, on what
 * it bound. */
function FromWayOut({ ask }: { ask: CounterpartyAsk }) {
  const port = useLedgerPort();
  const { stage, onStage } = useStoryStage();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: () => undefined,
  });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="p-4">
        <CounterpartiesPane
          port={port}
          reader={STORY_READER}
          locale="en"
          rows={null}
          stage={stage.content}
          onStage={onStage}
          years={null}
          fallbackYear={STORY_PERIOD.year}
          period={STORY_PERIOD}
          ask={ask}
        />
      </div>
    </WritePauseContext.Provider>
  );
}

export const OpenedFromWayOut: StoryObj<{ ask: CounterpartyAsk }> = {
  name: "Opened from a calculation note's way out",
  args: { ask: { tax_identifier: null, country_code: null, kind: null } },
  render: (args) => <FromWayOut ask={args.ask} />,
  play: async ({ canvasElement }) => {
    // The way out bound nothing: the person names the counterparty.
    await expect(
      canvasElement.querySelector(".ledger-counterparty-asked"),
    ).not.toBeNull();
    await expect(
      canvasElement.querySelector(".ledger-counterparty-answer"),
    ).toBeNull();
  },
};

export const OpenedFromWayOutBound: StoryObj<{ ask: CounterpartyAsk }> = {
  name: "Opened from a way out that names the counterparty",
  args: {
    ask: { tax_identifier: "B12345674", country_code: null, kind: "entity" },
  },
  render: (args) => <FromWayOut ask={args.ask} />,
  play: async ({ canvasElement }) => {
    // The named counterparty is read at once, and the kind the way out bound
    // is chosen for a name not yet stated.
    const answer = await waitFor(() => {
      const found = canvasElement.querySelector<HTMLElement>(
        ".ledger-counterparty-filing-name",
      );
      if (!found) throw new Error("not yet");
      return found;
    });
    const kinds = [...answer.querySelectorAll("select")].map(
      (select) => select.value,
    );
    await expect(kinds).toContain("entity");
    await expect(slotRows(canvasElement).length).toBeGreaterThan(0);
    // Nothing offers to withdraw what is stated for the counterparty.
    await expect(
      canvasElement.querySelector(".ledger-counterparty-withdraw"),
    ).toBeNull();
    await expect(
      within(canvasElement).queryByRole("button", { name: /withdraw/i }),
    ).toBeNull();
  },
};
