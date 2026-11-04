import { formatDay } from "../../../shared/dateFormats";
import { servedRefusalWords } from "../../../shell/ledger";
import { formatDecimal } from "../../../shared/numbers";
import type {
  InventoryMovement,
  InventoryRefusal,
} from "../../../shell/ledgerSetup";
import type { Translate } from "../../../shell/strings";
import type { SetupCall } from "../setup/setupModel";
import { wordOf, servedWord, type Offers } from "./stockVocabulary";

/** The refusal a call carries, wherever the call put it. */
export function refusalOf(
  call: SetupCall<unknown> | null,
): InventoryRefusal | null {
  if (call?.kind === "refused")
    return (
      (call.detail as { refusal?: InventoryRefusal | null } | null)?.refusal ??
      null
    );
  if (call?.kind === "done")
    return (
      (call.result as { refusal?: InventoryRefusal | null } | null)?.refusal ??
      null
    );
  return null;
}

/** Words for a refused call: the sentence the inventory operation served for
 * its refusal, else said plainly and never as a key or a code. */
export function refusalWords(t: Translate, call: SetupCall<unknown> | null) {
  return (): string | null => {
    const found = refusalOf(call);
    if (call?.kind !== "refused" && found === null) return null;
    return (
      servedRefusalWords(found) ??
      (call?.kind === "refused" ? servedRefusalWords(call.detail) : null) ??
      t("desktop.ledger.stock.refused")
    );
  };
}

/** The choices the backend serves for one family, in the words it has for
 * each. */
export function choicesOf(
  t: Translate,
  offers: Offers,
  family: string,
  allowed?: readonly string[],
) {
  return (offers[family] ?? [])
    .filter((served) => allowed === undefined || allowed.includes(served.value))
    .map((served) => ({
      value: served.value,
      label: servedWord(t, served),
    }));
}

/** The movement a form acts on, in a line. */
export function movementLine(
  t: Translate,
  locale: string,
  movement: InventoryMovement,
) {
  return t("desktop.ledger.stock.fact.movement", {
    date: formatDay(locale, movement.movement_date),
    kind: wordOf(t, "movement_kind", movement.kind),
    quantity: formatDecimal(locale, movement.quantity.decimal),
  });
}
