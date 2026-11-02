import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

async function openCalendar(
  page: Page,
  scenario: string,
  extra = "",
  locale = "en",
) {
  await page.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&lang=${locale}${extra}`,
  );
  await page
    .getByRole("navigation", { name: label("desktop.rail.label", {}, locale) })
    .getByRole("button", { name: label("desktop.calendar.title", {}, locale) })
    .click();
  return page.getByRole("region", {
    name: label("desktop.calendar.title", {}, locale),
  });
}

for (const locale of ["en", "es", "ca", "hu"]) {
  test(`calendar coverage retains each reason without asserting no obligations (${locale})`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 700, height: 900 });
    const calendar = await openCalendar(
      page,
      "signed-in",
      "&calendar=advice_only",
      locale,
    );
    const messages = [
      label(
        "desktop.calendar.coverage.applicable_window_missing",
        {
          modelos: new Intl.ListFormat(locale, { type: "conjunction" }).format([
            "123",
            "216",
          ]),
        },
        locale,
      ),
      label(
        "desktop.calendar.coverage.applicability_undetermined",
        { modelos: "347" },
        locale,
      ),
      label(
        "desktop.calendar.coverage.registry_unmodeled",
        { modelos: "720" },
        locale,
      ),
    ];
    for (const message of messages) {
      expect(message).not.toContain("desktop.calendar.");
      await expect(calendar.getByText(message, { exact: true })).toBeVisible();
    }
    const note = calendar.getByRole("list").filter({ hasText: messages[0] });
    await expect(note.getByRole("listitem")).toHaveText(messages);
    await expect(calendar).toContainText(
      label("desktop.calendar.coverage.no_dates", {}, locale),
    );
    await expect(calendar).not.toContainText(
      label("desktop.calendar.empty", {}, locale),
    );
    expect(
      await note.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
  });
}

test("coverage advice remains visible beside dated obligations", async ({
  page,
}) => {
  const calendar = await openCalendar(page, "signed-in", "&calendar=advice");
  await expect(calendar).toContainText(
    label("desktop.calendar.coverage.registry_unmodeled", { modelos: "720" }),
  );
  await expect(calendar).not.toContainText(
    label("desktop.calendar.coverage.no_dates"),
  );
});

test("an empty calendar without advice adds no coverage note", async ({
  page,
}) => {
  const calendar = await openCalendar(page, "empty");
  await expect(calendar).toContainText(label("desktop.calendar.empty"));
  await expect(calendar).not.toContainText(
    label("desktop.calendar.coverage.no_dates"),
  );
  await expect(calendar.getByRole("listitem")).toHaveCount(0);
});
