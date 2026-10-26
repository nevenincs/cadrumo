// The one action registry. The keymap, the palette, rail tooltips and menu
// shortcuts all derive from it, so a chord or a label is declared exactly once.

import type { IconName } from "@/components/ui/icon";
import type { BridgeChord } from "../ipc/contract";
import {
  elementOf,
  type NavigationRegister,
  type Surface,
} from "./navigation/register";
import type { Translate } from "./strings";

// User-agent client hints where the engine has them (WebView2); the older
// platform string elsewhere (WebKit), which still reports macOS correctly.
const platform =
  typeof navigator === "undefined"
    ? ""
    : ((navigator as Navigator & { userAgentData?: { platform?: string } })
        .userAgentData?.platform ?? navigator.platform);
export const IS_MAC = /mac|iphone|ipad/i.test(platform);

/** Where a chord fires. "global": everywhere, focused terminals included.
 * "app": everywhere except a focused terminal, which keeps the key. "docs": the
 * documentation frame and shell chrome. "terminal": only a focused terminal. */
export type ChordScope = "global" | "app" | "docs" | "terminal";

export type Chord = {
  /** KeyboardEvent.code, the physical key, so every layout reaches it. */
  code: string;
  /** Display text for the key itself. */
  key: string;
  /** Platform primary modifier: Command on macOS, Control elsewhere. */
  mod?: boolean;
  /** The literal Control key on every platform. */
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  scope: ChordScope;
};

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
  /** Where it opens, when that is not the window. */
  badge?: string;
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

type Modifiers = {
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
};

export function chordModifiers(chord: Chord): Modifiers {
  return {
    metaKey: IS_MAC && !!chord.mod,
    ctrlKey: IS_MAC ? !!chord.ctrl : !!chord.mod || !!chord.ctrl,
    shiftKey: !!chord.shift,
    altKey: !!chord.alt,
  };
}

export function chordLabel(chord: Chord | undefined): string {
  if (!chord) return "";
  const m = chordModifiers(chord);
  if (IS_MAC) {
    return (
      (m.ctrlKey ? "⌃" : "") +
      (m.altKey ? "⌥" : "") +
      (m.shiftKey ? "⇧" : "") +
      (m.metaKey ? "⌘" : "") +
      chord.key
    );
  }
  const parts: string[] = [];
  if (m.ctrlKey) parts.push("Ctrl");
  if (m.altKey) parts.push("Alt");
  if (m.shiftKey) parts.push("Shift");
  parts.push(chord.key);
  return parts.join("+");
}

export function primaryChord(action: Action | undefined): string {
  return chordLabel(action?.chords?.[0]);
}

const ALLOWED: Record<FocusArea, readonly ChordScope[]> = {
  terminal: ["global", "terminal"],
  docs: ["global", "app", "docs"],
  chrome: ["global", "app", "docs"],
};

function matches(chord: Chord, event: KeyboardEvent): boolean {
  const m = chordModifiers(chord);
  return (
    event.code === chord.code &&
    event.ctrlKey === m.ctrlKey &&
    event.metaKey === m.metaKey &&
    event.shiftKey === m.shiftKey &&
    event.altKey === m.altKey
  );
}

export function findAction(
  actions: readonly Action[],
  event: KeyboardEvent,
  focus: FocusArea,
): Action | null {
  if (event.isComposing) return null;
  for (const action of actions) {
    for (const chord of action.chords ?? []) {
      if (!ALLOWED[focus].includes(chord.scope)) continue;
      if (!matches(chord, event)) continue;
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
 * The palette's view actions, one per register element some surface can
 * open now: the window's first, in register order, then those only the TUI
 * implements, badged with where they open. `opensIn` says which surface
 * opens an element itself, not an ancestor; `open` opens it through the
 * navigator. A pane or the panel names whether it is shown, and its entry
 * then hides or shows it. A section without a chord of its own is quiet:
 * it is listed only for a query that finds it.
 */
export function viewActions(
  register: NavigationRegister,
  t: Translate,
  specs: Readonly<Record<string, ViewActionSpec>>,
  opensIn: (id: string) => Surface | null,
  open: (id: string) => void,
): Action[] {
  const window: Action[] = [];
  const terminal: Action[] = [];
  for (const element of register.elements) {
    const spec = Object.hasOwn(specs, element.id)
      ? specs[element.id]
      : undefined;
    const where = opensIn(element.id);
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
      ...(where === "tui"
        ? { badge: t("navigation.view.terminal.label") }
        : {}),
      group: spec?.group ?? "views",
      icon: spec?.icon ?? (where === "tui" ? "tui" : "page"),
      keywords: element.keywords,
      ...(spec?.chords ? { chords: spec.chords } : {}),
      quiet: element.parent !== null && !spec?.chords?.length,
      enabled: () => where !== null && (spec?.enabled?.() ?? true),
      run: spec?.run ?? show,
      choose: spec?.shown === true && spec.run ? spec.run : show,
    };
    (element.surfaces.includes("gui") ? window : terminal).push(action);
  }
  return [...window, ...terminal];
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
    action.badge,
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
