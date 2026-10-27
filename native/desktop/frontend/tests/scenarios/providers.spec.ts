import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  FIXTURE_SETTINGS_LANES,
  FIXTURE_SIGN_IN_PROVIDERS,
} from "../../src/dev/providerSettingsFixture";
import { label } from "../support/strings";

// The agent's settings: the signed-in profile's model providers, one card
// for each lane cadrumo-agent has, named as the catalog names it and drawn
// with its provider's own mark, each lane set up on its own. They are opened
// from the agent's own header and only for a profile signed in here. A key is
// written, saved and forgotten; it is never shown again, and never left
// behind in the page, its storage, its address or what the host was asked.

const FAKE_KEY = "FAKE-KEY-not-a-real-key-0000";

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const open = (target: Page, scenario = "signed-in", language = "en") =>
  target.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off&lang=${language}`,
  );

const settings = (target: Page, language = "en") =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title", {}, language),
  });

const settingsButton = (target: Page, language = "en") =>
  target.locator(".pane-agent").getByRole("button", {
    name: label("desktop.agent.settings", {}, language),
  });

/** One lane's card, by the lane's id. Two lanes of one provider carry the
 * same name, so the id is what tells their cards apart. */
const lane = (target: Page, id: string) =>
  settings(target).locator(`[data-lane="${id}"]`);

const providerGroup = (target: Page, provider: string) =>
  settings(target).locator(`li[data-provider="${provider}"]`);

const nameOf = (id: string) =>
  FIXTURE_SETTINGS_LANES.find((declared) => declared.id === id)?.display_name ??
  id;

type Status =
  "ready" | "saved" | "not_checked" | "setup_needed" | "sign_in_needed" | "off";

const STATUS_WORDS = {
  ready: "desktop.providers.status_ready",
  saved: "desktop.providers.status_saved",
  not_checked: "desktop.providers.status_not_checked",
  setup_needed: "desktop.providers.status_setup_needed",
  sign_in_needed: "desktop.providers.status_sign_in_needed",
  off: "desktop.providers.status_off",
} as const satisfies Record<Status, string>;

/** The only statuses drawn: a connection in use, and one that waits on the
 * person. Every other is its name in secondary text, with no glyph. */
const GLYPH: Partial<Record<Status, string>> = {
  ready: "check",
  sign_in_needed: "alert",
};

const statusMark = (scope: Locator) =>
  scope.locator('[data-slot="provider-status"]');

const colourOf = (node: Locator) =>
  node.evaluate((element) => getComputedStyle(element).color);

/** `card` shows `status`: its glyph where the status has one and none where
 * it has not, with the status in words kept for a screen reader and never
 * laid out to be read. */
async function expectStatus(card: Locator, status: Status) {
  const words = label(STATUS_WORDS[status]);
  const mark = statusMark(card);
  await expect(mark).toHaveCount(1);
  await expect(mark).toHaveAttribute("data-status", status);
  await expect(mark).toHaveText(words);
  const glyph = GLYPH[status];
  if (glyph) {
    const drawn = mark.locator("[data-icon]");
    await expect(drawn).toHaveAttribute("data-icon", glyph);
    await expect(drawn).toBeVisible();
  } else {
    await expect(mark.locator("[data-icon]")).toHaveCount(0);
  }
  const spoken = await mark.getByText(words, { exact: true }).boundingBox();
  expect(spoken?.width).toBeLessThanOrEqual(1);
  expect(spoken?.height).toBeLessThanOrEqual(1);
}

const signInCapableLane = FIXTURE_SETTINGS_LANES.find(
  (declared) =>
    declared.auth_kind === "provider_sign_in_only" &&
    FIXTURE_SIGN_IN_PROVIDERS.includes(declared.provider),
)!;
const signInUnavailableLanes = FIXTURE_SETTINGS_LANES.filter(
  (declared) =>
    declared.auth_kind === "provider_sign_in_only" &&
    !FIXTURE_SIGN_IN_PROVIDERS.includes(declared.provider),
);

async function openSettings(target: Page, expandProviders = true) {
  await settingsButton(target).click();
  await expect(settings(target)).toBeVisible();
  if (expandProviders)
    await settings(target)
      .locator("li[data-provider] > details")
      .evaluateAll((nodes) =>
        nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
      );
}

/** Writes `secret` in a lane's key field and saves it. */
async function saveKey(
  target: Page,
  id: string,
  secret: string,
  baseUrl?: string,
) {
  const entry = lane(target, id);
  await entry
    .getByRole("button", {
      name: new RegExp(
        `^(${escaped(label("desktop.providers.add_key"))}|${escaped(label("desktop.providers.replace_key"))})$`,
      ),
    })
    .click();
  await entry.getByLabel(new RegExp(`^${escaped(nameOf(id))} `)).fill(secret);
  if (baseUrl !== undefined)
    await entry
      .getByLabel(label("desktop.providers.base_url_label"))
      .fill(baseUrl);
  await entry
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();
}

/** Where a key could be left behind: the page, its fields, its storage, its
 * address and the calls made to the host. */
const traces = (target: Page, key: string) =>
  target.evaluate((secret) => {
    const stored = (storage: Storage) =>
      Array.from({ length: storage.length }, (_, index) => {
        const name = storage.key(index) ?? "";
        return `${name}=${storage.getItem(name) ?? ""}`;
      }).join("\n");
    return {
      page: document.documentElement.outerHTML.includes(secret),
      fields: [...document.querySelectorAll("input")].some((input) =>
        input.value.includes(secret),
      ),
      local: stored(localStorage).includes(secret),
      session: stored(sessionStorage).includes(secret),
      address: location.href.includes(secret),
      calls: (window.__scenarioHostCalls ?? []).join("\n").includes(secret),
    };
  }, key);

const NO_TRACE = {
  page: false,
  fields: false,
  local: false,
  session: false,
  address: false,
  calls: false,
};

const hostCalls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("providers start collapsed and keep each connection separately accessible", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target, false);

  // One group for each provider, initially collapsed, with each connection
  // still present under the disclosure.
  await expect(settings(target).locator("li[data-provider]")).toHaveCount(
    new Set(FIXTURE_SETTINGS_LANES.map((declared) => declared.provider)).size,
  );
  await expect(settings(target).locator("[data-lane]")).toHaveCount(
    FIXTURE_SETTINGS_LANES.length,
  );
  await expect(
    settings(target).locator("li[data-provider] > details[open]"),
  ).toHaveCount(0);
  await settings(target)
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
    );
  for (const declared of FIXTURE_SETTINGS_LANES) {
    const card = lane(target, declared.id);
    await expect(card).toHaveCount(1);
    await expect(card.getByRole("heading", { level: 5 })).toHaveText(
      label(
        declared.transport === "api"
          ? "desktop.providers.connection_api"
          : "desktop.providers.connection_app",
      ),
    );
    const mark = providerGroup(target, declared.provider).locator(
      "[data-slot=provider-mark]",
    );
    await expect(mark).toHaveCount(1);
    await expect(mark).toHaveAttribute("data-provider", declared.provider);
    const bundled =
      declared.provider === "codex" || declared.provider === "claude";
    await expect(mark).toHaveAttribute(
      "data-mark",
      bundled ? "mono" : "generic",
    );
    const style = await mark.getAttribute("style");
    if (bundled) expect(style).toContain("data:image/svg+xml");
    else expect(style).toBeNull();
  }

  // Example Alpha and Example Beta each have separate API and provider-app rows.
  for (const name of ["Example Alpha", "Example Beta"])
    await expect(
      settings(target).getByRole("heading", { level: 4, name, exact: true }),
    ).toHaveCount(1);

  // The row label names the kind of connection; nothing merges two lanes' status.
  await expect(settings(target).getByRole("radio")).toHaveCount(0);
  const words: string[] = [];
  for (const declared of FIXTURE_SETTINGS_LANES) {
    const card = lane(target, declared.id);
    words.push(await card.getByRole("heading", { level: 5 }).innerText());
    if (declared.auth_kind !== "none")
      words.push(...(await card.locator(":scope > p").allInnerTexts()));
  }
  for (const laneWords of words) {
    expect(laneWords).not.toMatch(/\bCLI\b/i);
    expect(laneWords).not.toMatch(/command[- ]line/i);
    expect(laneWords).not.toMatch(/over the internet/i);
    expect(laneWords).not.toMatch(/on this computer/i);
  }

  const credits = settings(target).locator("details").last();
  await expect(credits.locator("summary")).toHaveText(
    label("desktop.providers.icon_credits"),
  );
  await expect(credits).not.toHaveAttribute("open", "");
  await credits.locator("summary").click();
  await expect(credits).toContainText("Lobe Icons");
  await expect(credits).toContainText("MIT");
  await expect(credits).toContainText("Copyright (c) 2023 LobeHub");
  await expect(credits).toContainText("trademarks of their respective holders");
});

test("a connection is drawn only when ready or waiting on the person, and is quiet text otherwise", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const intro = settings(target).getByText(
    label("desktop.providers.group_intro"),
  );
  const secondary = await colourOf(intro);
  const name = (card: Locator) => card.getByRole("heading", { level: 5 });

  const ready = lane(target, "local_api");
  const unset = lane(target, "alpha_api");
  const signIn = lane(target, "beta_cli");
  await expectStatus(ready, "ready");
  await expectStatus(unset, "setup_needed");
  await expectStatus(signIn, "sign_in_needed");

  // Ready is the ordinary text with a green glyph; a connection that waits on
  // the person has a glyph of another colour; one not set up is its name in
  // the secondary text colour and nothing more.
  const green = await colourOf(statusMark(ready));
  const warning = await colourOf(statusMark(signIn));
  expect(await colourOf(name(ready))).not.toBe(secondary);
  expect(await colourOf(name(signIn))).not.toBe(secondary);
  expect(await colourOf(name(unset))).toBe(secondary);
  expect(new Set([green, warning, secondary]).size).toBe(3);

  // The collapsed group says the same for each of its connections: the
  // connection's name, the same glyph or none, and the status in words only
  // for a screen reader.
  for (const declared of FIXTURE_SETTINGS_LANES) {
    const chip = providerGroup(target, declared.provider).locator(
      `summary [data-lane-summary="${declared.id}"]`,
    );
    const status = await statusMark(lane(target, declared.id)).getAttribute(
      "data-status",
    );
    expect(status, declared.id).toBeTruthy();
    await expect(statusMark(chip)).toHaveAttribute("data-status", status ?? "");
    await expect(chip).toHaveText(
      label(
        declared.transport === "api"
          ? "desktop.providers.connection_api"
          : "desktop.providers.connection_app",
      ) + (await statusMark(chip).textContent()),
    );
    await expect(chip.locator("[data-icon]")).toHaveCount(
      GLYPH[status as Status] ? 1 : 0,
    );
  }
  const quietChip = providerGroup(target, "alpha").locator(
    'summary [data-lane-summary="alpha_api"]',
  );
  const readyChip = providerGroup(target, "local").locator(
    'summary [data-lane-summary="local_api"]',
  );
  expect(await colourOf(quietChip)).toBe(secondary);
  expect(await colourOf(readyChip)).not.toBe(secondary);

  // A saved key is not ready, so it stays quiet text with no glyph.
  await saveKey(target, "alpha_api", FAKE_KEY);
  await expectStatus(unset, "saved");
  await expect(statusMark(quietChip)).toHaveAttribute("data-status", "saved");
  await expect(quietChip.locator("[data-icon]")).toHaveCount(0);
  expect(await colourOf(quietChip)).toBe(secondary);
  expect(await colourOf(name(unset))).toBe(secondary);
});

test("settings search finds providers and agent keys", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target, false);
  const pane = target.locator(".pane-agent");
  const search = pane.getByLabel(label("desktop.settings.agent_search"));
  const access = pane.getByRole("region", {
    name: label("desktop.automation_access.title"),
  });

  const keyName = await access.locator(".agent-key h4").first().innerText();
  await expect(search).toBeVisible();
  await expect(pane.locator('input[type="search"]')).toHaveCount(1);
  await expect(settings(target)).toBeVisible();
  await expect(access).toBeVisible();

  await search.fill("Codex");
  await expect(providerGroup(target, "codex")).toBeVisible();
  await expect(providerGroup(target, "alpha")).toBeHidden();

  await search.fill(label("desktop.providers.connection_api"));
  for (const declared of FIXTURE_SETTINGS_LANES) {
    const connection = lane(target, declared.id);
    await expect(connection).toHaveCount(1);
    if (declared.transport === "api") await expect(connection).toBeVisible();
    else await expect(connection).toBeHidden();
  }

  await search.fill(keyName);
  await expect(access).toBeVisible();
  await expect(
    access.getByRole("heading", { name: keyName, exact: true }),
  ).toBeVisible();

  await search.fill(label("desktop.automation_access.standing_suspended"));
  await expect(access).toBeVisible();
  await expect(
    access.getByText(label("desktop.automation_access.standing_suspended")),
  ).toBeVisible();
  await expect(settings(target)).toBeHidden();

  await search.fill("no matching setting 918273");
  await expect(pane.getByRole("status")).toHaveText(
    label("desktop.settings.agent_search_empty"),
  );
  await expect(settings(target)).toBeHidden();
  await expect(access).toBeHidden();
});

test("the settings load once, and reopen at once while they are read again", async ({
  page: target,
}) => {
  const resolved = async () =>
    (await hostCalls(target)).filter(
      (call) => call === "providerStatusResolved",
    ).length;
  const spinners = target.locator(".pane-agent [data-slot=spinner]");
  await open(target);
  // Nothing is read until the settings open.
  expect(await resolved()).toBe(0);
  await settingsButton(target).click();
  await expect(settings(target)).toBeVisible();
  // The panel's one loader is gone once both sections are read.
  await expect(spinners).toHaveCount(0);
  expect(await resolved()).toBe(1);

  await settingsButton(target).click();
  await expect(settings(target)).toHaveCount(0);
  await settingsButton(target).click();
  // What was read stays on screen, with no loader, while it is read again.
  await expect(settings(target)).toBeVisible();
  await expect(spinners).toHaveCount(0);
  await expect.poll(resolved).toBe(2);
});

test("provider settings read errors give a refresh action without exposing a code", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSettingsRead(),
  );
  await settingsButton(target).click();

  const pane = target.locator(".pane-agent");
  await expect(
    pane.getByText(label("desktop.providers.load_failed"), { exact: true }),
  ).toBeVisible();
  await expect(pane).not.toContainText("read_failed");
  await expect(pane).not.toContainText("provider_error");
  await pane
    .getByRole("button", { name: label("desktop.providers.refresh") })
    .click();
  await expect(settings(target)).toBeVisible();
  await expect(pane).not.toContainText("read_failed");
});

for (const language of ["es", "hu"] as const) {
  test(`provider group names and connection marks fit a narrow ${language} panel`, async ({
    page: target,
  }) => {
    await target.setViewportSize({ width: 390, height: 844 });
    await open(target, "signed-in", language);
    await target.locator("[data-rail=agent]").click();
    await settingsButton(target, language).click();
    const providerSettings = settings(target, language);
    await expect(providerSettings).toBeVisible();

    const gamma = FIXTURE_SETTINGS_LANES[0]!;
    const alpha = FIXTURE_SETTINGS_LANES.find(
      (declared) => declared.display_name === "Example Alpha",
    )!;
    const measureGroup = async (provider: string) =>
      providerSettings
        .locator(`li[data-provider="${provider}"] > details > summary`)
        .evaluate((summary) => {
          const header = summary.children[0] as HTMLElement;
          const chevron = summary.children[1] as HTMLElement;
          const statuses = summary.children[2] as HTMLElement;
          const name = header.querySelector("h4") as HTMLElement;
          const box = (node: HTMLElement) => {
            const rect = node.getBoundingClientRect();
            return {
              left: rect.left,
              right: rect.right,
              top: rect.top,
              bottom: rect.bottom,
              width: rect.width,
              height: rect.height,
            };
          };
          return {
            summary: {
              width: summary.clientWidth,
              scrollWidth: summary.scrollWidth,
            },
            header: box(header),
            name: box(name),
            lineHeight: Number.parseFloat(getComputedStyle(name).lineHeight),
            chevron: box(chevron),
            statuses: box(statuses),
            chips: [...statuses.children].map((chip) =>
              box(chip as HTMLElement),
            ),
          };
        });

    for (const declared of [gamma, alpha]) {
      const summary = providerSettings.locator(
        `li[data-provider="${declared.provider}"] > details > summary`,
      );
      await expect(summary.getByRole("heading", { level: 4 })).toHaveText(
        declared.display_name,
      );
      const metrics = await measureGroup(declared.provider);
      expect(metrics.summary.scrollWidth).toBeLessThanOrEqual(
        metrics.summary.width,
      );
      expect(metrics.name.width).toBeGreaterThan(80);
      expect(metrics.name.height).toBeLessThanOrEqual(
        metrics.lineHeight * 2 + 1,
      );
      expect(
        Math.abs(metrics.chevron.top - metrics.header.top),
      ).toBeLessThanOrEqual(2);
      expect(metrics.statuses.top).toBeGreaterThanOrEqual(
        metrics.header.bottom - 1,
      );
      for (const chip of metrics.chips) {
        expect(chip.left).toBeGreaterThanOrEqual(metrics.statuses.left - 1);
        expect(chip.right).toBeLessThanOrEqual(metrics.statuses.right + 1);
      }
    }
    expect(
      await target.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
}

test("a lane with an app says in plain words where it stands, and the API lane says nothing of one", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await expect(settings(target).locator("[data-lane]")).toHaveCount(
    FIXTURE_SETTINGS_LANES.length,
  );
  const cards = await settings(target)
    .locator("[data-lane]")
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        id: node.getAttribute("data-lane"),
        text: node.textContent ?? "",
      })),
    );
  // The backend has no safe check yet of a provider's app: a lane that only
  // signs in through it asks for that sign-in, and none says an app is
  // missing.
  for (const declared of FIXTURE_SETTINGS_LANES) {
    const text = cards.find((card) => card.id === declared.id)?.text ?? "";
    expect(text, declared.id).not.toContain(
      label("desktop.providers.detail_app_missing", {
        provider: declared.display_name,
      }),
    );
    const signIn = label("desktop.providers.detail_sign_in", {
      provider: declared.display_name,
    });
    if (declared.auth_kind === "provider_sign_in_only")
      expect(text, declared.id).toContain(signIn);
    else expect(text, declared.id).not.toContain(signIn);
  }
  // Nothing says what an entry is used for: only the agent uses a key.
  await expect(settings(target)).not.toContainText("Reading documents");
});

test("a key is saved from the agent's settings and never kept anywhere", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const alpha = lane(target, "alpha_api");
  await expectStatus(alpha, "setup_needed");
  // Save waits for a key, and the field offers none of its own.
  await alpha
    .getByRole("button", { name: label("desktop.providers.add_key") })
    .click();
  const field = alpha.getByLabel(/^Example Alpha /);
  await expect(field).toHaveAttribute("type", "password");
  await expect(field).not.toHaveAttribute("placeholder", /.+/);
  await expect(
    alpha.getByRole("button", { name: label("desktop.providers.save") }),
  ).toBeDisabled();
  await field.fill(FAKE_KEY);
  await alpha
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();

  await expectStatus(alpha, "saved");
  await expect(
    alpha.getByRole("button", {
      name: label("desktop.providers.replace_key"),
    }),
  ).toBeVisible();
  // The other lane of the same provider is not changed by it.
  await expectStatus(lane(target, "alpha_cli"), "setup_needed");
  // Nowhere a key could be left behind holds it.
  expect(await traces(target, FAKE_KEY)).toEqual(NO_TRACE);
});

test("a key that is refused or replaced is not kept either", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const refused = "not a key";
  await saveKey(target, "beta_api", refused);
  await expect(lane(target, "beta_api").getByRole("alert")).toHaveText(
    label("desktop.providers.refused_invalid_key_format"),
  );
  await expectStatus(lane(target, "beta_api"), "setup_needed");
  expect(await traces(target, refused)).toEqual(NO_TRACE);

  await saveKey(target, "beta_api", FAKE_KEY);
  await expectStatus(lane(target, "beta_api"), "saved");
  const replacement = "FAKE-KEY-replacement-0001";
  await saveKey(target, "beta_api", replacement);
  await expect(
    lane(target, "beta_api").getByRole("button", {
      name: label("desktop.providers.replace_key"),
    }),
  ).toBeVisible();
  for (const key of [FAKE_KEY, replacement])
    expect(await traces(target, key)).toEqual(NO_TRACE);
});

test("a gateway takes its address, and one with no default needs it", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  // With a default, the address may be left empty.
  const gateway = FIXTURE_SETTINGS_LANES.find(
    (declared) => declared.provider === "gateway",
  );
  expect(gateway?.default_base_url).toBeTruthy();
  await expect(lane(target, "gateway_cli")).toContainText(
    gateway?.default_base_url ?? "",
  );
  // Without one, Save waits for it too.
  const relayName = nameOf("relay_cli");
  const relay = lane(target, "relay_cli");
  await relay
    .getByRole("button", { name: label("desktop.providers.add_key") })
    .click();
  await relay.getByLabel(/^Example Relay /).fill(FAKE_KEY);
  const save = relay.getByRole("button", {
    name: label("desktop.providers.save"),
  });
  await expect(save).toBeDisabled();
  await relay
    .getByLabel(label("desktop.providers.base_url_label"))
    .fill("http://plain.gateway.example");
  await save.click();
  await expect(relay.getByRole("alert")).toHaveText(
    label("desktop.providers.refused_base_url_rejected"),
  );
  expect(relayName).toBeTruthy();
  await saveKey(target, "relay_cli", FAKE_KEY, "https://relay.gateway.example");
  await expect(relay).toContainText(
    label("desktop.providers.address", {
      url: "https://relay.gateway.example",
    }),
  );
  expect(await traces(target, FAKE_KEY)).toEqual(NO_TRACE);
});

/** The entries of the agent's provider list, by lane, as the composer's
 * model settings offer them. */
async function pickerWays(target: Page) {
  await target
    .locator(".pane-agent")
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first()
    .click();
  await target
    .getByRole("dialog", { name: label("desktop.agent.settings_title") })
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  const ways = await target
    .getByRole("listbox")
    .locator("[role=option][data-way]")
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-way")));
  await target.keyboard.press("Escape");
  await target.keyboard.press("Escape");
  return ways;
}

test("every connection has one switch, apart from its setup, and one turned off leaves the provider list", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  // The same one switch on every connection, whatever it signs in with.
  for (const declared of FIXTURE_SETTINGS_LANES)
    await expect(
      lane(target, declared.id).getByRole("switch"),
      declared.id,
    ).toHaveCount(1);

  await saveKey(target, "alpha_api", FAKE_KEY);
  const alpha = lane(target, "alpha_api");
  const toggle = alpha.getByRole("switch", {
    name: label("desktop.providers.use_in_agent", {
      provider: nameOf("alpha_api"),
      connection: label("desktop.providers.connection_api"),
    }),
  });
  await expect(toggle).toBeChecked();
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  await expectStatus(alpha, "off");
  // Off keeps the key, and setting it up waits until it is on again.
  await expect(alpha).toContainText(label("desktop.providers.detail_off_kept"));
  await expect(alpha.getByRole("button")).toHaveCount(0);

  await settingsButton(target).click();
  expect(await pickerWays(target)).not.toContain("alpha/api");

  await openSettings(target);
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expectStatus(alpha, "saved");
  await expect(
    alpha.getByRole("button", { name: label("desktop.providers.replace_key") }),
  ).toBeVisible();
  await settingsButton(target).click();
  expect(await pickerWays(target)).toContain("alpha/api");
  expect(await traces(target, FAKE_KEY)).toEqual(NO_TRACE);
});

test("a connection that signs in through its app turns off and on like any other", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const beta = lane(target, "beta_cli");
  await beta.getByRole("switch").click();
  await expectStatus(beta, "off");
  await expect(beta).toContainText(label("desktop.providers.detail_off"));
  await beta.getByRole("switch").click();
  await expectStatus(beta, "sign_in_needed");
  // It has no key to change.
  await expect(
    beta.getByRole("button", { name: label("desktop.providers.add_key") }),
  ).toHaveCount(0);
});

test("GUI sign-in is capability-gated by the agent's declared provider list", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);

  await expect(
    lane(target, signInCapableLane.id).getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    }),
  ).toBeVisible();
  for (const unsupported of signInUnavailableLanes) {
    const card = lane(target, unsupported.id);
    await expect(card.getByRole("note")).toHaveText(
      label("desktop.providers.sign_in_unavailable", {
        provider: nameOf(unsupported.id),
      }),
    );
    await expect(
      card.getByRole("button", {
        name: label("desktop.providers.sign_in_action"),
      }),
    ).toHaveCount(0);
  }
  expect(signInUnavailableLanes.length).toBeGreaterThan(0);
});

test("the dialog offers only sign-in methods declared by the agent", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.setMethods(["browser"]),
  );
  await openSettings(target);
  const card = lane(target, signInCapableLane.id);
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect
    .poll(async () => hostCalls(target))
    .toContain(`providerSignInStart ${signInCapableLane.id} browser`);
  expect(
    (await hostCalls(target)).filter((call) =>
      call.startsWith("providerSignInStart "),
    ),
  ).toEqual([`providerSignInStart ${signInCapableLane.id} browser`]);
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_close") })
    .last()
    .click();
});

test("provider sign-in errors explain the issue and retry with a fresh revision", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.deferNextStatus(),
  );
  const card = lane(target, signInCapableLane.id);
  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.failNextStart("provider_unavailable");
  });
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInFailureQueued provider_unavailable");
  const statusCallsBefore = (await hostCalls(target)).filter(
    (call) => call === "providerStatus",
  ).length;
  const resolvedReadsBefore = (await hostCalls(target)).filter(
    (call) => call === "providerStatusResolved",
  ).length;
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInFailureReturned provider_unavailable");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_provider_unavailable", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
  await expect(dialog).toContainText(nameOf(signInCapableLane.id));
  const retry = dialog.getByRole("button", {
    name: label("desktop.providers.sign_in_retry"),
  });
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter((call) => call === "providerStatus")
          .length,
    )
    .toBeGreaterThan(statusCallsBefore);
  await expect(retry).toHaveCount(0);
  expect(
    (await hostCalls(target)).filter(
      (call) => call === "providerStatusResolved",
    ),
  ).toHaveLength(resolvedReadsBefore);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.completeStatus(),
  );
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter(
          (call) => call === "providerStatusResolved",
        ).length,
    )
    .toBeGreaterThan(resolvedReadsBefore);
  await expect(retry).toBeVisible();

  await retry.click();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  expect(
    (await hostCalls(target)).filter((call) =>
      call.startsWith(`providerSignInStart ${signInCapableLane.id} `),
    ),
  ).toHaveLength(2);
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_cancel") })
    .click();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_cancelled"),
  );
});

test("generic provider sign-in errors use a plain message and allow retry", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const card = lane(target, signInCapableLane.id);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextStart("provider_error"),
  );
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_provider_error", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
  await expect(dialog).not.toContainText("provider_error");
  await expect(dialog).toContainText(label("desktop.providers.sign_in_retry"));
});

test("successful provider sign-in shows completion and returns to settings", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await lane(target, signInCapableLane.id)
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await expect
    .poll(async () =>
      (await hostCalls(target)).filter(
        (call) => call === "providerSignInOpenExternal",
      ),
    )
    .toHaveLength(1);

  const catalogReadsBefore = (await hostCalls(target)).filter(
    (call) => call === "agentProviderCatalogResolved",
  ).length;
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.succeedCurrentAttempt(),
  );
  await expect(dialog).toHaveCount(0);
  await expect(settings(target)).toBeVisible();
  await expectStatus(lane(target, signInCapableLane.id), "not_checked");
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter(
          (call) => call === "agentProviderCatalogResolved",
        ).length,
    )
    .toBeGreaterThan(catalogReadsBefore);
});

test("a late cancel reply cannot replace a retry attempt after polling fails", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await lane(target, signInCapableLane.id)
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInOpenExternal");

  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.deferNextCancel(),
  );
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_cancel") })
    .click();
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInCancel");
  // Let the status poll terminalize the old attempt while its cancel response
  // remains outstanding, then use the fresh-revision retry path.
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failCurrentAttempt(),
  );
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInAttemptFailed provider_unavailable");
  await expect(dialog.getByRole("alert")).toBeVisible();
  const retry = dialog.getByRole("button", {
    name: label("desktop.providers.sign_in_retry"),
  });
  await expect(retry).toBeVisible();
  await retry.click();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );

  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.completeCancel(),
  );
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await expect(dialog.getByRole("alert")).toHaveCount(0);
});

test("a late browser handoff failure cannot clear a retry attempt", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.deferNextOpenExternal(),
  );
  await lane(target, signInCapableLane.id)
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInOpenExternal");
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failCurrentAttempt(),
  );
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInAttemptFailed provider_unavailable");
  await expect(dialog.getByRole("alert")).toBeVisible();
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_retry") })
    .click();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );

  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.completeOpenExternal(true),
  );
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await expect(dialog.getByRole("alert")).toHaveCount(0);
});

test("browser sign-in opens once after explicit start and status reads retry", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextStatus(),
  );
  const card = lane(target, signInCapableLane.id);
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();

  const dialog = target.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await expect
    .poll(async () =>
      (await hostCalls(target)).filter(
        (call) => call === "providerSignInOpenExternal",
      ),
    )
    .toHaveLength(1);
  await expect
    .poll(async () => hostCalls(target))
    .toContain("providerSignInStatusFailureReturned read_failed");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await expect(dialog.getByRole("alert")).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter(
          (call) => call === "providerSignInStatus",
        ).length,
    )
    .toBeGreaterThan(1);

  const authUrl = "https://provider.example/sign-in";
  await expect(dialog).not.toContainText(authUrl);
  expect(
    await target.evaluate(
      (url) =>
        document.documentElement.outerHTML.includes(url) ||
        (window.__scenarioHostCalls ?? []).join("\n").includes(url) ||
        location.href.includes(url),
      authUrl,
    ),
  ).toBe(false);
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_cancel") })
    .click();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_cancelled"),
  );
  const calls = await hostCalls(target);
  expect(calls).toContain(
    `providerSignInStart ${signInCapableLane.id} browser`,
  );
  expect(calls).toContain("providerSignInCancel");
  expect(
    calls.filter((call) => call === "providerStatus").length,
  ).toBeGreaterThan(1);
  expect(calls.join("\n")).not.toContain(authUrl);
});

test("closing during active sign-in refreshes the committed provider revision", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const card = lane(target, signInCapableLane.id);
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );

  const previousReads = (await hostCalls(target)).filter(
    (call) => call === "providerStatusResolved",
  ).length;
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_close") })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect
    .poll(async () =>
      (await hostCalls(target)).filter(
        (call) => call === "providerSignInCancelSettled",
      ),
    )
    .toHaveLength(1);
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter(
          (call) => call === "providerStatusResolved",
        ).length,
    )
    .toBeGreaterThan(previousReads);

  await expectStatus(card, "not_checked");

  // Starting again succeeds only with the revision returned by that refresh.
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const nextDialog = target.getByRole("dialog");
  await expect(nextDialog).toContainText(
    label("desktop.providers.sign_in_waiting"),
  );
  await nextDialog
    .getByRole("button", { name: label("desktop.providers.sign_in_cancel") })
    .click();
  await expect(nextDialog).toContainText(
    label("desktop.providers.sign_in_cancelled"),
  );
});

test("a late active start is cancelled after the signed-in profile changes", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.deferNextStart(),
  );
  await lane(target, signInCapableLane.id)
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect
    .poll(async () =>
      (await hostCalls(target)).filter((call) =>
        call.startsWith("providerSignInStart "),
      ),
    )
    .toHaveLength(1);

  const readsBeforeSwitch = (await hostCalls(target)).filter(
    (call) => call === "providerStatusResolved",
  ).length;
  await target.evaluate(() =>
    window.__scenarioLanguage!.switchAccount("Other profile", "en"),
  );
  await expect(dialog).toHaveCount(0);
  await expect(
    target.getByRole("button", { name: /Other profile Signed in/ }),
  ).toBeVisible();
  await target.evaluate(() => window.__scenarioProviderSignIn!.completeStart());
  await expect
    .poll(async () =>
      (await hostCalls(target)).filter(
        (call) => call === "providerSignInCancelSettled",
      ),
    )
    .toHaveLength(1);
  expect(
    (await hostCalls(target)).filter((call) => call === "providerSignInStatus"),
  ).toEqual([]);
  await target.waitForTimeout(100);
  expect(
    (await hostCalls(target)).filter(
      (call) => call === "providerStatusResolved",
    ).length,
  ).toBe(readsBeforeSwitch);
});

test("without a profile signed in here, the agent and its settings are not offered and nothing is asked", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  // The agent's place in the rail is held, and says why; its column is gone.
  const rail: Locator = target.locator("[data-rail=agent]");
  await expect(rail).toHaveAttribute("aria-disabled", "true");
  await expect(target.locator(".agent-column")).toBeHidden();
  await expect(settingsButton(target)).toHaveCount(0);
  await expect(settings(target)).toHaveCount(0);
  // Pressing the held place does not bring it back.
  await rail.click({ force: true });
  await expect(target.locator(".agent-column")).toBeHidden();
  // Nothing of the agent's, and none of its settings, is asked of the host.
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => /^(agent|provider)/.test(call))).toEqual([]);
});

test("browser-code sign-in opens the coalesced URL and submits a transient code once", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.setMethods(["browser-code"]),
  );
  await openSettings(target);
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  const input = dialog.getByLabel(
    label("desktop.providers.sign_in_code_label"),
  );
  await expect(input).toBeVisible();
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter(
          (call) => call === "providerSignInOpenExternal",
        ).length,
    )
    .toBe(1);
  await input.fill("bad code");
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.providers.sign_in_code_submit"),
    }),
  ).toBeDisabled();
  const secret = "FAKE-authorization-code-9876";
  await input.fill(secret);
  await dialog
    .getByRole("button", {
      name: label("desktop.providers.sign_in_code_submit"),
    })
    .click();
  await expect(input).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter(
          (call) => call === "providerSignInSubmitCode",
        ).length,
    )
    .toBe(1);
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_code_checking"),
  );
  expect((await hostCalls(target)).join("\n")).not.toContain(secret);
  expect(
    await target.evaluate(
      (value) =>
        document.documentElement.outerHTML.includes(value) ||
        location.href.includes(value) ||
        JSON.stringify(localStorage).includes(value),
      secret,
    ),
  ).toBe(false);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.succeedCurrentAttempt(),
  );
  await expect(dialog).toHaveCount(0);
});

test("a provider failure after accepting a code replaces checking with an error and retry", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.setMethods(["browser-code"]),
  );
  await openSettings(target);
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  await dialog
    .getByLabel(label("desktop.providers.sign_in_code_label"))
    .fill("FAKE-rejected-code-123");
  await dialog
    .getByRole("button", {
      name: label("desktop.providers.sign_in_code_submit"),
    })
    .click();
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_code_checking"),
  );
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failCurrentAttempt(),
  );
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.providers.sign_in_provider_unavailable", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
  await expect(dialog).not.toContainText(
    label("desktop.providers.sign_in_code_checking"),
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.providers.sign_in_retry"),
    }),
  ).toBeVisible();
});

test("cancelling browser-code sign-in clears an unsubmitted code", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.setMethods(["browser-code"]),
  );
  await openSettings(target);
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  const input = dialog.getByLabel(
    label("desktop.providers.sign_in_code_label"),
  );
  const secret = "FAKE-cancel-code-4231";
  await input.fill(secret);
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_cancel") })
    .click();
  await expect(input).toHaveCount(0);
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_cancelled"),
  );
  expect((await hostCalls(target)).join("\n")).not.toContain(secret);
  expect(
    await target.evaluate(
      (value) =>
        document.documentElement.outerHTML.includes(value) ||
        location.href.includes(value) ||
        JSON.stringify(localStorage).includes(value),
      secret,
    ),
  ).toBe(false);
  expect(await hostCalls(target)).not.toContain("providerSignInSubmitCode");
});

test("a refused code submission settles the attempt and offers an explicit retry", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.setMethods(["browser-code"]);
    window.__scenarioProviderSignIn!.failNextSubmit();
  });
  await openSettings(target);
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  const input = dialog.getByLabel(
    label("desktop.providers.sign_in_code_label"),
  );
  const submit = dialog.getByRole("button", {
    name: label("desktop.providers.sign_in_code_submit"),
  });
  await input.fill('"'.repeat(2048));
  await expect(submit).toBeDisabled();
  await input.fill("FAKE-refused-code-123");
  await submit.click();
  await expect(input).toHaveCount(0);
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.providers.sign_in_busy", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.providers.sign_in_retry"),
    }),
  ).toBeVisible();
  expect(
    (await hostCalls(target)).filter(
      (call) => call === "providerSignInSubmitCode",
    ),
  ).toHaveLength(1);
  expect(await hostCalls(target)).toContain("providerSignInCancel");
});
