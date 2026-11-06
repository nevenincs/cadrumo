import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { modeloFixture, type ModeloShape } from "../../../dev/modeloFixture";
import { ModeloEnvelope } from "../../../dev/ModeloEnvelope";
import { formatAmount } from "../../../shared/numbers";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import { clearIntent, useFormSession, type FormSession } from "../form/session";
import { Details } from "./Details";
import { TodoRail } from "./TodoRail";
import {
  createModeloWriteHolds,
  declarationWriteKey,
} from "../../../shell/modeloWriteHolds";
import { ModeloWriteScope, ScopedWriteHoldNotice } from "../WriteScope";

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

/** The stories' typed figure, as the filer writes it in their own language. */
export const typedAmount = (locale: unknown) =>
  formatAmount(storyLanguage(locale), "1234.56");

/** The session over the envelope stored for a declaration in the language
 * shown (`modelo-130-1T` is read as `modelo-130-1T-es`), so its words and
 * its figures are one language. `adjust` changes the envelope read, for a
 * state the application's own read did not produce. */
export function StorySession({
  declaration,
  adjust,
  ...session
}: Omit<SessionProps, "envelope"> & {
  declaration: string;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
}) {
  const language = storyLanguage(session.locale);
  return (
    <ModeloEnvelope
      key={language}
      name={`${declaration}-${language}`}
      adjust={adjust}
    >
      {(read) => <Session {...session} envelope={read} />}
    </ModeloEnvelope>
  );
}

type SessionProps = {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: unknown;
  shape?: ModeloShape;
  choose?: string;
  edits?: StoryEdit[];
  children: (props: StoryProps) => ReactNode;
};

function Session({
  envelope: initial,
  locale,
  shape = "fixture",
  choose,
  edits = [],
  children,
}: SessionProps) {
  const language = storyLanguage(locale);
  const port = useMemo(
    () =>
      modeloFixture({
        say: () => undefined,
        translate: translator,
        wait: () => Promise.resolve(),
        signedIn: () => true,
        shape,
      }),
    [shape],
  );
  const [envelope, setEnvelope] = useState(initial);
  const [holds] = useState(createModeloWriteHolds);
  const target = declarationWriteKey(envelope.work_unit_id);
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
    const before = holds.get(target);
    // A new read of the same declaration: the same envelope as a new object.
    setEnvelope(structuredClone(envelope));
    if (before) holds.readCompleted(before);
    return Promise.resolve(true);
  };
  return (
    <ModeloWriteScope holds={holds} target={target} port={port} reload={reread}>
      <ScopedWriteHoldNotice />
      {children({ envelope, port, language, session, reread })}
    </ModeloWriteScope>
  );
}

const M130 = "modelo-130-1T";
const M303 = "modelo-303-1T";
const M100 = "modelo-100-0A";

const meta: Meta = {
  title: "Modelo/Details",
  parameters: { surface: "card" },
  excludeStories: ["StorySession", "storyLanguage", "typedAmount"],
};
export default meta;
type Story = StoryObj;

function Panel({
  declaration,
  choose,
  edits,
  locale,
  docked = false,
}: {
  declaration: string;
  choose?: string;
  edits?: StoryEdit[];
  locale: unknown;
  docked?: boolean;
}) {
  return (
    <StorySession
      declaration={declaration}
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
  render: (_, { globals }) => (
    <Panel declaration={M130} locale={globals.locale} />
  ),
};

export const FormulaAndCitations: Story = {
  name: "130 · box 07 with its formula and citations",
  render: (_, { globals }) => (
    <Panel declaration={M130} choose="07" locale={globals.locale} />
  ),
};

export const CouldNotWorkOut: Story = {
  name: "130 · box 19 could not be worked out",
  render: (_, { globals }) => (
    <Panel declaration={M130} choose="19" locale={globals.locale} />
  ),
};

export const OutsideFigure: Story = {
  name: "303 · box 27 uses a figure kept outside the form",
  render: (_, { globals }) => (
    <Panel declaration={M303} choose="27" locale={globals.locale} />
  ),
};

export const StagedChange: Story = {
  name: "130 · box 06 changed, not applied, docked",
  render: (_, { globals }) => (
    <Panel
      declaration={M130}
      choose="06"
      edits={[{ casilla: "06", value: typedAmount(globals.locale) }]}
      locale={globals.locale}
      docked
    />
  ),
};

export const CardUnavailable: Story = {
  name: "130 · box 08 whose card was not read",
  render: (_, { globals }) => (
    <Panel declaration={M130} choose="08" locale={globals.locale} />
  ),
};

const withoutBaseline = (envelope: ModeloWorkbenchFormProjectionV1) => {
  envelope.admitted_baseline = null;
};

function Rail({
  declaration,
  adjust,
  locale,
}: {
  declaration: string;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
  locale: unknown;
}) {
  return (
    <StorySession declaration={declaration} adjust={adjust} locale={locale}>
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
  render: (_, { globals }) => (
    <Rail declaration={M130} locale={globals.locale} />
  ),
};

export const TodoNothing: Story = {
  name: "303 · To do with nothing that needs the filer",
  render: (_, { globals }) => (
    <Rail declaration={M303} locale={globals.locale} />
  ),
};

export const TodoLocked: Story = {
  name: "130 · To do on a declaration that takes no edits",
  render: (_, { globals }) => (
    <Rail declaration={M130} adjust={withoutBaseline} locale={globals.locale} />
  ),
};

export const RentaCreditUnresolved: Story = {
  name: "100 · box 0596 the register has no certificate for",
  render: (_, { globals }) => (
    <Panel declaration={M100} choose="0596" locale={globals.locale} />
  ),
};

export const RentaCreditSupplied: Story = {
  name: "100 · box 0596 supplied by the register",
  render: (_, { globals }) => (
    <Panel declaration={`${M100}-pay`} choose="0596" locale={globals.locale} />
  ),
};

export const RentaResultCard: Story = {
  name: "100 · box 0670, the result of the return",
  render: (_, { globals }) => (
    <Panel declaration={`${M100}-pay`} choose="0670" locale={globals.locale} />
  ),
};

export const TodoRenta: Story = {
  name: "100 · To do with the credits and totals that could not be worked out",
  render: (_, { globals }) => (
    <Rail declaration={M100} locale={globals.locale} />
  ),
};
