import type { Meta, StoryObj } from "@storybook/react-vite";
import { userEvent } from "storybook/test";
import { LedgerPrototype, type Scenario } from "./App";
import { find, press, saveAll } from "./plays";
import { SCENARIOS } from "./scenarios";

// Design prototype for the ledger, from the reviewed standalone build. The
// ledger is synthetic and deterministic; every write is simulated and
// nothing survives a reload. A story is one state of the page: a section, a
// dialog, a sealed period, an empty one, a refusal. Where reaching it takes
// a person's steps, the story takes them, so the canvas shows the result.

const meta: Meta = {
  title: "Prototypes/Ledger",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;

type Story = StoryObj;

const PHONE = { viewport: { value: "mobile2", isRotated: false } };

function story(
  scenario: Scenario,
  more: Omit<Story, "render"> & { phone?: boolean } = {},
): Story {
  const { phone, ...rest } = more;
  return {
    render: () => <LedgerPrototype scenario={scenario} />,
    ...(phone ? { globals: PHONE } : {}),
    ...rest,
  };
}

const tab = (name: string) => async (canvas: HTMLElement) => {
  await press(canvas, "[role=tab]", { text: name });
};

/* ── Movements. ──────────────────────────────────────────────────────── */

export const Movements: Story = story(SCENARIOS.default, {
  name: "Movements",
});

export const MovementsWithPrototypeControls: Story = story(
  SCENARIOS.withControls,
  { name: "Movements with the prototype's controls" },
);

export const PageWithoutWindow: Story = story(SCENARIOS.bare, {
  name: "The page alone, without the window around it",
});

export const SetupMenu: Story = story(SCENARIOS.default, {
  name: "Movements, set-up menu open",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".setup-btn");
    await find(canvasElement, ".menu");
  },
});

export const GroupedByCounterparty: Story = story(
  SCENARIOS.groupedByCounterparty,
  { name: "Movements grouped by counterparty" },
);

export const RuleFromGroup: Story = story(SCENARIOS.groupRule, {
  name: "Make a rule from a group",
});

export const ToMatchView: Story = story(SCENARIOS.toMatch, {
  name: "To match: movements beside their invoice candidates",
});

export const ReadinessChipFix: Story = story(SCENARIOS.readiness, {
  name: "Readiness strip, a missing category",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".strip .btn.pill", { text: "Category" });
  },
});

export const PeriodSelector: Story = story(SCENARIOS.default, {
  name: "Period selector open",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".pane-head .period-btn");
    await find(canvasElement, ".period-pop");
    await press(canvasElement, ".period-pop [aria-label='Previous year']");
  },
});

export const SealedPeriod: Story = story(SCENARIOS.sealed, {
  name: "A sealed period: filed movements are read-only",
});

export const ColumnsAndDensity: Story = story(SCENARIOS.columns, {
  name: "Columns and density",
});

export const Shortcuts: Story = story(SCENARIOS.shortcuts, {
  name: "Keyboard shortcuts",
});

export const CommandPalette: Story = story(SCENARIOS.default, {
  name: "Command palette, searching a year",
  play: async () => {
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.keyboard("2019");
  },
});

export const PasteFromSpreadsheet: Story = story(SCENARIOS.default, {
  name: "Paste preview from a spreadsheet",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".g-row [id$='-description']", { nth: 3 });
    const grid = await find(canvasElement, ".grid");
    const data = new DataTransfer();
    data.setData("text/plain", "CAFE\tCafé Central SL\nTAXI\t\nHOTEL\tNH\n");
    grid.dispatchEvent(
      new ClipboardEvent("paste", {
        clipboardData: data,
        bubbles: true,
        cancelable: true,
      }),
    );
    await find(canvasElement, ".dialog");
  },
});

/* ── The inspector. ──────────────────────────────────────────────────── */

export const InspectorWithSuggestion: Story = story(SCENARIOS.suggestion, {
  name: "Inspector, a model suggestion to accept or reject",
});

export const ApprovalReview: Story = story(SCENARIOS.suggestion, {
  name: "Approving a suggestion, then reviewing it",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".inspector button", { text: "Approve" });
    await press(canvasElement, ".tray-review");
    await find(canvasElement, ".dialog");
  },
});

export const InspectorCombobox: Story = story(SCENARIOS.combobox, {
  name: "Inspector, choosing a category",
  play: async ({ canvasElement }) => {
    const term = await find(canvasElement, ".inspector dt", {
      text: "Category",
    });
    const button =
      term.nextElementSibling?.querySelector<HTMLElement>(".dd-btn");
    if (button) await userEvent.click(button);
    await find(canvasElement, ".insp-combo");
    await userEvent.keyboard("{ArrowDown}{ArrowDown}");
  },
});

export const LinkChooser: Story = story(SCENARIOS.ambiguousInvoice, {
  name: "Inspector, two invoices fit one movement",
});

export const PermanentLink: Story = story(SCENARIOS.permanentLink, {
  name: "Inspector, linking an invoice permanently",
});

export const MultiSelect: Story = story(SCENARIOS.multiSelect, {
  name: "Inspector on several movements",
});

export const HiddenSelection: Story = story(SCENARIOS.hiddenSelection, {
  name: "A selection the search hides",
});

/* ── Staged work. ────────────────────────────────────────────────────── */

export const StagedChanges: Story = story(SCENARIOS.staged, {
  name: "Staged changes, marked in the grid",
});

export const TrayExpanded: Story = story(SCENARIOS.stagedRows, {
  name: "Changes tray expanded",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".tray-toggle");
  },
});

export const ReviewBeforeSaving: Story = story(SCENARIOS.review, {
  name: "Review before saving",
});

export const ReviewConflicts: Story = story(SCENARIOS.reviewConflict, {
  name: "Review, a movement changed elsewhere",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".dialog-foot button", { text: "Save" });
    await find(canvasElement, ".dialog label", {
      text: "I have looked at what changed",
    });
  },
});

export const SaveMixedOutcome: Story = story(SCENARIOS.reviewMix, {
  name: "Saved: some changes saved, some refused",
  play: async ({ canvasElement }) => saveAll(canvasElement),
});

export const SaveBatchRefused: Story = story(SCENARIOS.reviewBatchRefused, {
  name: "Saved: the whole batch refused",
  play: async ({ canvasElement }) => saveAll(canvasElement),
});

export const SaveBatchUnknown: Story = story(SCENARIOS.reviewBatchUnknown, {
  name: "Saved: the batch's outcome is unknown",
  play: async ({ canvasElement }) => saveAll(canvasElement),
});

export const UnknownOutcomeBanner: Story = story(SCENARIOS.unknownOutcome, {
  name: "An unknown outcome pauses writes",
});

export const LeaveGuard: Story = story(SCENARIOS.leaveGuard, {
  name: "Leaving with staged work",
});

export const DiscardChanges: Story = story(SCENARIOS.discard, {
  name: "Discard staged changes",
});

/* ── Dialogs. ────────────────────────────────────────────────────────── */

export const ImportFiles: Story = story(SCENARIOS.importFiles, {
  name: "Import, choosing files",
});

export const ImportDuplicate: Story = story(SCENARIOS.importFiles, {
  name: "Import, a duplicate to compare with the existing one",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".dialog button", { text: "Choose files" });
    for (const file of [
      "bbva-movimientos-2026-10-b.xlsx",
      "n26-business-2026-10.csv",
      "caixabank-export.csv",
    ])
      await press(canvasElement, ".popover li label", { text: file });
    await press(canvasElement, ".popover button", { text: "Open" });
    await press(canvasElement, ".dialog-foot button", { text: "Preview" });
    await press(canvasElement, ".dialog button", {
      text: "Compare with the existing one",
    });
  },
});

export const Export: Story = story(SCENARIOS.exportStaged, {
  name: "Export, with staged changes",
});

export const ExportClean: Story = story(SCENARIOS.exportClean, {
  name: "Export",
});

export const SplitMovement: Story = story(SCENARIOS.split, {
  name: "Split a movement into parts",
  play: async ({ canvasElement }) => {
    const field = await find(
      canvasElement,
      "input[aria-label='Part 1 amount']",
    );
    await userEvent.clear(field);
    await userEvent.type(field, "70.00");
  },
});

export const ClassifySelection: Story = story(SCENARIOS.classify, {
  name: "Classify a selection",
});

export const ModelSuggestions: Story = story(SCENARIOS.suggestions, {
  name: "Model suggestions for several movements",
});

export const GridAtScale: Story = story(SCENARIOS.gridDemo, {
  name: "The grid at ten thousand rows",
});

/* ── The other sections. ─────────────────────────────────────────────── */

export const Invoices: Story = story(SCENARIOS.invoices, {
  name: "Invoices",
});

export const InvoiceSheetBlank: Story = story(SCENARIOS.invoiceSheetNew, {
  name: "Invoice sheet, a new invoice",
});

export const InvoiceSheetIssued: Story = story(SCENARIOS.invoiceSheetNew, {
  name: "Invoice sheet, an invoice I issued",
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".sheet .seg-item", {
      text: "Invoice I issued",
    });
    await press(canvasElement, ".sheet .pill", { text: "15%" });
  },
});

export const InvoiceSheetExisting: Story = story(
  SCENARIOS.invoiceSheetExisting,
  { name: "Invoice sheet, an existing invoice" },
);

export const Documents: Story = story(SCENARIOS.documents, {
  name: "Documents, a draft with findings",
});

export const DocumentsAll: Story = story(SCENARIOS.documents, {
  name: "Documents, all evidence",
  play: async ({ canvasElement }) => tab("All evidence")(canvasElement),
});

export const DocumentsFolderIntake: Story = story(SCENARIOS.documents, {
  name: "Documents, folder intake",
  play: async ({ canvasElement }) => tab("Folder intake")(canvasElement),
});

export const DocumentsConsent: Story = story(SCENARIOS.documents, {
  name: "Documents, what was sent off this computer",
  play: async ({ canvasElement }) =>
    tab("Sent off this computer")(canvasElement),
});

export const Rules: Story = story(SCENARIOS.rules, {
  name: "Rules, classification rules",
});

export const Ratios: Story = story(SCENARIOS.rules, {
  name: "Rules, business-use ratios",
  play: async ({ canvasElement }) => tab("Business-use ratios")(canvasElement),
});

export const Counterparties: Story = story(SCENARIOS.rules, {
  name: "Rules, counterparties",
  play: async ({ canvasElement }) => tab("Counterparties")(canvasElement),
});

export const ModelDiagnostics: Story = story(SCENARIOS.rules, {
  name: "Rules, model diagnostics",
  play: async ({ canvasElement }) => tab("Model diagnostics")(canvasElement),
});

export const OwnAccounts: Story = story(SCENARIOS.registers, {
  name: "Registers, own accounts",
});

export const Prorrata: Story = story(SCENARIOS.registers, {
  name: "Registers, prorrata",
  play: async ({ canvasElement }) => tab("Prorrata")(canvasElement),
});

export const CapitalGoods: Story = story(SCENARIOS.registers, {
  name: "Registers, bienes de inversión",
  play: async ({ canvasElement }) => tab("Bienes de inversión")(canvasElement),
});

export const Inventory: Story = story(SCENARIOS.registers, {
  name: "Registers, inventory",
  play: async ({ canvasElement }) => tab("Inventory")(canvasElement),
});

export const ActivityAssets: Story = story(SCENARIOS.registers, {
  name: "Registers, activity assets",
  play: async ({ canvasElement }) => tab("Activity assets")(canvasElement),
});

export const Health: Story = story(SCENARIOS.health, {
  name: "Health, the check not yet run",
});

export const HealthChecked: Story = story(SCENARIOS.health, {
  name: "Health, after the check",
  play: async ({ canvasElement }) => {
    await press(canvasElement, "button", { text: "Run the check" });
    await find(canvasElement, ".panel-body .list-rows");
  },
});

/* ── States of the ledger. ───────────────────────────────────────────── */

export const FirstRun: Story = story(SCENARIOS.firstRun, {
  name: "State, first run: nothing imported yet",
});

export const EmptyPeriod: Story = story(SCENARIOS.emptyPeriod, {
  name: "State, a period without movements",
});

export const PartialWindow: Story = story(SCENARIOS.partialWindow, {
  name: "State, a partial window of a long period",
});

export const NoExchangeRate: Story = story(SCENARIOS.noRate, {
  name: "State, no exchange rate for a movement",
});

export const Loading: Story = story(SCENARIOS.loading, {
  name: "State, loading",
});

export const SignedOut: Story = story(SCENARIOS.signedOut, {
  name: "State, not signed in",
});

export const SessionLost: Story = story(SCENARIOS.sessionLost, {
  name: "State, session lost",
});

export const LedgerUnavailable: Story = story(SCENARIOS.unavailable, {
  name: "State, ledger unavailable",
});

export const Locked: Story = story(SCENARIOS.locked, {
  name: "State, locked",
});

export const NeverRead: Story = story(SCENARIOS.neverCaptured, {
  name: "State, never read",
});

export const Stale: Story = story(SCENARIOS.stale, {
  name: "State, stale",
});

export const ModelUnavailable: Story = story(SCENARIOS.modelUnavailable, {
  name: "State, model unavailable",
});

export const NotMeasured: Story = story(SCENARIOS.unmeasured, {
  name: "State, not measured",
});

/* ── A phone's width. ────────────────────────────────────────────────── */

export const PhoneCards: Story = story(SCENARIOS.default, {
  name: "Phone, movements as cards",
  phone: true,
});

export const PhoneSheet: Story = story(SCENARIOS.default, {
  name: "Phone, a movement's sheet",
  phone: true,
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".card-main", { nth: 2 });
  },
});

export const PhoneReview: Story = story(SCENARIOS.review, {
  name: "Phone, review before saving",
  phone: true,
});

export const PhonePeriod: Story = story(SCENARIOS.default, {
  name: "Phone, period selector",
  phone: true,
  play: async ({ canvasElement }) => {
    await press(canvasElement, ".pane-head .period-btn");
  },
});
