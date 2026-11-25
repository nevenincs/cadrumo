import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { RENTA_UNIT } from "../src/dev/rentaUnit";
import { MODELO_FIXTURES } from "./support/windowFixtures";

// The Renta stories open their declaration by work unit; a reseed that moves
// the unit would otherwise leave every one of them refused as another
// profile's declaration.
test("the Renta stories open the work unit the seeded Renta form serves", () => {
  const served = JSON.parse(
    readFileSync(new URL("modelo-100-0A-en.json", MODELO_FIXTURES), "utf8"),
  ) as { work_unit_id: string };
  expect(served.work_unit_id).toBe(RENTA_UNIT);
});
