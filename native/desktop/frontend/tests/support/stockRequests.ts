// The requests the Stock panel's forms make, for a test that checks them
// against the backend's own request contracts. The file is bundled and run by
// Node on the scenarios given on standard input; it opens no page and holds no
// state. A scenario is what a person types and attaches; the references the
// window mints are minted here as the window mints them.

import {
  blankExtra,
  blankMovement,
  bookRequest,
  movementRequest,
  type BookDraft,
  type MovementDraft,
  type ProofDraft,
  type ProofSlotKey,
} from "../../src/components/ledger/assets/stockModel";

type Proof = { kind?: string; digest: string };

type Scenario =
  | { id: string; kind: "book"; year: number; draft: BookDraft }
  | {
      id: string;
      kind: "movement";
      book: { actividad_id: string; year: number };
      /** The text of each field, by its key. */
      values: Record<string, string>;
      /** The extra costs of a purchase, each with the file attached to it. */
      extras?: {
        kind: string;
        price: string;
        iva: string;
        share: string;
        proof: Proof;
      }[];
      /** The files the purchase rests on, by slot. */
      proofs?: Partial<Record<ProofSlotKey, Proof>>;
    };

const mint = () => crypto.randomUUID();

const attach = (blank: ProofDraft, given: Proof | undefined): ProofDraft =>
  given === undefined
    ? blank
    : { ...blank, kind: given.kind ?? blank.kind, digest: given.digest };

/** The draft a movement form holds once the person has typed and attached. */
function draftOf(scenario: Extract<Scenario, { kind: "movement" }>) {
  const start = blankMovement(mint);
  const draft: MovementDraft = {
    values: scenario.values,
    extras: (scenario.extras ?? []).map((extra) => {
      const blank = blankExtra(mint);
      return {
        ...blank,
        kind: extra.kind,
        price: extra.price,
        iva: extra.iva,
        share: extra.share,
        proof: attach(blank.proof, extra.proof),
      };
    }),
    proofs: {
      price: attach(start.proofs.price, scenario.proofs?.price),
      cost_check: attach(start.proofs.cost_check, scenario.proofs?.cost_check),
      iva_check: attach(start.proofs.iva_check, scenario.proofs?.iva_check),
    },
  };
  return draft;
}

function build(scenario: Scenario) {
  const made =
    scenario.kind === "book"
      ? bookRequest(scenario.year, scenario.draft)
      : movementRequest(scenario.book, mint(), draftOf(scenario));
  return {
    id: scenario.id,
    request: made.request,
    problems: made.problems,
    missing: [...made.missing],
  };
}

const chunks: string[] = [];
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk: string) => chunks.push(chunk));
process.stdin.on("end", () => {
  const scenarios = JSON.parse(chunks.join("")) as Scenario[];
  process.stdout.write(JSON.stringify(scenarios.map(build)));
});
