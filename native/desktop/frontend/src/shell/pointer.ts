/**
 * Whether a `contextmenu` event came from a pointer. The menu key sends the
 * event too: in some engines with no pointer type, in Chromium as a mouse
 * event that has no button. A menu asked for by keyboard belongs at what has
 * focus, not wherever the cursor was left.
 */
export function fromPointer(event: MouseEvent): boolean {
  return event.button !== -1 && (event as PointerEvent).pointerType !== "";
}
