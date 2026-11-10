import type * as React from "react";
import type { CellRange, CommitKey, SelectionCause } from "./dataGridModel";
import type { GridClipboard } from "./dataGridClipboard";

/** What a cell's renderer knows of where it stands. */
export type CellContext = {
  key: string;
  active: boolean;
  selected: boolean;
  /** The column is drawn at its narrower width. */
  narrowed: boolean;
};

/** What an editor needs: the key that opened it, its accessible name and
 * description, and the two ways out. */
export type EditorContext = {
  key: string;
  column: string;
  /** The character typed to open the editor, which replaces the value. */
  initial?: string;
  label: string;
  describedBy?: string;
  commit: (value: unknown, via?: CommitKey) => void;
  /** Drops the edit. Focus goes back to the cell unless `refocus` is false,
   * as when the person pressed somewhere else. */
  cancel: (refocus?: boolean) => void;
};

export type GridColumn<R> = {
  /** Stable: widths, order and `aria-colindex` follow it. */
  id: string;
  /** Already localized header content. */
  header: React.ReactNode;
  /** The column's name in words, for announcements, where `header` is not
   * plain text. */
  label?: string;
  /** In rem. */
  width: number;
  minWidth?: number;
  /** A share of the room left once every column has its width. */
  grow?: number;
  /** Pinned at an inline edge while the rest scrolls. */
  sticky?: "start" | "end";
  /** The narrower width, in rem, a pinned column takes where the pinned
   * groups would otherwise leave no scrolling column room to show whole. */
  narrowWidth?: number;
  /** The header drawn at the narrower width. */
  narrowHeader?: React.ReactNode;
  /** `end` for figures, which also take tabular numerals. */
  align?: "start" | "end";
  sortable?: boolean;
  /** Default true. */
  resizable?: boolean;
  cell: (row: R, context: CellContext) => React.ReactNode;
  /** Null makes the cell read-only for that row. */
  editor?: (row: R, context: EditorContext) => React.ReactNode | null;
  /** Announced when an edit is asked of a cell that cannot take one. */
  readOnlyReason?: (row: R) => string | undefined;
};

/** Props a custom row spreads on each of its focusable cells. */
export type CustomCellProps = {
  id: string;
  role: "gridcell";
  tabIndex: number;
  "aria-colindex": number;
  "aria-describedby"?: string;
  "data-slot": "data-grid-cell";
  "data-active"?: true;
  className: string;
  onPointerDown: (event: React.PointerEvent) => void;
  onDoubleClick: () => void;
  onContextMenu: (event: React.MouseEvent) => void;
};

export type RowContext = {
  key: string;
  active: boolean;
  /** Which of the row's cells is active, when the row is. */
  activeCell: number | null;
  cellProps: (index: number) => CustomCellProps;
  /** The cell being edited, and the editor to draw in it. */
  editingCell: number | null;
  editor: React.ReactNode;
};

export type GridRow<R> =
  | { kind: "data"; key: string; data: R }
  | {
      kind: "section";
      key: string;
      label: React.ReactNode;
      depth?: number;
      collapsed?: boolean;
      /** A quieter line beside the label: what the section holds. */
      hint?: React.ReactNode;
      /** At the trailing edge: a count or a total. */
      summary?: React.ReactNode;
    }
  | {
      kind: "custom";
      key: string;
      render: (context: RowContext) => React.ReactNode;
      /** How many focusable cells it has: one by default, which the grid
       * draws across the row; none for a row that only divides. */
      cells?: number;
    };

/** Where a menu opens: a point, or with a height the edge of a cell. */
export type GridMenuAnchor = { x: number; y: number; height?: number };

export type RowState = {
  changed?: boolean;
  refused?: boolean;
  locked?: boolean;
  current?: boolean;
};

export type CellDescription = {
  text?: string;
  invalid?: boolean;
  readOnlyReason?: string;
};

export type DataGridHandle = {
  /** Scrolls the row into view and focuses its cell. */
  focusCell: (key: string, column?: string) => void;
  scrollToKey: (key: string, align?: "nearest" | "start" | "center") => void;
  /** The active cell; `key` is null on the header row. */
  activeCell: () => { key: string | null; column: string } | null;
  /** The cell range drawn from an anchor, or null where only the active
   * cell is chosen. */
  cellRange: () => CellRange | null;
  edit: (key: string, column: string, initial?: string) => void;
  /** Empties the live region.
   *
   * What it last said describes a cell as it was then. Once the rows it
   * described are written and read again, that sentence is about a state the
   * grid no longer holds, and a screen reader asked to repeat it would read a
   * change that is already saved as still unsaved. The owner of the write
   * empties it; the next keyboard move says the row as it is now. */
  clearAnnouncement: () => void;
};

export type DataGridProps<R> = {
  ref?: React.Ref<DataGridHandle>;
  /** The grid's accessible name. */
  label: string;
  columns: readonly GridColumn<R>[];
  /** Already filtered, sorted and grouped. */
  rows: readonly GridRow<R>[];
  /** "Row 3 of 40": the start of what a keyboard move announces. */
  positionLabel: (row: number, count: number) => string;
  /** In rem; undefined has the row measured once and kept by key. Without
   * it data and section rows take the density's height and custom rows are
   * measured. */
  rowHeight?: (row: GridRow<R>) => number | undefined;
  editorForCell?: (
    key: string,
    index: number,
    context: EditorContext,
  ) => React.ReactNode | null;
  density?: "compact" | "comfortable";
  sort?: { column: string; direction: "asc" | "desc" } | null;
  onSort?: (column: string) => void;
  /** Selected row keys; leave out for a grid without row selection. */
  selection?: ReadonlySet<string>;
  onSelectionChange?: (
    next: ReadonlySet<string>,
    cause: SelectionCause,
  ) => void;
  /** Enter on a cell without an editor, or a double click. */
  onActivate?: (key: string) => void;
  /** An editor's value; null asks for the cell to be cleared. */
  onCommit?: (key: string, column: string, value: unknown) => void;
  onMenu?: (key: string, column: string | null, at: GridMenuAnchor) => void;
  onToggleSection?: (key: string) => void;
  /** The text to put on the clipboard for a range, or null for none. */
  onCopy?: (range: CellRange) => string | null;
  onPaste?: (range: CellRange, text: string) => void;
  /** The host clipboard. With it Ctrl+C, Ctrl+X and Ctrl+V are handled on
   * the key itself, since a desktop webview raises no clipboard event for
   * them; without it the browser's own copy and paste events serve. */
  clipboard?: GridClipboard;
  onFill?: (range: CellRange, direction: "down" | "right") => void;
  /** In rem. */
  onColumnResize?: (column: string, width: number) => void;
  /** Every column id, in the new drawn order. */
  onColumnOrder?: (order: string[]) => void;
  rowState?: (key: string) => RowState | undefined;
  /** A hidden status for the row, read with each of its cells. */
  describeRow?: (key: string) => string | undefined;
  describeCell?: (key: string, column: string) => CellDescription | undefined;
  empty?: React.ReactNode;
  overscan?: number;
  className?: string;
  /** Names the header's cue for columns scrolled out of view under the
   * pinned end group; without it no cue is drawn. */
  moreColumnsLabel?: (count: number) => string;
  /** Names the cue for columns scrolled out of view under the pinned start
   * group; without it no cue is drawn. */
  earlierColumnsLabel?: (count: number) => string;
  /** Told the least width, in CSS pixels of the whole grid, at which any
   * scrolling column can be shown whole beside the pinned ones. */
  onLeast?: (width: number) => void;
};

export type Active = { key: string | null; column: string };
export type Editing = { key: string; column: string; initial?: string };
