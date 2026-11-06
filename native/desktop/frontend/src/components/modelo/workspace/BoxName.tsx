import type { PublicModeloFormField } from "../../../shell/modeloContract/modeloWorkForm";
import { BoxNumber } from "../form/BoxNumber";
import { BoxLabel } from "./BoxLabel";

/** A box named by its printed number and the form's label for it. */
export function BoxName({
  field,
  box,
}: {
  field: PublicModeloFormField | null;
  box: string | null;
}) {
  return (
    <span className="flex min-w-0 items-start gap-2">
      <BoxNumber box={box} />
      {field && (
        <span className="min-w-0 text-base">
          <BoxLabel text={field.label} />
        </span>
      )}
    </span>
  );
}
