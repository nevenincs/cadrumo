import { protoActions, seedStaged, type Scenario } from "./App";
import { effDate } from "./model";
import { reconciliationSuggestions } from "./Movements";
import type { Action } from "./store";
import type { Movement, State } from "./types";

// How each story starts the ledger prototype. A scenario is chosen from what
// the synthetic ledger holds, never from fixed ids, so a story names the
// movement it means by what it says. Each is a module-level constant: the
// prototype builds its page once per scenario.

const rowsOf = (state: State): Movement[] =>
  state.data.order.flatMap((id) => state.data.byId[id] ?? []);

/** The movement a story is about; a ledger that lacks it is a broken story. */
function movement(
  state: State,
  what: string,
  match: (row: Movement) => boolean,
): Movement {
  const found = rowsOf(state).find(match);
  if (!found) throw new Error(`The synthetic ledger holds no ${what}.`);
  return found;
}

const described = (state: State, text: string) =>
  movement(state, `movement "${text}"`, (r) => r.description.startsWith(text));

/** The movements of the opening quarter, newest first, as the grid lists them. */
const inQuarter = (state: State, n: number): Movement[] =>
  rowsOf(state)
    .filter(
      (r) =>
        r.lifecycle === "active" &&
        effDate(r) >= "2026-10-01" &&
        r.direction !== "transfer",
    )
    .sort((a, b) => effDate(b).localeCompare(effDate(a)))
    .slice(0, n);

const outcome = (name: string): Action => ({
  type: "PROTO",
  patch: { outcome: name },
});

const staged = (state: State): Action[] => seedStaged(state);

const page = { chrome: true } satisfies Scenario;

export const SCENARIOS = {
  default: { ...page },
  bare: {},
  withControls: { ...page, controls: true },

  // Staged work and the review before saving it.
  staged: {
    ...page,
    prepare: staged,
    start: (state) => ({
      focus: {
        id: movement(state, "staged movement", (r) =>
          Object.keys(state.staged.rows).includes(r.id),
        ).id,
        col: "cls",
      },
    }),
  },
  stagedRows: { ...page, prepare: staged },
  review: {
    ...page,
    prepare: staged,
    start: () => ({ dialog: { name: "review" } }),
  },
  reviewBatchRefused: {
    ...page,
    prepare: (state) => [...staged(state), outcome("batchRefused")],
    start: () => ({ dialog: { name: "review" } }),
  },
  reviewBatchUnknown: {
    ...page,
    prepare: (state) => [...staged(state), outcome("batchUnknown")],
    start: () => ({ dialog: { name: "review" } }),
  },
  reviewMix: {
    ...page,
    prepare: (state) => [...staged(state), outcome("mix")],
    start: () => ({ dialog: { name: "review" } }),
  },
  reviewConflict: {
    ...page,
    prepare: (state) => {
      const row = movement(state, "movement changed elsewhere", (r) =>
        Boolean(r.remoteChange),
      );
      return [
        ...staged(state),
        {
          type: "STAGE",
          changes: [
            { id: row.id, field: "notes", value: "Receipt asked for" },
            { id: row.id, field: "cls", value: "business" },
          ],
          label: "Edit",
        },
      ];
    },
    start: () => ({ dialog: { name: "review" } }),
  },
  leaveGuard: {
    ...page,
    prepare: staged,
    start: () => ({
      dialog: {
        name: "leave",
        props: { what: "Opening Settings", onLeave: () => undefined },
      },
    }),
  },
  discard: {
    ...page,
    prepare: staged,
    start: () => ({ dialog: { name: "discard" } }),
  },
  exportStaged: {
    ...page,
    prepare: staged,
    start: () => ({ dialog: { name: "export" } }),
  },
  unknownOutcome: {
    ...page,
    prepare: (state) => protoActions("unknown", state).actions,
  },

  // The inspector on one movement, or on several.
  suggestion: {
    ...page,
    start: (state) => ({
      focus: {
        id: described(state, "GRAFICAS TURIA SEGUNDA").id,
        col: "description",
      },
    }),
  },
  combobox: {
    ...page,
    start: (state) => ({
      focus: { id: described(state, "DOMESTIKA").id, col: "description" },
      inspectorAt: "classification",
    }),
  },
  ambiguousInvoice: {
    ...page,
    start: (state) => {
      const best = Object.values(
        reconciliationSuggestions(state.data, []).best,
      ).find((b) => b.ambiguous);
      if (!best) throw new Error("The synthetic ledger holds no tie.");
      return {
        focus: { id: best.rowId, col: "match" },
        inspectorAt: "invoice",
      };
    },
  },
  permanentLink: {
    ...page,
    start: (state) => ({
      focus: {
        id: described(state, "ARROYO ASESORES HONORARIOS 10/2026").id,
        col: "match",
      },
      inspectorAt: "invoice",
    }),
  },
  multiSelect: {
    ...page,
    prepare: (state) => [
      {
        type: "SELECT",
        mode: "set",
        ids: inQuarter(state, 5)
          .slice(2)
          .map((r) => r.id),
      },
    ],
    start: (state) => ({
      focus: { id: inQuarter(state, 3)[2]!.id, col: "date" },
    }),
  },
  hiddenSelection: {
    ...page,
    prepare: (state) => [
      {
        type: "SELECT",
        mode: "set",
        ids: inQuarter(state, 5)
          .slice(2)
          .map((r) => r.id),
      },
      { type: "VIEW", patch: { search: "repsol" } },
    ],
  },
  sealed: {
    ...page,
    prepare: () => [
      { type: "VIEW", patch: { period: { year: 2026, code: "1T" } } },
    ],
    start: (state) => ({
      focus: {
        id: movement(
          state,
          "sealed movement",
          (r) =>
            Boolean(r.sealed) &&
            effDate(r) >= "2026-01-01" &&
            effDate(r) < "2026-04-01",
        ).id,
        col: "description",
      },
    }),
  },

  // How the grid is arranged.
  groupedByCounterparty: {
    ...page,
    prepare: () => [{ type: "VIEW", patch: { groupBy: "counterparty" } }],
  },
  groupRule: {
    ...page,
    prepare: () => [{ type: "VIEW", patch: { groupBy: "counterparty" } }],
    start: (state) => ({
      dialog: {
        name: "rule",
        props: {
          rows: rowsOf(state).filter((r) =>
            r.counterparty.startsWith("Repsol"),
          ),
          from: "Repsol",
        },
      },
    }),
  },
  toMatch: {
    ...page,
    prepare: () => [{ type: "VIEW", patch: { savedView: "match" } }],
  },
  readiness: {
    ...page,
    prepare: () => [
      { type: "VIEW", patch: { period: { year: 2026, code: "3T" } } },
    ],
  },
  columns: { ...page, start: () => ({ dialog: { name: "columns" } }) },

  // Dialogs a movement or a selection opens.
  split: {
    ...page,
    start: (state) => ({
      dialog: {
        name: "action",
        props: {
          type: "split",
          ids: [described(state, "IKEA ALFAFAR").id],
        },
      },
    }),
  },
  classify: {
    ...page,
    start: (state) => ({
      dialog: {
        name: "classify",
        props: {
          kind: "business",
          ids: inQuarter(state, 5)
            .slice(2)
            .map((r) => r.id),
          skipped: 0,
          partial: null,
        },
      },
    }),
  },
  suggestions: {
    ...page,
    start: (state) => ({
      dialog: {
        name: "suggestions",
        props: { ids: inQuarter(state, 6).map((r) => r.id) },
      },
    }),
  },
  importFiles: { ...page, start: () => ({ dialog: { name: "import" } }) },
  exportClean: { ...page, start: () => ({ dialog: { name: "export" } }) },
  shortcuts: { ...page, start: () => ({ dialog: { name: "shortcuts" } }) },
  gridDemo: { ...page, start: () => ({ dialog: { name: "gridDemo" } }) },

  // Pages beside the movements.
  invoices: { ...page, start: () => ({ section: "invoices" }) },
  invoiceSheetNew: {
    ...page,
    start: () => ({ section: "invoices", sheet: { id: null } }),
  },
  invoiceSheetExisting: {
    ...page,
    start: (state) => {
      const invoice = state.data.invoices[0];
      if (!invoice) throw new Error("The synthetic ledger holds no invoice.");
      return { section: "invoices", sheet: { id: invoice.id } };
    },
  },
  documents: { ...page, start: () => ({ section: "documents" }) },
  rules: { ...page, start: () => ({ section: "rules" }) },
  registers: { ...page, start: () => ({ section: "registers" }) },
  health: { ...page, start: () => ({ section: "health" }) },

  // The states the ledger can be in, as the prototype's controls set them.
  firstRun: {
    ...page,
    prepare: (state) => protoActions("firstRun", state).actions,
  },
  emptyPeriod: {
    ...page,
    prepare: (state) => protoActions("empty", state).actions,
  },
  partialWindow: {
    ...page,
    prepare: (state) => [
      ...protoActions("partial", state).actions,
      { type: "VIEW", patch: { search: "repsol" } },
    ],
  },
  noRate: {
    ...page,
    prepare: (state) => protoActions("noRate", state).actions,
    start: (state) => {
      const focus = protoActions("noRate", state).focus;
      return focus ? { focus } : {};
    },
  },
  loading: {
    ...page,
    prepare: (state) => protoActions("loading", state).actions,
  },
  signedOut: {
    ...page,
    prepare: (state) => protoActions("signedOut", state).actions,
  },
  sessionLost: {
    ...page,
    prepare: (state) => protoActions("sessionLost", state).actions,
  },
  unavailable: {
    ...page,
    prepare: (state) => protoActions("unavailable", state).actions,
  },
  locked: {
    ...page,
    prepare: (state) => protoActions("locked", state).actions,
  },
  neverCaptured: {
    ...page,
    prepare: (state) => protoActions("neverCaptured", state).actions,
  },
  stale: {
    ...page,
    prepare: (state) => protoActions("stale", state).actions,
  },
  modelUnavailable: {
    ...page,
    prepare: (state) => protoActions("modelUnavailable", state).actions,
  },
  unmeasured: {
    ...page,
    prepare: (state) => protoActions("unmeasured", state).actions,
  },
} satisfies Record<string, Scenario>;
