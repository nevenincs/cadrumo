import { listOf, type ListKind } from "../shared/lists";
import type { Translate } from "./strings";

// Text put together from several pieces. Where a piece joins another, the
// locale decides the separator, the punctuation and the order, so no caller
// writes ": ", " · " or ", " between words a person reads.

/** A piece of a line; one that is absent is left out. */
export type Piece = string | number | null | undefined | false;

const present = (pieces: readonly Piece[]): string[] =>
  pieces.flatMap((piece) =>
    piece === null || piece === undefined || piece === false || piece === ""
      ? []
      : [String(piece)],
  );

/** A name and what it is: "Label: value". */
export function labelled(
  t: Translate,
  label: string,
  value: string | number,
): string {
  return t("desktop.compose.labelled", { label, value });
}

/** Text with a remark beside it: "Text (note)". */
export function noted(t: Translate, text: string, note: string): string {
  return t("desktop.compose.noted", { text, note });
}

/** Facts about one thing, shown side by side on a line. */
export function facts(t: Translate, pieces: readonly Piece[]): string {
  return present(pieces).reduce(
    (line, fact) =>
      line === ""
        ? fact
        : t("desktop.compose.facts", { head: line, tail: fact }),
    "",
  );
}

/** What stands between two facts that are separate elements, as `facts`
 * would put it between two strings. */
export function factsGap(t: Translate): string {
  return t("desktop.compose.facts", { head: "", tail: "" });
}

/** What stands between a label and its value that are separate elements,
 * as `labelled` would put it between two strings. */
export function labelGap(t: Translate): string {
  return t("desktop.compose.labelled", { label: "", value: "" });
}

/** What an assistive technology reads between visible text and a detail
 * that follows it, as `described` would put it after a name. */
export function describedGap(t: Translate): string {
  return t("desktop.compose.described", { name: "", detail: "" });
}

/** What an assistive technology reads after a name: the name, then each
 * detail that applies. */
export function described(
  t: Translate,
  name: string,
  ...details: readonly Piece[]
): string {
  return present(details).reduce(
    (spoken, detail) =>
      t("desktop.compose.described", { name: spoken, detail }),
    name,
  );
}

/** Items as the active locale writes a list of them. */
export function listed(
  t: Translate,
  items: readonly Piece[],
  kind: ListKind = "and",
): string {
  return listOf(t.locale, present(items), kind);
}
