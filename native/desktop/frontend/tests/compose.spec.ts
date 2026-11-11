import { expect, test } from "@playwright/test";
import {
  described,
  describedGap,
  facts,
  factsGap,
  labelGap,
  labelled,
  listed,
  noted,
} from "../src/shell/compose";
import { listOf } from "../src/shared/lists";
import type { Translate } from "../src/shell/strings";

// Text put together from pieces takes its separators and its order from the
// catalogue templates. The shell's translator reads a generated catalogue a
// plain test has no build for, so these translators hold the templates a
// locale could author: English as shipped, and one that turns each around.
const ENGLISH: Record<string, string> = {
  "desktop.compose.described": "{name}, {detail}",
  "desktop.compose.facts": "{head} · {tail}",
  "desktop.compose.labelled": "{label}: {value}",
  "desktop.compose.noted": "{text} ({note})",
};
const TEMPLATES: Record<string, Record<string, string>> = {
  en: ENGLISH,
  turned: {
    "desktop.compose.described": "{detail} < {name}",
    "desktop.compose.facts": "{tail} | {head}",
    "desktop.compose.labelled": "{value} @ {label}",
    "desktop.compose.noted": "[{note}] {text}",
  },
};

function words(locale: string): Translate {
  const table = TEMPLATES[locale] ?? ENGLISH;
  return Object.assign(
    (key: string, values?: Record<string, string | number>) =>
      (table[key] ?? key).replace(/\{(\w+)\}/g, (whole, name: string) =>
        values && name in values ? String(values[name]) : whole,
      ),
    { locale },
  );
}

test("a label and its value follow the locale's template", () => {
  expect(labelled(words("en"), "Period", "2026-3T")).toBe("Period: 2026-3T");
  expect(labelled(words("turned"), "Period", "2026-3T")).toBe(
    "2026-3T @ Period",
  );
  expect(labelGap(words("en"))).toBe(": ");
  expect(labelGap(words("turned"))).toBe(" @ ");
  expect(noted(words("en"), "Oct 20", "not reported")).toBe(
    "Oct 20 (not reported)",
  );
  expect(noted(words("turned"), "Oct 20", "not reported")).toBe(
    "[not reported] Oct 20",
  );
});

test("facts keep present pieces in order and leave out absent ones", () => {
  const t = words("en");
  expect(facts(t, ["Ready", "3 issues", null, undefined, false, "", 0])).toBe(
    "Ready · 3 issues · 0",
  );
  expect(facts(t, ["Only"])).toBe("Only");
  expect(facts(t, [null, ""])).toBe("");
  expect(facts(words("turned"), ["a", "b", "c"])).toBe("c | b | a");
  expect(factsGap(t)).toBe(" · ");
  expect(factsGap(words("turned"))).toBe(" | ");
});

test("a spoken description adds each detail that applies", () => {
  const t = words("en");
  expect(described(t, "Open", "Modelo 303", null, "Due")).toBe(
    "Open, Modelo 303, Due",
  );
  expect(described(t, "Open")).toBe("Open");
  expect(described(t, "Open", false, "")).toBe("Open");
  expect(described(words("turned"), "Open", "Due")).toBe("Due < Open");
  expect(describedGap(t)).toBe(", ");
  expect(describedGap(words("turned"))).toBe(" < ");
});

test("a list is written the way the locale writes it", () => {
  const items = ["303", "130", "390"];
  expect(listed(words("en"), items)).toBe("303, 130, and 390");
  expect(listed(words("en"), items, "or")).toBe("303, 130, or 390");
  expect(listed(words("en"), items, "plain")).toBe("303, 130, 390");
  expect(listed(words("es"), items)).toBe("303, 130 y 390");
  expect(listed(words("ca"), items)).toBe("303, 130 i 390");
  expect(listed(words("hu"), items)).toBe("303, 130 és 390");
  expect(listed(words("en"), ["303", "130"])).toBe("303 and 130");
  expect(listed(words("en"), ["303"])).toBe("303");
  expect(listed(words("en"), [])).toBe("");
  expect(listed(words("en"), ["303", null, "", false, "130"])).toBe(
    "303 and 130",
  );
});

test("a primitive without a translator lists with the page language", () => {
  expect(listOf("es", ["a", "b", "c"], "plain")).toBe(
    listed(words("es"), ["a", "b", "c"], "plain"),
  );
  expect(listOf(undefined, ["a"], "and")).toBe("a");
});
