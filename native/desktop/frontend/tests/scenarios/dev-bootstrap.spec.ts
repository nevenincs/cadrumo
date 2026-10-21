import { expect, test, type WebSocketRoute } from "@playwright/test";
import { label } from "../support/strings";

test("refreshing the scenario entry disposes its previous shell and dialogs", async ({
  page,
}) => {
  let hmr: WebSocketRoute | undefined;
  const duplicateRoots: string[] = [];
  let updated = false;
  page.on("console", (message) => {
    const text = message.text();
    if (text.includes("already been passed to createRoot"))
      duplicateRoots.push(text);
    if (text.includes("hot updated: /src/dev/main.tsx")) updated = true;
  });
  // Drive the real Vite client on this page alone. Its invalidation message
  // stays in this mock socket, so other pages on the dev server never reload.
  await page.routeWebSocket("**", (socket) => {
    hmr = socket;
    socket.send(JSON.stringify({ type: "connected" }));
  });
  await page.goto("/scenarios.html?scenario=odd-names&latency=0&bar=off");
  const dialog = page.locator(".sign-in");
  await expect(dialog.locator(".profile-unnameable")).toHaveText(
    label("desktop.signin.unnameable"),
  );
  await dialog.evaluate((element) => {
    element.setAttribute("data-before-hmr", "");
  });
  if (!hmr) throw new Error("The scenario entry has no Vite connection.");
  hmr.send(
    JSON.stringify({
      type: "update",
      updates: [
        {
          type: "js-update",
          path: "/src/dev/main.tsx",
          acceptedPath: "/src/dev/main.tsx",
          timestamp: Date.now(),
        },
      ],
    }),
  );
  await expect.poll(() => updated).toBe(true);
  await expect(page.locator(".sign-in[data-before-hmr]")).toHaveCount(0);
  await expect(dialog).toHaveCount(1);
  await expect(dialog.locator("#profile-password")).toBeFocused();
  await expect(dialog.locator(".profile-unnameable")).toHaveText(
    label("desktop.signin.unnameable"),
  );
  expect(duplicateRoots).toEqual([]);
});
