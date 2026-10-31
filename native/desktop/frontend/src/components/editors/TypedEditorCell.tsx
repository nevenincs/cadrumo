import { useState, type FocusEvent, type KeyboardEvent } from "react";
import { TypedField } from "@/components/editors/TypedField";
import { commitKeyOf } from "@/components/ui/dataGridModel";
import type { EditorContext } from "@/components/ui/data-grid";
import type { FieldSpec } from "@/shared/fieldKind";

const inPopover = (target: EventTarget | null) =>
  target instanceof Element && target.closest("[data-slot=popover-content]");

function TypedCellEditor({
  field,
  context,
  initial,
}: {
  field: FieldSpec;
  context: EditorContext;
  initial: string;
}) {
  const [value, setValue] = useState(context.initial ?? initial);
  const [done, setDone] = useState(false);
  const commit = (
    held: string,
    via?: Parameters<EditorContext["commit"]>[1],
  ) => {
    setDone(true);
    context.commit(held, via);
  };
  // Keys and focus also arrive from a calendar in its portal, which is still
  // part of this edit and keeps its own keys.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.target as Node)) return;
    const how = commitKeyOf(event);
    if (!how) return;
    event.preventDefault();
    event.stopPropagation();
    if (how === "cancel") {
      setDone(true);
      context.cancel();
    } else commit(value, how);
  };
  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    const next = event.relatedTarget;
    if (done || inPopover(event.target) || inPopover(next)) return;
    if (next instanceof Node && event.currentTarget.contains(next)) return;
    if (value === initial && context.initial === undefined) {
      setDone(true);
      context.cancel(false);
    } else commit(value, "pointer");
  };
  return (
    <div data-slot="typed-cell-editor" onKeyDown={onKeyDown} onBlur={onBlur}>
      <TypedField
        field={field}
        value={value}
        onChange={setValue}
        onPicked={(picked) => commit(picked, "pointer")}
        aria-label={context.label}
        describedBy={context.describedBy}
        controlSize="sm"
        autoFocus
      />
    </div>
  );
}

/**
 * A column's `editor` for a typed field: `editor: typedEditorCell({ kind: "money" },
 * (row) => row.amount)`. `commit` receives the held text, canonical or unread,
 * for the column's own check; a row with no `valueOf` is read-only.
 */
export function typedEditorCell<R>(
  field: FieldSpec,
  valueOf: (row: R) => string | null,
) {
  return function editor(row: R, context: EditorContext) {
    const initial = valueOf(row);
    return initial === null ? null : (
      <TypedCellEditor field={field} context={context} initial={initial} />
    );
  };
}
