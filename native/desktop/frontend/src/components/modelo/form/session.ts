import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ledgerFailure } from "../../../shell/ledger";
import { modeloEditBody, type ModeloPort } from "../../../shell/modelo";
import type {
  ModeloEditApplyBaselineV1,
  ModeloEditNormalisation,
  ModeloEditOperatorInputV2,
  ModeloEditTypedEntryV1,
  ModeloEditValueAddressV1,
  ModeloEditWireScalar,
  ModeloFormAddressV1,
  ModeloEditHeldAddressV1,
  ModeloEditHeldChangeV1,
  ModeloEditHeldKind,
  ModeloFormRebaseEntryV1,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
  PublicModeloFormField,
  PublicModeloWorkForm,
} from "../../../shell/modeloContract";

// The form's working state: the edits staged on it and the box chosen. It
// lives in memory only, for one declaration, and is handed to the review and
// the details panel. A staged edit carries the contract intent for the box's
// edit address and, for a typed value, the value the application read from
// what the filer typed; nothing here reads an amount, a date or a NIF.

/** A form address as one string: `c:<casilla>` or `b:<binding>`. */
export const addressKey = (address: ModeloFormAddressV1) =>
  address.kind === "casilla"
    ? `c:${address.casilla_id}`
    : `b:${address.binding_id}`;

/** The key a box is chosen by: its own address. */
export const fieldKey = (field: PublicModeloFormField) =>
  addressKey(field.address);

/** The key an edit of a box is staged under: the address the application
 * says the edit takes, which for a value fed by a source is its binding. */
export const editKey = (field: PublicModeloFormField) =>
  addressKey(field.edit_address);

/** The edit contract's spelling of a box's edit address. */
export function editAddress(
  field: PublicModeloFormField,
): ModeloEditValueAddressV1 {
  const address = field.edit_address;
  return address.kind === "casilla"
    ? { kind: "scalar", casilla_id: address.casilla_id }
    : { kind: "binding", binding_id: address.binding_id };
}

/** A value set on a box, and the same value as the application compares
 * entries of it (for a value read from what the filer typed, or an assumed
 * value confirmed); null when it gave none. */
type SetValue = {
  value: ModeloEditWireScalar;
  change: "set";
  comparable: ModeloEditWireScalar;
};

/** One staged edit as the edit contract names it: a box takes a typed
 * value, a clear or a restore; a binding that feeds a box takes an override
 * or its removal. `change` is the kind of change the filer made, as a
 * preflight is told it: removing an override clears a value the filer gave,
 * or gives the box back to its source. */
export type StagedIntent =
  | ({ kind: "set_typed_value" } & SetValue)
  | { kind: "clear_declared_value"; change: "clear" }
  | { kind: "restore_source_value"; change: "restore" }
  | ({ kind: "set_override_value" } & SetValue)
  | {
      kind: "remove_override";
      change: Exclude<ModeloEditHeldKind, "set">;
    };

export type StagedEdit = {
  /** `editKey` of the box. */
  key: string;
  address: ModeloEditValueAddressV1;
  /** The box as the edit was last staged on it: as the form read it when
   * the filer staged it, or as a renewal's read restaged it. */
  field: PublicModeloFormField;
  intent: StagedIntent;
  /** What the filer typed, shown as typed until the edit is applied. */
  entry: string | null;
  /** What the application did to read the entry. */
  normalisations: ModeloEditNormalisation[];
  /** The box changed under the edit when the baseline was renewed; the
   * filer looks at it again before applying. */
  beforeChanged: boolean;
};

/** What the last renewal did to the staged edits, until the filer
 * acknowledges it. */
export type Rebased = { changed: number; dropped: number };

/** What reports moved or dropped, by the address of each box (its own,
 * which a restage never changes), until the filer acknowledges it. */
export type Moved = ReadonlyMap<string, "changed" | "dropped">;

/** `moved` with what one report did added: a box counts once, and a box
 * first changed and then dropped counts as dropped. */
export function noteMoved(
  moved: Moved,
  found: Iterable<[string, "changed" | "dropped"]>,
): Moved {
  const next = new Map(moved);
  for (const [key, outcome] of found)
    if (outcome === "dropped" || next.get(key) !== "dropped")
      next.set(key, outcome);
  return next;
}

/** The notice `moved` gives: how many boxes changed and how many were
 * dropped, or null when none. */
export function rebasedOf(moved: Moved): Rebased | null {
  if (moved.size === 0) return null;
  let changed = 0;
  let dropped = 0;
  for (const outcome of moved.values())
    if (outcome === "changed") changed += 1;
    else dropped += 1;
  return { changed, dropped };
}

const atBinding = (field: PublicModeloFormField) =>
  field.edit_address.kind === "binding";

/** The intent that sets a box to `value` at its edit address. */
export const valueIntent = (
  field: PublicModeloFormField,
  value: ModeloEditWireScalar,
  comparable: ModeloEditWireScalar = null,
): StagedIntent =>
  atBinding(field)
    ? { kind: "set_override_value", value, change: "set", comparable }
    : { kind: "set_typed_value", value, change: "set", comparable };

/** The intent that takes the filer's value out of a box. */
export const clearIntent = (field: PublicModeloFormField): StagedIntent =>
  atBinding(field)
    ? { kind: "remove_override", change: "clear" }
    : { kind: "clear_declared_value", change: "clear" };

/** The intent that gives a box back to its source, or null where the box
 * offers none. */
export function restoreIntent(
  field: PublicModeloFormField,
): StagedIntent | null {
  if (!field.restorable) return null;
  return atBinding(field)
    ? { kind: "remove_override", change: "restore" }
    : { kind: "restore_source_value", change: "restore" };
}

/** The intent that confirms an assumed value as the filer's own, or null
 * where the application does not offer it. */
export function confirmIntent(
  field: PublicModeloFormField,
): StagedIntent | null {
  if (!field.confirmable || field.confirm_value === null) return null;
  return valueIntent(field, field.confirm_value, field.confirm_comparable);
}

/** An edit address as one string, as a preflight's report names it. */
const heldKey = (address: ModeloEditHeldAddressV1) =>
  address.kind === "scalar"
    ? `s:${address.casilla_id}`
    : `b:${address.binding_id}`;

/** A staged edit as a preflight is told it was held: its edit address, the
 * kind of change and the box's state when it was staged, so the preflight
 * says what became of it. */
function held(edit: StagedEdit): ModeloEditHeldChangeV1 | null {
  const { address } = edit;
  if (address.kind !== "scalar" && address.kind !== "binding") return null;
  return {
    address,
    kind: edit.intent.change,
    held_state: edit.field.state_digest,
  };
}

/** The staged edits as one submission, valid for a preflight and for an
 * apply: typed values only, never entries as typed. Findings and refusals
 * come back said in `language`. A preflight is also told the changes held,
 * `heldChanges`, and reports what became of each. */
export function editSubmission(
  baseline: ModeloEditApplyBaselineV1,
  edits: Iterable<StagedEdit>,
  language: OutputLanguage,
  heldChanges = false,
): ModeloEditOperatorInputV2 {
  const all = [...edits];
  const scalar: NonNullable<
    ModeloEditOperatorInputV2["submission"]["scalar_intents"]
  > = [];
  const binding: NonNullable<
    ModeloEditOperatorInputV2["submission"]["binding_intents"]
  > = [];
  for (const edit of all) {
    const { address, intent } = edit;
    const value = "value" in intent ? { value: intent.value } : {};
    if (address.kind === "scalar") {
      if (
        intent.kind === "set_typed_value" ||
        intent.kind === "clear_declared_value" ||
        intent.kind === "restore_source_value"
      )
        scalar.push({ address, kind: intent.kind, ...value });
    } else if (
      address.kind === "binding" &&
      (intent.kind === "set_override_value" ||
        intent.kind === "remove_override")
    )
      binding.push({ address, kind: intent.kind, ...value });
  }
  return {
    input_version: 2,
    output_language: language,
    submission: {
      baseline,
      mutation_family: baseline.mutation_family,
      scalar_intents: scalar,
      binding_intents: binding,
      ...(heldChanges
        ? {
            held: all.flatMap((edit) => {
              const change = held(edit);
              return change ? [change] : [];
            }),
          }
        : {}),
    },
  };
}

/** A preflight that only reads one entry as the filer typed it. */
export function entrySubmission(
  baseline: ModeloEditApplyBaselineV1,
  field: PublicModeloFormField,
  lexeme: string,
  language: OutputLanguage,
): ModeloEditOperatorInputV2 {
  return {
    input_version: 2,
    output_language: language,
    submission: {
      baseline,
      mutation_family: baseline.mutation_family,
      lexemes: [
        { address: editAddress(field), entry_locale: language, lexeme },
      ],
    },
  };
}

/** Where a box is drawn: the page and section holding it. Boxes not yet
 * placed and working figures have pages of their own. */
export type PlacedField = {
  field: PublicModeloFormField;
  key: string;
  pageId: string;
  sectionId: string;
};

export const UNPLACED_PAGE = "unplaced";
export const WORKING_FIGURES_PAGE = "working-figures";

/** Every box of the form in reading order. */
export function placedFields(form: PublicModeloWorkForm): PlacedField[] {
  const out: PlacedField[] = [];
  const add = (
    field: PublicModeloFormField,
    pageId: string,
    sectionId: string,
  ) => out.push({ field, key: fieldKey(field), pageId, sectionId });
  for (const page of form.pages)
    for (const section of page.sections)
      for (const block of section.blocks) {
        if (block.kind === "field") add(block.field, page.id, section.id);
        else if (block.kind === "binding_inputs")
          for (const field of block.fields) add(field, page.id, section.id);
        else if (block.kind === "grid")
          for (const row of block.rows)
            for (const cell of row.cells)
              if (cell.field) add(cell.field, page.id, section.id);
      }
  for (const unplaced of form.unplaced)
    add(unplaced.field, UNPLACED_PAGE, UNPLACED_PAGE);
  for (const field of form.working_figures)
    add(field, WORKING_FIGURES_PAGE, WORKING_FIGURES_PAGE);
  return out;
}

/** The intent an edit takes when it is staged again on `field`, as the
 * box now stands, or null when the box no longer takes it: a value the box
 * already holds as the filer's own changes nothing, a clear needs a value
 * of the filer's to remove, and a restore needs a source to go back to. */
export function restaged(
  edit: StagedEdit,
  field: PublicModeloFormField,
): StagedIntent | null {
  const { intent } = edit;
  if (intent.change === "set") {
    if (!field.takes_typed_value) return null;
    if (
      field.own_value !== null &&
      intent.comparable !== null &&
      intent.comparable === field.own_value
    )
      return null;
    return valueIntent(field, intent.value, intent.comparable);
  }
  if (intent.change === "clear")
    return field.clearable ? clearIntent(field) : null;
  return restoreIntent(field);
}

/** The staged edits as a preflight's `report` leaves them on the boxes
 * `placed` as they now stand: each kept or changed edit staged again on its
 * box, the others dropped; and what the report moved or dropped, by the
 * box's own address. */
export function rebasedEdits(
  staged: ReadonlyMap<string, StagedEdit>,
  report: ModeloFormRebaseEntryV1[],
  placed: readonly PlacedField[],
): {
  next: Map<string, StagedEdit>;
  found: [string, "changed" | "dropped"][];
} {
  const outcomes = new Map(
    report.map((entry) => [heldKey(entry.address), entry.outcome]),
  );
  const now = new Map(placed.map((p) => [p.key, p.field]));
  const next = new Map<string, StagedEdit>();
  const found: [string, "changed" | "dropped"][] = [];
  for (const edit of staged.values()) {
    const change = held(edit);
    const outcome = (change && outcomes.get(heldKey(change.address))) ?? "kept";
    const where = addressKey(edit.field.address);
    const field = now.get(where);
    const intent = field && outcome !== "dropped" && restaged(edit, field);
    if (!field || !intent) {
      found.push([where, "dropped"]);
      continue;
    }
    if (outcome === "changed") found.push([where, "changed"]);
    const key = editKey(field);
    next.set(key, {
      ...edit,
      key,
      address: editAddress(field),
      field,
      intent,
      beforeChanged: outcome === "changed" || edit.beforeChanged,
    });
  }
  return { next, found };
}

/** Whether a box can be typed into here: the form admits edits and the
 * application says the box takes a typed value. */
export function editableHere(
  envelope: ModeloWorkbenchFormProjectionV1,
  field: PublicModeloFormField,
): boolean {
  return editsAdmitted(envelope) && field.takes_typed_value;
}

/** Whether the declaration takes edits at all. */
export const editsAdmitted = (envelope: ModeloWorkbenchFormProjectionV1) =>
  envelope.admitted_baseline !== null &&
  envelope.form.form.edit_closure === null;

/** What reading one typed entry came to. */
export type EntryOutcome =
  | { kind: "staged" }
  | { kind: "unchanged" }
  | { kind: "refused"; entry: ModeloEditTypedEntryV1 }
  /** Not read: the check was refused, in its own words where it gave
   * them, or never reached the application. */
  | { kind: "failed"; code: string; words: string | null };

/** A request to bring a box or a section into view; `seq` repeats it. */
export type Reveal = { key: string | null; sectionId: string; seq: number };

export type FormSession = {
  staged: ReadonlyMap<string, StagedEdit>;
  stagedCount: number;
  stage(field: PublicModeloFormField, intent: StagedIntent): void;
  unstage(editKey: string): void;
  discardAll(): void;
  /** Keeps the staged edits a preflight's `report` keeps, staged again
   * against the declaration as it stands, and drops the others. */
  rebase(report: ModeloFormRebaseEntryV1[]): void;
  /** What the last report moved or dropped, until acknowledged; null when
   * nothing. */
  rebased: Rebased | null;
  /** A report not yet applied: until it is, the staged edits do not carry
   * what it says. */
  rebasePending: boolean;
  /** Takes the renewal's marks off the edits the filer has looked at. */
  acknowledge(): void;
  /** Reads what the filer typed into a box through the application and
   * stages the value it reads. An empty entry takes back a value typed here,
   * or else takes the filer's value out of the box. */
  enter(field: PublicModeloFormField, text: string): Promise<EntryOutcome>;
  selectedKey: string | null;
  selected: PublicModeloFormField | null;
  select(key: string | null): void;
  /** Chooses the box printed with `box` and brings it into view. */
  selectBox(box: string): boolean;
  /** Chooses the box of a casilla and brings it into view. */
  selectCasilla(casillaId: string): boolean;
  /** Chooses the box at a form address and brings it into view. */
  selectAddress(address: ModeloFormAddressV1): boolean;
  /** The box at a form address, where the form draws one. */
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  /** Chooses the next box after the chosen one that needs the filer, or
   * whose calculation failed, and brings it into view. */
  jumpToNext(kind: "todo" | "failed"): boolean;
  goSection(sectionId: string): void;
  pageId: string | null;
  setPageId(id: string): void;
  reveal: Reveal | null;
  placed: readonly PlacedField[];
};

export function useFormSession({
  envelope,
  port,
  language,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  language: OutputLanguage;
}): FormSession {
  const form = envelope.form.form;
  const placed = useMemo(() => placedFields(form), [form]);
  const byKey = useMemo(() => new Map(placed.map((p) => [p.key, p])), [placed]);
  const [staged, setStaged] = useState<ReadonlyMap<string, StagedEdit>>(
    () => new Map(),
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [pageId, setPageId] = useState<string | null>(
    form.pages[0]?.id ?? null,
  );
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const seq = useRef(0);

  // Staged edits belong to one declaration; another one starts clean.
  const unit = envelope.work_unit_id;
  const [heldUnit, setHeldUnit] = useState(unit);
  if (heldUnit !== unit) {
    setHeldUnit(unit);
    setStaged(new Map());
    setSelectedKey(null);
    setPageId(form.pages[0]?.id ?? null);
    setReveal(null);
  }
  useEffect(() => {
    if (pageId === null && form.pages[0]) setPageId(form.pages[0].id);
  }, [pageId, form.pages]);

  const stage = useCallback(
    (
      field: PublicModeloFormField,
      intent: StagedIntent,
      entry: string | null = null,
      normalisations: ModeloEditNormalisation[] = [],
    ) => {
      const key = editKey(field);
      setStaged((now) => {
        const next = new Map(now);
        next.set(key, {
          key,
          address: editAddress(field),
          field: now.get(key)?.field ?? field,
          intent,
          entry,
          normalisations,
          beforeChanged: now.get(key)?.beforeChanged ?? false,
        });
        return next;
      });
    },
    [],
  );
  const unstage = useCallback((key: string) => {
    setStaged((now) => {
      if (!now.has(key)) return now;
      const next = new Map(now);
      next.delete(key);
      return next;
    });
  }, []);
  const [moved, setMoved] = useState<Moved>(() => new Map());
  const rebased = useMemo(() => rebasedOf(moved), [moved]);
  const discardAll = useCallback(() => {
    setStaged(new Map());
    setMoved(new Map());
  }, []);

  // A renewal's report is applied once the declaration is read again: each
  // kept edit is staged again against its box as it now stands, as the
  // TUI's rebase does, and a box that changed under its edit is marked.
  const [pendingRebase, setPendingRebase] = useState<
    ModeloFormRebaseEntryV1[] | null
  >(null);
  const rebase = useCallback(
    (report: ModeloFormRebaseEntryV1[]) => setPendingRebase(report),
    [],
  );
  useEffect(() => {
    if (!pendingRebase) return;
    setPendingRebase(null);
    const { next, found } = rebasedEdits(staged, pendingRebase, placed);
    setStaged(next);
    // What a report moved or dropped is said until the filer acknowledges
    // it: a later check is told only the changes still held, so it adds what
    // it finds, by box, and never takes back what an earlier report dropped.
    if (found.length) setMoved((shown) => noteMoved(shown, found));
  }, [pendingRebase, placed, staged]);
  const acknowledge = useCallback(() => {
    setMoved(new Map());
    setStaged((held) => {
      if (![...held.values()].some((edit) => edit.beforeChanged)) return held;
      return new Map(
        [...held].map(([key, edit]) => [
          key,
          { ...edit, beforeChanged: false },
        ]),
      );
    });
  }, []);

  const baseline = envelope.admitted_baseline;
  const enter = useCallback(
    async (field: PublicModeloFormField, text: string) => {
      const lexeme = text.trim();
      const key = editKey(field);
      const held = staged.get(key);
      if (!lexeme) {
        // Emptying a value typed here takes it back; emptying a value the
        // box holds takes the filer's value out of it.
        if (held && "value" in held.intent) {
          unstage(key);
          return { kind: "staged" } as const;
        }
        if (held || !field.clearable) return { kind: "unchanged" } as const;
        stage(field, clearIntent(field));
        return { kind: "staged" } as const;
      }
      if (held?.entry === lexeme) return { kind: "unchanged" } as const;
      if (!baseline)
        return { kind: "failed", code: "not_admitted", words: null } as const;
      try {
        const outcome = await port.edit(
          "modelo.edit.preflight",
          modeloEditBody(entrySubmission(baseline, field, lexeme, language)),
        );
        if (outcome.kind !== "settled")
          return { kind: "failed", code: outcome.kind, words: null } as const;
        const read = outcome.result;
        if (read.outcome.outcome === "refused")
          return {
            kind: "failed",
            code: read.outcome.refusal.kind,
            words: read.refusal_words,
          } as const;
        const entry = read.parsed[0];
        if (!entry)
          return { kind: "failed", code: "unknown", words: null } as const;
        if (entry.refusal) return { kind: "refused", entry } as const;
        // Typing the filer's own value again changes nothing; an assumed value
        // typed unchanged is staged, as keeping it is how it is confirmed.
        if (
          field.own_value !== null &&
          entry.comparable_value === field.own_value
        ) {
          if (held) unstage(key);
          return { kind: "unchanged" } as const;
        }
        stage(
          field,
          valueIntent(field, entry.value, entry.comparable_value),
          lexeme,
          entry.normalisations,
        );
        return { kind: "staged" } as const;
      } catch (error) {
        return {
          kind: "failed",
          code: ledgerFailure(error).code,
          words: null,
        } as const;
      }
    },
    [baseline, language, port, stage, staged, unstage],
  );

  const bring = useCallback((target: PlacedField | undefined) => {
    if (!target) return false;
    setPageId(target.pageId);
    setSelectedKey(target.key);
    seq.current += 1;
    setReveal({
      key: target.key,
      sectionId: target.sectionId,
      seq: seq.current,
    });
    return true;
  }, []);
  const selectBox = useCallback(
    (box: string) => bring(placed.find((p) => p.field.box === box)),
    [bring, placed],
  );
  const selectCasilla = useCallback(
    (casillaId: string) => bring(byKey.get(`c:${casillaId}`)),
    [bring, byKey],
  );
  const selectAddress = useCallback(
    (address: ModeloFormAddressV1) => bring(byKey.get(addressKey(address))),
    [bring, byKey],
  );
  const fieldAt = useCallback(
    (address: ModeloFormAddressV1) =>
      byKey.get(addressKey(address))?.field ?? null,
    [byKey],
  );
  const jumpToNext = useCallback(
    (kind: "todo" | "failed") => {
      const wanted = placed.filter((p) =>
        kind === "todo"
          ? p.field.standing === "needs_you" && !staged.has(editKey(p.field))
          : p.field.origin === "calculation_failed",
      );
      const at = wanted.findIndex((p) => p.key === selectedKey);
      return bring(wanted[(at + 1) % Math.max(wanted.length, 1)]);
    },
    [bring, placed, selectedKey, staged],
  );
  const goSection = useCallback(
    (sectionId: string) => {
      const page =
        form.pages.find((p) => p.sections.some((s) => s.id === sectionId))
          ?.id ?? sectionId;
      setPageId(page);
      seq.current += 1;
      setReveal({ key: null, sectionId, seq: seq.current });
    },
    [form.pages],
  );

  return {
    staged,
    stagedCount: staged.size,
    stage,
    unstage,
    discardAll,
    rebase,
    rebased,
    rebasePending: pendingRebase !== null,
    acknowledge,
    enter,
    selectedKey,
    selected: selectedKey ? (byKey.get(selectedKey)?.field ?? null) : null,
    select: setSelectedKey,
    selectBox,
    selectCasilla,
    selectAddress,
    fieldAt,
    jumpToNext,
    goSection,
    pageId,
    setPageId,
    reveal,
    placed,
  };
}
