import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, waitFor, within } from "storybook/test";
import type { ModeloShape } from "../../../dev/modeloFixture";
import { EXPORT_DISCLOSURE } from "../../../dev/modeloExportDisclosure";
import { translator } from "../../../shell/strings";
import type {
  ModeloFormExportHold,
  ModeloWorkbenchFormProjectionV1,
} from "../../../shell/modeloContract/modeloWorkForm";
import { StorySession, typedAmount } from "../details/Details.stories";
import { FilingView } from "./FilingView";
import { ReviewDialog } from "./ReviewDialog";

// The review dialog and the Export and record view on the modelo 130
// envelope the application's read path produced for the synthetic taxpayer.
// The scenario host answers the edit preflight as the application did; it
// has no answer for an apply or an export, so a story's shape says whether
// those are refused, never reach the runtime, or are lost in transit. The
// filing stages are the envelopes the application read for the first
// quarter's modelo 130 after its check, its export, a recorded filing and a
// calculation that changed after the export, each in the language shown.

// The envelope is read when the story opens, and the review waits for it.
const READ_WAIT = 15_000;

const M130 = "modelo-130-1T";
const M303 = "modelo-303-1T";
const M100 = "modelo-100-0A";

const meta: Meta = {
  title: "Modelo/Review and filing",
  parameters: { layout: "fullscreen", fill: true },
};
export default meta;
type Story = StoryObj;

function Review({
  locale,
  shape,
  adjust,
}: {
  locale: unknown;
  shape?: ModeloShape;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
}) {
  return (
    <StorySession
      declaration={M130}
      adjust={adjust}
      locale={locale}
      shape={shape}
      edits={[{ casilla: "06", value: typedAmount(locale) }]}
    >
      {(props) =>
        props.session.stagedCount > 0 && (
          <ReviewDialog
            open
            onOpenChange={() => undefined}
            envelope={props.envelope}
            session={props.session}
            port={props.port}
            language={props.language}
            onReread={props.reread}
          />
        )
      }
    </StorySession>
  );
}

export const ReviewChecked: Story = {
  name: "Review · one change, checked",
  render: (_, { globals }) => <Review locale={globals.locale} />,
};

const withoutKnownEntries = (envelope: ModeloWorkbenchFormProjectionV1) => {
  envelope.form.form.operator_entries_known = false;
};

export const ReviewUnattributed: Story = {
  name: "Review · values typed outside this screen",
  render: (_, { globals }) => (
    <Review locale={globals.locale} adjust={withoutKnownEntries} />
  ),
};

export const ReviewApplyUnknown: Story = {
  name: "Review · apply whose outcome was not seen",
  render: (_, { globals }) => (
    <Review locale={globals.locale} shape="unknown" />
  ),
  play: async ({ canvasElement, globals }) => {
    const page = within(canvasElement.ownerDocument.body);
    const apply = await page.findByRole(
      "button",
      {
        name: translator(String(globals.locale))(
          "workspace.modelo.review.apply",
        ),
      },
      { timeout: READ_WAIT },
    );
    await waitFor(() => expect(apply).toBeEnabled(), {
      timeout: READ_WAIT,
    });
    await userEvent.click(apply);
    await page.findByRole("alert");
    await expect(apply).toBeDisabled();
  },
};

export const ReviewApplyRefused: Story = {
  name: "Review · apply refused",
  render: (_, { globals }) => (
    <Review locale={globals.locale} shape="refused" />
  ),
  play: async ({ canvasElement, globals }) => {
    const page = within(canvasElement.ownerDocument.body);
    const apply = await page.findByRole(
      "button",
      {
        name: translator(String(globals.locale))(
          "workspace.modelo.review.apply",
        ),
      },
      { timeout: READ_WAIT },
    );
    await waitFor(() => expect(apply).toBeEnabled(), {
      timeout: READ_WAIT,
    });
    await userEvent.click(apply);
  },
};

/** A checked form: nothing holds the file back. For a declaration whose
 * check the application did not read, the check's own fields are set. */
const checked = (envelope: ModeloWorkbenchFormProjectionV1) => {
  envelope.verification_report_id = "f".repeat(64);
  envelope.form.verified = true;
  envelope.form.form.verification = "complete";
  envelope.header.export_hold = null;
  envelope.calculation_revision_id ??= "e".repeat(64);
};

const HOLD_TAKEN = fn();

function Filing({
  locale,
  declaration,
  adjust,
  shape,
  onTakeAction = () => undefined,
}: {
  locale: unknown;
  declaration: string;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
  shape?: ModeloShape;
  onTakeAction?: (action: ModeloFormExportHold["action"]) => void;
}) {
  return (
    <StorySession
      declaration={declaration}
      adjust={adjust}
      locale={locale}
      shape={shape}
    >
      {(props) => (
        <div className="@container h-full overflow-y-auto px-6 py-6">
          <FilingView
            envelope={props.envelope}
            port={props.port}
            language={props.language}
            session={props.session}
            onTakeAction={onTakeAction}
            onReread={props.reread}
            openLink={() => undefined}
          />
        </div>
      )}
    </StorySession>
  );
}

export const FilingHeld: Story = {
  name: "Export and record · something blocks filing",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} declaration={M130} />
  ),
};

// The hold names the action that lifts it, and the view's one door takes
// that action; it picks none of its own.
export const FilingHoldNamesItsAction: Story = {
  name: "Export and record · the hold's door takes the action it names",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={M130}
      adjust={(envelope) => {
        envelope.header.export_hold = {
          reason: "verify",
          count: 0,
          words: "Synthetic hold.",
          action: "verify",
        };
      }}
      onTakeAction={HOLD_TAKEN}
    />
  ),
  play: async ({ canvasElement, globals }) => {
    HOLD_TAKEN.mockClear();
    const t = translator(String(globals.locale));
    const door = await within(canvasElement).findByRole(
      "button",
      { name: t("workspace.modelo.next_button.verify") },
      { timeout: READ_WAIT },
    );
    expect(door).toHaveAttribute("data-hold-action", "verify");
    await userEvent.click(door);
    await waitFor(() => expect(HOLD_TAKEN).toHaveBeenCalledWith("verify"));
  },
};

export const FilingReady: Story = {
  name: "Export and record · checked, ready to export",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} declaration={`${M130}-checked`} />
  ),
};

export const FilingElections: Story = {
  name: "Export and record · 303 checked, asking its elections",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} declaration={M303} adjust={checked} />
  ),
};

export const FilingStale: Story = {
  name: "Export and record · file from an earlier calculation",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} declaration={`${M130}-stale`} />
  ),
};

export const FilingRecorded: Story = {
  name: "Export and record · recorded as filed",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} declaration={`${M130}-filed`} />
  ),
};

export const FilingRecordUnknown: Story = {
  name: "Export and record · recording whose outcome was not seen",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M130}-exported`}
      shape="unknown"
    />
  ),
};

export const FilingCutoffUnverified: Story = {
  name: "Export and record · direct debit whose cutoff was not checked",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M130}-exported`}
      shape="export-cutoff-unverified"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale));
    const page = within(canvasElement.ownerDocument.body);
    const again = await page.findByRole(
      "button",
      { name: t("workspace.modelo.filing.export_again") },
      { timeout: READ_WAIT },
    );
    await waitFor(() => expect(again).toBeEnabled(), { timeout: READ_WAIT });
    await userEvent.click(again);
    await page.findByText(
      t("tui.modelo.export.result.warning.cutoff_unverified"),
      undefined,
      { timeout: READ_WAIT },
    );
  },
};

export const FilingElectionsRenta: Story = {
  name: "Export and record · 100 checked, result to pay, asking its elections",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M100}-pay`}
      adjust={checked}
    />
  ),
};

export const FilingRentaToRefund: Story = {
  name: "Export and record · 100 checked, result to refund, nothing to elect",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M100}-refund`}
      adjust={checked}
    />
  ),
};

export const FilingRentaHeld: Story = {
  name: "Export and record · 100 whose credits are unresolved",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} declaration={M100} />
  ),
};

/** Exports the file again from a story's Export and record view, once the
 * view lets it. */
async function exportAgain(canvasElement: HTMLElement, locale: unknown) {
  const t = translator(String(locale));
  const page = within(canvasElement.ownerDocument.body);
  const again = await page.findByRole(
    "button",
    { name: t("workspace.modelo.filing.export_again") },
    { timeout: READ_WAIT },
  );
  await waitFor(() => expect(again).toBeEnabled(), { timeout: READ_WAIT });
  await userEvent.click(again);
  return { t, page };
}

export const FilingExportDisclosure: Story = {
  name: "Export and record · file whose result discloses limitations",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M130}-exported`}
      shape="export-disclosure"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const { page } = await exportAgain(canvasElement, globals.locale);
    // The served disclosure is drawn as it is: its lead sentence, then each
    // limitation in its served words, apart from the saved file's warnings
    // and never as one.
    const lead = await page.findByText(
      EXPORT_DISCLOSURE.lead_words,
      undefined,
      {
        timeout: READ_WAIT,
      },
    );
    const disclosure = lead.closest("[data-disclosure]");
    await expect(disclosure?.getAttribute("data-disclosure")).toBe(
      "limitation",
    );
    await expect(disclosure?.getAttribute("data-tone")).toBe("neutral");
    const drawn = [
      ...(disclosure as HTMLElement).querySelectorAll("[data-limitation]"),
    ];
    await expect(drawn.map((each) => each.textContent)).toEqual(
      EXPORT_DISCLOSURE.limitations.map((limitation) => limitation.words),
    );
    await expect(
      drawn.map((each) => each.getAttribute("data-limitation")),
    ).toEqual(
      EXPORT_DISCLOSURE.limitations.map(
        (limitation) => limitation.message_locale_key,
      ),
    );
    await expect(
      canvasElement.ownerDocument.querySelectorAll(
        '[data-disclosure="warning"]',
      ),
    ).toHaveLength(0);
  },
};

export const FilingExportNoDisclosure: Story = {
  name: "Export and record · file whose result discloses nothing",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M130}-exported`}
      shape="exported"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    await exportAgain(canvasElement, globals.locale);
    const doc = canvasElement.ownerDocument;
    await waitFor(
      () => expect(doc.querySelector('[data-tone="success"]')).not.toBeNull(),
      { timeout: READ_WAIT },
    );
    // A result that serves no disclosure draws none.
    await expect(
      canvasElement.ownerDocument.querySelectorAll("[data-disclosure]"),
    ).toHaveLength(0);
  },
};

export const FilingExportRefused: Story = {
  name: "Export and record · export refused, in the served sentence",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      declaration={`${M130}-exported`}
      shape="export-past-cutoff"
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const { t, page } = await exportAgain(canvasElement, globals.locale);
    // The refusal is drawn by the window's one refusal notice, with the
    // sentence the backend served and no generic notice beside it.
    const notice = await waitFor(
      () => {
        const found = canvasElement.ownerDocument.querySelector(
          '[data-slot="refusal-notice"]',
        );
        if (!found) throw new Error("no refusal notice yet");
        return found as HTMLElement;
      },
      { timeout: READ_WAIT },
    );
    await expect(notice.textContent?.trim()).not.toBe("");
    await expect(
      page.queryByText(t("workspace.modelo.outcome.not_done")),
    ).toBeNull();
  },
};
