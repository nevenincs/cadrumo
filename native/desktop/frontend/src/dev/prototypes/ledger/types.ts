import type { IconName } from "./Icon";

// The ledger prototype's vocabulary of facts: movements, invoices, documents
// and the page state they live in. Every value here is synthetic.

export type Cls =
  | "business"
  | "personal"
  | "mixed"
  | "pending"
  | "unclassified"
  | "failed"
  | "skipped"
  | "excluded";
export type ReviewStatus = "pending" | "reviewed" | "skipped" | "excluded";
export type Direction = "in" | "out" | "transfer";
export type Lifecycle = "active" | "archived" | "stashed" | "split";
export type SealState =
  "verified" | "filed_local" | "filed_receipt" | "superseded" | "draft";

export type ClsDef = {
  label: string;
  token: string;
  status: ReviewStatus;
  assignable?: boolean;
};

/** A choice in a combobox or a menu. */
export type Option = {
  value: string;
  label: string;
  token?: string;
  group?: string;
  note?: string;
  icon?: IconName;
  disabled?: string | null;
};

export type Period = { year: number; code: string };

export type Fx = { rate: number; eur: number; source: string; date: string };
export type Use = {
  modelo: string;
  period: string;
  state: SealState;
  label: string;
};
export type HistoryEntry = { at: string | null; what: string; by: string };
export type Provenance = {
  file: string;
  row: number;
  provider: string;
  format: string;
  ingested: string;
  sha: string;
};
export type Suggestion = {
  cls: Cls;
  category?: string | null;
  ivaCategory?: string | null;
  share?: number | null;
  confidence: number;
  reason: string;
  digest?: string;
};
export type SplitInfo =
  | { role: "parent"; children: string[] }
  | { role: "child"; parent: string; siblings: string[] };

export type Movement = {
  id: string;
  providerId: string;
  booked: string;
  valueDate: string | null;
  amount: number;
  currency: string;
  direction: Direction;
  counterparty: string;
  description: string;
  cls: Cls;
  share: number | null;
  category: string | null;
  ivaCategory: string | null;
  base: number | null;
  ivaRate: number | null;
  ivaAmount: number | null;
  recargo: number | null;
  irpf: string | null;
  usageRatio: string | null;
  counterpartyCountry: string | null;
  idState: string | null;
  sourceJurisdiction: string | null;
  account: string | null;
  group: string | null;
  notes: string;
  lifecycle: Lifecycle;
  classifiedBy: string;
  classifiedAt: string | null;
  invoiceId: string | null;
  evidenceId: string | null;
  attachments: string[];
  fx: Fx | null;
  fxMissing: boolean;
  batch: string | null;
  prov: Provenance;
  sealed: Use[] | null;
  uses: Use[];
  suggestion: Suggestion | null;
  modelRejected: boolean;
  issue: string | null;
  forceIssues: string[] | null;
  split: SplitInfo | null;
  created: string;
  modified: string | null;
  history: HistoryEntry[];
  remoteChange: boolean;
  classifiedHistory?: {
    at: string;
    cls: Cls;
    category: string | null;
    by: string;
  }[];
  lineage?: { prev: string; at: string }[];
  deductionKind?: string | null;
  investmentAsset?: string | null;
  m210?: string | null;
  prorrataSector?: string | null;
  date?: string;
};

/** A value a cell can hold. */
export type Value = string | number | boolean | null | undefined;

export type Seed = {
  date: string;
  amount: number;
  account?: string;
  manual?: boolean;
  booked?: string;
  valueDate?: string | null;
  currency?: string;
  direction?: Direction;
  counterparty?: string;
  description: string;
  cls?: Cls;
  share?: number | null;
  category?: string | null;
  ivaCategory?: string | null;
  base?: number | null;
  ivaRate?: number | null;
  ivaAmount?: number | null;
  recargo?: number | null;
  irpf?: string | null;
  usageRatio?: string | null;
  country?: string | null;
  idState?: string | null;
  jurisdiction?: string | null;
  group?: string | null;
  notes?: string;
  lifecycle?: Lifecycle;
  classifiedBy?: string;
  fx?: Fx | null;
  fxMissing?: boolean;
  suggestion?: Suggestion | null;
  modelRejected?: boolean;
  issue?: string | null;
  forceIssues?: string[] | null;
  freshCls?: Cls;
  remoteChange?: boolean;
};

export type Account = {
  id: string;
  label: string;
  bank: string;
  iban: string;
  currency: string;
  opened: string;
  closed: string | null;
  holding: string;
  roles: string[];
};

export type InvoiceLine = {
  description: string;
  qty: number;
  qtyText: string;
  price: number;
  priceText: string;
  subtotal: number;
  rate: string;
  iva: number;
  category: string | null;
};
export type Invoice = {
  id: string;
  kind: string;
  cls: string;
  series: string | null;
  number: string;
  date: string;
  opDate: string | null;
  counterparty: string;
  nif: string | null;
  country: string;
  idState: string | null;
  base: number;
  iva: number;
  recargo: number | null;
  retentionRate: number | null;
  retention: number | null;
  total: number;
  currency: string;
  lines: InvoiceLine[];
  payment: string;
  paymentId: string | null;
  linked: string[];
  notes: string;
  ivaCategory: string | null;
  operationType: string | null;
  rectifies: string | null;
  created: string;
  provenance: string;
};

/** [value, origin, grounding] of one field the reader drafted. */
export type DraftField = [string, string, string];
export type Finding = {
  id: string;
  reason: string;
  field: string;
  detail: string;
  candidates: { value: string; note: string }[];
};
export type Doc = {
  id: string;
  file: string;
  media: string;
  added: string;
  kind: string | null;
  state: string;
  draft: Record<string, DraftField>;
  findings: Finding[];
  suggestedRow?: Movement;
  note?: string;
  invoice?: string;
  rowId?: string;
  fallback?: string;
  sha: string;
  reviewSha: string;
};
export type Rule = {
  id: string;
  name?: string;
  pattern?: string;
  kind?: string;
  value?: string;
  min?: number | null;
  max?: number | null;
  cls: Cls;
  category: string | null;
  priority?: number;
  order?: number;
  created: string;
  actor: string;
};
export type Counterparty = {
  name: string;
  taxId: string;
  country: string;
  scope: string;
  idState: string | null;
  confirmed: string | null;
  note: string;
};
export type ProrrataYear = {
  year: number;
  regime: string;
  provisional: string;
  source: string;
  definitive: string;
  sectors: string[];
};
export type CapitalGood = {
  id: string;
  description: string;
  kind: string;
  acquired: number;
  ledgerRow: string;
  cuota: number;
  prorrata: string;
  regularization: string;
  disposal: string | null;
};
export type InventoryMovement = {
  id: string;
  date: string;
  kind: string;
  qty: number;
  unit: number | null;
  base: number | null;
  note: string;
};
export type Inventory = {
  year: number;
  activity: string;
  method: string;
  movements: InventoryMovement[];
  closing: { qty: number; unit: number; base: number } | null;
};
export type Asset = {
  id: string;
  name: string;
  acquired: string;
  base: number;
  method: string;
  claimed: string;
  revisions: number;
};
export type Consent = {
  at: string;
  file: string;
  provider: string;
  acknowledged: boolean;
  derived: string[];
  effect: string;
};
export type Batch = {
  id: string;
  file: string;
  account: string;
  ingested: string;
  provider: string;
  format: string;
  sha: string;
  rows: number;
};

export type Ledger = {
  rows: Movement[];
  invoices: Invoice[];
  docs: Doc[];
  batches: Batch[];
  dupA: Movement;
};

/** What a field's parser hands back: a value, an error, or "left empty". */
export type Parsed = {
  value?: Value;
  text?: string;
  error?: string;
  empty?: boolean;
  maybe?: number;
};

export type FieldDef = {
  label: string;
  required?: boolean;
  editor: "date" | "text" | "combo" | "amount" | "share" | "rate";
  hint?: string;
  max?: number;
  clearable?: boolean;
  num?: boolean;
  needsClass?: boolean;
  tax?: boolean;
  addOnly?: boolean;
  notOnAdd?: boolean;
  clearRefusal?: string;
};

/** Staged edits: row id, then field, then the value it would take. */
export type StagedRows = Record<string, Record<string, Value>>;

export type ApprovalFields = {
  cls: Cls;
  share?: number | null;
  category?: string | null;
  ivaCategory?: string | null;
};
export type RuleMatch = {
  id: string;
  cls: Cls;
  category?: string | null;
  rule: string;
  pattern: string;
};
export type ActionPayload = {
  reason?: string;
  fields?: ApprovalFields;
  model?: string;
  newRule?: Rule;
  matches?: RuleMatch[];
  children?: {
    amount: number;
    description: string;
    cls?: Cls;
    category?: string | null;
  }[];
  invoiceId?: string;
  number?: string;
  asEvidence?: boolean;
  docId?: string;
  file?: string;
  newDoc?: Doc;
  evidence?: boolean;
  [more: string]: unknown;
};
export type ActionType =
  | "archive"
  | "stash"
  | "restore"
  | "exclude"
  | "split"
  | "merge"
  | "remove"
  | "link"
  | "attach"
  | "detach"
  | "reject"
  | "approve"
  | "rules"
  | "keepBoth";
export type StagedAction = {
  id: string;
  type: ActionType;
  rowIds: string[];
  label: string;
  tech?: string;
  detail?: string;
  payload?: ActionPayload;
  holdReason?: string;
};
export type Draft = {
  key: string;
  idem: string;
  fields: Record<string, Value>;
};
export type Staging = {
  rows: StagedRows;
  drafts: Draft[];
  actions: StagedAction[];
  derived?: Record<string, Record<string, boolean>>;
};

export type Check = {
  at: string;
  issues: Record<string, string[]>;
  changedSince: number;
};

export type Filters = {
  status: string[];
  direction: Direction[];
  cls: Cls[];
  account: string[];
  batch: string | null;
  issue: string | null;
  group: string | null;
  hideRejected: boolean;
  reason: string | null;
  foreign: boolean;
  lifecycle: Lifecycle[];
  unsaved: boolean;
  toMatch: boolean;
  noRate: boolean;
};

export type DataState = {
  byId: Record<string, Movement>;
  order: string[];
  invoices: Invoice[];
  docs: Doc[];
  batches: Batch[];
  rules: Rule[];
  ratios: Record<string, Record<string, number>>;
  accounts: Account[];
  counterparties: Counterparty[];
  prorrata: ProrrataYear[];
  capital: CapitalGood[];
  inventory: Inventory;
  assets: Asset[];
  consent: Consent[];
  dupA: string;
};

export type Blocker = { type: string; text: string; action?: StagedAction };
export type PlanEntry = {
  id: string;
  missing?: boolean;
  base: Movement;
  eff: Movement;
  fields: string[];
  routes: Record<string, string>;
  bulk: string[];
  classify: string[];
  update: string[];
  blockers: Blocker[];
  notes: string[];
  derived: string[];
  clears: string[];
  gross?: { sum: number; text: string };
  identityNote?: string;
};
export type PlanDraft = Draft & { missing: string[] };
type PlanOpBase = { key: string; label: string; tech?: string };
export type BulkOp = PlanOpBase & {
  kind: "bulk";
  part: number;
  parts: number;
  entries: PlanEntry[];
};
export type ClassifyOp = PlanOpBase & {
  kind: "classify";
  entries: PlanEntry[];
};
export type UpdateOp = PlanOpBase & { kind: "update"; entries: PlanEntry[] };
export type AddOp = PlanOpBase & { kind: "add"; draft: PlanDraft };
export type ActionOp = PlanOpBase & { kind: "action"; action: StagedAction };
export type PlanOp = BulkOp | ClassifyOp | UpdateOp | AddOp | ActionOp;
export type Plan = {
  entries: PlanEntry[];
  ready: PlanEntry[];
  blocked: PlanEntry[];
  blockedDrafts: PlanDraft[];
  heldActions: StagedAction[];
  ops: PlanOp[];
  drafts: PlanDraft[];
  words: string[];
  links: StagedAction[];
  changes: number;
  held: number;
  oneAtATime: number;
};
export type PlanChange = {
  field: string;
  from: string;
  to: string;
  ids: string[];
};

/** What the window around the grid knows when it filters and sorts. */
export type WindowCtx = {
  check?: Check | null;
  invoiceNumber?: (id: string) => string;
  stagedIds: Set<string>;
  bestByRow?: Record<string, unknown>;
};

export type Sort = { key: string; dir: "asc" | "desc" };
export type View = {
  period: Period;
  search: string;
  filters: Filters;
  savedView: string;
  groupBy: string;
  collapsed: Record<string, boolean>;
  sort: Sort;
  order: string[];
  visible: string[];
  preset: string;
  widths: Record<string, number>;
  density: "compact" | "comfortable";
  inspector: boolean;
  inspectorW: number | null;
  loaded: number;
  missingMark: string | null;
};
export type Snapshot = { staged: Staging; label: string };
export type Refusal = { raw: string; msg: string };
export type Outcome = { status: string; msg?: string };
export type Paused = {
  id: string;
  label: string;
  kind: "row" | "part";
  ids?: string[];
  fields?: string[][];
};
export type UnknownNote = {
  id: string;
  label: string;
  saved: boolean;
  at: string;
};
export type Conflict = {
  id: string;
  before: Movement;
  after: Movement;
  changed: string[];
};
export type ProtoState = {
  state: string;
  outcome: string;
  unknownResolves: string;
};
export type State = {
  data: DataState;
  readAt: string;
  check: Check;
  staged: Staging;
  undo: Snapshot[];
  redo: Snapshot[];
  appliedAt: string | null;
  refusals: Record<string, Record<string, Refusal>>;
  outcomes: Record<string, Outcome>;
  unknownNotes: UnknownNote[];
  paused: Paused | null;
  selection: Record<string, true>;
  view: View;
  proto: ProtoState;
  draftN: number;
  rekeyed?: { from: string; to: string };
  conflicts?: Conflict[];
  conflictInfo?: Conflict[];
  lastAdded?: string;
};

/** One candidate pairing of an invoice with a movement, with why it fits. */
export type Pair = {
  invoiceId: string;
  rowId: string;
  inv: Invoice;
  row: Movement;
  num: boolean;
  gap: number;
  counterparty: boolean;
  key: number[];
  chips: string[];
  settle: number;
};
export type Match = Pair & {
  ambiguous: boolean;
  ties: Pair[];
  others: Pair[];
  rivalOf?: string;
};
export type Recon = {
  best: Record<string, Match>;
  pairs: Pair[];
  list: Match[];
};

/** What the grid is given to draw: a movement, a draft or a group heading. */
export type RowItem = {
  key: string;
  kind: "row";
  row?: Movement;
  draft?: Draft;
  nested?: boolean;
};
export type GroupItem = {
  key: string;
  kind: "group";
  height: number;
  gk: string;
  grouping: string;
  label: string;
  rows: Movement[];
  collapsed: boolean;
};
export type Item = RowItem | GroupItem;
export type MovementWindow = {
  inPeriod: Movement[];
  windowRows: Movement[];
  filtered: Movement[];
  kids: Set<string>;
  truncated: boolean;
  totalCount: number;
  sortKey: string;
  elsewhere: Movement[];
};
