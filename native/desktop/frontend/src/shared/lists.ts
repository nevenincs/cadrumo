// Lists as a locale writes them: its separators, its last-item word and its
// order. A caller never joins items with a comma of its own. Primitives that
// receive no translator pass the page language, `document.documentElement.lang`.

/** How a list reads: every item, any one of them, or a run of attributes. */
export type ListKind = "and" | "or" | "plain";

const OPTIONS: Record<ListKind, Intl.ListFormatOptions> = {
  and: { type: "conjunction", style: "long" },
  or: { type: "disjunction", style: "long" },
  plain: { type: "unit", style: "long" },
};

const formats = new Map<string, Intl.ListFormat>();

export function listOf(
  locale: string | undefined,
  items: readonly string[],
  kind: ListKind = "and",
): string {
  const key = `${locale ?? ""}|${kind}`;
  let format = formats.get(key);
  if (!format) {
    format = new Intl.ListFormat(locale || undefined, OPTIONS[kind]);
    formats.set(key, format);
  }
  return format.format(items);
}
