import { createContext, useContext, type RefObject } from "react";
import type { GridActive, GridApi } from "./DataGrid";
import type { Invoice, Movement, Suggestion, Value } from "./types";

// What the page offers the sections it holds: the one object every section
// reaches through `usePage`. The page fills it in; the movements section
// registers the parts only it can answer.

export type WindowInfo = { truncated: boolean; total: number; loaded: number };

export type PasteChange = { id: string; field: string; value: Value };
export type PasteRefusal = {
  id: string;
  field: string;
  raw: string;
  msg: string;
};
export type PastePlan = {
  changes: PasteChange[];
  refusals: PasteRefusal[];
  blanks: number;
  dropped: number;
  identity: number;
  cols: string[];
  rows: number;
  needsPreview: boolean;
};

export type ActionOpts = { proposal?: boolean };
export type LifecycleActionType =
  "archive" | "stash" | "exclude" | "restore" | "merge" | "split" | "remove";

/** The props each dialog takes when the page opens it by name. */
export type DialogProps = {
  review: undefined;
  discard: undefined;
  leave: { what: string; onLeave: () => void };
  action: { type: LifecycleActionType; ids: string[]; opts?: ActionOpts };
  import: { kind?: string } | undefined;
  export: { selection?: string[] } | undefined;
  shortcuts: undefined;
  paste: { plan: PastePlan; onPaste: () => void };
  rule: { rows: Movement[]; from?: string };
  columns: undefined;
  suggestions: { ids: string[] };
  classify: {
    kind: string;
    ids: string[];
    skipped: number;
    partial: WindowInfo | null;
  };
  gridDemo: undefined;
};
export type DialogName = keyof DialogProps;
export type DialogState = {
  [N in DialogName]: undefined extends DialogProps[N]
    ? { name: N; props?: DialogProps[N] }
    : { name: N; props: DialogProps[N] };
}[DialogName];
type DialogArgs<N extends DialogName> = undefined extends DialogProps[N]
  ? [props?: DialogProps[N]]
  : [props: DialogProps[N]];

/** The parts of the page the movements section answers for. */
export type Registered = {
  startAdd?: () => void;
  visibleIds?: () => string[];
  focusGrid?: () => void;
  startEdit?: (id: string, col: string) => boolean;
  windowInfo?: () => WindowInfo;
  focusFirst?: () => void;
  jumpTo?: (id: string, col?: string) => boolean;
};

export type PageApi = {
  gridApi: RefObject<GridApi | null>;
  searchRef: RefObject<HTMLInputElement | null>;
  toast: (text: string) => void;
  rereading: boolean;
  docFocus: string | null;
  peekId: string | null;
  inspTick: number;
  sheetInvoice?: string | null;
  readonly windowInfo: Partial<WindowInfo>;
  register: (parts: Registered) => void;
  setSection: (section: string) => void;
  openDialog: <N extends DialogName>(name: N, ...args: DialogArgs<N>) => void;
  openAction: (
    type: LifecycleActionType,
    ids: string[],
    opts?: ActionOpts,
  ) => void;
  visibleIds: () => string[];
  focusGrid: () => void;
  focusFirstRow: () => void;
  jumpTo: (id: string, col?: string) => void;
  setPeek: (id: string | null) => void;
  showInGrid: (id: string) => void;
  editCell: (id: string, field: string) => void;
  openInvoice: (id: string) => void;
  newInvoiceFor: (row: Movement) => void;
  addInvoice: () => void;
  offerLink: (rowId: string, inv: Invoice) => void;
  openDoc: (id: string) => void;
  copyRows: (ids: string[]) => void;
  askModel: (ids: string[], mode?: string) => Promise<void>;
  dropSuggestion: (id: string) => void;
  suggestionFor: (row: Movement) => Suggestion | null;
  startAdd: () => void;
  hiddenSelected: () => { sel: string[]; hidden: string[] };
  classifySelection: (
    kind: string,
    ids?: string[],
    opts?: { group?: boolean },
  ) => boolean;
  altI: () => void;
  toggleInspector: () => void;
  openInspectorAt: (section: string) => void;
  showSelected: () => void;
  stageArchiveDuplicate: (id: string) => void;
  stageKeepBoth: (id: string) => void;
  reread: () => Promise<void>;
  inspFocusIndex?: boolean;
  inspAt?: string | null;
  /** The cell the grid opens on; read once when the section mounts. */
  startFocus?: GridActive;
  invUnmatched?: boolean;
  focusShare?: boolean;
};

export const PageCtx = createContext<PageApi | null>(null);
export function usePage(): PageApi {
  const page = useContext(PageCtx);
  if (!page) throw new Error("The ledger page is not provided.");
  return page;
}
