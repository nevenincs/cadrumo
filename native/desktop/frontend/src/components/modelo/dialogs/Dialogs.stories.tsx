import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import form130 from "../../../dev/fixtures/modelo/modelo-130-1T-en.json";
import form303 from "../../../dev/fixtures/modelo/modelo-303-1T-en.json";
import type { ModeloShape } from "../../../dev/modeloFixture";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract";
import { StorySession } from "../details/Details.stories";
import { FilingView } from "./FilingView";
import { ReviewDialog } from "./ReviewDialog";

// The review dialog and the Export and record view on the modelo 130
// envelope the application's read path produced for the synthetic taxpayer.
// The scenario host answers the edit preflight as the application did; it
// has no answer for an apply or an export, so a story's shape says whether
// those are refused, never reach the runtime, or are lost in transit. The
// filing stages below change the envelope's own filing fields the way a
// check, an export and a recorded filing change them; the words they set are
// English only.

const F130 = form130 as unknown as ModeloWorkbenchFormProjectionV1;
const F303 = form303 as unknown as ModeloWorkbenchFormProjectionV1;

const meta: Meta = {
  title: "Modelo/Review and filing",
  parameters: { layout: "fullscreen", fill: true },
};
export default meta;
type Story = StoryObj;

function Review({
  locale,
  shape,
  envelope = F130,
}: {
  locale: unknown;
  shape?: ModeloShape;
  envelope?: ModeloWorkbenchFormProjectionV1;
}) {
  return (
    <StorySession
      envelope={envelope}
      locale={locale}
      shape={shape}
      edits={[{ casilla: "06", value: "1.234,56" }]}
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

export const ReviewUnattributed: Story = {
  name: "Review · values typed outside this screen",
  render: (_, { globals }) => (
    <Review
      locale={globals.locale}
      envelope={{
        ...F130,
        form: {
          ...F130.form,
          form: { ...F130.form.form, operator_entries_known: false },
        },
      }}
    />
  ),
};

export const ReviewApplyUnknown: Story = {
  name: "Review · apply whose outcome was not seen",
  render: (_, { globals }) => (
    <Review locale={globals.locale} shape="unknown" />
  ),
  play: async ({ canvasElement }) => {
    const page = within(canvasElement.ownerDocument.body);
    const apply = await page.findByRole("button", {
      name: /workspace\.modelo\.review\.apply|Apply/,
    });
    await waitFor(() => expect(apply).toBeEnabled());
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
  play: async ({ canvasElement }) => {
    const page = within(canvasElement.ownerDocument.body);
    const apply = await page.findByRole("button", {
      name: /workspace\.modelo\.review\.apply|Apply/,
    });
    await waitFor(() => expect(apply).toBeEnabled());
    await userEvent.click(apply);
  },
};

/** The envelope as checking, exporting and recording leave it. */
function staged(
  stage: "checked" | "exported" | "stale" | "recorded",
  base = F130,
) {
  const form = structuredClone(base);
  form.verification_report_id = "f".repeat(64);
  form.form.verified = true;
  form.form.form.verification = "complete";
  form.header.export_hold = null;
  const calculation = form.calculation_revision_id ?? "e".repeat(64);
  form.calculation_revision_id = calculation;
  if (stage !== "checked") {
    form.form.form.last_export = {
      exported_at: "2026-04-14T09:30:00Z",
      calculation_revision_id: calculation,
      current: stage !== "stale",
    };
    form.header.file = {
      exported_at: "2026-04-14T09:30:00Z",
      created_on: "2026-04-14",
      current: stage !== "stale",
      // A synthetic stage the scenario read did not produce; its words are
      // the English the application gives such a file.
      words:
        stage === "stale"
          ? "The file from 14/04/2026 is out of date. Create it again."
          : "File created on 14/04/2026.",
    };
  }
  if (stage === "recorded") {
    form.form.form.filing = { recorded_at: "2026-04-15T11:00:00Z" };
    form.receipt = {
      recorded_at: "2026-04-15T11:00:00Z",
      verified: false,
      verified_at: null,
      words: "Not confirmed by an AEAT receipt yet.",
    };
  }
  return form;
}

function Filing({
  locale,
  envelope,
  shape,
}: {
  locale: unknown;
  envelope: ModeloWorkbenchFormProjectionV1;
  shape?: ModeloShape;
}) {
  return (
    <StorySession envelope={envelope} locale={locale} shape={shape}>
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
    <Filing locale={globals.locale} envelope={F130} />
  ),
};

export const FilingReady: Story = {
  name: "Export and record · checked, ready to export",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} envelope={staged("checked")} />
  ),
};

export const FilingElections: Story = {
  name: "Export and record · 303 checked, asking its elections",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} envelope={staged("checked", F303)} />
  ),
};

export const FilingStale: Story = {
  name: "Export and record · file from an earlier calculation",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} envelope={staged("stale")} />
  ),
};

export const FilingRecorded: Story = {
  name: "Export and record · recorded as filed",
  render: (_, { globals }) => (
    <Filing locale={globals.locale} envelope={staged("recorded")} />
  ),
};

export const FilingRecordUnknown: Story = {
  name: "Export and record · recording whose outcome was not seen",
  render: (_, { globals }) => (
    <Filing
      locale={globals.locale}
      envelope={staged("exported")}
      shape="unknown"
    />
  ),
};
