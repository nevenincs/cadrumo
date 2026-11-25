// The platform's notation for a key chord, shared by the action registry that
// binds chords and the menu primitive that shows them, so a shown shortcut is
// drawn one way everywhere.

// User-agent client hints where the engine has them (WebView2); the older
// platform string elsewhere (WebKit), which still reports macOS correctly.
const platform =
  typeof navigator === "undefined"
    ? ""
    : ((navigator as Navigator & { userAgentData?: { platform?: string } })
        .userAgentData?.platform ?? navigator.platform);
export const IS_MAC = /mac|iphone|ipad/i.test(platform);

/** The keys of a chord, apart from where it fires. */
export type ChordKeys = {
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
  /** Matched by what the press types (KeyboardEvent.key) with Shift left out,
   * for a symbol whose key and Shift state differ with the layout, such as
   * "/" and "?", or a named key with more than one physical key, such as
   * Enter. `code` is then only where a US keyboard has it, and is not
   * compared. For a page's own keys: the registry's chords are physical. */
  typed?: boolean;
};

type Modifiers = {
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
};

export function chordModifiers(chord: ChordKeys): Modifiers {
  return {
    metaKey: IS_MAC && !!chord.mod,
    ctrlKey: IS_MAC ? !!chord.ctrl : !!chord.mod || !!chord.ctrl,
    shiftKey: !!chord.shift,
    altKey: !!chord.alt,
  };
}

/** Whether a key press is this chord: its key and exactly its modifiers. The
 * one test, for the registry's keymap and for every page that binds its own
 * keys, so a chord a menu shows is the chord that runs. */
export function chordMatches(
  chord: ChordKeys,
  press: Pick<
    KeyboardEvent,
    "code" | "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey"
  >,
): boolean {
  const m = chordModifiers(chord);
  const sameModifiers =
    press.ctrlKey === m.ctrlKey &&
    press.metaKey === m.metaKey &&
    press.altKey === m.altKey;
  if (chord.typed) return sameModifiers && press.key === chord.key;
  return (
    sameModifiers && press.shiftKey === m.shiftKey && press.code === chord.code
  );
}

/** A chord's keys in the platform's order and notation, one part per key, for
 * drawing each as its own keycap. */
export function chordParts(chord: ChordKeys): string[] {
  const m = chordModifiers(chord);
  const parts: string[] = [];
  if (m.ctrlKey) parts.push(IS_MAC ? "⌃" : "Ctrl");
  if (m.altKey) parts.push(IS_MAC ? "⌥" : "Alt");
  if (m.shiftKey) parts.push(IS_MAC ? "⇧" : "Shift");
  if (m.metaKey) parts.push("⌘");
  parts.push(chord.key);
  return parts;
}

/** The chord as one string: symbols run together on macOS, joined by + elsewhere. */
export function chordText(chord: ChordKeys): string {
  return chordParts(chord).join(IS_MAC ? "" : "+");
}

/** The chord in ARIA aria-keyshortcuts notation: modifiers named in full
 * (Meta on macOS, Control elsewhere), a single letter upper-cased, joined by +. */
export function chordAria(chord: ChordKeys): string {
  const m = chordModifiers(chord);
  const parts: string[] = [];
  if (m.ctrlKey) parts.push("Control");
  if (m.altKey) parts.push("Alt");
  if (m.shiftKey) parts.push("Shift");
  if (m.metaKey) parts.push("Meta");
  parts.push(chord.key.length === 1 ? chord.key.toUpperCase() : chord.key);
  return parts.join("+");
}
