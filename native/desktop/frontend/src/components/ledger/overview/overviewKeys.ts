// When the overview's chord is the person's to take: not while they type in
// a field, where Alt+Enter belongs to the field.

/** Whether a key press lands in a field the person is typing in. */
export const typing = (target: EventTarget | null): boolean =>
  (target as HTMLElement | null)?.closest?.(
    "input, textarea, select, [contenteditable=true]",
  ) != null;
