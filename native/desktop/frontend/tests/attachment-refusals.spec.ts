import { expect, test } from "@playwright/test";
import {
  groupBarredReads,
  isBarCode,
  refusalKey,
  type BarredRead,
} from "../src/shell/attachmentRefusals";

// How the window gathers the reads one bar refused: once per bar, each file
// named once, and every request kept so each can be answered.

const read = (
  requestId: string,
  name: string | null,
  code: BarredRead["code"] = "profile_not_eligible",
): BarredRead => ({ requestId, code, name });

test("reads refused for one bar are one group naming each file and holding each request", () => {
  expect(
    groupBarredReads([
      read("p-1", "escaneo.pdf"),
      read("p-2", "foto.jpg"),
      read("p-3", "factura.xml"),
      read("p-4", "gastos.xlsx"),
    ]),
  ).toEqual([
    {
      code: "profile_not_eligible",
      names: ["escaneo.pdf", "foto.jpg", "factura.xml", "gastos.xlsx"],
      requestIds: ["p-1", "p-2", "p-3", "p-4"],
    },
  ]);
});

test("a file read twice is named once, and both its requests are answered", () => {
  expect(
    groupBarredReads([read("p-1", "foto.jpg"), read("p-2", "foto.jpg")]),
  ).toEqual([
    {
      code: "profile_not_eligible",
      names: ["foto.jpg"],
      requestIds: ["p-1", "p-2"],
    },
  ]);
});

test("each bar is its own group, in the order a bar first refused a read", () => {
  const groups = groupBarredReads([
    read("p-1", "a.pdf", "gestor_mode"),
    read("p-2", "b.pdf", "profile_not_eligible"),
    read("p-3", "c.pdf", "gestor_mode"),
  ]);
  expect(groups.map((group) => group.code)).toEqual([
    "gestor_mode",
    "profile_not_eligible",
  ]);
  expect(groups[0]?.requestIds).toEqual(["p-1", "p-3"]);
});

test("a read the service gave no name is still answered, and no name is invented", () => {
  expect(groupBarredReads([read("p-1", null)])).toEqual([
    { code: "profile_not_eligible", names: [], requestIds: ["p-1"] },
  ]);
});

test("nothing refused is no group", () => {
  expect(groupBarredReads([])).toEqual([]);
});

test("only the three bars on every off-host read are grouped, and each has its own words", () => {
  for (const code of [
    "gestor_mode",
    "cloud_upload_not_permitted",
    "profile_not_eligible",
  ]) {
    expect(isBarCode(code)).toBe(true);
    expect(refusalKey(code)).toBe(`desktop.agent.attachment_refusal.${code}`);
  }
  for (const code of [
    "document_removed",
    "reference_unknown",
    "not_signed_in",
    "service_failed",
    "anything_else",
  ])
    expect(isBarCode(code)).toBe(false);
});
