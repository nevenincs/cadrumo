import { readFileSync } from "node:fs";
import { windowFixture } from "./windowFixtures";
import type { UserProfile } from "../../src/shell/userProfile";

/** The profile the scenario host serves, as dev.desktop_profile_fixture
 * projected the catalogue persona into the generated fixture. */
const profile = (
  JSON.parse(
    readFileSync(windowFixture("desktop-profile", "userProfile"), "utf8"),
  ) as { en: UserProfile }
).en;

/** What the served profile states at `path`, or an empty string. */
export function profileStated(path: string): string {
  const field = profile.sections
    .flatMap((section) => section.fields)
    .find((entry) => entry.path === path);
  return field?.value ?? "";
}

/** The taxpayer's surnames, which the profile page shows once it has read the profile. */
export const PROFILE_SURNAMES = profileStated("identity.surnames");

/** The name the product heads the profile with, which the page's summary shows. */
export const PROFILE_NAME = profile.name;

/** How many required details the served profile reports missing. */
export const PROFILE_REQUIRED_MISSING = profile.missing_required.length;

/** How many are still missing once the Censo setup has stated the tax ID. */
export const PROFILE_REQUIRED_MISSING_AFTER_CENSO =
  profile.missing_required.filter((path) => path !== "identity.tax_id").length;

/** The titles of the sections the profile schema declares, in order. */
export const PROFILE_SECTION_TITLES = profile.sections.map(
  (section) => section.title,
);

/** The title the served profile gives the section `key`, or an empty string. */
export function profileSectionTitle(key: string): string {
  return profile.sections.find((section) => section.key === key)?.title ?? "";
}
