import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import type { ModeloShape } from "../../../dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
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

function Filing({
  locale,
  declaration,
  adjust,
  shape,
}: {
  locale: unknown;
  declaration: string;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
  shape?: ModeloShape;
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
            onOpenCheck={() => undefined}
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
