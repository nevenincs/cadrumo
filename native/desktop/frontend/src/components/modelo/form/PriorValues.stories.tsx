import type { Meta, StoryObj } from "@storybook/react-vite";
import { useCallback, useMemo, useRef, useState, useEffect } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { modeloFixture } from "@/dev/modeloFixture";
import { ModeloEnvelope } from "@/dev/ModeloEnvelope";
import {
  PRIOR_FAMILY,
  PRIOR_WORDS,
  readingEntries,
  withPriorValues,
  type PriorShape,
} from "@/dev/modeloPriorValuesFixture";
import { translator } from "../../../shell/strings";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import type { RefusalIntent } from "../../../shell/refusal";
import {
  createModeloWriteHolds,
  declarationWriteKey,
} from "../../../shell/modeloWriteHolds";
import { storyLanguage } from "../details/Details.stories";
import { ReviewDialog } from "../dialogs/ReviewDialog";
import { ModeloWriteScope } from "../WriteScope";
import { FormView } from "./FormView";
import { useFormSession, type FormSession } from "./session";

// The figures a filer can state for earlier returns the application does not
// hold, on the Modelo 100 the application read for a synthetic salaried
// filer, with two of its carries served as one family of earlier returns in
// placeholder words (`@/dev/modeloPriorValuesFixture`): offered, stated and
// withdrawn as a whole, or refused with the served way out.

const noop = () => undefined;
const READ_WAIT = 15_000;
const RENTA = "modelo-100-0A-pay";

type Setup = (session: FormSession) => void;

function Session({
  envelope,
  locale,
  setup,
  review,
  onRefusalAction,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: unknown;
  setup?: Setup;
  review: boolean;
  onRefusalAction?: (intent: RefusalIntent) => void;
}) {
  const language = storyLanguage(locale);
  const port = useMemo(
    () =>
      readingEntries(
        modeloFixture({
          say: noop,
          translate: translator,
          wait: () => Promise.resolve(),
          signedIn: () => true,
          shape: "fixture",
        }),
      ),
    [],
  );
  const [holds] = useState(createModeloWriteHolds);
  const target = declarationWriteKey(envelope.work_unit_id);
  const session = useFormSession({ envelope, port, language });
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
          onOpenSurface={noop}
          onRefusalAction={onRefusalAction}
          opensRefusalPlace={(place) =>
            place.page === "declarations" &&
            place.definition === "modelo.work.list"
          }
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

function Renta({
  locale,
  shape,
  setup,
  review = false,
  onRefusalAction,
}: {
  locale: unknown;
  shape: PriorShape;
  setup?: Setup;
  review?: boolean;
  onRefusalAction?: (intent: RefusalIntent) => void;
}) {
  const language = storyLanguage(locale);
  const adjust = useCallback(
    (envelope: ModeloWorkbenchFormProjectionV1) =>
      withPriorValues(envelope, shape),
    [shape],
  );
  return (
    <ModeloEnvelope
      key={language}
      name={`${RENTA}-${language}`}
      adjust={adjust}
    >
      {(envelope) => (
        <Session
          envelope={envelope}
          locale={locale}
          setup={setup}
          review={review}
          onRefusalAction={onRefusalAction}
        />
      )}
    </ModeloEnvelope>
  );
}

/** Chooses the first box holding a stated figure, so its page is drawn. */
const chooseStated: Setup = (session) => {
  const found = session.placed.find(
    (placed) => placed.field.stated_prior_value,
  );
  if (found) session.selectAddress(found.field.address);
};

const meta: Meta = {
  title: "Modelo/Figures of earlier returns",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

/** The offer's section once the form draws it. */
const offer = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>(
        "[data-prior-values]",
      );
      if (!found) throw new Error("the figures are not offered yet");
      return found;
    },
    { timeout: READ_WAIT },
  );

export const Offered: Story = {
  name: "100 · a family of earlier returns offered, and a figure stated",
  render: (_, { globals }) => <Renta locale={globals.locale} shape="offered" />,
  play: async ({ canvasElement }) => {
    const section = await offer(canvasElement);
    const family = section.querySelector<HTMLElement>(
      `[data-prior-family="${PRIOR_FAMILY}"]`,
    );
    await expect(family).not.toBeNull();
    const group = within(family as HTMLElement);
    // The family is headed by the served earlier returns, and each carry
    // offers the served action with what it states and does.
    await expect(group.getByText(PRIOR_WORDS.source)).toBeVisible();
    const entries = (family as HTMLElement).querySelectorAll(
      "[data-prior-entry]",
    );
    await expect(entries).toHaveLength(2);
    const first = within(entries[0] as HTMLElement);
    await expect(first.getAllByText(PRIOR_WORDS.statement)).toHaveLength(1);
    // Typing a figure and stating it stages the served statement.
    await userEvent.type(
      first.getByRole("textbox", { name: PRIOR_WORDS.action }),
      "1234",
    );
    await userEvent.click(
      first.getByRole("button", { name: PRIOR_WORDS.action }),
    );
    await waitFor(() => expect(first.getByText("1234")).toBeVisible(), {
      timeout: READ_WAIT,
    });
  },
};

export const Stated: Story = {
  name: "100 · figures stated for one family, each box marked",
  render: (_, { globals }) => (
    <Renta locale={globals.locale} shape="stated" setup={chooseStated} />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const section = await offer(canvasElement);
    // Each carry of the family reads as stated, and the form marks each box
    // with the served words for where its value comes from.
    await expect(
      section.querySelectorAll('[data-prior-entry][data-stated="true"]'),
    ).toHaveLength(2);
    await waitFor(
      () =>
        expect(
          canvasElement.querySelectorAll(
            `[data-stated-prior="${PRIOR_FAMILY}"]`,
          ).length,
        ).toBeGreaterThan(0),
      { timeout: READ_WAIT },
    );
    await expect(
      within(section).getAllByText(t("desktop.modelo.statements.mark")),
    ).toHaveLength(2);
    // The family offers its one served withdrawal.
    const withdraw = section.querySelector<HTMLButtonElement>(
      `[data-withdraw-prior="${PRIOR_FAMILY}"]`,
    );
    await expect(withdraw?.textContent).toContain(PRIOR_WORDS.withdrawAction);
    await expect(
      within(section).getByText(PRIOR_WORDS.withdrawEffect),
    ).toBeVisible();
  },
};

export const Withdrawn: Story = {
  name: "100 · withdrawing a family withdraws every figure stated for it",
  render: (_, { globals }) => (
    <Renta locale={globals.locale} shape="stated" review />
  ),
  play: async ({ canvasElement }) => {
    const section = await offer(canvasElement);
    const withdraw = section.querySelector<HTMLButtonElement>(
      `[data-withdraw-prior="${PRIOR_FAMILY}"]`,
    );
    await userEvent.click(withdraw as HTMLButtonElement);
    // Both carries are staged as one withdrawal, on one review line in the
    // served words.
    const page = within(canvasElement.ownerDocument.body);
    const dialog = await page.findByRole("dialog", {}, { timeout: READ_WAIT });
    await waitFor(
      () =>
        expect(dialog.querySelectorAll("[data-statement-line]")).toHaveLength(
          1,
        ),
      { timeout: READ_WAIT },
    );
    const line = dialog.querySelector<HTMLElement>("[data-statement-line]");
    await expect(line?.textContent).toContain(PRIOR_WORDS.withdrawAction);
    await expect(line?.textContent).toContain(PRIOR_WORDS.withdrawEffect);
  },
};

/** The served ways out a story's refusal notice followed. */
const followed: RefusalIntent[] = [];

export const Refused: Story = {
  name: "100 · a carry whose earlier return is held, refused with its way out",
  render: (_, { globals }) => (
    <Renta
      locale={globals.locale}
      shape="refused"
      onRefusalAction={(intent) => followed.push(intent)}
    />
  ),
  play: async ({ canvasElement }) => {
    followed.length = 0;
    const section = await offer(canvasElement);
    const refused = section.querySelector<HTMLElement>(
      '[data-prior-entry][data-admitted="false"]',
    );
    await expect(refused).not.toBeNull();
    const entry = within(refused as HTMLElement);
    // The served sentence, and the served way out by its served words; no
    // figure can be typed on the refused carry.
    await expect(entry.getByText(PRIOR_WORDS.refusal)).toBeVisible();
    await expect(entry.queryByRole("textbox")).toBeNull();
    await userEvent.click(
      entry.getByRole("button", { name: PRIOR_WORDS.door }),
    );
    await expect(followed.map((intent) => intent.place)).toEqual([
      { page: "declarations", definition: "modelo.work.list" },
    ]);
  },
};
