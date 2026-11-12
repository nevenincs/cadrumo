import type { Meta, StoryObj } from "@storybook/react-vite";
import { userEvent, waitFor } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type {
  CounterpartyFilingName as StatedFilingName,
  LedgerCounterpartyResult,
} from "../../../shell/ledgerClassificationSetup";
import { usePagePause, WritePauseContext } from "../WritePause";
import { CounterpartyFilingName } from "./CounterpartyFilingName";

// The filing-name statement under a counterparty's answer: none stated, a
// natural person, an entity with two renderings, the person editing, the
// backend's finding about the kind, and a refusal as the backend worded it.

type Args = {
  stated: StatedFilingName | null;
  tax_identifier: string;
  findings?: LedgerCounterpartyResult["findings"];
  refuse?: string;
};

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
});

function Stage(args: Args) {
  const served = useLedgerPort();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: () => undefined,
  });
  const port = args.refuse
    ? {
        ...served,
        submit: async () => ({
          kind: "refused" as const,
          operation_id: "refused",
          revision: 1,
          reason: "REFUSED_LEDGER_COUNTERPARTY_FILING_NAME_INPUT",
          detail: { refusal_words: args.refuse } as never,
        }),
      }
    : served;
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="p-4">
        <CounterpartyFilingName
          port={port}
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

export const NoneStated: Story = { name: "None stated" };

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
  },
};

export const EntityWithRenderings: Story = {
  name: "Entity stated with two renderings",
  args: {
    tax_identifier: "B12345674",
    stated: {
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
    },
  },
};

export const EditingWithoutSecondSurname: Story = {
  name: "Editing, no second surname",
  args: { stated: null },
  play: async ({ canvasElement }) => {
    const root = canvasElement;
    await userEvent.selectOptions(
      root.querySelector("select")!,
      "natural_person",
    );
    await waitFor(() =>
      root.querySelector(".ledger-counterparty-no-second-surname"),
    );
    await userEvent.click(
      root.querySelector(".ledger-counterparty-no-second-surname")!,
    );
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
    findings: [
      {
        code: "counterparty_filing_name_kind_contradicts_identifier_form",
        declared_kind: "natural_person",
        observed_form: "entity",
      },
    ],
  },
};

export const Refused: Story = {
  name: "Refused",
  args: {
    refuse: "A rendering is longer than the width it is stated for.",
    stated: null,
  },
  play: async ({ canvasElement }) => {
    const root = canvasElement;
    await userEvent.selectOptions(root.querySelector("select")!, "entity");
    const input = await waitFor(() => {
      const found = root.querySelector("input");
      if (!found) throw new Error("not yet");
      return found;
    });
    await userEvent.type(input, "Trazo SL");
    await userEvent.click(
      root.querySelector(".ledger-counterparty-filing-name-save")!,
    );
  },
};
