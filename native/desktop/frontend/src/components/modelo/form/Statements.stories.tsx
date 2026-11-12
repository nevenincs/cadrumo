import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { modeloFixture } from "@/dev/modeloFixture";
import { ModeloEnvelope } from "@/dev/ModeloEnvelope";
import {
  checkingStatements,
  withoutRemoval,
  withStated,
  withStatementsOf,
  type StatementCheck,
} from "@/dev/modeloStatementsFixture";
import { translator } from "../../../shell/strings";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import {
  createModeloWriteHolds,
  declarationWriteKey,
} from "../../../shell/modeloWriteHolds";
import { storyLanguage } from "../details/Details.stories";
import { ReviewDialog } from "../dialogs/ReviewDialog";
import { ModeloWriteScope } from "../WriteScope";
import { FormView } from "./FormView";
import { useFormSession, type FormSession } from "./session";

// The statements a declaration serves, on the Modelo 100 the application
// read for a synthetic salaried filer: each Renta read serves one
// statement, so the form serving two adds the one the uncalculated filer's
// read serves to the paying filer's. A stated box, a baseline that keeps one
// box from being taken out and the check's answers are made in
// `@/dev/modeloStatementsFixture`, since no read holds them yet.

const noop = () => undefined;
const READ_WAIT = 15_000;

/** The salaried filer's Renta, and the read whose statement it adds. */
const RENTA = "modelo-100-0A-pay";
const OTHER = "modelo-100-0A-uncalculated";
/** A declaration that serves no statement. */
const M130 = "modelo-130-1T";

/** What a story does to the read and to the form once it is open. */
type Adjust = (envelope: ModeloWorkbenchFormProjectionV1) => void;
type Setup = (session: FormSession) => void;

function Session({
  envelope,
  locale,
  check,
  setup,
  review,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: unknown;
  check: StatementCheck;
  setup?: Setup;
  review: boolean;
}) {
  const language = storyLanguage(locale);
  const port = useMemo(
    () =>
      checkingStatements(
        modeloFixture({
          say: noop,
          translate: translator,
          wait: () => Promise.resolve(),
          signedIn: () => true,
          shape: "fixture",
        }),
        check,
      ),
    [check],
  );
  const [holds] = useState(createModeloWriteHolds);
  const target = declarationWriteKey(envelope.work_unit_id);
  const session = useFormSession({ envelope, port, language });
  const [details, setDetails] = useState(false);
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current || !setup) return;
    ran.current = true;
    setup(session);
  }, [session, setup]);
  return (
    <ModeloWriteScope
      holds={holds}
      target={target}
      port={port}
      reload={() => Promise.resolve(true)}
    >
      <div className="flex h-full min-h-0 flex-col bg-background">
        <FormView
          envelope={envelope}
          session={session}
          detailsOpen={details}
          onDetailsOpenChange={setDetails}
          onOpenSurface={noop}
        />
        {review && session.stagedCount > 0 && (
          <ReviewDialog
            open
            onOpenChange={noop}
            envelope={envelope}
            session={session}
            port={port}
            language={language}
            onReread={() => Promise.resolve(true)}
          />
        )}
      </div>
    </ModeloWriteScope>
  );
}

/** The paying filer's read with the other read's statement added, then
 * `adjust`ed. */
function TwoStatements({
  other,
  locale,
  adjust,
  children,
}: {
  other: ModeloWorkbenchFormProjectionV1;
  locale: unknown;
  adjust?: Adjust;
  children: (envelope: ModeloWorkbenchFormProjectionV1) => ReactNode;
}) {
  const both = useCallback(
    (envelope: ModeloWorkbenchFormProjectionV1) => {
      withStatementsOf(envelope, other);
      adjust?.(envelope);
    },
    [other, adjust],
  );
  return (
    <ModeloEnvelope name={`${RENTA}-${storyLanguage(locale)}`} adjust={both}>
      {children}
    </ModeloEnvelope>
  );
}

function Renta({
  locale,
  adjust,
  setup,
  check = CHECKED,
  review = false,
}: {
  locale: unknown;
  adjust?: Adjust;
  setup?: Setup;
  check?: StatementCheck;
  review?: boolean;
}) {
  const language = storyLanguage(locale);
  return (
    <ModeloEnvelope key={language} name={`${OTHER}-${language}`}>
      {(other) => (
        <TwoStatements other={other} locale={locale} adjust={adjust}>
          {(envelope) => (
            <Session
              envelope={envelope}
              locale={locale}
              check={check}
              setup={setup}
              review={review}
            />
          )}
        </TwoStatements>
      )}
    </ModeloEnvelope>
  );
}

const CHECKED: StatementCheck = { kind: "checked" };
/** The refusal a check of a withdrawal answers, in words given to the story:
 * the application serves its own, which no read holds yet. */
const REFUSED: StatementCheck = {
  kind: "refused",
  words: "‹the refusal the application serves for this withdrawal›",
};

/** The read with its first statement applied. */
const stated: Adjust = (envelope) => {
  const first = envelope.form.form.carry_attestations[0];
  if (first) withStated(envelope, first);
};

/** The first box a statement stands on. */
const firstStated = (session: FormSession) =>
  session.placed.find((placed) => placed.field.stated_absent !== null)?.field;

const chooseStated: Setup = (session) => {
  const field = firstStated(session);
  if (field) session.selectAddress(field.address);
};

const meta: Meta = {
  title: "Modelo/Statements",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

/** The offer's section once the form draws it. */
const offer = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found =
        canvasElement.querySelector<HTMLElement>("[data-statements]");
      if (!found) throw new Error("the statements are not offered yet");
      return found;
    },
    { timeout: READ_WAIT },
  );

export const TwoServed: Story = {
  name: "100 · two statements served at once",
  render: (_, { globals }) => <Renta locale={globals.locale} />,
  play: async ({ canvasElement }) => {
    const section = await offer(canvasElement);
    await expect(section.querySelectorAll("[data-statement]")).toHaveLength(2);
  },
};

export const BothStaged: Story = {
  name: "100 · both statements staged in one review",
  render: (_, { globals }) => (
    <Renta
      locale={globals.locale}
      review
      setup={(session) => {
        session.stageStatements(session.statements);
      }}
    />
  ),
  play: async ({ canvasElement }) => {
    const page = within(canvasElement.ownerDocument.body);
    const dialog = await page.findByRole("dialog", {}, { timeout: READ_WAIT });
    await waitFor(
      () =>
        expect(dialog.querySelectorAll("[data-statement-line]")).toHaveLength(
          2,
        ),
      { timeout: READ_WAIT },
    );
  },
};

export const StatedBox: Story = {
  name: "100 · a stated box, and its withdrawal offered",
  render: (_, { globals }) => (
    <Renta locale={globals.locale} adjust={stated} setup={chooseStated} />
  ),
  play: async ({ canvasElement }) => {
    await waitFor(
      () => {
        if (!canvasElement.querySelector("[data-stated]"))
          throw new Error("no stated box is drawn yet");
        if (!canvasElement.querySelector("[data-withdraw]"))
          throw new Error("no withdrawal is offered yet");
      },
      { timeout: READ_WAIT },
    );
  },
};

export const FamilyWithdrawn: Story = {
  name: "100 · withdrawing one box withdraws its whole statement",
  render: (_, { globals }) => (
    <Renta
      locale={globals.locale}
      adjust={stated}
      review
      setup={(session) => {
        const field = firstStated(session);
        if (field) session.withdraw(field);
      }}
    />
  ),
  play: async ({ canvasElement }) => {
    const page = within(canvasElement.ownerDocument.body);
    const dialog = await page.findByRole("dialog", {}, { timeout: READ_WAIT });
    await waitFor(
      () =>
        expect(dialog.querySelectorAll("[data-statement-line]")).toHaveLength(
          1,
        ),
      { timeout: READ_WAIT },
    );
  },
};

export const WithdrawalRefused: Story = {
  name: "100 · a withdrawal the check refuses, in the words served",
  render: (_, { globals }) => (
    <Renta
      locale={globals.locale}
      adjust={stated}
      review
      check={REFUSED}
      setup={(session) => {
        const field = firstStated(session);
        if (field) session.withdraw(field);
      }}
    />
  ),
  play: async ({ canvasElement }) => {
    const page = within(canvasElement.ownerDocument.body);
    await page.findByText(
      REFUSED.kind === "refused" ? REFUSED.words : "",
      {},
      { timeout: READ_WAIT },
    );
  },
};

/** The read with its first statement applied and the last of its boxes kept
 * from being taken out. */
const oneKept: Adjust = (envelope) => {
  const first = envelope.form.form.carry_attestations[0];
  if (!first) return;
  withStated(envelope, first);
  const last = first.binding_ids.at(-1);
  if (last) withoutRemoval(envelope, last);
};

export const WithdrawalKept: Story = {
  name: "100 · a statement one of whose boxes cannot be taken out",
  render: (_, { globals }) => (
    <Renta locale={globals.locale} adjust={oneKept} setup={chooseStated} />
  ),
  play: async ({ canvasElement }) => {
    const withdraw = await waitFor(
      () => {
        const found =
          canvasElement.querySelector<HTMLButtonElement>("[data-withdraw]");
        if (!found) throw new Error("no withdrawal is offered yet");
        return found;
      },
      { timeout: READ_WAIT },
    );
    await userEvent.click(withdraw);
    await within(canvasElement).findByRole("status");
  },
};

export const NoneServed: Story = {
  name: "130 · a declaration serving no statement",
  render: (_, { globals }) => (
    <ModeloEnvelope name={`${M130}-${storyLanguage(globals.locale)}`}>
      {(envelope) => (
        <Session
          envelope={envelope}
          locale={globals.locale}
          check={CHECKED}
          review={false}
        />
      )}
    </ModeloEnvelope>
  ),
  play: async ({ canvasElement }) => {
    await waitFor(
      () => {
        if (!canvasElement.querySelector("[data-modelo-form]"))
          throw new Error("the form is not drawn yet");
      },
      { timeout: READ_WAIT },
    );
    await expect(canvasElement.querySelector("[data-statements]")).toBeNull();
  },
};
