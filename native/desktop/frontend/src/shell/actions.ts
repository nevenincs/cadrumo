// The one action registry. The keymap, the palette, rail tooltips and menu
// shortcuts all derive from it, so a chord or a label is declared exactly once.

import type { BridgeChord } from "../ipc/contract";

export const IS_MAC =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.platform);

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
  icon: string;
  keywords?: string;
  chords?: readonly Chord[];
  /** Kept out of the palette (shortcut-only actions such as terminal copy). */
  hidden?: boolean;
  enabled?: () => boolean;
  run: () => void;
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

/** Palette relevance: every query word must start or occur in the text. */
export function scoreAction(action: Action, query: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const haystack =
    `${action.label} ${action.keywords ?? ""} ${action.group}`.toLowerCase();
  const words = haystack.split(/[^\p{L}\p{N}]+/u);
  let score = 0;
  for (const part of q.split(/\s+/)) {
    if (words.some((word) => word.startsWith(part))) score += 2;
    else if (haystack.includes(part)) score += 1;
    else return 0;
  }
  return score;
}
