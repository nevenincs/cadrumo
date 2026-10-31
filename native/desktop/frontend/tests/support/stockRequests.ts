// The requests the Stock panel's forms make, for a test that checks them
// against the backend's own request contracts. The file is bundled and run by
// Node on the scenarios given on standard input; it opens no page and holds no
// state. A scenario is what a person types and attaches, with the choices the
// backend serves; the references the window mints are minted here as the
// window mints them, and a file kept by the backend is named as it names it.

import {
  blankExtra,
  blankMovement,
  bookRequest,
  closingRequest,
  correctRequest,
  describeRequest,
  draftOfMovement,
  evidenceRequest,
  movementCorrectionRequest,
  movementRequest,
  offersOf,
  proofFromKept,
  restoreRequest,
  retireRequest,
  vocabularyOf,
  reverseRequest,
  type BookDraft,
  type ClosingDraft,
  type CorrectDraft,
  type DescribeDraft,
  type MovementDraft,
  type ProofDraft,
  type ProofSlotKey,
  type Vocabulary,
} from "../../src/components/ledger/assets/stockModel";
import type { FileToken } from "../../src/shell/ledger";
import type {
  InventoryEvidenceAddResult,
  InventoryMovement,
  InventoryOptionsResult,
} from "../../src/shell/ledgerSetup";

/** A file the backend kept: what it named it by, and the mark it answered. */
type Proof = { kind?: string; reference: string; digest: string };

type Book = { actividad_id: string; year: number };

/** What a movement form holds. */
type MovementFacts = {
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

type Scenario =
  | { id: string; kind: "book"; year: number; draft: BookDraft }
  | ({ id: string; kind: "movement"; book: Book } & MovementFacts)
  | ({
      id: string;
      kind: "movement_correct";
      book: Book;
      target: string;
      reason: string;
    } & MovementFacts)
  | { id: string; kind: "describe"; book: Book; draft: DescribeDraft }
  | { id: string; kind: "correct"; book: Book; draft: CorrectDraft }
  | {
      id: string;
      kind: "reverse";
      book: Book;
      target: string;
      reason: string;
    }
  | { id: string; kind: "retire"; book: Book; reason: string }
  | { id: string; kind: "restore"; book: Book }
  | { id: string; kind: "evidence"; token: string }
  | { id: string; kind: "roles" }
  | {
      id: string;
      kind: "kept_names";
      movement: InventoryMovement;
    }
  | {
      id: string;
      kind: "evidence_result";
      /** What the backend answered to keeping a file. */
      result: InventoryEvidenceAddResult;
      fileName: string;
    }
  | {
      id: string;
      kind: "movement_correct_kept";
      book: Book;
      target: string;
      reason: string;
      /** The movement as the inspect read serves it. */
      movement: InventoryMovement;
    }
  | {
      id: string;
      kind: "closing";
      book: Book;
      decision: string;
      draft: ClosingDraft;
    };

const mint = () => crypto.randomUUID();

const attach = (blank: ProofDraft, given: Proof | undefined): ProofDraft =>
  given === undefined
    ? blank
    : {
        reference: given.reference,
        kind: given.kind ?? blank.kind,
        digest: given.digest,
      };

/** The draft a movement form holds once the person has typed and attached. */
function draftOf(scenario: MovementFacts) {
  const start = blankMovement();
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

/** Each form makes its request with the references the window mints, judging
 * its choices by the vocabulary the backend serves. */
function made(scenario: Scenario, vocabulary: Vocabulary) {
  switch (scenario.kind) {
    case "book":
      return bookRequest(scenario.year, scenario.draft, vocabulary);
    case "movement":
      return movementRequest(
        scenario.book,
        mint(),
        draftOf(scenario),
        vocabulary,
      );
    case "movement_correct":
      return movementCorrectionRequest(
        scenario.book,
        { correction: mint(), movement: mint() },
        scenario.target,
        scenario.reason,
        draftOf(scenario),
        vocabulary,
      );
    case "describe":
      return describeRequest(scenario.book, mint(), scenario.draft);
    case "correct":
      return correctRequest(scenario.book, mint(), scenario.draft, vocabulary);
    case "reverse":
      return reverseRequest(
        scenario.book,
        mint(),
        scenario.target,
        scenario.reason,
        vocabulary,
      );
    case "retire":
      return retireRequest(scenario.book, mint(), scenario.reason, vocabulary);
    case "evidence":
      return {
        request: evidenceRequest(scenario.token as FileToken),
        problems: {},
        missing: new Set<string>(),
      };
    case "roles":
      return {
        request: vocabulary.roles,
        problems: {},
        missing: new Set<string>(),
      };
    case "kept_names": {
      // The names a correction shows for the files the book kept, by slot.
      const proofs = draftOfMovement(scenario.movement, vocabulary).proofs;
      return {
        request: Object.fromEntries(
          Object.entries(proofs).map(([slot, proof]) => [
            slot,
            proof.fileName ?? null,
          ]),
        ),
        problems: {},
        missing: new Set<string>(),
      };
    }
    case "evidence_result":
      return {
        request: proofFromKept(scenario.result, scenario.fileName),
        problems: {},
        missing: new Set<string>(),
      };
    case "movement_correct_kept":
      return movementCorrectionRequest(
        scenario.book,
        { correction: mint(), movement: mint() },
        scenario.target,
        scenario.reason,
        draftOfMovement(scenario.movement, vocabulary),
        vocabulary,
      );
    case "closing":
      return closingRequest(
        scenario.book,
        { decision: scenario.decision },
        scenario.draft,
        vocabulary,
      );
    case "restore":
      return {
        request: restoreRequest(scenario.book, mint()),
        problems: {},
        missing: new Set<string>(),
      };
  }
}

function build(scenario: Scenario, vocabulary: Vocabulary) {
  const built = made(scenario, vocabulary);
  return {
    id: scenario.id,
    request: built.request,
    problems: built.problems,
    missing: [...built.missing],
  };
}

const chunks: string[] = [];
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk: string) => chunks.push(chunk));
process.stdin.on("end", () => {
  const given = JSON.parse(chunks.join("")) as {
    /** What the options read serves: every choice, with its role. */
    options: InventoryOptionsResult;
    scenarios: Scenario[];
  };
  const vocabulary = vocabularyOf(offersOf(given.options));
  process.stdout.write(
    JSON.stringify(
      given.scenarios.map((scenario) => build(scenario, vocabulary)),
    ),
  );
});
