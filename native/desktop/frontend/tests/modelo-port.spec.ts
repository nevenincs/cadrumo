import { expect, test } from "@playwright/test";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ledgerFailure, type FileToken } from "../src/shell/ledger";
import type { HostCall } from "../src/shell/hostCall";
import {
  isModeloDefinition,
  modeloEditBody,
  needsWorkUnit,
} from "../src/shell/modelo";
import {
  MODELO_EDIT_DEFINITIONS,
  MODELO_STORED_SUBJECT_DEFINITIONS,
  type ModeloEditOperatorInputV2,
  type ModeloEditPreflightProjectionV1,
  type ModeloWorkbenchFormProjectionV1,
} from "../src/shell/modeloContract";
import { tauriModelo } from "../src/shell/tauriModelo";
import {
  modeloFixture,
  type ModeloEnvelopes,
  type ModeloShape,
} from "../src/dev/modeloFixture";

// The modelo port: the Tauri adapter's command lines, and the scenario
// host's answers from the envelopes the application's read path produced.
// No page is opened.

type Sent = { command: string; args: object };
function recording(answer: unknown = { kind: "running" }) {
  const sent: Sent[] = [];
  const call = ((command: string, args: object) => {
    sent.push({ command, args });
    return Promise.resolve(answer);
  }) as HostCall;
  return { sent, call };
}

test("each special definition is one the host admits", () => {
  for (const id of [
    ...MODELO_EDIT_DEFINITIONS,
    ...MODELO_STORED_SUBJECT_DEFINITIONS,
  ])
    expect(isModeloDefinition(id)).toBe(true);
  expect(isModeloDefinition("ledger.list")).toBe(false);
  expect(needsWorkUnit("modelo.work.file")).toBe(true);
  expect(needsWorkUnit("modelo.work.calculate")).toBe(false);
});

test("the adapter names the host's commands and its argument names", async () => {
  const { sent, call } = recording();
  const port = tauriModelo(null, call);
  const unit = "a".repeat(64);
  await port.declarations("es");
  await port.form(unit, "en");
  await port.casillaHelp({
    workUnitId: unit,
    casillaId: "03",
    registryRevisionId: "2019-y-siguientes",
    calculationRevisionId: null,
    language: "ca",
  });
  await port.submit("modelo.work.calculate", {
    work_unit_id: unit,
    actor: "operator",
  } as never);
  await port.submit("modelo.work.file", {} as never, unit);
  await port.observe("op");
  await port.answer("op", "d".repeat(64), "reject");
  await port.cancel("op", 4);
  await port.pickFile("evidence", "Receipts");
  await port.saveFile("boe", "AEAT file");
  await port.forgetFiles([]);
  await port.revealFile("t" as FileToken);
  expect(sent).toEqual([
    { command: "modelo_declarations", args: { outputLanguage: "es" } },
    {
      command: "modelo_form",
      args: { workUnitId: unit, outputLanguage: "en" },
    },
    {
      command: "modelo_casilla_help",
      args: {
        workUnitId: unit,
        casillaId: "03",
        registryRevisionId: "2019-y-siguientes",
        calculationRevisionId: null,
        outputLanguage: "ca",
      },
    },
    {
      command: "modelo_submit",
      args: {
        definition: "modelo.work.calculate",
        payload: { work_unit_id: unit, actor: "operator" },
      },
    },
    {
      command: "modelo_submit",
      args: { definition: "modelo.work.file", payload: {}, workUnit: unit },
    },
    { command: "modelo_observe", args: { operation: "op" } },
    {
      command: "modelo_answer",
      args: {
        operation: "op",
        reviewDigest: "d".repeat(64),
        decision: "reject",
      },
    },
    { command: "modelo_cancel", args: { operation: "op", revision: 4 } },
    {
      command: "modelo_files_pick",
      args: { purpose: "evidence", filterLabel: "Receipts" },
    },
    {
      command: "modelo_files_save",
      args: { format: "boe", filterLabel: "AEAT file", suggestedName: null },
    },
    { command: "modelo_files_forget", args: { tokens: [] } },
    { command: "modelo_files_reveal", args: { token: "t" } },
  ]);
});

test("an edit body is zeroed even when it is never sent", async () => {
  const { sent, call } = recording();
  const body = new TextEncoder().encode('{"input_version":2}');
  await expect(
    tauriModelo(null, call).edit("modelo.edit.preflight", body),
  ).rejects.toThrow();
  expect(body.every((byte) => byte === 0)).toBe(true);
  expect(sent).toEqual([]);
});

// The development server's glob is not available here, so the scenario
// reads the same envelopes from disk.
const FIXTURES = fileURLToPath(
  new URL("../src/dev/fixtures/modelo/", import.meta.url),
);
const ENVELOPES: ModeloEnvelopes = Object.fromEntries(
  readdirSync(FIXTURES)
    .filter((name) => name.endsWith(".json"))
    .map((name) => [
      name.slice(0, -".json".length),
      async () => JSON.parse(readFileSync(FIXTURES + name, "utf8")) as unknown,
    ]),
);

function scenario(shape: ModeloShape = "fixture") {
  const calls: string[] = [];
  const port = modeloFixture({
    say: (line) => calls.push(line),
    wait: () => Promise.resolve(),
    signedIn: () => true,
    shape,
    envelopes: ENVELOPES,
  });
  return { port, calls };
}

test("the scenario lists the declarations the envelopes read and opens each one", async () => {
  const { port } = scenario();
  const list = await port.declarations("en");
  const local = list.rows.filter((row) => row.work_unit_id);
  expect(local.map((row) => row.modelo).sort()).toEqual([
    "130",
    "303",
    "347",
    "390",
  ]);
  for (const row of local) {
    const form = await port.form(row.work_unit_id!, "es");
    expect(form.work_unit_id).toBe(row.work_unit_id);
    expect(form.profile_id).toBe(list.profile_id);
    expect(form.form.form.modelo).toBe(row.modelo);
    expect(form.form.form.language).toBe("es");
    // Exactly one admission outcome, as the projection's model requires.
    expect(
      (form.admitted_baseline === null) !== (form.admission_refusal === null),
    ).toBe(true);
  }
});

async function formOf(
  modelo: string,
): Promise<ModeloWorkbenchFormProjectionV1> {
  const { port } = scenario();
  const row = (await port.declarations("en")).rows.find(
    (each) => each.modelo === modelo && each.work_unit_id,
  )!;
  return port.form(row.work_unit_id!, "en");
}

test("a help card is the one read for the form's revision", async () => {
  const { port } = scenario();
  const form = await formOf("130");
  const help = await port.casillaHelp({
    workUnitId: form.work_unit_id,
    casillaId: "03",
    registryRevisionId: form.registry_revision_id,
    calculationRevisionId: form.calculation_revision_id,
    language: "en",
  });
  expect(help.work_unit_id).toBe(form.work_unit_id);
  expect(help.card.casilla_id).toBe("03");
  expect(
    ledgerFailure(
      await port
        .casillaHelp({
          workUnitId: form.work_unit_id,
          casillaId: "99",
          registryRevisionId: form.registry_revision_id,
          calculationRevisionId: null,
          language: "en",
        })
        .catch((error: unknown) => error),
    ).code,
  ).toBe("unavailable");
});

test("a preflight answers the application's reading and zeroes the body", async () => {
  const { port, calls } = scenario();
  const form = await formOf("130");
  const input = {
    input_version: 2,
    output_language: "en",
    submission: {
      baseline: form.admitted_baseline!,
      mutation_family: "calculate",
      lexemes: [],
    },
  } as unknown as ModeloEditOperatorInputV2;
  const body = modeloEditBody(input);
  const outcome = await port.edit("modelo.edit.preflight", body);
  expect(body.every((byte) => byte === 0)).toBe(true);
  expect(outcome.kind).toBe("settled");
  const result = (outcome as { result: ModeloEditPreflightProjectionV1 })
    .result;
  expect(result.work_unit_id).toBe(form.work_unit_id);
  expect(result.parsed.map((entry) => entry.refusal === null)).toEqual([
    true,
    false,
  ]);
  // A call line names the definition, never what was typed.
  expect(calls).toContain("modelo edit modelo.edit.preflight");
  expect(calls.join("\n")).not.toContain("1.234,56");
});

test("the scenario never makes up a result it has no envelope for", async () => {
  const unit = (await formOf("130")).work_unit_id;
  const failure = (shape: ModeloShape) =>
    scenario(shape)
      .port.submit("modelo.work.calculate", {
        work_unit_id: unit,
      } as never)
      .catch((error: unknown) => ledgerFailure(error));
  expect(await failure("fixture")).toEqual({
    code: "unavailable",
    operation_id: null,
  });
  expect((await failure("unknown")) as object).toMatchObject({
    code: "unknown",
  });
  expect((await failure("refused")) as object).toMatchObject({
    code: "refused",
  });
});

test("the scenario refuses a request the host would refuse", async () => {
  const { port } = scenario();
  const unit = (await formOf("130")).work_unit_id;
  const refused = (promise: Promise<unknown>) =>
    promise.then(
      () => null,
      (error: unknown) => ledgerFailure(error).code,
    );
  expect(
    await refused(
      port.submit("modelo.work.calculate", {
        profile_id: "x",
        work_unit_id: unit,
      } as never),
    ),
  ).toBe("invalid");
  // The port's type requires the work unit; a caller that bypasses it is
  // refused as the host refuses it.
  const untyped = port.submit as (...args: unknown[]) => Promise<unknown>;
  expect(await refused(untyped("modelo.work.file", {}))).toBe("invalid");
  expect(
    await refused(
      untyped("modelo.work.calculate", { work_unit_id: unit }, unit),
    ),
  ).toBe("invalid");
  expect(await refused(scenario("unavailable").port.declarations("en"))).toBe(
    "unavailable",
  );
});

test("a renewal answers the application's renewal of the form's baseline", async () => {
  const { port } = scenario();
  const form = await formOf("130");
  const outcome = await port.submit("modelo.edit.renew", {
    baseline: form.admitted_baseline!,
    output_language: "en",
  });
  expect(outcome.kind).toBe("settled");
  if (outcome.kind === "settled") {
    expect(outcome.result.refusal).toBeNull();
    expect(outcome.result.renewed_baseline?.work_unit_id).toBe(
      form.work_unit_id,
    );
  }
});

test("the later shapes read the first quarter's 130 after its check and after recording it", async () => {
  const unit = (await formOf("130")).work_unit_id;
  const checked = await scenario("checked").port.form(unit, "en");
  expect(checked.work_unit_id).toBe(unit);
  expect(checked.form.form.verification).not.toBeNull();
  expect(checked.form.form.issues.map((issue) => issue.attention)).toContain(
    "blocks",
  );
  expect(checked.form.form.edit_closure).toBeNull();
  const filed = await scenario("filed").port.form(unit, "es");
  expect(filed.work_unit_id).toBe(unit);
  expect(filed.form.form.edit_closure).toBe("recorded_as_filed");
  expect(filed.form.form.filing).not.toBeNull();
  // Every other declaration reads as the plain fixture does.
  const other = (await scenario().port.declarations("en")).rows.find(
    (row) => row.modelo === "347" && row.work_unit_id,
  )!;
  expect(
    (await scenario("filed").port.form(other.work_unit_id!, "en")).form.form
      .edit_closure,
  ).toBeNull();
});

test("only a saved file is shown in the file manager", async () => {
  const { port } = scenario();
  const failure = (promise: Promise<void>) =>
    promise.then(
      () => null,
      (error: unknown) => ledgerFailure(error).code,
    );
  const saved = (await port.saveFile("boe", "AEAT file", "130.boe")).files[0]!;
  expect(saved.name).toBe("130.boe");
  expect(await failure(port.revealFile(saved.token))).toBeNull();
  const picked = (await port.pickFile("evidence", "Receipts")).files[0]!;
  expect(await failure(port.revealFile(picked.token))).toBe("invalid");
  await port.forgetFiles([saved.token]);
  expect(await failure(port.revealFile(saved.token))).toBe("file_unavailable");
});
