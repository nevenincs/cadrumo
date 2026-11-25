import type { ModeloEditBindingAddressV1 } from "../../../shell/modeloContract/modeloEditWork";
import type {
  AbsenceAttestationFamily,
  ModeloFormCarryAttestation,
} from "../../../shell/modeloContract/modeloWorkForm";

// The statements a form serves for a family stated row by row: one entry for
// each row of a repeating group, naming the row. Each is staged on the
// bindings it names at the address of that binding and that row, and drawn
// nowhere on the form's boxes: the row has no box of its own to hold it, so
// these edits are kept apart from the boxes' and reach the review and the
// submission beside them.

/** The row a served statement speaks of; null for a form-wide statement. */
export const rowOfStatement = (
  statement: ModeloFormCarryAttestation,
): string | null =>
  typeof statement.row_identity === "string" ? statement.row_identity : null;

/** One binding of one row's statement, in the words the form served. */
export type RowStatementEdit = {
  /** The binding and the row, as one key. */
  key: string;
  /** The statement the edit belongs to: its family and row, as one key. */
  group: string;
  address: ModeloEditBindingAddressV1 & { kind: "binding" };
  family: AbsenceAttestationFamily;
  /** The row, in the words served for it. */
  rowWords: string | null;
  words: string;
  effect: string;
};

/** The statements of a form that are not stated row by row. */
export const formWideStatements = (
  served: readonly ModeloFormCarryAttestation[],
): ModeloFormCarryAttestation[] =>
  served.filter((statement) => rowOfStatement(statement) === null);

/** The edit of each binding `statement` names, at its row; none for a
 * form-wide statement. */
export function rowStatementEdits(
  statement: ModeloFormCarryAttestation,
): RowStatementEdit[] {
  const row = rowOfStatement(statement);
  if (row === null) return [];
  return statement.binding_ids.map((bindingId) => ({
    key: `b:${bindingId}@${row}`,
    group: `state:${statement.family}@${row}`,
    address: { kind: "binding", binding_id: bindingId, row_identity: row },
    family: statement.family,
    rowWords: statement.row_words ?? null,
    words: statement.action_words,
    effect: statement.effect_words,
  }));
}

/** Whether `staged` holds the edit of every binding `statement` names. */
export const stagesRowStatement = (
  staged: ReadonlyMap<string, RowStatementEdit>,
  statement: ModeloFormCarryAttestation,
): boolean => {
  const edits = rowStatementEdits(statement);
  return edits.length > 0 && edits.every((edit) => staged.has(edit.key));
};

/** The row statements `chosen` stages, in the order `served` serves them. */
export function chosenRowStatements(
  served: readonly ModeloFormCarryAttestation[],
  chosen: readonly ModeloFormCarryAttestation[],
): Map<string, RowStatementEdit> {
  const next = new Map<string, RowStatementEdit>();
  for (const statement of served)
    if (chosen.includes(statement))
      for (const edit of rowStatementEdits(statement)) next.set(edit.key, edit);
  return next;
}

/** `staged` with every statement whole: a row statement the form no longer
 * serves, or one of whose bindings it no longer names or is not all staged,
 * is dropped. */
export function wholeRowStatements(
  staged: ReadonlyMap<string, RowStatementEdit>,
  served: readonly ModeloFormCarryAttestation[],
): ReadonlyMap<string, RowStatementEdit> {
  const kept = chosenRowStatements(
    served,
    served.filter((statement) => stagesRowStatement(staged, statement)),
  );
  const same =
    kept.size === staged.size && [...staged.keys()].every((k) => kept.has(k));
  return same ? staged : kept;
}

/** The staged row statements as the review lists them: the edits of one
 * statement together, in the order staged. */
export function rowStatementLines(
  staged: Iterable<RowStatementEdit>,
): RowStatementEdit[][] {
  const lines = new Map<string, RowStatementEdit[]>();
  for (const edit of staged)
    lines.set(edit.group, [...(lines.get(edit.group) ?? []), edit]);
  return [...lines.values()];
}
