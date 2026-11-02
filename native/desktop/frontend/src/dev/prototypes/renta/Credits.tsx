import { Button } from "@/components/ui/button";
import { useStrings } from "@/shell/strings";
import { BoxLine } from "./BoxLine";
import type { CreditsCase } from "./fixtures";
import { Gap } from "./Gap";
import type { ProjectV2 } from "./projectV2";

// Withholding and payments on account. Every box is drawn from its served
// field: its origin and editability decide what it shows and offers. The
// withholding boxes are fed by the register the filer keeps, so the form
// serves them without an editor and the place to correct them is the
// withholding register. Where the read names that place, the panel offers to
// open it; where it does not, the panel says so instead of guessing.

export function Credits({
  credits,
  projection,
  onOpenWithholding,
}: {
  credits: CreditsCase;
  projection?: ProjectV2;
  onOpenWithholding?: () => void;
}) {
  const t = useStrings();
  const linesOf = (box: string | null) =>
    credits.issue_lines.filter((line) => box !== null && line.box === box);
  const surfaced = credits.issue_lines.some(
    (line) => line.surface === "withholding",
  );
  return (
    <section className="flex max-w-3xl flex-col gap-4 p-4">
      <h2 className="text-lg font-semibold">
        {t("workspace.renta.outline.credits")}
      </h2>
      <ul className="rounded-md border border-border px-3">
        {credits.fields.map((field) => (
          <BoxLine
            key={field.state_digest}
            field={field}
            lines={linesOf(field.box)}
          />
        ))}
      </ul>
      {surfaced ? (
        <Button variant="outline" onClick={onOpenWithholding}>
          {t("workspace.modelo.surface.open.withholding")}
        </Button>
      ) : (
        <Gap operation="modelo.work.form: issue_lines[].surface for the withholding boxes" />
      )}
      {projection && (
        <div className="flex flex-col gap-2 rounded-md border border-border p-3">
          <ul className="flex flex-col gap-1 font-mono text-xs text-muted-foreground">
            {projection.unresolved_bindings.map((entry) => (
              <li key={entry.binding_id}>
                {entry.casilla_id} · {entry.reason} · {entry.note}
              </li>
            ))}
            {projection.unresolved_casillas.map((entry) => (
              <li key={entry.casilla_id}>
                {entry.casilla_id} · {entry.reason} · {entry.formula_id}
              </li>
            ))}
          </ul>
          <Gap operation="modelo.project v2: served words for unresolved_bindings and unresolved_casillas" />
        </div>
      )}
    </section>
  );
}
