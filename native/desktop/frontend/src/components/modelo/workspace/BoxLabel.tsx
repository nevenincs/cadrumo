import type { ModeloFormText } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { calm } from "../form/FieldRow";

/** A box's served label, with a note where the words are not the window's
 * own language: this view draws boxes outside the form, so it states the
 * disclosure itself. */
export function BoxLabel({ text }: { text: ModeloFormText }) {
  const t = useStrings();
  return (
    <>
      {calm(text.text)}
      {text.disclosure !== "localized" && (
        <span className="ml-1.5 text-xs text-faint">
          ({t(`workspace.modelo.disclosure.${text.disclosure}`)})
        </span>
      )}
    </>
  );
}
