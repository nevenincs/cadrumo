import { Icon } from "@/components/ui/icon";
import type {
  PublicModeloFormContextFieldBlock,
  PublicModeloFormRepeatingBlock,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import { calm, Label } from "./FieldRow";

/** How many of a record's columns the table shows; the rest are counted. */
const SHOWN_COLUMNS = 5;

/** Repeated records, read as a table. Their lines are made from the filer's
 * records, so they are changed there; when those records could not be read
 * the number of lines is unknown, never zero. */
export function RepeatingBlock({
  block,
}: {
  block: PublicModeloFormRepeatingBlock;
}) {
  const t = useStrings();
  const shown = block.columns.slice(0, SHOWN_COLUMNS);
  const hidden = block.columns.length - shown.length;
  return (
    <div className="rounded-lg border border-border">
      <div className="flex items-center gap-2 border-b border-border bg-muted px-3 py-2 text-sm">
        <Icon name="sheet" size="sm" className="text-muted-foreground" />
        <span className="font-medium">
          {block.rows_known
            ? t("workspace.modelo.repeating", { count: block.rows.length })
            : t("workspace.modelo.grid.records_unknown")}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              {shown.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className="px-3 py-2 text-left text-sm font-medium text-muted-foreground"
                >
                  <Label text={column.heading} />
                </th>
              ))}
              {hidden > 0 && (
                <td className="px-3 py-2 text-right text-sm text-faint">
                  +{hidden}
                </td>
              )}
            </tr>
          </thead>
          {block.rows_known && (
            <tbody>
              {block.rows.map((row) => {
                const texts = row.value_texts;
                return (
                  <tr key={row.index} className="border-t border-border">
                    {shown.map((column, index) => (
                      <td
                        key={column.key}
                        className="px-3 py-2 text-sm tabular-nums"
                      >
                        {texts[index] ?? "—"}
                      </td>
                    ))}
                    {hidden > 0 && <td />}
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
      </div>
      <p className="px-3 py-3 text-sm text-muted-foreground">
        {t("workspace.modelo.grid.records_read_only")}
      </p>
    </div>
  );
}

/** Facts the form prints about the filer and the period, as a short list;
 * a fact not known yet says so. */
export function ContextSummary({
  items,
}: {
  items: PublicModeloFormContextFieldBlock[];
}) {
  const t = useStrings();
  return (
    <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-6 gap-y-1 rounded-lg bg-muted px-4 py-3 text-sm @3xl:grid-cols-[minmax(0,auto)_minmax(0,1fr)_minmax(0,auto)_minmax(0,1fr)]">
      {items.map((item) => {
        const text = item.value_text;
        return (
          <div key={item.id} className="contents">
            <dt className="truncate text-muted-foreground">
              {calm(item.label.text)}
            </dt>
            <dd className={text ? "text-foreground" : "text-faint"}>
              {text ?? t("workspace.modelo.value.not_known_yet")}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
