import { expect, test } from "@playwright/test";
import {
  nameProblem,
  passwordProblem,
  targetOf,
  type ProfileList,
} from "../src/shell/profiles";
import { canSignIn, phaseOf } from "../src/shell/signIn";
import type { SignInStatus } from "../src/ipc/contract";

// The rules of choosing and creating a profile, checked at their
// boundaries. No page is opened.

const list = (
  names: string[],
  active: number | null = null,
  complete = true,
): ProfileList => ({
  profiles: names.map((name, index) => ({ name, active: index === active })),
  complete,
});

const status = (change: Partial<SignInStatus> = {}): SignInStatus => ({
  supported: true,
  state: "absent",
  active_profile: null,
  runtimeAvailable: true,
  refusal: null,
  ...change,
});

test("a password goes to the chosen profile, else the selected one, else the only one", () => {
  const several = list(["Ana", "Berta", "Carles"], 1);
  expect(targetOf(several, null)?.name).toBe("Berta");
  expect(targetOf(several, "Carles")?.name).toBe("Carles");
  // A choice that is no longer listed is not a choice.
  expect(targetOf(several, "gone")?.name).toBe("Berta");
  expect(targetOf(list(["Ana"]), null)?.name).toBe("Ana");
});

test("with several profiles and none selected there is no profile to send a password to", () => {
  expect(targetOf(list(["Ana", "Berta"]), null)).toBeNull();
  expect(targetOf(list([]), null)).toBeNull();
  expect(targetOf(null, "Ana")).toBeNull();
});

test("a profile's name is refused when blank, hyphen-led, too long, or another profile's", () => {
  const held = list(["Ana Soler"]);
  expect(nameProblem("", held)).toBe("missing");
  expect(nameProblem("   ", held)).toBe("missing");
  expect(nameProblem("--help", held)).toBe("hyphen");
  expect(nameProblem("  -Ana", held)).toBe("hyphen");
  expect(nameProblem("Ana-Maria", held)).toBeNull();
  expect(nameProblem("x".repeat(160), held)).toBeNull();
  expect(nameProblem("x".repeat(161), held)).toBe("long");
  // Counted in characters, not in the units a string stores them in.
  expect(nameProblem("😀".repeat(160), held)).toBeNull();
  expect(nameProblem("ana soler", held)).toBe("taken");
  expect(nameProblem("  Ana Soler ", held)).toBe("taken");
  expect(nameProblem("Ana Soler Vidal", held)).toBeNull();
  // Where the list is not known, the product is left to judge.
  expect(nameProblem("Ana Soler", null)).toBeNull();
});

test("a password is refused under eight characters and over the product's bounds", () => {
  expect(passwordProblem("")).toBe("short");
  expect(passwordProblem("1234567")).toBe("short");
  expect(passwordProblem("12345678")).toBeNull();
  expect(passwordProblem("😀".repeat(8))).toBeNull();
  expect(passwordProblem("x".repeat(256))).toBeNull();
  expect(passwordProblem("x".repeat(257))).toBe("long");
  // Counted in characters: the longest the product takes, at four bytes
  // each, is exactly its bound in bytes.
  expect(passwordProblem("😀".repeat(256))).toBeNull();
  expect(new TextEncoder().encode("😀".repeat(256))).toHaveLength(1024);
  expect(passwordProblem("😀".repeat(257))).toBe("long");
});

test("with no profile selected, the profiles that exist are still there to sign in to", () => {
  const none = status();
  expect(phaseOf(true, none, false)).toBe("no-profile");
  expect(phaseOf(true, none, false, list([]))).toBe("no-profile");
  expect(phaseOf(true, none, false, list(["Ana", "Berta"]))).toBe("signed-out");
  expect(canSignIn(phaseOf(true, none, false, list(["Ana"])), null)).toBe(true);
  // What comes before it in the reading is not changed by a list.
  expect(
    phaseOf(true, status({ state: "present" }), false, list(["Ana"])),
  ).toBe("signed-in");
  expect(
    phaseOf(true, status({ runtimeAvailable: false }), false, list(["Ana"])),
  ).toBe("services-down");
});
