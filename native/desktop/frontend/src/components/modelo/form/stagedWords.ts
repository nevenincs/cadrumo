import type { Translate } from "../../../shell/strings";
import type { StagedEdit } from "./session";

/** A staged edit as the box, the details and the review say it: a typed
 * value as the application read it, in the format of the value it replaces,
 * or as typed where the application said nothing; a confirmed value as the
 * form showed it; a yes or no as those words; a value taken out in the
 * words for where the box goes back to; a statement in the words the form
 * served for it, and its withdrawal as one. */
export function stagedText(t: Translate, edit: StagedEdit): string {
  switch (edit.intent.kind) {
    case "set_typed_value":
    case "set_override_value":
      if (typeof edit.intent.value === "boolean")
        return t(
          edit.intent.value
            ? "desktop.ledger.form.yes"
            : "desktop.ledger.form.no",
        );
      return edit.read ?? edit.entry ?? edit.field.value_text ?? "";
    case "clear_declared_value":
      return t("workspace.modelo.staged.clear");
    case "restore_source_value":
      return t(
        edit.intent.change === "remove"
          ? "workspace.modelo.staged.remove"
          : "workspace.modelo.staged.restore",
      );
    case "remove_override":
      return t(
        edit.intent.withdraws === undefined
          ? "workspace.modelo.staged.restore"
          : "desktop.modelo.statements.withdrawn",
      );
    case "attest_no_amount":
      return edit.intent.words;
  }
}
