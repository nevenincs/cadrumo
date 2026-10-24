// Where a view request opens: the window's implementation of
// `resolve_view` in `src/cadrumo_client/contracts/navigation.py`, held to
// it by the shared conformance vectors.

import type { ViewLink } from "./links";
import { paramRefusal } from "./links";
import {
  idsFor,
  lineage,
  type NavigationRegister,
  type Surface,
  type ViewParams,
} from "./register";

/** What one surface can open now: element ids, and per element the
 * parameter names it honours. */
export type SurfaceImplementation = {
  readonly views: ReadonlySet<string>;
  readonly params: ReadonlyMap<string, ReadonlySet<string>>;
};

export type Implemented = Partial<Record<Surface, SurfaceImplementation>>;

/** Which element and surface opened compared with the request. */
export type ViewFallback = "none" | "other_surface" | "ancestor";

export type ViewOpened = {
  readonly kind: "opened";
  readonly requested: ViewLink;
  readonly opened: string;
  readonly surface: Surface;
  readonly fallback: ViewFallback;
  /** The parameters passed on to the opened element. */
  readonly params: ViewParams;
  /** Whether the person must be told it opened other than asked. */
  readonly noticeDue: boolean;
};

export type ViewRefusalReason =
  | "unknown_view"
  | "unknown_param"
  | "param_not_accepted"
  | "param_malformed"
  | "not_implemented";

export type ViewRefused = {
  readonly kind: "refused";
  readonly requested: ViewLink;
  readonly reason: ViewRefusalReason;
};

const sameParams = (a: ViewParams, b: ViewParams) => {
  const keys = Object.keys(a);
  return (
    keys.length === Object.keys(b).length &&
    keys.every((key) => Object.hasOwn(b, key) && a[key] === b[key])
  );
};

/** What each surface implements according to the register alone, each
 * honouring every parameter its elements declare. */
export function declaredImplementation(
  register: NavigationRegister,
): Implemented {
  const of = (surface: Surface): SurfaceImplementation => ({
    views: idsFor(register, surface),
    params: new Map(
      register.elements
        .filter((element) => element.surfaces.includes(surface))
        .map((element) => [element.id, new Set(Object.keys(element.params))]),
    ),
  });
  return { gui: of("gui"), tui: of("tui") };
}

/**
 * Chooses the surface and element a view request opens. The preferred
 * surface is the window unless the request asks for the TUI. The first that
 * applies opens: the preferred surface honouring the element and every
 * parameter; the other surface likewise; the element without its parameters
 * on the preferred surface and then the other; the nearest ancestor without
 * parameters on the preferred surface and then the other. Otherwise the
 * request is refused. A surface missing from `implemented` opens nothing.
 */
export function resolveView(
  request: ViewLink,
  implemented: Implemented,
  register: NavigationRegister,
): ViewOpened | ViewRefused {
  const refusal = paramRefusal(register, request.viewId, request.params);
  if (refusal) return { kind: "refused", requested: request, reason: refusal };
  const first: Surface = request.prefer ?? "gui";
  const order: Surface[] = [first, first === "gui" ? "tui" : "gui"];
  const names = Object.keys(request.params);
  const honours = (surface: Surface, id: string, wanted: string[]) => {
    const implementation = implemented[surface];
    if (!implementation?.views.has(id)) return false;
    const honoured = implementation.params.get(id);
    return wanted.every((name) => honoured?.has(name) ?? false);
  };
  const opened = (
    id: string,
    surface: Surface,
    fallback: ViewFallback,
    params: ViewParams,
  ): ViewOpened => ({
    kind: "opened",
    requested: request,
    opened: id,
    surface,
    fallback,
    params,
    noticeDue: fallback !== "none" || !sameParams(params, request.params),
  });
  for (const surface of order)
    if (honours(surface, request.viewId, names))
      return opened(
        request.viewId,
        surface,
        surface === first ? "none" : "other_surface",
        request.params,
      );
  if (names.length > 0)
    for (const surface of order)
      if (honours(surface, request.viewId, []))
        return opened(
          request.viewId,
          surface,
          surface === first ? "none" : "other_surface",
          {},
        );
  for (const ancestor of lineage(register, request.viewId).slice(1))
    for (const surface of order)
      if (honours(surface, ancestor.id, []))
        return opened(ancestor.id, surface, "ancestor", {});
  return { kind: "refused", requested: request, reason: "not_implemented" };
}
