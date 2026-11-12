import { seededUnit } from "@/dev/seededUnits";
import { RENTA_UNIT } from "@/dev/rentaUnit";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, waitFor } from "storybook/test";
import rulesIncomplete from "@fixtures/modelo/scenario-rules-incomplete.json" with { type: "json" };
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import { typedAmount } from "../details/Details.stories";
import { FormView } from "./FormView";
import { useFormSession, type FormSession } from "./session";

// The generated form over the envelopes the application read for a
// synthetic taxpayer, one declaration per story. Nothing here knows a
// modelo: each story names a work unit and the form draws what its read
// holds.

const noop = () => undefined;

const UNITS = {
  "130": seededUnit("130"),
  "303": seededUnit("303"),
  "347": seededUnit("347"),
  "rules-incomplete": rulesIncomplete.work_unit_id,
  "100": RENTA_UNIT,
} as const;

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

/** What a story does to the form once it is open. */
type Setup = (
  session: FormSession,
  envelope: ModeloWorkbenchFormProjectionV1,
) => void | Promise<void>;

function Loaded({
  envelope,
  port,
  locale,
  setup,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  locale: OutputLanguage;
  setup?: Setup;
}) {
  const session = useFormSession({ envelope, port, language: locale });
  const [details, setDetails] = useState(false);
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current || !setup) return;
    ran.current = true;
    void setup(session, envelope);
  }, [session, setup, envelope]);
  return (
    <FormView
      envelope={envelope}
      session={session}
      detailsOpen={details}
      onDetailsOpenChange={setDetails}
      onOpenSurface={noop}
    />
  );
}

function Form({
  modelo,
  locale,
  setup,
  shape = "fixture",
}: {
  modelo: keyof typeof UNITS;
  locale: OutputLanguage;
  setup?: Setup;
  shape?: ModeloShape;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: noop,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  const [envelope, setEnvelope] =
    useState<ModeloWorkbenchFormProjectionV1 | null>(null);
  useEffect(() => {
    let live = true;
    void port.current?.form(UNITS[modelo], locale).then((read) => {
      if (live) setEnvelope(read);
    });
    return () => {
      live = false;
    };
  }, [modelo, locale]);
  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      {envelope && port.current && (
        <Loaded
          key={`${modelo}-${locale}`}
          envelope={envelope}
          port={port.current}
          locale={locale}
          setup={setup}
        />
      )}
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Form",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

/** Opens what the read serves about the chosen box, once the form draws it. */
async function openChosenFacts(canvasElement: HTMLElement) {
  const button = await waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLButtonElement>(
        '[aria-selected="true"] [data-field-facts]',
      );
      if (!found) throw new Error("the chosen box is not drawn yet");
      return found;
    },
    { timeout: 15_000 },
  );
  button.click();
}

export const OnePage: Story = {
  name: "130 · one page, boxes that could not be calculated",
  render: (_, { globals }) => <Form modelo="130" locale={language(globals)} />,
};

export const BoxNotes: Story = {
  name: "130 · what the calculation noted beside a box",
  render: (_, { globals }) => (
    <Form modelo="130" locale={language(globals)} shape="income" />
  ),
  play: async ({ canvasElement }) => {
    await waitFor(
      () => {
        if (!canvasElement.querySelector("[data-level]"))
          throw new Error("the box notes are not drawn yet");
      },
      { timeout: 15_000 },
    );
  },
};

export const FieldHelp: Story = {
  name: "130 · a box's help and details",
  render: (_, { globals }) => (
    <Form
      modelo="130"
      locale={language(globals)}
      setup={(session, envelope) => {
        // A box the read gives help for, whichever box that is.
        const helped = envelope.form.form.pages
          .flatMap((page) => page.sections)
          .flatMap((section) => section.blocks)
          .flatMap((block) => (block.kind === "field" ? [block.field] : []))
          .find((field) => field.help !== null && field.box !== null);
        if (helped) session.selectAddress(helped.address);
      }}
    />
  ),
  play: ({ canvasElement }) => openChosenFacts(canvasElement),
};

export const FieldWithoutHelp: Story = {
  name: "303 · a box the read gives no help",
  render: (_, { globals }) => (
    <Form
      modelo="303"
      locale={language(globals)}
      setup={(session, envelope) => {
        // A box on its own line, so its row is the one the story opens.
        const bare = envelope.form.form.pages
          .flatMap((page) => page.sections)
          .flatMap((section) => section.blocks)
          .flatMap((block) => (block.kind === "field" ? [block.field] : []))
          .find((field) => field.help === null && field.box !== null);
        if (bare) session.selectAddress(bare.address);
      }}
    />
  ),
  play: ({ canvasElement }) => openChosenFacts(canvasElement),
};

export const Staged: Story = {
  name: "130 · a typed value, not applied",
  render: (_, { globals }) => (
    <Form
      modelo="130"
      locale={language(globals)}
      setup={async (session) => {
        const box = (number: string) =>
          session.placed.find((placed) => placed.field.box === number)?.field;
        const typed = box("06");
        if (typed) await session.enter(typed, typedAmount(globals.locale));
        session.selectBox("06");
      }}
    />
  ),
};

export const ReplaceSource: Story = {
  name: "303 · a value carried from a source, chosen to replace",
  render: (_, { globals }) => (
    <Form
      modelo="303"
      locale={language(globals)}
      setup={(session) => {
        const fed = session.placed.find(
          (placed) =>
            placed.field.editability === "overridable_source" &&
            placed.field.edit_address.kind === "binding" &&
            placed.field.bindings[0]?.policy.surface !== "none",
        );
        if (fed) session.select(fed.key);
        if (fed) session.setPageId(fed.pageId);
      }}
    />
  ),
};

export const Pages: Story = {
  name: "303 · pages, grids, repeated records, unplaced boxes",
  render: (_, { globals }) => <Form modelo="303" locale={language(globals)} />,
};

export const Records: Story = {
  name: "347 · repeated records",
  render: (_, { globals }) => (
    <Form
      modelo="347"
      locale={language(globals)}
      setup={(session, envelope) => {
        const page = envelope.form.form.pages.find((candidate) =>
          candidate.sections.some((section) =>
            section.blocks.some((block) => block.kind === "repeating"),
          ),
        );
        if (page) session.setPageId(page.id);
      }}
    />
  ),
};

export const ReadOnly: Story = {
  name: "Editing not admitted",
  render: (_, { globals }) => (
    <Form modelo="rules-incomplete" locale={language(globals)} />
  ),
};

export const RentaHeadings: Story = {
  name: "100 · employment income under the heading the read serves",
  render: (_, { globals }) => (
    <Form
      modelo="100"
      locale={language(globals)}
      setup={(session) => {
        session.selectBox("0003");
      }}
    />
  ),
};

export const RentaCreditsUnresolved: Story = {
  name: "100 · withholding credits no certificate supplies, unresolved",
  render: (_, { globals }) => (
    <Form
      modelo="100"
      locale={language(globals)}
      setup={(session) => {
        session.selectBox("0596");
      }}
    />
  ),
  play: ({ canvasElement }) => openChosenFacts(canvasElement),
};

export const RentaCreditFromRegister: Story = {
  name: "100 · a withholding credit the register supplies",
  render: (_, { globals }) => (
    <Form
      modelo="100"
      shape="renta-pay"
      locale={language(globals)}
      setup={(session) => {
        session.selectBox("0596");
      }}
    />
  ),
  play: ({ canvasElement }) => openChosenFacts(canvasElement),
};

export const RentaResultToPay: Story = {
  name: "100 · result of the return, to pay",
  render: (_, { globals }) => (
    <Form
      modelo="100"
      shape="renta-pay"
      locale={language(globals)}
      setup={(session) => {
        session.selectBox("0670");
      }}
    />
  ),
};

export const RentaResultToRefund: Story = {
  name: "100 · result of the return, to refund",
  render: (_, { globals }) => (
    <Form
      modelo="100"
      shape="renta-refund"
      locale={language(globals)}
      setup={(session) => {
        session.selectBox("0670");
      }}
    />
  ),
};

export const RentaActivityIncome: Story = {
  name: "100 · activity income from the ledger, result not calculated",
  render: (_, { globals }) => (
    <Form
      modelo="100"
      shape="renta-activity"
      locale={language(globals)}
      setup={(session) => {
        session.selectBox("0171");
      }}
    />
  ),
};

/** The row of `box` once the form draws it. */
const rowOf = (canvasElement: HTMLElement, box: string) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>(
        `[data-key="c:${box}"]`,
      );
      if (!found) throw new Error(`box ${box} is not drawn yet`);
      return found;
    },
    { timeout: 15_000 },
  );

/** A Renta story that chooses `box` and checks the row it draws. */
function renta(
  name: string,
  box: string,
  check: (row: HTMLElement) => void,
): Story {
  return {
    name,
    render: (_, { globals }) => (
      <Form
        modelo="100"
        shape="renta-pay"
        locale={language(globals)}
        setup={(session) => {
          session.selectBox(box);
        }}
      />
    ),
    play: async ({ canvasElement }) => check(await rowOf(canvasElement, box)),
  };
}

/** A calculated box carries a figure and offers no field to type into. */
const worked = (row: HTMLElement) =>
  expect(row.querySelector("input, textarea")).toBeNull();
/** An answer the filer gives is offered as something to edit. */
const given = (row: HTMLElement) =>
  expect(row.querySelector("input, textarea, select, button")).not.toBeNull();

export const RentaBeforeCompensation: Story = renta(
  "100 · the base before compensation is worked out, not typed",
  "0500",
  worked,
);

export const RentaAmountCompensated: Story = renta(
  "100 · the amount compensated is worked out from the chain, not typed",
  "1391",
  worked,
);

export const RentaEarlierNegativeBase: Story = renta(
  "100 · the earlier negative base is the filer's to give",
  "1388",
  given,
);

export const RentaDirectEstimation: Story = renta(
  "100 · whether direct estimation is normal is the filer's to give",
  "0168",
  given,
);
