import { expect } from "storybook/test";

/** A card that scrolls its content keeps its answers in view: every button of
 * its last row is inside both the card and the window, whatever the part
 * above holds, so the answers do not leave with the scroll. */
export async function answersStayInView(canvasElement: HTMLElement) {
  const card = canvasElement.querySelector("section");
  const above = card?.firstElementChild;
  const answers = card?.lastElementChild;
  if (!card || !above || !answers || above === answers)
    throw new Error("The card has no scrolling part and answer row");
  const frame = card.getBoundingClientRect();
  const buttons = [...answers.querySelectorAll("button")];
  await expect(buttons.length).toBeGreaterThan(0);
  for (const button of buttons) {
    const box = button.getBoundingClientRect();
    await expect(box.top).toBeGreaterThanOrEqual(frame.top);
    await expect(box.bottom).toBeLessThanOrEqual(frame.bottom + 1);
    await expect(box.bottom).toBeLessThanOrEqual(window.innerHeight);
  }
}
