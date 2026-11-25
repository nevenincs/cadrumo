import type { CellRange } from "./dataGridModel";

/** The clipboard a grid reaches through its host. A refusal is the owner's
 * to say aloud, so `read` settles to null and `write` never rejects. */
export interface GridClipboard {
  write(text: string): void;
  read(): Promise<string | null>;
}

/**
 * Where a paste lands. A single active cell with several rows selected
 * (by checkbox, Ctrl or Shift) pastes into the active column of every
 * selected row, in grid order; a drawn range, or an active row outside the
 * selection, keeps the range as it is.
 */
export function pasteRange(
  range: CellRange,
  selection: ReadonlySet<string> | undefined,
  dataKeys: readonly string[],
): CellRange {
  if (!selection || selection.size < 2) return range;
  if (range.rows.length !== 1 || range.columns.length !== 1) return range;
  if (!selection.has(range.rows[0]!)) return range;
  return {
    rows: dataKeys.filter((key) => selection.has(key)),
    columns: range.columns,
  };
}

/** Whether a key press is the primary-modifier copy, cut or paste chord. */
export function clipboardChord(
  press: { code: string },
  primary: boolean,
): "copy" | "cut" | "paste" | null {
  if (!primary) return null;
  if (press.code === "KeyC") return "copy";
  if (press.code === "KeyX") return "cut";
  if (press.code === "KeyV") return "paste";
  return null;
}
