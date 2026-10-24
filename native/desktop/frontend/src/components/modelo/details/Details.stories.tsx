import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { modeloFixture, type ModeloShape } from "../../../dev/modeloFixture";
import form130 from "../../../dev/fixtures/modelo/modelo-130-1T-en.json";
import form303 from "../../../dev/fixtures/modelo/modelo-303-1T-en.json";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { clearIntent, useFormSession, type FormSession } from "../form/session";
import { Details } from "./Details";
import { TodoRail } from "./TodoRail";

// The details panel and the To do rail on the envelopes the application's
// read path produced for the synthetic taxpayer, with the help cards it
// answered for boxes 07 and 19 of modelo 130 and 27 of modelo 303.

// The stories' declaration: a form envelope the application's own read path
// produced for the synthetic taxpayer, the scenario host's modelo port in the
// chosen shape, and a form session with the boxes chosen and the edits staged
// that a story names. What it shows is design and test evidence only.

export type StoryEdit =
  { casilla: string; value: string } | { casilla: string; clear: true };

export type StoryProps = {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  language: OutputLanguage;
  session: FormSession;
  reread: () => Promise<boolean>;
};

export const storyLanguage = (locale: unknown): OutputLanguage =>
  locale === "es" || locale === "ca" || locale === "hu" ? locale : "en";

export function StorySession({
  envelope: initial,
  locale,
  shape = "fixture",
  choose,
  edits = [],
  children,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: unknown;
  shape?: ModeloShape;
  choose?: string;
  edits?: StoryEdit[];
  children: (props: StoryProps) => ReactNode;
}) {
  const language = storyLanguage(locale);
  const port = useMemo(
    () =>
      modeloFixture({
        say: () => undefined,
        wait: () => Promise.resolve(),
        signedIn: () => true,
        shape,
      }),
    [shape],
  );
  const [envelope, setEnvelope] = useState(initial);
  const session = useFormSession({ envelope, port, language });
  const prepared = useRef(false);
  useEffect(() => {
    if (prepared.current) return;
    prepared.current = true;
    for (const edit of edits) {
      const field = session.fieldAt({
        kind: "casilla",
        casilla_id: edit.casilla,
      });
      if (!field) continue;
      // A typed value is read by the application, as the form reads it.
      if ("clear" in edit) session.stage(field, clearIntent(field));
      else void session.enter(field, edit.value);
    }
    if (choose) session.selectCasilla(choose);
  }, [session, edits, choose]);
  const reread = async () => {
    // A new read of the same declaration: the same envelope as a new object.
    setEnvelope(structuredClone(envelope));
    return Promise.resolve(true);
  };
  return <>{children({ envelope, port, language, session, reread })}</>;
}

const F130 = form130 as unknown as ModeloWorkbenchFormProjectionV1;
const F303 = form303 as unknown as ModeloWorkbenchFormProjectionV1;

const meta: Meta = {
  title: "Modelo/Details",
  parameters: { surface: "card" },
  excludeStories: ["StorySession", "storyLanguage"],
};
export default meta;
type Story = StoryObj;

function Panel({
  envelope,
  choose,
  edits,
  locale,
  docked = false,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  choose?: string;
  edits?: StoryEdit[];
  locale: unknown;
  docked?: boolean;
}) {
  return (
    <StorySession
      envelope={envelope}
      locale={locale}
      choose={choose}
      edits={edits}
    >
      {(props) => (
        <div className="w-88 border border-border bg-card">
          <Details
            {...props}
            openLink={() => undefined}
            onOpenSurface={() => undefined}
            onClose={docked ? () => undefined : undefined}
          />
        </div>
      )}
    </StorySession>
  );
}

export const NothingChosen: Story = {
  name: "130 · nothing chosen",
  render: (_, { globals }) => <Panel envelope={F130} locale={globals.locale} />,
};

export const FormulaAndCitations: Story = {
  name: "130 · box 07 with its formula and citations",
  render: (_, { globals }) => (
    <Panel envelope={F130} choose="07" locale={globals.locale} />
  ),
};

export const CouldNotWorkOut: Story = {
  name: "130 · box 19 could not be worked out",
  render: (_, { globals }) => (
    <Panel envelope={F130} choose="19" locale={globals.locale} />
  ),
};

export const OutsideFigure: Story = {
  name: "303 · box 27 uses a figure kept outside the form",
  render: (_, { globals }) => (
    <Panel envelope={F303} choose="27" locale={globals.locale} />
  ),
};

export const StagedChange: Story = {
  name: "130 · box 06 changed, not applied, docked",
  render: (_, { globals }) => (
    <Panel
      envelope={F130}
      choose="06"
      edits={[{ casilla: "06", value: "1.234,56" }]}
      locale={globals.locale}
      docked
    />
  ),
};

export const CardUnavailable: Story = {
  name: "130 · box 08 whose card was not read",
  render: (_, { globals }) => (
    <Panel envelope={F130} choose="08" locale={globals.locale} />
  ),
};

function Rail({
  envelope,
  locale,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: unknown;
}) {
  return (
    <StorySession envelope={envelope} locale={locale}>
      {(props) => (
        <div className="flex h-160 w-64 flex-col border border-border bg-chrome">
          <TodoRail envelope={props.envelope} session={props.session} />
        </div>
      )}
    </StorySession>
  );
}

export const TodoFailed: Story = {
  name: "130 · To do with boxes that could not be worked out",
  render: (_, { globals }) => <Rail envelope={F130} locale={globals.locale} />,
};

export const TodoNothing: Story = {
  name: "303 · To do with nothing that needs the filer",
  render: (_, { globals }) => <Rail envelope={F303} locale={globals.locale} />,
};

export const TodoLocked: Story = {
  name: "130 · To do on a declaration that takes no edits",
  render: (_, { globals }) => (
    <Rail
      envelope={{ ...F130, admitted_baseline: null }}
      locale={globals.locale}
    />
  ),
};
