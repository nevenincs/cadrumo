import { userEvent, waitFor } from "storybook/test";

// The few steps a story takes to reach what it shows: opening a menu, a
// dialog's second step. Each waits for the element a person would wait for.

type Target = { text?: string; nth?: number };

export async function find(
  root: HTMLElement,
  selector: string,
  { text, nth = 0 }: Target = {},
): Promise<HTMLElement> {
  return waitFor(
    () => {
      const hit = [...root.querySelectorAll<HTMLElement>(selector)].filter(
        (el) => text === undefined || (el.textContent ?? "").includes(text),
      )[nth];
      if (!hit)
        throw new Error(
          `Nothing matches ${selector}${text === undefined ? "" : ` with "${text}"`}.`,
        );
      return hit;
    },
    { timeout: 8000 },
  );
}

export async function press(
  root: HTMLElement,
  selector: string,
  target: Target = {},
) {
  await userEvent.click(await find(root, selector, target));
}

/** Saves what is staged, through the conflict check that may come first, to
 * the dialog's result. */
export async function saveAll(root: HTMLElement) {
  await press(root, ".dialog-foot button", { text: "Save" });
  const settled = await waitFor(
    () => {
      const foot = [
        ...root.querySelectorAll<HTMLElement>(".dialog-foot button"),
      ];
      const proceed = foot.find((b) =>
        b.textContent?.includes("Continue saving"),
      );
      const done = foot.find((b) => b.textContent?.includes("Done"));
      if (!proceed && !done) throw new Error("The save has not settled.");
      return { proceed };
    },
    { timeout: 30000 },
  );
  if (settled.proceed) {
    await press(root, ".dialog label", {
      text: "I have looked at what changed",
    });
    await userEvent.click(settled.proceed);
  }
  await find(root, ".dialog-foot button", { text: "Done" });
}
