import { expect, test } from "@playwright/test";
import { optionScore, rankOptions } from "../src/components/ui/combobox";

// How the combobox ranks an option against what was typed. No page is opened.

const score = (search: string, ...words: string[]) =>
  optionScore(search, words);

test("a name that starts with the query outranks a word that does, which outranks one that holds it, then scattered letters", () => {
  const office = score("office", "Office supplies");
  const homeOffice = score("office", "Home-office electricity");
  const microsoft = score("soft", "Microsoft licences");
  const scattered = score("soft", "Sales of tea");
  expect(office).toBeGreaterThan(homeOffice);
  expect(homeOffice).toBeGreaterThan(microsoft);
  expect(microsoft).toBeGreaterThan(scattered);
  expect(scattered).toBeGreaterThan(0);
  // Letters out of order do not match at all.
  expect(score("soft", "Fuel, tolls")).toBe(0);
});

test("the query is matched without regard to case or accents, on any of the option's words", () => {
  expect(score("FUEL", "Vehicle fuel")).toBe(score("fuel", "Vehicle fuel"));
  expect(score("telefono", "Teléfono móvil")).toBe(1);
  expect(score("movil", "Mobile phone", "", "teléfono móvil")).toBeGreaterThan(
    0.5,
  );
  expect(score("  ", "Anything")).toBe(1);
});

const option = (value: string, label: string, group: string) => ({
  value,
  label,
  group,
});

test("scattered matches give way to any better one, and groups and options follow their best score", () => {
  const ranked = rankOptions(
    [
      option("mutual", "Alternative mutual-insurance contribution", "Social"),
      option("ibi", "Property tax (IBI) on home used for business", "Home"),
      option("landline", "Landline phone", "Phone"),
      option("mobile", "Mobile phone", "Phone"),
      option("phones", "Phones and lines", "Phone"),
    ],
    "phone",
  );
  // "Property tax ... home" holds p-h-o-n-e only scattered: it is dropped.
  expect(ranked.map((group) => group.heading)).toEqual(["Phone"]);
  expect(ranked[0]!.options.map((entry) => entry.value)).toEqual([
    "phones",
    "landline",
    "mobile",
  ]);
  // With nothing better, a scattered match is still offered.
  expect(
    rankOptions([option("ibi", "Property tax on home", "Home")], "prtx").map(
      (group) => group.options.map((entry) => entry.value),
    ),
  ).toEqual([["ibi"]]);
  // A group whose best option matches better comes first.
  expect(
    rankOptions(
      [
        option("home", "Home-office electricity", "Home office"),
        option("office", "Office supplies", "Office"),
      ],
      "office",
    ).map((group) => group.heading),
  ).toEqual(["Office", "Home office"]);
});
