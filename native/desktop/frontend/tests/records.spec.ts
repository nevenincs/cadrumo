import { expect, test } from "@playwright/test";
import { DEFAULT_FILTERS, levelRank } from "../src/shell/records";

test("log filtering and level-menu thresholds share severity ordering", () => {
  expect(levelRank("DEBUG")).toBe(0);
  expect(levelRank("INFO")).toBe(1);
  expect(levelRank("WARNING")).toBe(2);
  expect(levelRank("ERROR")).toBe(3);
  expect(levelRank("CRITICAL")).toBe(4);
  expect(levelRank(null)).toBe(levelRank("INFO"));
  expect(DEFAULT_FILTERS.minLevel).toBe(levelRank("INFO"));
});
