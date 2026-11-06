import { expect, type Page } from "@playwright/test";
import { label } from "./strings";

// The window never starts a terminal on launch: neither a stored layout nor a
// sign-in shows the TUI. A spec that needs it asks for it as a person does,
// from the rail, and the TUI takes the keyboard as it opens.

const railTui = (target: Page, lang?: string) =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label", {}, lang) })
    .getByRole("button", {
      name: label("desktop.rail.tui", {}, lang),
      exact: true,
    });

/** Shows the TUI from the rail, unless it is already shown; on a touch
 * screen the rail is tapped. `lang` names the window's language when it is
 * not the default. */
export async function showTui(
  target: Page,
  { touch = false, lang }: { touch?: boolean; lang?: string } = {},
) {
  const button = railTui(target, lang);
  await expect(button).toBeVisible();
  if ((await button.getAttribute("aria-pressed")) !== "true")
    await (touch ? button.tap() : button.click());
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await expect(target.locator(".pane-tui")).toBeVisible();
}
