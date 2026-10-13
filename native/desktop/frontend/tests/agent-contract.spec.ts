import { expect, test } from "@playwright/test";
import {
  answerFaults,
  continuationFault,
  isBlank,
  isLineSafe,
  questionnaireFaults,
} from "../src/shell/agentClarification";
import { offeredOptions } from "../src/shell/agentPermission";
import type {
  AgentApprovalOption,
  AgentQuestion,
} from "../src/shell/agentSession";

// cadrumo-agent's clarification and permission rules, as the column reads
// them. Every expected value is written out from the agent's contract (its
// bounds, its identifier grammar, the Unicode Cc rule, the answer checks),
// not derived from the code under test.

const text = (id: string): AgentQuestion => ({
  id,
  prompt: "¿Algo más?",
  kind: "text",
  options: null,
  required: false,
});
const choice = (options: string[], required = true): AgentQuestion => ({
  id: "q",
  prompt: "¿Cuál?",
  kind: "choice",
  options,
  required,
});
const request = (questions: AgentQuestion[], request_id = "clar-1") => ({
  request_id,
  questions,
});

test.describe("a questionnaire the agent could have built", () => {
  test("one to four questions with distinct ids", () => {
    expect(questionnaireFaults(request([text("a")]))).toEqual([]);
    expect(
      questionnaireFaults(request(["a", "b", "c", "d"].map(text))),
    ).toEqual([]);
    expect(questionnaireFaults(request([]))).not.toEqual([]);
    expect(
      questionnaireFaults(request(["a", "b", "c", "d", "e"].map(text))),
    ).not.toEqual([]);
    expect(questionnaireFaults(request([text("a"), text("a")]))).not.toEqual(
      [],
    );
  });

  test("identifiers: ASCII, one to 64, not starting with a dot or a hyphen", () => {
    for (const good of [
      "a",
      "_a",
      "q-trimestre",
      "q.nif_2",
      "A1.-_",
      "x".repeat(64),
    ])
      expect(questionnaireFaults(request([text(good)]))).toEqual([]);
    for (const bad of [
      "",
      ".a",
      "-a",
      "a b",
      "ñ",
      "a/b",
      "a\n",
      "x".repeat(65),
    ])
      expect(questionnaireFaults(request([text(bad)]))).not.toEqual([]);
    // The request has the same grammar, to 128.
    expect(questionnaireFaults(request([text("a")], "r".repeat(128)))).toEqual(
      [],
    );
    for (const bad of ["", ".r", "r r", "r".repeat(129)])
      expect(questionnaireFaults(request([text("a")], bad))).not.toEqual([]);
  });

  test("a prompt is one to 512 characters of one line", () => {
    const asked = (prompt: string) =>
      questionnaireFaults(request([{ ...text("a"), prompt }]));
    expect(asked("x".repeat(512))).toEqual([]);
    // Characters are code points: an emoji is one.
    expect(asked("😀".repeat(512))).toEqual([]);
    expect(asked("😀".repeat(513))).not.toEqual([]);
    expect(asked("x".repeat(513))).not.toEqual([]);
    expect(asked("")).not.toEqual([]);
    // Only Unicode Cc is refused, and all of it.
    for (const bad of [
      "a\tb",
      "a\nb",
      "a\rb",
      "a\u0000b",
      "a\u007fb",
      "a\u0085b",
      "a\u009fb",
    ])
      expect(asked(bad)).not.toEqual([]);
    expect(asked("a\u00a0b\u200bc\u2028d")).toEqual([]);
  });

  test("a choice declares one to four distinct options of one to 128 characters", () => {
    const asked = (options: string[]) =>
      questionnaireFaults(request([choice(options)]));
    expect(asked(["a"])).toEqual([]);
    expect(asked(["a", "b", "c", "d"])).toEqual([]);
    expect(asked(["x".repeat(128)])).toEqual([]);
    expect(asked([])).not.toEqual([]);
    expect(asked(["a", "b", "c", "d", "e"])).not.toEqual([]);
    expect(asked(["a", "a"])).not.toEqual([]);
    expect(asked([""])).not.toEqual([]);
    expect(asked(["x".repeat(129)])).not.toEqual([]);
    expect(asked(["a\tb"])).not.toEqual([]);
    // A choice with no options at all.
    expect(
      questionnaireFaults(request([{ ...choice([]), options: null }])),
    ).not.toEqual([]);
    expect(
      questionnaireFaults(request([{ ...choice([]), options: undefined }])),
    ).not.toEqual([]);
  });

  test("a text question declares no options", () => {
    expect(
      questionnaireFaults(request([{ ...text("a"), options: undefined }])),
    ).toEqual([]);
    expect(
      questionnaireFaults(request([{ ...text("a"), options: null }])),
    ).toEqual([]);
    expect(
      questionnaireFaults(request([{ ...text("a"), options: [] }])),
    ).not.toEqual([]);
    expect(
      questionnaireFaults(request([{ ...text("a"), options: ["a"] }])),
    ).not.toEqual([]);
  });
});

test.describe("an answer the agent takes", () => {
  const quarter: AgentQuestion = {
    id: "quarter",
    prompt: "¿Qué trimestre?",
    kind: "choice",
    options: ["Primero", "Segundo"],
    required: true,
  };
  const notes: AgentQuestion = { ...text("notes"), required: false };
  const nif: AgentQuestion = { ...text("nif"), required: true };
  const questions = [quarter, nif, notes];
  const faults = (answers: Record<string, string>) =>
    answerFaults(questions, answers).map(({ id, kind }) => `${id}:${kind}`);

  test("every required question is answered, and only those", () => {
    expect(faults({ quarter: "Primero", nif: "B1" })).toEqual([]);
    expect(faults({ quarter: "Primero", nif: "B1", notes: "x" })).toEqual([]);
    expect(faults({ nif: "B1" })).toEqual(["quarter:missing"]);
    expect(faults({})).toEqual(["quarter:missing", "nif:missing"]);
    // An answer that says nothing is no answer; an optional one may be blank.
    expect(faults({ quarter: "Primero", nif: " \u00a0" })).toEqual([
      "nif:missing",
    ]);
    expect(faults({ quarter: "Primero", nif: "   " })).toEqual(["nif:missing"]);
    expect(faults({ quarter: "Primero", nif: "B1", notes: "" })).toEqual([]);
    // A question that does not say is required.
    expect(
      answerFaults([{ id: "a", prompt: "p", kind: "text" }], {}).map(
        (f) => f.kind,
      ),
    ).toEqual(["missing"]);
  });

  test("a choice is one of its options exactly as written", () => {
    expect(faults({ quarter: "primero", nif: "B1" })).toEqual([
      "quarter:not_an_option",
    ]);
    expect(faults({ quarter: "Primero ", nif: "B1" })).toEqual([
      "quarter:not_an_option",
    ]);
    expect(faults({ quarter: "Tercero", nif: "B1" })).toEqual([
      "quarter:not_an_option",
    ]);
  });

  test("an answer to a question nobody asked is refused", () => {
    expect(faults({ quarter: "Primero", nif: "B1", other: "x" })).toEqual([
      "other:unknown_question",
    ]);
    // An id such as __proto__ is a name like another.
    expect(
      answerFaults([{ ...text("__proto__"), required: true }], {}).map(
        (fault) => fault.kind,
      ),
    ).toEqual(["missing"]);
  });

  test("an answer is at most 2048 characters of one line", () => {
    expect(
      faults({ quarter: "Primero", nif: "B1", notes: "a".repeat(2048) }),
    ).toEqual([]);
    expect(
      faults({ quarter: "Primero", nif: "B1", notes: "😀".repeat(2048) }),
    ).toEqual([]);
    expect(
      faults({ quarter: "Primero", nif: "B1", notes: "a".repeat(2049) }),
    ).toEqual(["notes:too_long"]);
    expect(
      faults({ quarter: "Primero", nif: "B1", notes: "😀".repeat(2049) }),
    ).toEqual(["notes:too_long"]);
    for (const bad of ["a\tb", "a\nb", "a\u007fb", "a\u0085b"])
      expect(faults({ quarter: "Primero", nif: "B1", notes: bad })).toEqual([
        "notes:control_characters",
      ]);
    // The shape is judged before the questions: a required one left out is
    // not reported beside a malformed answer.
    expect(faults({ notes: "a".repeat(2049) })).toEqual(["notes:too_long"]);
  });

  test("at most four answers, to identifiers", () => {
    expect(
      answerFaults(
        questions,
        Object.fromEntries(["a", "b", "c", "d", "e"].map((id) => [id, "x"])),
      ).map((fault) => fault.kind),
    ).toEqual(["too_many"]);
    expect(faults({ "q r": "x" })).toEqual(["q r:invalid_id"]);
  });
});

test.describe("a message that continues a run in place of the answers", () => {
  test("says something, in at most 65536 characters", () => {
    expect(continuationFault("")).toBe("blank");
    expect(continuationFault(" \n\t\u00a0\u2028")).toBe("blank");
    expect(continuationFault("a")).toBeNull();
    expect(continuationFault("a".repeat(65536))).toBeNull();
    expect(continuationFault("a".repeat(65537))).toBe("too_long");
    expect(continuationFault("😀".repeat(65536))).toBeNull();
    expect(continuationFault("😀".repeat(65537))).toBe("too_long");
    // It keeps its line breaks.
    expect(continuationFault("uno\ndos\ttres")).toBeNull();
  });
});

test.describe("text predicates", () => {
  test("control characters are Unicode Cc and nothing else", () => {
    for (const bad of [
      "\u0000",
      "\t",
      "\n",
      "\r",
      "\u001f",
      "\u007f",
      "\u0080",
      "\u0085",
      "\u009f",
    ])
      expect(isLineSafe(bad)).toBe(false);
    for (const good of [
      "",
      " ",
      "\u00a0",
      "\u00ad",
      "\u200b",
      "\u2028",
      "\u2029",
      "\ufeff",
      "ñ",
      "😀",
    ])
      expect(isLineSafe(good)).toBe(true);
  });

  test("blank is white space only, as the agent strips it", () => {
    for (const blank of [
      "",
      " ",
      "\t\n",
      "\u00a0",
      "\u2003",
      "\u2028",
      "\u3000",
    ])
      expect(isBlank(blank)).toBe(true);
    for (const said of ["a", " a ", "\u200b", "\ufeff", "0"])
      expect(isBlank(said)).toBe(false);
  });
});

test.describe("the options a permission offers", () => {
  const option = (
    kind: AgentApprovalOption["kind"],
    option_id: string = kind,
  ): AgentApprovalOption => ({ option_id, name: kind, kind });

  test("those that answer this call alone, when there are any", () => {
    expect(
      offeredOptions([
        option("allow_always"),
        option("allow_once"),
        option("reject_always"),
        option("reject_once"),
      ]).map(({ kind }) => kind),
    ).toEqual(["allow_once", "reject_once"]);
    expect(
      offeredOptions([option("allow_once")]).map(({ kind }) => kind),
    ).toEqual(["allow_once"]);
  });

  test("otherwise every option, so that what a person could answer stays answerable", () => {
    expect(
      offeredOptions([option("allow_always"), option("reject_always")]).map(
        ({ kind }) => kind,
      ),
    ).toEqual(["allow_always", "reject_always"]);
    expect(offeredOptions([])).toEqual([]);
  });

  test("in the order the agent gave them", () => {
    expect(
      offeredOptions([
        option("reject_once", "b"),
        option("allow_always", "x"),
        option("allow_once", "a"),
        option("reject_once", "c"),
      ]).map(({ option_id }) => option_id),
    ).toEqual(["b", "a", "c"]);
  });
});
