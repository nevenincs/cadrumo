/** Whether Escape on this element belongs to a list open on the field, which
 * closes that first: the dialog around it must leave the key alone. */
export const suggestionsOpenOn = (target: EventTarget) =>
  target instanceof HTMLElement &&
  target.getAttribute("role") === "combobox" &&
  target.getAttribute("aria-expanded") === "true";
