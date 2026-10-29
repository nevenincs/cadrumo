// The one action registry. The keymap, the palette, rail tooltips and menu
// shortcuts all derive from it, so a chord or a label is declared exactly once.

import type { IconName } from "@/components/ui/icon";
import {
  chordMatches,
  chordModifiers,
  chordText,
  type ChordKeys,
} from "@/shared/chords";
import type { BridgeChord } from "../ipc/contract";
import { elementOf, type NavigationRegister } from "./navigation/register";
import type { Translate } from "./strings";

/** Where a chord fires. "global": everywhere, focused terminals included.
 * "app": everywhere except a focused terminal, which keeps the key. "docs": the
 * documentation frame and shell chrome. "terminal": only a focused terminal. */
export type ChordScope = "global" | "app" | "docs" | "terminal";

/** A window chord, by its physical key: the documentation bridge matches `code`,
 * so a chord matched by what it types is a page's own, not the registry's. */
export type Chord = Omit<ChordKeys, "typed"> & { scope: ChordScope };

export type Action = {
  id: string;
  label: string;
  group: string;
  icon: IconName;
  keywords?: string;
  /** The register element it shows, which the palette also finds it by. */
  view?: string;
  /** Said after the label where the label alone is ambiguous: a section's
   * page. */
  context?: string;
  /** The view's own name, where the label wraps it in "Show" or "Hide". */
  name?: string;
  chords?: readonly Chord[];
  /** Kept out of the palette (shortcut-only actions such as terminal copy). */
  hidden?: boolean;
  /** Listed in the palette only for a query that matches it: one of many
   * alike, such as a way to each profile section. */
  quiet?: boolean;
  enabled?: () => boolean;
  run: () => void;
  /** What choosing it by name does, where that differs from its chord: a
   * chord toggles a view, its name in the palette shows it. */
  choose?: () => void;
};

export type FocusArea = "terminal" | "docs" | "chrome";

export function chordLabel(chord: Chord | undefined): string {
  return chord ? chordText(chord) : "";
}

export function primaryChord(action: Action | undefined): string {
  return chordLabel(action?.chords?.[0]);
}

const ALLOWED: Record<FocusArea, readonly ChordScope[]> = {
  terminal: ["global", "terminal"],
  docs: ["global", "app", "docs"],
  chrome: ["global", "app", "docs"],
};

export function findAction(
  actions: readonly Action[],
  event: KeyboardEvent,
  focus: FocusArea,
): Action | null {
  if (event.isComposing) return null;
  for (const action of actions) {
    for (const chord of action.chords ?? []) {
      if (!ALLOWED[focus].includes(chord.scope)) continue;
      if (!chordMatches(chord, event)) continue;
      if (action.enabled && !action.enabled()) continue;
      return action;
    }
  }
  return null;
}

/** The bridge `keymap` payload: every chord the docs frame must hand back. */
export function bridgeChords(actions: readonly Action[]): BridgeChord[] {
  const out: BridgeChord[] = [];
  for (const action of actions) {
    for (const chord of action.chords ?? []) {
      if (!ALLOWED.docs.includes(chord.scope)) continue;
      out.push({ id: action.id, code: chord.code, ...chordModifiers(chord) });
    }
  }
  return out;
}

/** How the window offers one register element in the palette. The label,
 * keywords and the way it opens come from the register; this says only
 * what the window adds. */
export type ViewActionSpec = {
  /** The action's id where it is older than the register; `view.{id}`
   * otherwise. */
  readonly id?: string;
  readonly icon: IconName;
  readonly group: string;
  readonly chords?: readonly Chord[];
  /** What its chord and its rail button do, where that is not opening it:
   * a pane's toggles. Chosen by name, it opens. */
  readonly run?: () => void;
  readonly enabled?: () => boolean;
  /** For a pane or the panel, whether it is on screen now: its entry then
   * offers to hide it, with the same toggle its chord runs, and otherwise
   * to show it. A page has none: its entry only opens it. */
  readonly shown?: boolean;
};

/**
 * The palette's view actions, one per register element the window draws, in
 * register order. `opensHere` says whether the window opens an element
 * itself, not an ancestor; `open` opens it through the navigator. A pane or the panel names whether it is shown, and its entry
 * then hides or shows it. A section without a chord of its own is quiet:
 * it is listed only for a query that finds it.
 */
export function viewActions(
  register: NavigationRegister,
  t: Translate,
  specs: Readonly<Record<string, ViewActionSpec>>,
  opensHere: (id: string) => boolean,
  open: (id: string) => void,
): Action[] {
  const actions: Action[] = [];
  for (const element of register.elements) {
    if (!element.surfaces.includes("gui")) continue;
    const spec = Object.hasOwn(specs, element.id)
      ? specs[element.id]
      : undefined;
    const opens = opensHere(element.id);
    const parent =
      element.parent === null ? undefined : elementOf(register, element.parent);
    const show = () => open(element.id);
    const name = t(element.label);
    const action: Action = {
      id: spec?.id ?? `view.${element.id}`,
      view: element.id,
      label:
        spec?.shown === undefined
          ? name
          : t(
              spec.shown
                ? "desktop.palette.hide_view"
                : "desktop.palette.show_view",
              { view: name },
            ),
      ...(spec?.shown === undefined ? {} : { name }),
      ...(parent ? { context: t(parent.label) } : {}),
      group: spec?.group ?? "views",
      icon: spec?.icon ?? "page",
      keywords: element.keywords,
      ...(spec?.chords ? { chords: spec.chords } : {}),
      quiet: element.parent !== null && !spec?.chords?.length,
      enabled: () => opens && (spec?.enabled?.() ?? true),
      run: spec?.run ?? show,
      choose: spec?.shown === true && spec.run ? spec.run : show,
    };
    actions.push(action);
  }
  return actions;
}

/** Palette relevance: every query word must start or occur in the text: the
 * label, keywords, group, the section's page, where it opens, and the
 * register id of the element it shows. */
export function scoreAction(action: Action, query: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const haystack = [
    action.label,
    action.keywords,
    action.group,
    action.context,
    action.view,
  ]
    .filter((part) => part !== undefined)
    .join(" ")
    .toLowerCase();
  const words = haystack.split(/[^\p{L}\p{N}]+/u);
  let score = 0;
  for (const part of q.split(/\s+/)) {
    if (words.some((word) => word.startsWith(part))) score += 2;
    else if (haystack.includes(part)) score += 1;
    else return 0;
  }
  // Of equal matches, the one named by what was typed comes first.
  return action.label.toLowerCase().startsWith(q) ||
    (action.name?.toLowerCase().startsWith(q) ?? false)
    ? score + 1
    : score;
}
