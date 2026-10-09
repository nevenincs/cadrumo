import type { Page } from "@playwright/test";

/** Text assertions use xterm's DOM fallback; rendering tests cover WebGL. */
export async function useDomTerminal(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      ...args: Parameters<typeof original>
    ) {
      return args[0] === "webgl2" ? null : original.apply(this, args);
    } as typeof original;
  });
}
