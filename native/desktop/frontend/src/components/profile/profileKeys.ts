import type { ChordKeys } from "@/shared/chords";

// The profile page's own keys, declared once: the page runs them, its menus
// and its key sheet show them. They are the page's, not the window's, so
// the registry knows none of them.
export const PROFILE_KEYS = {
  /** Edits the focused detail; `editToo` do the same, and are not shown. */
  edit: { code: "Enter", key: "Enter", typed: true },
  editToo: [
    { code: "F2", key: "F2", typed: true },
    { code: "KeyE", key: "e", typed: true },
  ],
  copy: { code: "KeyC", key: "C", mod: true },
  // Typed, not positional: "/" and "?" sit on other keys, with or without
  // Shift, on the Spanish, Catalan and Hungarian layouts.
  search: { code: "Slash", key: "/", typed: true },
  help: { code: "Slash", key: "?", typed: true },
} as const satisfies Record<string, ChordKeys | readonly ChordKeys[]>;
