// `cadrumo://view/{id}` links: the window's implementation of the register's
// one grammar. It refuses a text for exactly the reason, and in exactly the
// order, `parse_view_link` in `src/cadrumo_client/contracts/navigation.py`
// does; the shared conformance vectors hold both to it.

import {
  elementOf,
  admitsValue,
  type NavigationRegister,
  type Surface,
  type ViewParams,
} from "./register";

/** Why a text is not a view link the window or the TUI may open. */
export type ViewLinkRefusal =
  | "too_long"
  | "malformed"
  | "uppercase"
  | "not_a_view_link"
  | "credentials"
  | "percent_encoding"
  | "fragment"
  | "query"
  | "too_many_segments"
  | "unknown_view"
  | "unknown_param"
  | "param_not_accepted"
  | "param_malformed";

/** A view request: the element, its parameters, and the surface it asks
 * for, if any. */
export type ViewLink = {
  readonly viewId: string;
  readonly params: ViewParams;
  readonly prefer: Surface | null;
};

export type ParsedViewLink =
  | { readonly kind: "link"; readonly link: ViewLink }
  | { readonly kind: "refused"; readonly reason: ViewLinkRefusal };

/** The scheme every Cadrumo link starts with, whatever its namespace. */
const SCHEME = "cadrumo://";
const SEGMENT = "[a-z0-9]+(?:-[a-z0-9]+)*";
const NAME = new RegExp(`^${SEGMENT}$`);
const PRINTABLE_ASCII = /^[!-~]+$/;

const viewIdPattern = (register: NavigationRegister) =>
  new RegExp(
    `^${SEGMENT}(?:/${SEGMENT}){0,${register.link.max_segments - 1}}$`,
  );

/** Whether `text` uses Cadrumo's own scheme: such a text is never an
 * address for the browser, whether or not it is a view link. */
export function isCadrumoLink(text: string): boolean {
  return /^cadrumo:/i.test(text);
}

/** Parameters in name order, as every implementation spells them. */
function sortedEntries(params: ViewParams): [string, string][] {
  return Object.entries(params).sort(([a], [b]) =>
    a < b ? -1 : a > b ? 1 : 0,
  );
}

/** The first rule the parameters break for this element, checked in name
 * order, or null when the element takes them all. */
export function paramRefusal(
  register: NavigationRegister,
  viewId: string,
  params: ViewParams,
):
  | "unknown_view"
  | "unknown_param"
  | "param_not_accepted"
  | "param_malformed"
  | null {
  const element = elementOf(register, viewId);
  if (!element) return "unknown_view";
  const declared = new Set(
    register.elements.flatMap((each) => Object.keys(each.params)),
  );
  for (const [name, value] of sortedEntries(params)) {
    if (!declared.has(name)) return "unknown_param";
    const kind = Object.hasOwn(element.params, name)
      ? element.params[name]
      : undefined;
    if (kind === undefined) return "param_not_accepted";
    if (!admitsValue(register, kind, value)) return "param_malformed";
  }
  return null;
}

/** The first whole-text rule `text` breaks, before its path is read. */
function syntaxRefusal(
  register: NavigationRegister,
  text: string,
): ViewLinkRefusal | null {
  // Counted in characters, as the register's limit is, not UTF-16 units.
  if ([...text].length > register.link.max_length) return "too_long";
  if (!PRINTABLE_ASCII.test(text)) return "malformed";
  if (text !== text.toLowerCase()) return "uppercase";
  if (!text.startsWith(SCHEME)) return "not_a_view_link";
  const authority = text.slice(SCHEME.length).split("/", 1)[0] ?? "";
  if (authority.includes("@")) return "credentials";
  if (!text.startsWith(register.link.prefix)) return "not_a_view_link";
  if (text.includes("%")) return "percent_encoding";
  if (text.includes("#")) return "fragment";
  return null;
}

/** The query's pairs, or null when it breaks the query's shape: every pair
 * a key in the name grammar with a non-empty value, no key twice, and
 * `prefer` naming a surface. */
function queryPairs(
  register: NavigationRegister,
  query: string,
): Map<string, string> | null {
  const pairs = new Map<string, string>();
  for (const pair of query.split("&")) {
    const equals = pair.indexOf("=");
    if (equals < 0) return null;
    const key = pair.slice(0, equals);
    const value = pair.slice(equals + 1);
    if (!value || value.includes("=") || value.includes("?")) return null;
    if (!NAME.test(key) || pairs.has(key)) return null;
    pairs.set(key, value);
  }
  const surface = pairs.get(register.link.prefer_key);
  if (surface !== undefined && !register.surfaces.includes(surface as Surface))
    return null;
  return pairs;
}

/** Reads one `cadrumo://view/{id}` link and its query, or refuses it with
 * the first rule it breaks: whole-text rules, then the query's shape and
 * `prefer`, then the path, then each parameter in name order. */
export function parseViewLink(
  text: string,
  register: NavigationRegister,
): ParsedViewLink {
  const refused = (reason: ViewLinkRefusal): ParsedViewLink => ({
    kind: "refused",
    reason,
  });
  const syntax = syntaxRefusal(register, text);
  if (syntax) return refused(syntax);
  const rest = text.slice(register.link.prefix.length);
  const mark = rest.indexOf("?");
  const path = mark < 0 ? rest : rest.slice(0, mark);
  const pairs =
    mark < 0
      ? new Map<string, string>()
      : queryPairs(register, rest.slice(mark + 1));
  if (!pairs) return refused("query");
  if (path.split("/").length > register.link.max_segments)
    return refused("too_many_segments");
  if (!viewIdPattern(register).test(path)) return refused("malformed");
  const prefer = (pairs.get(register.link.prefer_key) ??
    null) as Surface | null;
  pairs.delete(register.link.prefer_key);
  const params: Record<string, string> = {};
  for (const [name, value] of [...pairs].sort(([a], [b]) => (a < b ? -1 : 1)))
    params[name] = value;
  const refusal = paramRefusal(register, path, params);
  if (refusal) return refused(refusal);
  return { kind: "link", link: { viewId: path, params, prefer } };
}

/** Spells the link that opens one registered element: its parameters in
 * name order, then `prefer`. Throws for an element the register does not
 * declare or a parameter it does not take with a value of its kind. */
export function formatViewLink(
  register: NavigationRegister,
  viewId: string,
  params: ViewParams = {},
  prefer: Surface | null = null,
): string {
  const refusal = paramRefusal(register, viewId, params);
  if (refusal) throw new Error(`cannot link to view ${viewId}: ${refusal}`);
  const query = sortedEntries(params).map(
    ([name, value]) => `${name}=${value}`,
  );
  if (prefer !== null) query.push(`${register.link.prefer_key}=${prefer}`);
  const link = `${register.link.prefix}${viewId}`;
  return query.length > 0 ? `${link}?${query.join("&")}` : link;
}
