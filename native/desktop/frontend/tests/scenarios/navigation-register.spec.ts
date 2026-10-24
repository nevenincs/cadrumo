import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../../scripts/build-paths.mjs";
import {
  decide,
  GuardRegister,
  type GuardState,
  type Leaving,
} from "../../src/shell/navigation/guards";
import {
  formatViewLink,
  parseViewLink,
} from "../../src/shell/navigation/links";
import {
  idsFor,
  type NavigationRegister,
  type Surface,
} from "../../src/shell/navigation/register";
import {
  declaredImplementation,
  resolveView,
  type Implemented,
} from "../../src/shell/navigation/resolve";
import {
  WINDOW_VIEWS,
  mountedNow,
  unmountedBy,
} from "../../src/shell/navigation/windowViews";

// The window's link grammar, resolution and id table, held to the register
// the build projected and to the conformance vectors the Python
// implementation of the same grammar passes. Neither file is copied here.

const register = JSON.parse(
  readFileSync(
    resolve(buildPath("desktop_frontend_generated"), "navigation.json"),
    "utf8",
  ),
) as NavigationRegister;

type Params = Record<string, string>;
type Request = { view_id: string; params: Params; prefer: Surface | null };
type Vectors = {
  format: (Request & { link: string })[];
  parse: { link: string; expect: Request | { refused: string } }[];
  resolve: {
    link: Request;
    implemented: Record<
      string,
      { views: string[]; params: Record<string, string[]> }
    > | null;
    expect:
      | {
          opened: string;
          surface: Surface;
          fallback: string;
          notice: boolean;
          params: Params;
        }
      | { refused: string };
  }[];
};

const vectors = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL(
        "../../../../../src/cadrumo_client/contracts/tests/navigation_vectors.json",
        import.meta.url,
      ),
    ),
    "utf8",
  ),
) as Vectors;

const request = (link: Request) => ({
  viewId: link.view_id,
  params: link.params,
  prefer: link.prefer,
});

test("every format vector spells its link", () => {
  expect(vectors.format.length).toBeGreaterThan(0);
  for (const vector of vectors.format)
    expect(
      formatViewLink(register, vector.view_id, vector.params, vector.prefer),
      vector.view_id,
    ).toBe(vector.link);
  expect(() => formatViewLink(register, "nowhere")).toThrow();
  expect(() =>
    formatViewLink(register, "calendar", { select: "0".repeat(64) }),
  ).toThrow();
});

test("every parse vector parses, or is refused for the same first reason", () => {
  expect(vectors.parse.length).toBeGreaterThan(0);
  for (const vector of vectors.parse) {
    const parsed = parseViewLink(vector.link, register);
    const actual =
      parsed.kind === "refused"
        ? { refused: parsed.reason }
        : {
            view_id: parsed.link.viewId,
            params: parsed.link.params,
            prefer: parsed.link.prefer,
          };
    expect(actual, vector.link).toEqual(vector.expect);
  }
});

test("every resolve vector opens where the register's resolution does", () => {
  expect(vectors.resolve.length).toBeGreaterThan(0);
  for (const vector of vectors.resolve) {
    const implemented: Implemented =
      vector.implemented === null
        ? declaredImplementation(register)
        : Object.fromEntries(
            Object.entries(vector.implemented).map(([surface, each]) => [
              surface,
              {
                views: new Set(each.views),
                params: new Map(
                  Object.entries(each.params).map(([id, names]) => [
                    id,
                    new Set(names),
                  ]),
                ),
              },
            ]),
          );
    const resolved = resolveView(request(vector.link), implemented, register);
    const actual =
      resolved.kind === "refused"
        ? { refused: resolved.reason }
        : {
            opened: resolved.opened,
            surface: resolved.surface,
            fallback: resolved.fallback,
            notice: resolved.noticeDue,
            params: resolved.params,
          };
    expect(actual, JSON.stringify(vector.link)).toEqual(vector.expect);
  }
});

test("the window's table covers exactly the register's window elements", () => {
  expect(Object.keys(WINDOW_VIEWS).sort()).toEqual(
    [...idsFor(register, "gui")].sort(),
  );
  for (const [id, entry] of Object.entries(WINDOW_VIEWS)) {
    const element = register.elements.find((each) => each.id === id);
    // The window honours only parameters the element declares.
    for (const name of entry.honours)
      expect(Object.keys(element?.params ?? {}), id).toContain(name);
  }
});

test("leaving a page takes it down; a section, a pane or the panel keeps it", () => {
  const onLedger = mountedNow("ledger", "movements");
  const view = (id: string) => {
    const entry = WINDOW_VIEWS[id];
    if (!entry) throw new Error(id);
    return entry.view;
  };
  expect(
    [...unmountedBy(onLedger, view("calendar"), "movements")].sort(),
  ).toEqual(["ledger", "ledger/movements"]);
  expect([
    ...unmountedBy(onLedger, view("ledger/invoices"), "movements"),
  ]).toEqual(["ledger/movements"]);
  expect(unmountedBy(onLedger, view("ledger"), "movements").size).toBe(0);
  for (const id of ["agent", "terminal", "panel", "panel/logs"])
    expect(unmountedBy(onLedger, view(id), "movements").size, id).toBe(0);
});

test("guards weigh only what a navigation takes down, and a dialog anywhere", () => {
  const guards = new GuardRegister();
  let ledger: GuardState = "clean";
  let profile: GuardState = "clean";
  guards.register({ owner: "ledger", state: () => ledger });
  const release = guards.register({ owner: "profile", state: () => profile });
  const leaveLedger: Leaving = {
    kind: "navigate",
    unmounted: new Set(["ledger", "ledger/movements"]),
  };
  const showPane: Leaving = { kind: "navigate", unmounted: new Set() };
  const weigh = (leaving: Leaving) => {
    const decision = decide(leaving, guards.assess(leaving));
    return decision.kind === "refuse"
      ? `refuse:${decision.reason}`
      : decision.kind;
  };
  expect(weigh(leaveLedger)).toBe("proceed");
  ledger = "dirty";
  expect(weigh(leaveLedger)).toBe("ask_dirty");
  // Showing a pane takes nothing down and asks nothing.
  expect(weigh(showPane)).toBe("proceed");
  expect(weigh({ kind: "sign_out" })).toBe("ask_dirty");
  ledger = "busy";
  expect(weigh(leaveLedger)).toBe("refuse:busy");
  expect(weigh(showPane)).toBe("proceed");
  // The close asks over work in flight rather than refusing it.
  expect(weigh({ kind: "close" })).toBe("ask_busy_close");
  ledger = "clean";
  profile = "modal";
  // A dialog anywhere stands every navigation down, a pane's included.
  expect(weigh(leaveLedger)).toBe("refuse:modal");
  expect(weigh(showPane)).toBe("refuse:modal");
  // The close is never held by a dialog: it closes, or asks about the work
  // it would drop.
  expect(weigh({ kind: "close" })).toBe("proceed");
  expect(weigh({ kind: "sign_out" })).toBe("refuse:modal");
  ledger = "dirty";
  expect(weigh({ kind: "close" })).toBe("ask_dirty");
  ledger = "busy";
  expect(weigh({ kind: "close" })).toBe("ask_busy_close");
  ledger = "clean";
  release();
  expect(weigh(showPane)).toBe("proceed");
});
