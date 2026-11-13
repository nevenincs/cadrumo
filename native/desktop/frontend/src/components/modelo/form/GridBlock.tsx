import { cn } from "@/components/ui/cn";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  PublicModeloFormField,
  PublicModeloFormGridBlock,
  PublicModeloFormGridCell,
} from "../../../shell/modeloContract/modeloWorkForm";
import { factsGap } from "../../../shell/compose";
import { useStrings } from "../../../shell/strings";
import { BoxNoteMark } from "./BoxNoteList";
import { notesOf } from "./boxNotes";
import { BoxNumber } from "./BoxNumber";
import { readOnlyReason } from "./entryField";
import { FieldFacts } from "./FieldFacts";
import { calm, Label, useChosenFocus } from "./FieldRow";
import { openableSurface, useForm } from "./formContext";
import { editKey, fieldKey } from "./session";
import { ValueCell } from "./ValueCell";

// An official grid with its own rows and columns. A cell is a box, a figure
// the calculation asks for, a figure the form prints, or nothing.

function GridCell({ cell }: { cell: PublicModeloFormGridCell }) {
  const t = useStrings();
  const field = cell.field;
  if (cell.kind === "blank" || !field) return <td className="p-1" />;
  if (cell.kind === "design_constant")
    return (
      <td className="px-3 py-2 text-right align-middle">
        <Tooltip>
          <TooltipTrigger asChild>
            <span
              tabIndex={0}
              className="inline-flex items-center gap-1.5 text-base text-muted-foreground tabular-nums"
            >
              <BoxNumber box={field.box} size="sm" />
              {field.value_text ?? "—"}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {t("workspace.modelo.rate.printed_by_form")}
          </TooltipContent>
        </Tooltip>
      </td>
    );
  return <GridBox field={field} />;
}

function GridBox({ field }: { field: PublicModeloFormField }) {
  const t = useStrings();
  const form = useForm();
  const { session, editing, setEditing, onDone, onOpenSurface, notes } = form;
  const surface = openableSurface(form, field);
  const key = fieldKey(field);
  const selected = session.selectedKey === key;
  const open = editing?.key === key ? editing.request : null;
  const ref = useChosenFocus<HTMLTableCellElement>(selected, open !== null);
  const reason = readOnlyReason(field);
  const value = (
    <ValueCell
      field={field}
      staged={session.staged.get(editKey(field))}
      grammar={session.grammarOf(field)}
      editable={session.editable(field)}
      editing={open}
      onEditingChange={(request) =>
        setEditing(request ? key : null, request ?? undefined)
      }
      enter={session.enter}
      onDone={(how) => onDone(field, how)}
      onOpenSurface={surface ? onOpenSurface : undefined}
      align="grid"
    />
  );
  return (
    <td
      ref={ref}
      data-key={key}
      data-value-kind={field.value?.kind}
      data-value={field.value?.text}
      tabIndex={selected ? 0 : -1}
      aria-label={t("workspace.modelo.section.box", { box: field.box ?? "" })}
      className={cn(
        "group/cell p-1 align-middle outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
        selected && "bg-selected",
      )}
      onClick={() => session.select(key)}
      onFocus={(event) => {
        if (event.target === event.currentTarget) session.select(key);
      }}
    >
      <div className="flex items-center justify-end gap-2">
        <FieldFacts
          field={field}
          className={cn(
            !selected &&
              "invisible group-focus-within/cell:visible group-hover/cell:visible",
          )}
        />
        <BoxNoteMark notes={notesOf(notes, field)} />
        <BoxNumber box={field.box} size="sm" />
        {reason ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0} className="block">
                {value}
              </span>
            </TooltipTrigger>
            <TooltipContent>{reason}</TooltipContent>
          </Tooltip>
        ) : (
          value
        )}
      </div>
    </td>
  );
}

export function GridBlock({ block }: { block: PublicModeloFormGridBlock }) {
  const t = useStrings();
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-muted">
            <td className="w-2/5 px-3 py-2" />
            {block.columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className="px-3 py-2 text-right text-sm font-medium text-muted-foreground"
              >
                <Label text={column.heading} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row) => {
            const rate = row.cells.find(
              (cell) =>
                cell.kind === "design_constant" && cell.field?.printed_rate,
            );
            const rateText = rate?.field?.value_text ?? null;
            return (
              <tr key={row.key} className="border-t border-border">
                <th
                  scope="row"
                  className="px-3 py-2 text-left align-middle text-base font-normal"
                >
                  {calm(row.heading.text)}
                  {rateText && (
                    <span className="text-muted-foreground">
                      {factsGap(t)}
                      {rateText}
                    </span>
                  )}
                </th>
                {row.cells.map((cell, index) => (
                  <GridCell key={index} cell={cell} />
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
