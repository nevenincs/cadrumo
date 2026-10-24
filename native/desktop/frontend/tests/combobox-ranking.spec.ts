import { expect, test } from "@playwright/test";
import { optionScore } from "../src/components/ui/combobox";

// How the combobox ranks an option against what was typed. No page is opened.

const score = (search: string, ...words: string[]) =>
  optionScore("id", search, words);

test("a word that starts with the query outranks one that holds it, which outranks scattered letters", () => {
  const software = score("soft", "Software subscriptions");
  const microsoft = score("soft", "Microsoft licences");
  const scattered = score("soft", "Sales of tea");
  expect(software).toBeGreaterThan(microsoft);
  expect(microsoft).toBeGreaterThan(scattered);
  expect(scattered).toBeGreaterThan(0);
  // Letters out of order do not match at all.
  expect(score("soft", "Fuel, tolls")).toBe(0);
});

test("the query is matched without regard to case, on any of the option's words", () => {
  expect(score("FUEL", "Vehicle fuel")).toBe(score("fuel", "Vehicle fuel"));
  expect(score("mobile", "Telefonía", "Mobile phone")).toBe(1);
  expect(score("  ", "Anything")).toBe(1);
});
