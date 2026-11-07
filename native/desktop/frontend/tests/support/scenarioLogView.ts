import { openPanelTab } from "./panel";
import { expect, type Page } from "@playwright/test";
import { label } from "./strings";

export const openLogs = (target: Page) => openPanelTab(target, "logs");

/** How many error records the log holds, as its bar counts them: a number
 * that grows as records arrive, whatever span is drawn. One generated record
 * in seven is an error. It stops growing once the ring is full. */
export const errorsHeld = (target: Page) => async () =>
  Number(
    /\d+/.exec(
      (await target
        .locator(".logview [data-slot=badge][data-variant=danger]")
        .first()
        .textContent()) ?? "",
    )?.[0] ?? 0,
  );

// The log's Follow toggle and its list, with the pointer over the list.
export async function overLog(target: Page, drawnCount = 400) {
  const list = target.locator(".logview-list");
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await expect(list.locator(".record")).toHaveCount(drawnCount);
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  const box = await list.boundingBox();
  if (!box) throw new Error("The log's list is not on screen.");
  await target.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  return { list, follow };
}
