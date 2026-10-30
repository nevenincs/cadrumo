// Exercise actual React controls against the packaged docs bridge and Pagefind.
import assert from "node:assert/strict";
import { waitFor } from "./session.mjs";
import { PASS } from "./verdicts.mjs";

export async function docsUiChecks({
  session,
  check,
  visit,
  shown,
  localized,
  docsOrigin,
}) {
  const page = session.page;
  const chooseLanguage = async (code) => {
    const settings = page.locator(".settings");
    if (!(await settings.isVisible()))
      await page.locator('.rail [data-rail="settings"]').click();
    await settings.locator("select").selectOption(code);
    await waitFor(
      async () =>
        (await session.shell(() => document.documentElement.lang)) === code &&
        (await session.docs(
          () => document.documentElement.lang.split("-")[0],
        )) === code,
      { timeout: 30000, what: "the shared shell and documentation language" },
    );
    await settings.press("Escape");
    await settings.waitFor({ state: "hidden" });
  };
  // Rail order and Settings choice order are locale-independent UI contracts.
  const rail = page.locator(".rail-group").first().locator("button");
  await check(
    "palette-docs-navigation",
    "palette searches real Pagefind and opens its documentation result",
    async () => {
      await visit(shown);
      await rail.nth(0).click();
      const palette = page.locator(".palette");
      let failed = false;
      try {
        // Observe the real bridge reply; never replace the page's search provider.
        await session.shell((origin) => {
          window.__s14SearchResults = null;
          const receive = (event) => {
            const data = event.data;
            if (
              event.origin !== origin ||
              event.source !==
                document.querySelector(".docs-frame")?.contentWindow ||
              data?.channel !== "cadrumo-desktop" ||
              data?.type !== "search-results"
            )
              return;
            window.__s14SearchResults = data.results;
            window.removeEventListener("message", receive);
            clearTimeout(timer);
          };
          const timer = setTimeout(
            () => window.removeEventListener("message", receive),
            30000,
          );
          window.addEventListener("message", receive);
        }, docsOrigin);
        await palette.locator('input[role="combobox"]').fill("modelo");
        const results = await waitFor(
          () => session.shell(() => window.__s14SearchResults),
          {
            timeout: 30000,
            what: "the real documentation search bridge reply",
          },
        );
        assert(
          results.length > 0,
          "the real documentation search returned no results",
        );
        const rows = palette
          .locator(".palette-results > section")
          .first()
          .getByRole("option");
        await rows.first().waitFor({ state: "visible", timeout: 30000 });
        const count = await rows.count();
        const title = await rows.first().locator(".palette-title").innerText();
        assert(count > 0);
        const order = ["concept", "casilla", "cli", "page"];
        const rank = (kind) =>
          order.includes(kind) ? order.indexOf(kind) : order.length;
        const selected = [...results].sort(
          (a, b) => rank(a.kind) - rank(b.kind),
        )[0];
        assert(selected && title.startsWith(selected.title));
        const expectedUrl = new URL(selected.url, shown).href;
        assert(expectedUrl.startsWith(`${docsOrigin}/`));
        // Documentation rows have no action shortcut; the first section is docs.
        assert.equal(await rows.first().locator(".palette-chord").count(), 0);
        await rows.first().click();
        await palette.waitFor({ state: "hidden" });
        const destination = await waitFor(
          () => {
            const url = session.docsFrame()?.url();
            return url === expectedUrl ? url : null;
          },
          {
            timeout: 30000,
            what: "the selected documentation result navigation",
          },
        );
        await session.waitDocs();
        assert(await session.docs(() => document.body.innerText.length > 0));
        return {
          verdict: PASS,
          detail: `${count} live documentation results; clicked ${title}; navigated to ${destination}`,
        };
      } catch (error) {
        failed = true;
        try {
          await session.shell(() => {
            window.__s14DocsFailure = {
              text: document.querySelector(".palette")?.textContent,
              sections: [
                ...document.querySelectorAll(".palette-results > section"),
              ].map((node) => ({
                text: node.textContent,
                options: node.querySelectorAll('[role="option"]').length,
              })),
              results: window.__s14SearchResults,
            };
          });
        } catch {
          /* Keep the original search failure. */
        }
        throw error;
      } finally {
        try {
          if (await palette.isVisible()) {
            await page.keyboard.press("Escape");
            await palette.waitFor({ state: "hidden", timeout: 5000 });
          }
        } catch (error) {
          if (!failed) throw error;
        }
      }
    },
  );

  await check(
    "localized-docs-home",
    "Docs Home preserves the current documentation language",
    async () => {
      assert(
        localized,
        "the acceptance package must include a second documentation language",
      );
      const originalLanguage = await session.shell(
        () => document.documentElement.lang,
      );
      try {
        await chooseLanguage(localized.code);
        const descendant = new URL("search.html?q=modelo", localized.entry)
          .href;
        await visit(descendant);
        await waitFor(
          () =>
            session.docs(() =>
              window.__s10.messages.some(
                (message) => message.fromParent && message.type === "keymap",
              ),
            ),
          { timeout: 30000, what: "the documentation keymap handshake" },
        );
        const home = await session.docs(() => {
          const brand = document.querySelector(
            "a.cadrumo-header-brand[href], .header-center > a[href]",
          );
          if (!brand) throw new Error("the documentation home link is missing");
          return new URL(brand.getAttribute("href"), document.baseURI).href;
        });
        await session
          .docsFrame()
          .locator("body")
          .click({ position: { x: 4, y: 4 } });
        // Docs Home is the documentation's own chord; the rail toggles the pane.
        await page.keyboard.press("Alt+Home");
        await waitFor(() => session.docsFrame()?.url() === home, {
          timeout: 30000,
          what: "the localized documentation home",
        });
        await session.waitDocs();
        assert.equal(
          await session.docs(() => document.documentElement.lang.split("-")[0]),
          localized.code.split("-")[0],
        );
        return {
          verdict: PASS,
          detail: `Docs Home returned from ${descendant} to ${home}`,
        };
      } finally {
        await chooseLanguage(originalLanguage);
      }
    },
  );

  await check(
    "settings-docs-appearance",
    "Settings dark and Follow documentation synchronize shell and docs",
    async () => {
      const settingsButton = page
        .locator(".rail-group")
        .last()
        .locator("button")
        .first();
      await settingsButton.click();
      const settings = page.locator(".settings");
      const appearance = settings.getByRole("radiogroup").first();
      await appearance.getByRole("radio").nth(2).click();
      await waitFor(
        async () =>
          (await session.shell(
            () => document.documentElement.dataset.scheme === "dark",
          )) &&
          (await session.docs(() => document.body.dataset.theme === "dark")),
        { what: "forced dark appearance in both origins" },
      );
      assert.equal(
        await appearance.getByRole("radio").nth(2).getAttribute("aria-checked"),
        "true",
      );
      await appearance.getByRole("radio").nth(0).click();
      assert.equal(
        await appearance.getByRole("radio").nth(0).getAttribute("aria-checked"),
        "true",
      );
      await settings.press("Escape");
      const toggle = session
        .docsFrame()
        .locator("button.theme-toggle:visible")
        .first();
      // Furo cycles auto/light/dark. Reach explicit light through its own UI.
      for (let attempt = 0; attempt < 3; attempt++) {
        await toggle.click();
        if (await session.docs(() => document.body.dataset.theme === "light"))
          break;
      }
      await waitFor(
        async () =>
          (await session.docs(() => document.body.dataset.theme === "light")) &&
          (await session.shell(
            () => document.documentElement.dataset.scheme === "light",
          )),
        { what: "Follow documentation propagating the page's own light theme" },
      );
      return {
        verdict: PASS,
        detail:
          "Settings forced dark in both origins; Follow documentation then followed the real docs toggle to light",
      };
    },
  );
  await visit(shown);
}
