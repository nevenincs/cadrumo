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
} from "../../../shell/modeloContract";
import { factsGap } from "../../../shell/compose";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "./BoxNumber";
import { calm, Label, useChosenFocus } from "./FieldRow";
import { useForm } from "./formContext";
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
  const { session, editing, setEditing, onDone, onOpenSurface } = useForm();
  const key = fieldKey(field);
  const selected = session.selectedKey === key;
  const open = editing?.key === key ? editing.request : null;
  const ref = useChosenFocus<HTMLTableCellElement>(selected, open !== null);
  return (
    <td
      ref={ref}
      data-key={key}
      tabIndex={selected ? 0 : -1}
      aria-label={t("workspace.modelo.section.box", { box: field.box ?? "" })}
      className={cn(
        "p-1 align-middle outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
        selected && "bg-selected",
      )}
      onClick={() => session.select(key)}
      onFocus={(event) => {
        if (event.target === event.currentTarget) session.select(key);
      }}
    >
      <div className="flex items-center justify-end gap-2">
        <BoxNumber box={field.box} size="sm" />
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
          onOpenSurface={onOpenSurface}
          align="grid"
        />
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
