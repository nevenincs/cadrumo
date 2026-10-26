import type { Translate } from "../../../shell/strings";
import type { StagedEdit } from "./session";

/** A staged edit as the box, the details and the review say it: a typed
 * value as the filer typed it, a confirmed value as the form showed it, and
 * a value taken out in the words for where the box goes back to. */
export function stagedText(t: Translate, edit: StagedEdit): string {
  switch (edit.intent.kind) {
    case "set_typed_value":
    case "set_override_value":
      return edit.entry ?? edit.field.value_text ?? "";
    case "clear_declared_value":
      return t("workspace.modelo.staged.clear");
    case "restore_source_value":
    case "remove_override":
      return t("workspace.modelo.staged.restore");
  }
}
