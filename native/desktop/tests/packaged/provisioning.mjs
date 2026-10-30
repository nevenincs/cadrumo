// Evidence from the real packaged document and real setup responses. The init
// script observes; it never supplies a response or changes an IPC command.
import { FAIL, PASS } from "./verdicts.mjs";

const localElement = '.setup-dialog [data-setup-element="local_ai"]';
const attribute = (value) => JSON.stringify(value);

// The native catalog command answers busy while the agent prepares its answer;
// the next read retrieves that answer. Other refusals remain failures.
async function readCatalog(session, driver) {
  const answer = await driver.wait(
    async () => {
      const reply = await session.call("agent_provider_catalog");
      return !reply.ok && reply.error?.code === "agent_service_busy"
        ? null
        : reply;
    },
    { timeout: 30000, what: "the agent's catalog read handshake" },
  );
  if (!answer.ok)
    throw new Error(`the model catalog was refused: ${answer.error?.code}`);
  return answer;
}

/** Selection is acceptance-only: every identity and byte figure comes from the agent. */
export function smallestLocalModels(catalog, settings) {
  const keyless = new Set(
    (settings?.providers ?? [])
      .filter((lane) => lane.auth_kind === "none")
      .map((lane) => lane.id),
  );
  const declared = catalog?.kind === "declared";
  const lanes = declared ? catalog.catalog?.providers : catalog?.providers;
  const candidates = (lanes ?? [])
    .flatMap((entry) => {
      const lane = declared
        ? entry.id
        : `${entry.provider_id}_${entry.transport}`;
      if (!keyless.has(lane) || (!declared && entry.model_source !== "catalog"))
        return [];
      const recommended = Object.values(
        (declared ? entry : entry.catalog)?.recommended ?? {},
      );
      return ((declared ? entry.models : entry.catalog?.models) ?? []).flatMap(
        (model) => {
          const id = declared ? model.id : model.model;
          return id && Number.isFinite(model.size_bytes) && model.size_bytes > 0
            ? [
                {
                  lane,
                  provider: declared ? entry.provider : entry.provider_id,
                  model: id,
                  sizeBytes: model.size_bytes,
                  recommended: recommended.includes(id),
                },
              ]
            : [];
        },
      );
    })
    .sort(
      (a, b) =>
        a.sizeBytes - b.sizeBytes ||
        a.lane.localeCompare(b.lane) ||
        a.model.localeCompare(b.model),
    );
  if (!candidates.length)
    throw new Error(
      "the agent catalog names no keyless model with a known positive size",
    );
  return {
    ...candidates[0],
    customCandidate: candidates.find((model) => !model.recommended) ?? null,
  };
}

export async function openLocalAi(driver) {
  await driver.openComponents();
  const opener = driver.session.page.locator(`${localElement} > button`);
  if ((await opener.getAttribute("aria-expanded")) !== "true")
    await opener.click();
  await driver.session.page
    .locator(`${localElement} [data-testid="local-ai"]`)
    .waitFor({ state: "visible", timeout: 30000 });
  // The catalogue and the person's list load when the dropdown mounts.
  // A missing row is meaningful only after that real read has rendered its form.
  await driver.session.page
    .locator(`${localElement} [data-slot="local-model-add"]`)
    .first()
    .waitFor({ state: "visible", timeout: 30000 });
}

/** Read real catalogue metadata, open the dropdown and list its smallest model. */
export async function prepareSmallestModel({ session, driver }) {
  const [catalog, settings] = await Promise.all([
    readCatalog(session, driver),
    session.call("provider_settings_status"),
  ]);
  if (!catalog.ok || !settings.ok)
    throw new Error(
      "the real model catalog or provider settings could not be read",
    );
  const selected = smallestLocalModels(catalog.value, settings.value);
  await openLocalAi(driver);
  await session.page
    .locator(`${localElement} [data-slot="local-model-add"]`)
    .first()
    .waitFor({ state: "visible", timeout: 30000 });
  const row = session.page
    .locator(`${localElement} [data-model=${attribute(selected.model)}]`)
    .first();
  if (!(await row.count()))
    await addCustomLocalModel({ session, driver, ...selected });
  await row.waitFor({ state: "visible", timeout: 30000 });
  return selected;
}

/** Add through the existing form; readback proves the person's list changed. */
export async function addCustomLocalModel({ session, driver, lane, model }) {
  await openLocalAi(driver);
  // LocalModels renders one form for each keyless lane, in catalogue order.
  const settings = await session.call("provider_settings_status");
  const catalog = await readCatalog(session, driver);
  if (!settings.ok || !catalog.ok)
    throw new Error("local lane metadata could not be read");
  const answer = catalog.value;
  const lanes =
    answer.kind === "declared" ? answer.catalog.providers : answer.providers;
  const keyless = new Set(
    settings.value.providers
      .filter((entry) => entry.auth_kind === "none")
      .map((entry) => entry.id),
  );
  const ids = (lanes ?? [])
    .filter((entry) =>
      answer.kind === "declared"
        ? entry.models?.length
        : entry.model_source === "catalog" && entry.catalog?.models?.length,
    )
    .map((entry) =>
      answer.kind === "declared"
        ? entry.id
        : `${entry.provider_id}_${entry.transport}`,
    )
    .filter((id) => keyless.has(id));
  const index = ids.indexOf(lane);
  if (index < 0) throw new Error("the selected lane has no local model form");
  const form = session.page
    .locator(`${localElement} [data-slot="local-model-add"]`)
    .nth(index);
  await form.locator("input").fill(model);
  await form.locator('button[type="submit"]').click();
  await driver.wait(
    async () => {
      const read = await session.call("agent_local_models");
      return (
        read.ok &&
        read.value.state === "readable" &&
        read.value.models.some(
          (entry) => entry.lane === lane && entry.model === model,
        )
      );
    },
    { timeout: 30000, what: "the custom model's real list readback" },
  );
}

/** Start the model's download using its own row, preserving real plan review. */
export async function downloadLocalModel({ session, driver, model }) {
  await openLocalAi(driver);
  if (
    (await session.page
      .locator(`${localElement} [data-model=${attribute(model)}]`)
      .first()
      .getAttribute("data-installed")) === "true"
  )
    throw new Error(
      "the model is already installed; its download was not exercised",
    );
  const before = await driver.lastSequence();
  await session.page
    .locator(`${localElement} [data-model=${attribute(model)}]`)
    .first()
    .locator("button")
    .first()
    .click();
  const start = await driver.wait(
    async () =>
      (await driver.setupCommands(before)).find(
        (entry) => entry.cmd === "desktop_setup_start" && entry.ok !== null,
      ),
    { timeout: 30000, what: "the model row's setup start" },
  );
  if (!start.ok || start.args?.download?.model !== model)
    throw new Error(
      "the model row did not start the selected model's real setup",
    );
  return start;
}

/** Remove through the model row; readback proves both bytes and custom entry are gone. */
export async function removeCustomLocalModel({ session, driver, lane, model }) {
  await openLocalAi(driver);
  const row = session.page
    .locator(
      `${localElement} [data-model=${attribute(model)}][data-added="true"]`,
    )
    .first();
  await row.locator("button").last().click();
  await driver.wait(
    async () => {
      const read = await session.call("agent_local_models");
      return (
        read.ok &&
        read.value.state === "readable" &&
        !read.value.models.some(
          (entry) => entry.lane === lane && entry.model === model,
        ) &&
        !(await row.count())
      );
    },
    {
      timeout: 60000,
      what: "the removed custom model's list and rendered row",
    },
  );
}

/** Caller opens agent settings; the provider disclosure is navigated by its real identity. */
export async function assertLocalAiShared({
  session,
  driver,
  provider,
  openAgentSettings,
}) {
  await openLocalAi(driver);
  const panel = session.page.locator(
    `${localElement} [data-testid="local-ai"]`,
  );
  const panelProgram = await panel
    .locator('[data-setup-row="local_ai"]')
    .count();
  const panelModels = await panel.locator('[data-slot="local-models"]').count();
  await driver.closeDialog();
  await openAgentSettings();
  const group = session.page.locator(`[data-provider=${attribute(provider)}]`);
  const details = group.locator("details").first();
  if ((await details.getAttribute("open")) === null)
    await details.locator("summary").first().click();
  const shared = group.getByTestId("local-ai");
  await shared.waitFor({ state: "visible", timeout: 30000 });
  return verdict(
    panelProgram === 1 &&
      panelModels > 0 &&
      (await shared.count()) === 1 &&
      (await shared.locator('[data-setup-row="local_ai"]').count()) === 1 &&
      (await shared.locator('[data-slot="local-models"]').count()) === 1,
    "the provisioning dropdown and agent provider settings expose the shared local AI component by test id",
    {
      provider,
      testId: "local-ai",
      panelProgram,
      panelModels,
      agentProgram: await shared.locator('[data-setup-row="local_ai"]').count(),
      agentModels: await shared.locator('[data-slot="local-models"]').count(),
    },
  );
}

const verdict = (ok, detail, data) => ({
  verdict: ok ? PASS : FAIL,
  detail,
  ...(data === undefined ? {} : { data }),
});

/** Installed before the shell's scripts by Playwright, in the shell only. */
export function observeProvisioning() {
  if (window.top !== window || window.__provisioningEvidence) return;
  const evidence = { states: [], reads: [], progress: [], overflow: false };
  Object.defineProperty(window, "__provisioningEvidence", { value: evidence });
  const open = (selector) => {
    const node = document.querySelector(selector);
    return !!node && node.getClientRects().length > 0;
  };
  const record = () => {
    for (const figure of document.querySelectorAll(
      ".setup-dialog [data-setup-progress]",
    )) {
      const bar = figure.querySelector('[role="progressbar"]');
      const completed = bar ? Number(bar.getAttribute("aria-valuenow")) : null;
      const displayedBytes = [
        ...figure.querySelectorAll("p > span:not([data-setup-sentence])"),
      ]
        .map((node) => node.textContent.trim())
        .filter(Boolean)
        .join(" ");
      const sample = { completed, displayedBytes };
      if (JSON.stringify(evidence.progress.at(-1)) !== JSON.stringify(sample)) {
        if (evidence.progress.length >= 4096) evidence.overflow = true;
        else evidence.progress.push(sample);
      }
    }
    const state = {
      signIn: open('.sign-in[data-state="open"]'),
      panel: open('.setup-dialog[data-state="open"]'),
    };
    const last = evidence.states.at(-1);
    if (last && last.signIn === state.signIn && last.panel === state.panel)
      return;
    if (evidence.states.length >= 2000) evidence.overflow = true;
    else evidence.states.push(state);
  };
  new MutationObserver(record).observe(document, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: [
      "data-state",
      "style",
      "class",
      "hidden",
      "aria-valuenow",
    ],
  });
  record();
  window.addEventListener("packaged-setup-snapshot", (event) => {
    const value = event.detail;
    if (evidence.reads.length >= 2000) evidence.overflow = true;
    else evidence.reads.push(structuredClone(value));
  });
}

export async function startupObservation(session) {
  return session.shell(() => {
    const e = window.__provisioningEvidence;
    return e ? structuredClone(e) : null;
  });
}

/** Ordered mutations prove the panel did not overlap sign-in and opened after it. */
export function startupPanelVerdict(observation) {
  const states = observation?.states;
  if (!Array.isArray(states) || observation.overflow)
    return verdict(false, "startup observation is missing or overflowed");
  const held = states.findIndex((s) => s.signIn);
  if (held < 0) return verdict(false, "the sign-in dialog was never observed");
  if (states.some((s) => s.signIn && s.panel))
    return verdict(false, "the provisioning panel overlapped sign-in");
  const opened = states.findIndex(
    (s, index) => index > held && !s.signIn && s.panel,
  );
  if (opened < 0)
    return verdict(false, "the provisioning panel did not open after sign-in");
  const first = observation.reads?.find(
    (value) => value?.snapshot && Object.hasOwn(value.snapshot, "complete"),
  );
  if (
    !first ||
    first.failed ||
    first.snapshot === undefined ||
    first.snapshot === null
  )
    return verdict(false, "the first real setup snapshot was not captured");
  return verdict(
    true,
    "the panel stayed closed during sign-in and opened afterward",
    {
      firstComplete: first.snapshot.complete,
      nullFirstExercised: first.snapshot.complete === null,
    },
  );
}

/** A separate result: a real run need not happen to return an initially unread snapshot. */
export function firstNullSnapshotVerdict(observation) {
  const first = observation?.reads?.find(
    (value) => value?.snapshot && Object.hasOwn(value.snapshot, "complete"),
  );
  if (!first || first.failed || first.snapshot == null)
    return verdict(false, "the first real setup snapshot was not captured");
  if (first.snapshot.complete !== null)
    return verdict(
      false,
      "the first real snapshot was already decided; complete:null was not exercised",
    );
  return startupPanelVerdict(observation);
}

/** Read the visible panel without guessing localized labels. */
export async function panelObservation(session) {
  return session.shell(() => {
    const panel = document.querySelector('.setup-dialog[data-state="open"]');
    if (!panel) return null;
    const text = (node) => node?.textContent?.trim() ?? "";
    const components = panel.querySelector(".setup-components");
    const elements = components
      ? [...components.children].map((node) => {
          const row = node.matches("[data-setup-row]") ? node : null;
          const sentences = [...node.querySelectorAll("[data-setup-sentence]")]
            .filter(
              (sentence) =>
                !sentence.closest("[data-setup-row]") ||
                sentence.closest("[data-setup-row]") === row,
            )
            .map(text);
          return {
            item:
              node.getAttribute("data-setup-row") ??
              node.getAttribute("data-setup-element"),
            expandable: node.hasAttribute("data-setup-element"),
            expanded: node.getAttribute("data-expanded") === "true",
            sentences,
            buttons: [...node.querySelectorAll("button")]
              .filter((button) => !button.hidden)
              .map((button) => ({
                label: button.getAttribute("aria-label") || text(button),
                disabled: button.disabled,
              })),
            size: text(node.querySelector("[data-setup-size]")),
            nested:
              node.hasAttribute("data-setup-element") &&
              node.getAttribute("data-expanded") === "true"
                ? [...node.querySelectorAll("[data-setup-row]")].map(
                    (part) => ({
                      item: part.getAttribute("data-setup-row"),
                      sentences: [
                        ...part.querySelectorAll("[data-setup-sentence]"),
                      ].map(text),
                      actions: [...part.querySelectorAll("button")]
                        .filter((button) => button.getClientRects().length > 0)
                        .map((button) => ({
                          label: text(button),
                          disabled: button.disabled,
                        })),
                    }),
                  )
                : [],
          };
        })
      : [];
    return {
      elements,
      close: [...panel.querySelectorAll(":scope > button[aria-label]")].map(
        (button) => button.getAttribute("aria-label"),
      ),
    };
  });
}

/** Compare the engine's rows to the panel, including each row's own action. */
export function panelRowsVerdict(snapshot, panel) {
  const rows = snapshot?.rows;
  if (!Array.isArray(rows) || rows.length === 0 || !panel)
    return verdict(false, "the engine rows or visible panel are missing");
  const expected = rows.map((row) => row.item);
  const shown = panel.elements.map((element) => element.item);
  if (
    new Set(expected).size !== expected.length ||
    expected.length !== shown.length ||
    expected.some((item, i) => item !== shown[i])
  )
    return verdict(
      false,
      "the panel does not list each engine row once in order",
      { expected, shown },
    );
  if (panel.close.length !== 1 || !panel.close[0])
    return verdict(
      false,
      "the panel does not have exactly one labelled top close control",
    );
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const element = panel.elements[i];
    if (
      !element.expandable &&
      (element.sentences.length !== 1 || !element.sentences[0])
    )
      return verdict(false, `${row.item} does not state its status once`);
    if (
      element.expandable &&
      !element.expanded &&
      (element.sentences.length !== 1 || !element.sentences[0])
    )
      return verdict(
        false,
        `${row.item} does not state its collapsed status once`,
      );
    if (
      !element.expandable &&
      row.recovery !== null &&
      !element.buttons.some((button) => button.label && !button.disabled)
    )
      return verdict(false, `${row.item} has no enabled action of its own`);
    if (
      element.expandable &&
      !element.buttons.some((button) => button.label && !button.disabled)
    )
      return verdict(false, `${row.item} has no enabled expansion control`);
    if (element.expandable && element.expanded) {
      if (element.sentences.length !== 0)
        return verdict(
          false,
          `${row.item} repeats its status outside the expanded program row`,
        );
      const [program] = element.nested ?? [];
      if (
        element.nested?.length !== 1 ||
        program.item !== row.item ||
        program.sentences.length !== 1 ||
        !program.sentences[0]
      )
        return verdict(
          false,
          `${row.item}'s expanded program does not state its status once`,
        );
      if (
        row.recovery !== null &&
        !program.actions.some((button) => button.label && !button.disabled)
      )
        return verdict(
          false,
          `${row.item}'s expanded program has no enabled action`,
        );
    }
  }
  return verdict(
    true,
    "each engine element is listed with its own status and control; the panel has a close control",
  );
}

/** The bytes label is absent until bytes move; a part uses its own total. */
export function progressVerdict({
  completed,
  total,
  displayedBytes,
  expectedTotalText,
}) {
  if (completed == null || completed <= 0 || total == null || total <= 0)
    return verdict(
      !displayedBytes,
      "no byte count before bytes and a known total",
    );
  return verdict(
    Boolean(expectedTotalText) &&
      typeof displayedBytes === "string" &&
      displayedBytes.includes(expectedTotalText),
    "byte progress names the part's own known total",
  );
}

/** The byte label is the non-status span in a rendered progress figure. */
export async function progressObservation(session, selector) {
  return session.shell((selector) => {
    const figure = document
      .querySelector(selector)
      ?.querySelector("[data-setup-progress]");
    if (!figure) return null;
    const labels = [
      ...figure.querySelectorAll("p > span:not([data-setup-sentence])"),
    ]
      .map((span) => span.textContent.trim())
      .filter(Boolean);
    const bar = figure.querySelector('[role="progressbar"]');
    return {
      displayedBytes: labels.join(" "),
      value: bar?.getAttribute("aria-valuenow") ?? null,
    };
  }, selector);
}

/** Parts are checked against their own expected formatted sizes, not the aggregate. */
export function partSizesVerdict(expected, rendered) {
  if (
    !Array.isArray(expected) ||
    expected.length === 0 ||
    !Array.isArray(rendered)
  )
    return verdict(false, "no part size evidence");
  if (expected.length !== rendered.length)
    return verdict(false, "the rendered part count differs from the plan");
  for (let i = 0; i < expected.length; i += 1) {
    const part = expected[i];
    const actual = rendered[i];
    if (
      part.part !== actual.part ||
      (part.sizeBytes > 0 &&
        (!part.sizeText || !actual.text.includes(part.sizeText)))
    )
      return verdict(false, `part ${part.part} does not show its own size`);
  }
  return verdict(true, "each rendered plan part shows its own known size");
}

export async function planPartsObservation(session, item) {
  return session.shell((item) => {
    const entry = [
      ...document.querySelectorAll(".setup-dialog [data-setup-plan]"),
    ].find((node) => node.getAttribute("data-setup-plan") === item);
    return entry
      ? [...entry.querySelectorAll("[data-setup-part]")].map((node) => ({
          part: node.getAttribute("data-setup-part"),
          text: node.textContent.trim(),
        }))
      : null;
  }, item);
}

export async function assertPlanSizes(session, snapshot) {
  const evidence = [];
  const locale = await session.shell(() => document.documentElement.lang);
  for (const run of snapshot.runs.filter((run) => run.stage === "review")) {
    await session.page
      .locator(`.setup-dialog [data-setup-plan="${run.item}"]`)
      .waitFor({ state: "visible", timeout: 30000 });
    const expected = run.review.entries
      .flatMap((entry) => entry.parts)
      .map((part) => {
        let value = part.download_bytes;
        let index = 0;
        const units = ["byte", "kilobyte", "megabyte", "gigabyte"];
        while (value >= 1000 && index < units.length - 1) {
          value /= 1000;
          index += 1;
        }
        return {
          part: part.part,
          sizeBytes: part.download_bytes,
          sizeText:
            part.download_bytes === null
              ? null
              : new Intl.NumberFormat(locale, {
                  style: "unit",
                  unit: units[index],
                  unitDisplay: "short",
                  maximumFractionDigits: index > 0 && value < 10 ? 1 : 0,
                }).format(value),
        };
      });
    if (expected.length === 0) continue;
    const rendered = await planPartsObservation(session, run.item);
    const result = partSizesVerdict(expected, rendered);
    evidence.push({ item: run.item, ...result });
  }
  return verdict(
    evidence.length > 0 && evidence.every((entry) => entry.verdict === PASS),
    "known download sizes are rendered for each real plan part",
    evidence,
  );
}

export async function assertPreByteProgress(session) {
  const observed = await startupObservation(session);
  const samples = observed?.progress ?? [];
  const beforeBytes = samples.filter(
    (sample) => sample.completed === null || sample.completed === 0,
  );
  return verdict(
    !observed?.overflow &&
      beforeBytes.length > 0 &&
      beforeBytes.every((sample) => !sample.displayedBytes) &&
      samples.every(
        (sample) =>
          !/(?:^|\s)0(?:[.,]0+)?\s*(?:B|bytes)\b/.test(sample.displayedBytes),
      ),
    "real progress shows no byte count before its first byte",
    { beforeBytes },
  );
}

export async function installSmallestModel({ driver, lane, model }) {
  const session = driver.session;
  await openLocalAi(driver);
  if (
    !(await session.page
      .locator(`${localElement} [data-model=${attribute(model)}]`)
      .count())
  )
    await addCustomLocalModel({ session, driver, lane, model });
  const previous = (await driver.read()).snapshot?.runs?.find(
    (run) => run.item === "local_ai",
  )?.operation_id;
  await downloadLocalModel({ session, driver, lane, model });
  const approved = new Set();
  const settled = await driver.wait(
    async () => {
      const setup = await driver.read();
      const run = setup.snapshot?.runs?.find(
        (entry) => entry.item === "local_ai",
      );
      if (!run || run.operation_id === previous) return null;
      if (
        run.stage === "review" &&
        run.review &&
        !approved.has(run.review.plan_digest)
      ) {
        approved.add(run.review.plan_digest);
        await session.page
          .locator(`${localElement} [data-setup-review] button`)
          .last()
          .click();
      }
      return run.stage === "settled" ? run : null;
    },
    {
      timeout: 30 * 60 * 1000,
      what: "the selected model's real setup completion",
    },
  );
  if (["completed", "nothing_to_do"].includes(settled.outcome))
    await session.page
      .locator(
        `${localElement} [data-model=${attribute(model)}][data-installed="true"]`,
      )
      .first()
      .waitFor({ state: "visible", timeout: 30000 });
  return verdict(
    ["completed", "nothing_to_do"].includes(settled.outcome),
    "the selected catalog model's download settled successfully",
    { lane, model, run: settled },
  );
}

/** The real plan must distinguish the program from this model's download. */
export function localAiPartsVerdict(review, model, rendered) {
  const entry = review?.entries?.find((entry) => entry.item === "local_ai");
  const program = entry?.parts?.find((part) => part.part === "program");
  const download = entry?.parts?.find(
    (part) => part.model === model && part.part !== "program",
  );
  const shown =
    Array.isArray(rendered) &&
    rendered.some((part) => part.part === "program") &&
    rendered.some(
      (part) => part.part === download?.part && part.text.includes(model),
    );
  return verdict(
    Boolean(program && download && shown),
    "the local AI plan renders separate program and selected model steps",
    { model, parts: entry?.parts ?? [], rendered },
  );
}

export async function removeSmallestModel({ driver, lane, model }) {
  const session = driver.session;
  await openLocalAi(driver);
  const row = session.page
    .locator(`${localElement} [data-model=${attribute(model)}]`)
    .first();
  await row.waitFor({ state: "visible", timeout: 30000 });
  if ((await row.getAttribute("data-installed")) !== "true")
    return verdict(
      false,
      "the selected model was not shown as installed before removal",
    );
  const before = await driver.lastSequence();
  await row.locator("button").last().click();
  const removal = await driver.wait(
    async () =>
      (await driver.setupCommands(before)).find(
        (entry) =>
          entry.cmd === "desktop_setup_remove_model" && entry.ok !== null,
      ),
    { timeout: 60000, what: "the model row's real removal response" },
  );
  if (!removal.ok)
    return verdict(false, "the selected model's removal was refused", removal);
  await driver.wait(
    async () =>
      !(await row.count()) ||
      (await row.getAttribute("data-installed")) !== "true",
    { timeout: 30000, what: "the model's installed marker to clear" },
  );
  return verdict(true, "the selected model was removed through its own row", {
    lane,
    model,
    removal,
  });
}

/** Settings has one setup section and no other section or setup control. */
export function settingsVerdict(evidence) {
  if (
    !evidence ||
    evidence.sections !== 2 ||
    evidence.provisioningSections !== 1 ||
    evidence.statuses !== 1 ||
    !evidence.statusText ||
    evidence.provisioningButtons !== 1 ||
    evidence.windowButtons !== 1 ||
    evidence.extraSetupControls !== 0
  )
    return verdict(
      false,
      "Settings does not have exactly one provisioning section, status and button",
      evidence,
    );
  if (
    !evidence.panelOpened ||
    !evidence.panelClosed ||
    evidence.panelVerdict?.verdict !== PASS
  )
    return verdict(
      false,
      "Settings did not open and close the engine's provisioning panel",
      evidence,
    );
  return verdict(
    true,
    "Settings has one provisioning section and opens the engine's panel",
    evidence,
  );
}

export async function runSettingsAcceptance(session) {
  const page = session.page;
  const panel = page.locator('.setup-dialog[data-state="open"]');
  if (await panel.isVisible()) {
    await panel.locator(":scope > button[aria-label]").click();
    await panel.waitFor({ state: "hidden", timeout: 30000 });
  }
  const settings = page.locator('.settings[data-state="open"]');
  if (!(await settings.isVisible()))
    await page.locator('[data-rail="settings"]').click();
  await settings.waitFor({ state: "visible", timeout: 30000 });
  const evidence = await session.shell(() => {
    const settings = document.querySelector('.settings[data-state="open"]');
    const sections = [...settings.querySelectorAll(":scope > section")];
    const provisioning = settings.querySelector("[data-settings-provisioning]");
    const status = provisioning?.querySelector(
      "[data-settings-provisioning-status]",
    );
    const other = sections.filter(
      (section) => !section.hasAttribute("data-settings-provisioning"),
    );
    return {
      sections: sections.length,
      provisioningSections: settings.querySelectorAll(
        "[data-settings-provisioning]",
      ).length,
      statuses: settings.querySelectorAll("[data-settings-provisioning-status]")
        .length,
      statusText: status?.textContent.trim() ?? "",
      provisioningButtons: provisioning?.querySelectorAll("button").length ?? 0,
      windowButtons: other.reduce(
        (count, section) =>
          count + section.querySelectorAll('button:not([role="radio"])').length,
        0,
      ),
      extraSetupControls: settings.querySelectorAll(
        '[data-setup-row], [data-setup-element], [data-slot="local-ai"], [data-slot="local-models"], [data-setup-offer]',
      ).length,
    };
  });
  // Read only after the panel opens: the engine may publish a newer snapshot.
  await settings.locator("[data-settings-provisioning] button").click();
  await panel.waitFor({ state: "visible", timeout: 30000 });
  const read = await session.call("desktop_setup_read");
  evidence.panelOpened = await panel.isVisible();
  evidence.panelVerdict = panelRowsVerdict(
    read.ok ? read.value?.snapshot : null,
    await panelObservation(session),
  );
  await panel.locator(":scope > button[aria-label]").click();
  await panel.waitFor({ state: "hidden", timeout: 30000 });
  evidence.panelClosed = !(await panel.isVisible());
  return settingsVerdict(evidence);
}

/** A real confirmation must stay absent after the accepted removal and throughout reinstall. */
export function removalVerdict(evidence) {
  if (
    !evidence?.confirmationShown ||
    evidence.removal?.cmd !== "desktop_setup_remove" ||
    evidence.removal?.args?.removal !== "local_ai" ||
    !evidence.removal?.ok ||
    !evidence.removed ||
    !evidence.absentBefore ||
    !evidence.sawLive ||
    evidence.confirmationReappeared ||
    !evidence.absentAfter ||
    evidence.reinstall?.verdict !== PASS ||
    !evidence.modelInstalled
  )
    return verdict(
      false,
      "program removal or reinstall did not prove the confirmation remained dismissed",
      evidence,
    );
  return verdict(
    true,
    "the program was removed and restored with the model; its old confirmation stayed dismissed",
    evidence,
  );
}

export async function runRemovalAcceptance({ driver, model }) {
  const session = driver.session;
  const page = session.page;
  await openLocalAi(driver);
  const modelRow = page
    .locator(`${localElement} [data-model=${attribute(model.model)}]`)
    .first();
  await modelRow.waitFor({ state: "visible", timeout: 30000 });
  if ((await modelRow.getAttribute("data-installed")) !== "true")
    return verdict(
      false,
      "the selected model was not installed before program removal",
    );
  const beforeSetup = await driver.read();
  const beforeRow = beforeSetup.snapshot?.rows?.find(
    (row) => row.item === "local_ai",
  );
  if (!beforeRow || !["ready", "stale"].includes(beforeRow.state))
    return verdict(
      false,
      "the local AI was not usable before program removal",
      { beforeRow },
    );
  const offer = page.locator(`${localElement} [data-setup-removal="local_ai"]`);
  await offer.waitFor({ state: "visible", timeout: 30000 });
  // Remove the program and selected model together so the model's own
  // Download action restores the same catalog selection.
  const offers = offer.locator("button");
  if ((await offers.count()) !== 2)
    return verdict(
      false,
      "program-only removal is not offered beside whole removal",
    );
  await offers.first().click();
  const question = offer.locator(":scope > p");
  await question.waitFor({ state: "visible", timeout: 30000 });
  const confirmationShown = Boolean((await question.innerText()).trim());
  const before = await driver.lastSequence();
  await offer.locator("button").first().click();
  const removal = await driver.wait(
    async () =>
      (await driver.setupCommands(before)).find(
        (entry) => entry.cmd === "desktop_setup_remove" && entry.ok !== null,
      ),
    { timeout: 120000, what: "the program removal response" },
  );
  if (!removal.ok || removal.args?.removal !== "local_ai")
    return verdict(
      false,
      "the program removal command was refused or named another removal",
      { removal },
    );
  const removed = await driver.wait(
    async () => {
      const setup = await driver.read();
      const row = setup.snapshot?.rows?.find(
        (item) => item.item === "local_ai",
      );
      return row && !["ready", "stale"].includes(row.state) ? row : null;
    },
    { timeout: 120000, what: "the engine's reading after program removal" },
  );
  await question.waitFor({ state: "hidden", timeout: 30000 });
  await session.shell(() => {
    const state = { reappeared: false, sawLive: false };
    const question = () =>
      document.querySelector(
        '[data-setup-element="local_ai"] [data-setup-removal="local_ai"] > p',
      );
    const inspect = () => {
      if (question()) state.reappeared = true;
    };
    const observe = new MutationObserver(inspect);
    observe.observe(document, {
      subtree: true,
      childList: true,
      attributes: true,
    });
    const snapshot = (event) => {
      const value = event.detail?.snapshot ?? event.detail;
      if (
        value?.runs?.some(
          (run) => run.item === "local_ai" && run.stage !== "settled",
        )
      )
        state.sawLive = true;
    };
    window.addEventListener("packaged-setup-snapshot", snapshot);
    window.__removalEvidence = {
      state,
      stop: () => {
        inspect();
        observe.disconnect();
        window.removeEventListener("packaged-setup-snapshot", snapshot);
        return state;
      },
    };
    inspect();
  });
  const absentBefore = !(await question.isVisible());
  let reinstall;
  let observed;
  try {
    reinstall = await installSmallestModel({ driver, ...model });
    await driver.wait(
      async () => (await modelRow.getAttribute("data-installed")) === "true",
      {
        timeout: 60000,
        what: "the selected model's installed marker after reinstall",
      },
    );
  } finally {
    observed = await session.shell(() => {
      const result = window.__removalEvidence.stop();
      delete window.__removalEvidence;
      return result;
    });
  }
  return removalVerdict({
    confirmationShown,
    removal,
    removed: Boolean(removed),
    absentBefore,
    sawLive: observed.sawLive,
    confirmationReappeared: observed.reappeared,
    absentAfter: !(await question.isVisible()),
    reinstall,
    modelInstalled: (await modelRow.getAttribute("data-installed")) === "true",
  });
}
