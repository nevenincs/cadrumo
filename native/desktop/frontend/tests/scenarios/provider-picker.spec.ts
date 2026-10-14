import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";
import { agentColumn as column, ask, settled } from "../support/agent";
import { label } from "../support/strings";

// The agent's provider list: a list of lanes, each with its provider's own
// mark and the name cadrumo-agent's catalog gives it, and nothing that lets a
// person pick "how" a provider is reached. A provider the catalog serves two
// lanes for (Example Alpha and Example Beta) is two entries; the one chosen is
// the lane the next message runs on, and its models and efforts are that
// lane's own.

// The smallest side a control may have under a finger, less the rounding of a
// rem length to device pixels.
const FINGER = 44 - 1;

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** What the fixture catalog holds, read straight from it: every check below
 * compares the column with this, and none restates a provider. */
const lanes = FIXTURE_CATALOG.providers ?? [];
const wayOf = (served: { provider_id: string; transport: string }) =>
  `${served.provider_id}/${served.transport}`;
const laneOf = (way: string) => {
  const served = lanes.find((held) => wayOf(held) === way);
  if (!served) throw new Error(`The fixture catalog has no lane ${way}.`);
  return served;
};

/** Why the fixture holds a lane back, in the words the column has for it. */
function heldBy(served: (typeof lanes)[number]): string | null {
  if (served.health.selectable) return null;
  if (served.health.configured === "unavailable")
    return label("desktop.agent.lane_not_configured");
  if (served.health.authentication === "unauthenticated")
    return label("desktop.agent.lane_signed_out");
  if (served.health.transport === "unavailable")
    return label("desktop.agent.lane_unreachable");
  return label("desktop.agent.unavailable");
}

const effortWords = (efforts: readonly string[]) =>
  efforts.map((effort) => label(`desktop.agent.effort_${effort}`));

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);

const composerButton = (target: Page) =>
  column(target)
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first();

/** Opens the model settings from the composer. */
async function openSettings(target: Page) {
  await composerButton(target).click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  await expect(settings).toBeVisible();
  return settings;
}

const providerBox = (settings: Locator) =>
  settings.getByRole("combobox", { name: label("desktop.agent.provider") });
const modelBox = (settings: Locator) =>
  settings.getByRole("combobox", { name: label("desktop.agent.model") });
const effortBox = (settings: Locator) =>
  settings.getByRole("combobox", { name: label("desktop.agent.effort") });

/** The entry of the list for the lane `way`, once the list is open. */
const entry = (target: Page, way: string) =>
  target.locator(`[role=option][data-way="${way}"]`);

/** Opens the list and chooses the lane `way` in it. */
async function chooseLane(target: Page, settings: Locator, way: string) {
  await providerBox(settings).click();
  await entry(target, way).click();
}

/** Every selection the column has handed to the agent with a message, in
 * order. Only the scenario host can say: it is read off the session the
 * column sends through. */
const sentSelections = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __sentSelections?: unknown[] })
        .__sentSelections ?? [],
  );

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the list has one entry for each lane, each with its provider's own mark, and no switch", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);

  // Nothing offers a way to choose how a provider is reached: a person
  // chooses from one list.
  await expect(settings.getByRole("radiogroup")).toHaveCount(0);
  await expect(settings.getByRole("radio")).toHaveCount(0);
  await expect(settings.getByRole("switch")).toHaveCount(0);
  await expect(settings.getByRole("tablist")).toHaveCount(0);
  await expect(settings.getByRole("combobox")).toHaveCount(3);

  await providerBox(settings).click();
  const options = target.getByRole("option");
  await expect(options).toHaveCount(lanes.length);
  const rows = await options.evaluateAll((nodes) =>
    nodes.map((node) => ({
      way: node.getAttribute("data-way"),
      text: node.textContent ?? "",
      disabled: node.getAttribute("aria-disabled") === "true",
      marks: [...node.querySelectorAll("[data-slot=provider-mark]")].map(
        (mark) => ({
          provider: mark.getAttribute("data-provider"),
          kind: mark.getAttribute("data-mark"),
          tag: mark.tagName.toLowerCase(),
        }),
      ),
    })),
  );
  // One row for each lane, in the order the catalog serves them, named as
  // the catalog names the lane and nothing more, and drawn with the mark of
  // the provider the lane belongs to.
  expect(rows.map((row) => row.way)).toEqual(lanes.map(wayOf));
  for (const served of lanes) {
    const row = rows.find((held) => held.way === wayOf(served));
    const why = heldBy(served);
    expect(row?.text, wayOf(served)).toBe(served.display_name + (why ?? ""));
    expect(row?.disabled, wayOf(served)).toBe(why !== null);
    expect(row?.marks, wayOf(served)).toEqual([
      // Cadrumo holds no artwork: every provider gets the neutral ring.
      { provider: served.provider_id, kind: "none", tag: "span" },
    ]);
  }
  // Example Alpha and Example Beta are each listed twice under the same name.
  for (const name of ["Example Alpha", "Example Beta"])
    expect(rows.filter((row) => row.text.startsWith(name))).toHaveLength(2);
  // Those the catalog holds back stay in the list, disabled.
  await expect(target.locator("[role=option][aria-disabled=true]")).toHaveCount(
    lanes.filter((served) => !served.health.selectable).length,
  );
});

test("choosing an entry chooses its lane, and a message goes with that lane's transport", async ({
  page: target,
}, info) => {
  test.skip(
    info.project.metadata.agentHost === "live",
    "What the column hands the agent is read off the scenario host's session.",
  );
  await target.addInitScript(() => {
    // The scenario host assigns its session to this property each time the
    // column uses it; the first send follows an observe, so every send is
    // seen by the wrapper.
    type Sending = {
      send?: (request: { selection: unknown }) => Promise<unknown>;
      recorded?: boolean;
    };
    const sent: unknown[] = [];
    Object.assign(window, { __sentSelections: sent });
    let held: Sending | undefined;
    Object.defineProperty(window, "__fixtureAgentSession", {
      configurable: true,
      get: () => held,
      set: (session: Sending | undefined) => {
        held = session;
        if (!session || session.recorded || !session.send) return;
        session.recorded = true;
        const send = session.send.bind(session);
        session.send = (request) => {
          sent.push(request.selection);
          return send(request);
        };
      },
    });
  });
  await open(target);

  const startsWith = (way: string) => {
    const served = laneOf(way);
    const start =
      served.catalog.recommended_entry_id ??
      served.catalog.models?.[0]?.entry_id;
    const model = served.catalog.models?.find(
      (held) => held.entry_id === start,
    );
    return {
      provider: served.provider_id,
      transport: served.transport,
      model: model?.model,
    };
  };

  // The program entry of Example Beta: its own models, and a message goes by the
  // transport the catalog gives that lane.
  let settings = await openSettings(target);
  await chooseLane(target, settings, "beta/cli");
  await expect(providerBox(settings)).toHaveText("Example Beta");
  await expect(modelBox(settings).locator("option")).toHaveText(
    laneOf("beta/cli").catalog.models?.map((held) => held.display_name) ?? [],
  );
  await target.keyboard.press("Escape");
  await ask(target, "Primera");
  await expect.poll(() => sentSelections(target)).toHaveLength(1);
  expect((await sentSelections(target)).at(-1)).toEqual(startsWith("beta/cli"));
  expect(startsWith("beta/cli").transport).toBe("cli");
  await settled(target);

  // The other entry of the same name: another lane, with models of its own.
  settings = await openSettings(target);
  await chooseLane(target, settings, "beta/api");
  await expect(modelBox(settings).locator("option")).toHaveText(
    laneOf("beta/api").catalog.models?.map((held) => held.display_name) ?? [],
  );
  await target.keyboard.press("Escape");
  await ask(target, "Segunda");
  await expect.poll(() => sentSelections(target)).toHaveLength(2);
  expect((await sentSelections(target)).at(-1)).toEqual(startsWith("beta/api"));
  expect(startsWith("beta/api").transport).toBe("api");
  await settled(target);

  // The entry the column starts on goes by its own.
  settings = await openSettings(target);
  await chooseLane(target, settings, "alpha/api");
  await target.keyboard.press("Escape");
  await ask(target, "Tercera");
  await expect.poll(() => sentSelections(target)).toHaveLength(3);
  expect((await sentSelections(target)).at(-1)).toEqual(
    startsWith("alpha/api"),
  );
  expect(startsWith("alpha/api").transport).toBe("api");
});

test("a held entry cannot be chosen, and says why", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  await providerBox(settings).click();
  for (const served of lanes) {
    const why = heldBy(served);
    if (why === null) continue;
    const held = entry(target, wayOf(served));
    await expect(held).toHaveAttribute("aria-disabled", "true");
    await expect(held).toContainText(why);
  }
  // Closing the list leaves the lane in use as it was.
  await target.keyboard.press("Escape");
  await expect(providerBox(settings)).toContainText("Example Alpha");
  await expect(modelBox(settings)).toHaveValue("fixture-deep");
});

test("the efforts offered follow the model of the lane chosen", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  const efforts = effortBox(settings).locator("option");
  const takes = (way: string, model: string) =>
    laneOf(way).catalog.models?.find((held) => held.entry_id === model)
      ?.efforts ?? [];

  // Example Beta by its program: the lane's recommended model takes its efforts.
  await chooseLane(target, settings, "beta/cli");
  await expect(modelBox(settings)).toHaveValue("fixture-ultra");
  await expect(efforts).toHaveText(
    effortWords(takes("beta/cli", "fixture-ultra")),
  );
  await modelBox(settings).selectOption("fixture-tiered");
  await expect(efforts).toHaveText(
    effortWords(takes("beta/cli", "fixture-tiered")),
  );
  // The same name by its other entry: its models take none.
  await chooseLane(target, settings, "beta/api");
  await expect(effortBox(settings)).toHaveCount(0);
  // Example Alpha's models take their own, and one of them none.
  await chooseLane(target, settings, "alpha/api");
  await expect(modelBox(settings)).toHaveValue("fixture-deep");
  await expect(efforts).toHaveText([
    label("desktop.agent.effort_default"),
    ...effortWords(takes("alpha/api", "fixture-deep")),
  ]);
  await modelBox(settings).selectOption("fixture-quick");
  await expect(efforts).toHaveText(
    effortWords(takes("alpha/api", "fixture-quick")),
  );
  await modelBox(settings).selectOption("fixture-plain");
  await expect(effortBox(settings)).toHaveCount(0);
});

/** Everything in `scope` a screen reader or a pointer could meet that says
 * how it is reached: its text, and its names and titles. */
const wording = (scope: Locator) =>
  scope.evaluate((node) => {
    const names = [...node.querySelectorAll("[aria-label],[title]")].flatMap(
      (named) => [
        named.getAttribute("aria-label"),
        named.getAttribute("title"),
      ],
    );
    return [(node as HTMLElement).innerText, ...names].filter(Boolean);
  });

test("no “CLI” appears in the agent column, the list or the settings", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  // The lane that runs a program: the very one the old wording was for.
  await chooseLane(target, settings, "beta/cli");
  const said = [
    ...(await wording(settings)),
    ...(await column(target).evaluate((node) => [
      (node as HTMLElement).innerText,
    ])),
  ];
  await providerBox(settings).click();
  said.push(...(await wording(target.getByRole("listbox"))));
  await target.keyboard.press("Escape");
  await target.keyboard.press("Escape");

  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings"), exact: true })
    .click();
  const providers = column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });
  await expect(providers).toBeVisible();
  await expect(providers.locator("[data-lane]")).toHaveCount(
    FIXTURE_SETTINGS_LANES.length,
  );
  said.push(...(await wording(providers)));

  // What was read is the whole of what a person is shown there.
  const everything = said.join(" ");
  for (const shown of [
    "Example Relay",
    label("desktop.providers.title"),
    label("desktop.providers.cli_unknown"),
    label("desktop.agent.lane_not_configured"),
    label("desktop.agent.effort"),
  ])
    expect(everything).toContain(shown);
  for (const text of said) {
    expect(text).not.toMatch(/\bCLI\b/i);
    expect(text).not.toMatch(/command[- ]line/i);
  }
});

/** The relative luminance of a computed `rgb(...)` colour. */
function luminance(colour: string): number {
  const [red = 0, green = 0, blue = 0] = (colour.match(/[\d.]+/g) ?? [])
    .slice(0, 3)
    .map((part) => {
      const channel = Number(part) / 255;
      return channel <= 0.03928
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4;
    });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

for (const mode of ["light", "dark", "forced colours"] as const) {
  test(`a mark follows the text colour of the list (${mode})`, async ({
    page: target,
  }) => {
    await target.emulateMedia({
      colorScheme: mode === "dark" ? "dark" : "light",
      forcedColors: mode === "forced colours" ? "active" : "none",
    });
    await open(target);
    const settings = await openSettings(target);
    await providerBox(settings).click();
    await expect(target.getByRole("option")).toHaveCount(lanes.length);
    const marks = await target.getByRole("option").evaluateAll((nodes) =>
      nodes.map((node) => {
        const mark = node.querySelector("[data-slot=provider-mark]");
        return {
          provider: mark?.getAttribute("data-provider") ?? "",
          text: mark ? getComputedStyle(mark).color : "",
          fills: [...(mark?.querySelectorAll("path") ?? [])].map(
            (piece) => getComputedStyle(piece).fill,
          ),
        };
      }),
    );
    expect(marks).toHaveLength(lanes.length);
    // The ring has no drawn pieces, so nothing carries a colour of its own.
    for (const mark of marks) expect(mark.fills, mark.provider).toEqual([]);
    // The text colour is the theme's: dark ink on the light list, light on
    // the dark one, so a mark drawn in it can be seen on either.
    const plain = marks.find((mark) => mark.provider === "beta");
    if (mode === "light")
      expect(luminance(plain?.text ?? ""), mode).toBeLessThan(0.3);
    if (mode === "dark")
      expect(luminance(plain?.text ?? ""), mode).toBeGreaterThan(0.5);
  });
}

for (const width of [390, 520]) {
  test.describe(`a window ${width} wide`, () => {
    test.use({
      viewport: { width, height: 844 },
      hasTouch: true,
      isMobile: true,
    });

    const overflowing = (target: Page) =>
      target.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );

    /** Opens the agent, which a window this narrow shows on its own. */
    async function showAgent(target: Page) {
      await open(target);
      await target.locator("[data-rail=agent]").tap();
      await expect(composerButton(target)).toBeVisible();
    }

    test("the settings and the list fit, the list scrolls inside itself, and each entry is finger sized", async ({
      page: target,
    }) => {
      await showAgent(target);
      await composerButton(target).tap();
      const settings = target.getByRole("dialog", {
        name: label("desktop.agent.settings_title"),
      });
      await expect(settings).toBeVisible();
      // Measured once the popover has finished arriving: it grows as it opens.
      await expect
        .poll(async () => {
          const box = await settings.boundingBox();
          return box ? box.x >= 0 && box.x + box.width <= width : false;
        })
        .toBe(true);
      expect(await overflowing(target)).toBe(false);
      expect(
        await settings.evaluate((node) => node.scrollWidth > node.clientWidth),
      ).toBe(false);
      // Every field of it is a fingertip.
      for (const field of await settings.getByRole("combobox").all()) {
        const box = await field.boundingBox();
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(FINGER);
        expect((box?.x ?? -1) + (box?.width ?? 0)).toBeLessThanOrEqual(width);
      }

      await providerBox(settings).tap();
      const list = target.getByRole("listbox");
      await expect(list).toBeVisible();
      await expect(target.getByRole("option")).toHaveCount(lanes.length);
      const edge = (await list.boundingBox())!;
      expect(edge.x).toBeGreaterThanOrEqual(0);
      expect(edge.x + edge.width).toBeLessThanOrEqual(width);
      expect(edge.y).toBeGreaterThanOrEqual(0);
      expect(edge.y + edge.height).toBeLessThanOrEqual(844);
      expect(await overflowing(target)).toBe(false);

      // The entries are a fingertip each, and none is cut off sideways.
      const rows = await target.getByRole("option").evaluateAll((nodes) =>
        nodes.map((node) => {
          const box = node.getBoundingClientRect();
          return {
            way: node.getAttribute("data-way"),
            height: box.height,
            width: box.width,
            clipped: node.scrollWidth > node.clientWidth,
          };
        }),
      );
      for (const row of rows) {
        expect(row.height, row.way ?? "").toBeGreaterThanOrEqual(FINGER);
        expect(row.width, row.way ?? "").toBeGreaterThanOrEqual(FINGER);
        expect(row.clipped, row.way ?? "").toBe(false);
      }

      // More entries than fit: the list scrolls inside itself, down to its
      // last entry, without the window moving or the list growing sideways.
      const scroller = list.locator("[data-radix-select-viewport]");
      const sizes = await scroller.evaluate((node) => ({
        tall: node.scrollHeight > node.clientHeight,
        wide: node.scrollWidth > node.clientWidth,
      }));
      expect(sizes).toEqual({ tall: true, wide: false });
      await scroller.evaluate((node) => {
        node.scrollTop = node.scrollHeight;
      });
      const last = lanes.map(wayOf).at(-1) ?? "";
      await expect
        .poll(() =>
          scroller.evaluate((node, way) => {
            const inside = node.getBoundingClientRect();
            const row = node
              .querySelector(`[data-way="${way}"]`)
              ?.getBoundingClientRect();
            return row
              ? row.top >= inside.top - 1 && row.bottom <= inside.bottom + 1
              : false;
          }, last),
        )
        .toBe(true);
      expect(await overflowing(target)).toBe(false);

      // A tap on an entry that can be chosen chooses it.
      await entry(target, "beta/cli").scrollIntoViewIfNeeded();
      await entry(target, "beta/cli").tap();
      await expect(providerBox(settings)).toHaveText("Example Beta");
      await expect(modelBox(settings).locator("option")).toHaveText(
        laneOf("beta/cli").catalog.models?.map((held) => held.display_name) ??
          [],
      );
      expect(await overflowing(target)).toBe(false);
    });

    test("the settings of the providers fit, each card under a finger", async ({
      page: target,
    }) => {
      await showAgent(target);
      await column(target)
        .getByRole("button", {
          name: label("desktop.agent.settings"),
          exact: true,
        })
        .tap();
      const providers = column(target).getByRole("region", {
        name: label("desktop.providers.title"),
      });
      await expect(providers).toBeVisible();
      await expect(providers.locator("[data-lane]")).not.toHaveCount(0);
      const edge = (await providers.boundingBox())!;
      expect(edge.x).toBeGreaterThanOrEqual(0);
      expect(edge.x + edge.width).toBeLessThanOrEqual(width);
      expect(await overflowing(target)).toBe(false);
      // Nothing of any card reaches past the region, and a card's name is
      // whole: it wraps rather than being cut.
      const spill = await providers.evaluate((region) => {
        const box = region.getBoundingClientRect();
        return [...region.querySelectorAll("*")]
          .filter((node) => {
            const at = node.getBoundingClientRect();
            return at.right > box.right + 1 || at.left < box.left - 1;
          })
          .map((node) => node.tagName.toLowerCase());
      });
      expect(spill).toEqual([]);
      const names = await providers
        .getByRole("heading", { level: 4 })
        .evaluateAll((nodes) =>
          nodes.map((node) => node.scrollWidth > node.clientWidth),
        );
      expect(names).not.toContain(true);
      // Every control of a card is a fingertip.
      const small = await providers.getByRole("button").evaluateAll((nodes) =>
        nodes
          .map((node) => node.getBoundingClientRect())
          .filter((box) => box.height < 44 || box.width < 44)
          .map((box) => `${box.width}x${box.height}`),
      );
      expect(small).toEqual([]);
    });
  });
}
