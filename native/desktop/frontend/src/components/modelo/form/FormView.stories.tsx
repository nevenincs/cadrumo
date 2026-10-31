import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { modeloFixture } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { FormView } from "./FormView";
import { useFormSession, type FormSession } from "./session";

// The generated form over the envelopes the application read for a
// synthetic taxpayer, one declaration per story. Nothing here knows a
// modelo: each story names a work unit and the form draws what its read
// holds.

const noop = () => undefined;

const UNITS = {
  "130": "66354cafad021ef81e8c4bce2a0d361a2fa3ba568efc325ee607266291fd8fb3",
  "303": "b650ba021eda8c3082ea9d66d8be078c7c6247610af8772ddd48d75b604198f6",
  "347": "f8b5118f6aa31dfa3ba496cc98360941661880792b4f29c991453f94e77e97da",
  "390": "af66ad3c64bd5b1a6d6670a20a645c9966136f578c4209d2eab1e83d69f16aa3",
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
}: {
  modelo: keyof typeof UNITS;
  locale: OutputLanguage;
  setup?: Setup;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: noop,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "fixture",
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

export const OnePage: Story = {
  name: "130 · one page, boxes that could not be calculated",
  render: (_, { globals }) => <Form modelo="130" locale={language(globals)} />,
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
        if (typed) await session.enter(typed, "1.234,56");
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
  name: "390 · editing not admitted, eight pages",
  render: (_, { globals }) => <Form modelo="390" locale={language(globals)} />,
};
