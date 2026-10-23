// How the profile page lists a profile: its details as rows with a state,
// filtered, grouped and sorted as the person chose, and the few facts the
// summary header names. Nothing here reads or writes; it only arranges what
// the product reported.

import type { ProfileView } from "./layout";
import {
  fieldValue,
  profileText,
  type ProfileField,
  type ProfileSection,
  type UserProfile,
} from "./userProfile";

export type Show = ProfileView["show"];
export type Group = ProfileView["group"];
export type Sort = ProfileView["sort"];

/** One detail as the page lists it. `required`: the product reports it
 * missing; `unset`: empty and not asked for. */
export type Row = {
  id: string;
  section: ProfileSection;
  field: ProfileField;
  state: "required" | "unset" | "filled";
  order: number;
};

export const isEmpty = (field: ProfileField) =>
  field.value === null || field.value === "";

/** A field's key within its section, without the section or its entry. */
export const fieldKey = (section: ProfileSection, field: ProfileField) =>
  field.path.slice(
    section.key.length +
      1 +
      (field.row_index === null ? 0 : field.row_index.length + 1),
  );

/** A repeatable section's entries, by entry. A section without entries is
 * reported as one unindexed group of the fields an entry has: no entry. */
export function entries(section: ProfileSection) {
  const rows = new Map<string, ProfileField[]>();
  for (const field of section.fields)
    if (field.row_index !== null)
      rows.set(field.row_index, [...(rows.get(field.row_index) ?? []), field]);
  return [...rows.entries()];
}

/** The fields an entry of a repeatable section has, once each. */
export const columns = (section: ProfileSection) => [
  ...new Map(
    section.fields.map((field) => [fieldKey(section, field), field]),
  ).values(),
];

/** A section asks for something where one of its own details is required.
 * A repeatable section's requirements hold per entry, and are said there. */
export const requiredSection = (section: ProfileSection) =>
  !section.repeatable && section.fields.some((field) => field.required);

export function rowsOf(data: UserProfile): Row[] {
  const missing = new Set(data.missing_required);
  let order = 0;
  return data.sections.flatMap((section) =>
    section.repeatable
      ? []
      : section.fields.map((field) => ({
          id: field.path,
          section,
          field,
          order: order++,
          state: missing.has(field.path)
            ? ("required" as const)
            : isEmpty(field)
              ? ("unset" as const)
              : ("filled" as const),
        })),
  );
}

/** Every detail the profile holds, entries included, and how many are filled. */
export function counts(data: UserProfile) {
  const fields = data.sections.flatMap((section) =>
    section.repeatable
      ? section.fields.filter((field) => field.row_index !== null)
      : section.fields,
  );
  return {
    total: fields.length,
    filled: fields.filter((field) => !isEmpty(field)).length,
    missing: data.missing_required.length,
  };
}

export function sectionCounts(section: ProfileSection, missing: Set<string>) {
  const fields = section.repeatable
    ? section.fields.filter((field) => field.row_index !== null)
    : section.fields;
  return {
    total: fields.length,
    filled: fields.filter((field) => !isEmpty(field)).length,
    missing: fields.filter((field) => missing.has(field.path)).length,
    entries: section.repeatable ? entries(section).length : 0,
  };
}

/** Whether a detail is marked required: declared so, or reported missing. */
export const marked = (row: Row) =>
  row.field.required || row.state === "required";

export function matches(row: Row, show: Show, needle: string) {
  const shown =
    show === "all" ||
    (show === "unset" && row.state !== "filled") ||
    (show === "required" && marked(row)) ||
    (show === "filled" && row.state === "filled");
  return (
    shown &&
    (!needle ||
      profileText(
        [
          row.section.title,
          row.field.label,
          row.field.masked ? "" : (fieldValue(row.field) ?? ""),
        ].join(" "),
      ).includes(needle))
  );
}

const RANK = { required: 0, unset: 1, filled: 2 } as const;

export function sorted(rows: Row[], sort: Sort, language: string) {
  const collator = new Intl.Collator(language, { sensitivity: "base" });
  return [...rows].sort((a, b) =>
    sort === "alpha"
      ? collator.compare(a.field.label, b.field.label) || a.order - b.order
      : sort === "missing"
        ? RANK[a.state] - RANK[b.state] || a.order - b.order
        : a.order - b.order,
  );
}

/** A value as the page shows it: a masked one is never spelled out. */
export const shownValue = (field: ProfileField) =>
  field.masked && !isEmpty(field) ? "••••" : fieldValue(field);

export const fieldAt = (data: UserProfile, path: string) =>
  data.sections
    .flatMap((section) => section.fields)
    .find((field) => field.path === path);

/** The taxpayer's name: given name and surnames, else the legal name. */
export function nameOf(data: UserProfile) {
  const value = (path: string) => fieldAt(data, path)?.value;
  return (
    [value("identity.name"), value("identity.surnames")]
      .filter(Boolean)
      .join(" ") ||
    value("identity.legal_name") ||
    ""
  );
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => [...part][0]!.toLocaleUpperCase())
    .join("");
}

/** Details whose value the product guards: edited in the AEAT sign-in
 * settings of the workspace, never in the page. */
export const guarded = (field: ProfileField) =>
  field.masked || field.path.startsWith("auth.");
