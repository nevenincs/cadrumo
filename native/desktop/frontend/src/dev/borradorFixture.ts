import { requireServed } from "./servedFixtures";
import type { BorradorComparison, BorradorPort } from "../shell/borrador";

// The comparison of the AEAT draft with the saved Modelo 100 calculation that
// the application read for a synthetic filer through
// `live.borrador.100.compare`, in every language, at each stage a profile
// reaches. Regenerate with scripts/modelo_fixtures.py; never invent fields
// here. The profile's drafts themselves are not served: a scenario that asks
// for them is told they are unavailable.

/** The stages the application read, for a page to choose among. */
export const BORRADOR_SCENARIOS = [
  "no-capture",
  "capture-refused",
  "no-calculation",
  "compared",
  "stale",
  "unavailable",
] as const;
export type BorradorScenario = (typeof BORRADOR_SCENARIOS)[number];

/** The comparison envelopes by name, each read on first use. */
export type BorradorEnvelopes = Record<string, () => Promise<unknown>>;

function servedEnvelopes(): BorradorEnvelopes {
  const found = requireServed(
    "modelo/borrador-100-0A-*.json",
    import.meta.glob<unknown>("@fixtures/modelo/borrador-100-0A-*.json", {
      import: "default",
    }),
  );
  return Object.fromEntries(
    Object.entries(found).map(([path, load]) => [
      path.slice(path.lastIndexOf("/") + 1, -".json".length),
      load,
    ]),
  );
}

/** A rejected call, shaped as the host rejects one. */
const reject = (code: string): never => {
  throw Object.assign(new Error(code), { code, operation_id: null });
};

/** What a made-up host answers for the profile's AEAT drafts. */
export function borradorFixture({
  scenario,
  say,
  envelopes = servedEnvelopes(),
}: {
  scenario: BorradorScenario;
  say: (call: string) => void;
  envelopes?: BorradorEnvelopes;
}): BorradorPort {
  return {
    async read() {
      say("borrador read");
      return reject("unavailable");
    },
    async query() {
      say("borrador query");
      return reject("unavailable");
    },
    async compare(_profile, _year, language) {
      say(`borrador compare ${language}`);
      if (scenario === "unavailable") return reject("unavailable");
      const load = envelopes[`borrador-100-0A-${scenario}-${language}`];
      if (!load) return reject("unavailable");
      return structuredClone(await load()) as BorradorComparison;
    },
  };
}
