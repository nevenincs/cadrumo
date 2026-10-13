import type { AgentQuestion } from "./agentSession";

// cadrumo-agent's clarification contract, as the column and the scenario
// host read it: what a questionnaire may hold, and what an answer to it may
// say. Its bounds and rules are the agent's own, kept here so that nothing is
// offered that it would refuse. The agent remains the judge: what this
// misses, it refuses.
//
// The agent counts characters as code points, so a count here is a count of
// code points and never of UTF-16 units.

/** At most this many questions in one request. */
export const MAX_QUESTIONS_PER_REQUEST = 4;
/** At most this many options in one choice. */
export const MAX_OPTIONS_PER_QUESTION = 4;
export const MAX_PROMPT_CHARS = 512;
export const MAX_OPTION_CHARS = 128;
export const MAX_ANSWER_CHARS = 2048;
/** A continuation is a new message of the run: it shares the run message
 * ceiling. */
export const MAX_CONTINUATION_CHARS = 65536;
const MAX_QUESTION_ID_CHARS = 64;
const MAX_REQUEST_ID_CHARS = 128;

// A question's id and a request's id share one grammar, ASCII only.
const IDENTIFIER = /^[A-Za-z0-9_][A-Za-z0-9_.-]*$/;
// A control character is one of the Unicode category Cc, and nothing
// narrower: line breaks and tabs are refused with the rest, DEL and the C1
// range too.
const CONTROL = /\p{Cc}/u;
const BLANK = /^\p{White_Space}*$/u;

export const characters = (text: string): number => [...text].length;

/** Whether `text` holds no control character. */
export const isLineSafe = (text: string): boolean => !CONTROL.test(text);

/** Whether `text` says nothing: empty, or only white space. */
export const isBlank = (text: string): boolean => BLANK.test(text);

const identifier = (text: string, most: number): boolean =>
  text !== "" && text.length <= most && IDENTIFIER.test(text);

const labelled = (text: string, most: number): boolean =>
  text !== "" && characters(text) <= most && isLineSafe(text);

/**
 * Why cadrumo-agent could not have built this questionnaire, one note for
 * each rule it breaks; none when it could have. The agent builds its
 * questions strictly, so a request that breaks a rule did not come from it.
 */
export function questionnaireFaults(request: {
  request_id: string;
  questions: readonly AgentQuestion[];
}): string[] {
  const notes: string[] = [];
  if (!identifier(request.request_id, MAX_REQUEST_ID_CHARS))
    notes.push("the request id is not an identifier of at most 128 characters");
  const { questions } = request;
  if (questions.length < 1 || questions.length > MAX_QUESTIONS_PER_REQUEST)
    notes.push("a request holds one to four questions");
  if (new Set(questions.map((question) => question.id)).size < questions.length)
    notes.push("question ids repeat");
  for (const question of questions) {
    const named = `question ${JSON.stringify(question.id)}`;
    if (!identifier(question.id, MAX_QUESTION_ID_CHARS))
      notes.push(`${named}: its id is not an identifier of at most 64`);
    if (!labelled(question.prompt, MAX_PROMPT_CHARS))
      notes.push(`${named}: its prompt is empty, too long or not one line`);
    const { options } = question;
    if (question.kind === "choice") {
      if (!options || options.length === 0)
        notes.push(`${named}: a choice declares no options`);
      else {
        if (options.length > MAX_OPTIONS_PER_QUESTION)
          notes.push(`${named}: a choice declares at most four options`);
        if (new Set(options).size < options.length)
          notes.push(`${named}: its options repeat`);
        if (!options.every((option) => labelled(option, MAX_OPTION_CHARS)))
          notes.push(`${named}: an option is empty, too long or not one line`);
      }
    } else if (question.kind === "text") {
      if (options !== undefined && options !== null)
        notes.push(`${named}: a text question declares no options`);
    } else notes.push(`${named}: its kind is neither choice nor text`);
  }
  return notes;
}

/** What is wrong with one answer, or with the answers as a whole. */
export type AnswerFaultKind =
  | "too_many"
  | "invalid_id"
  | "too_long"
  | "control_characters"
  | "unknown_question"
  | "missing"
  | "not_an_option";

export type AnswerFault = {
  /** The question the fault is of; empty for the answers as a whole. */
  id: string;
  kind: AnswerFaultKind;
};

/**
 * Whether `answers`, by question id, would be refused by cadrumo-agent as
 * the answers to `questions`, and why. Its two checks come in its order: the
 * shape of the answers first, and only when that holds, the answers against
 * the questions. A required question needs an answer that says something; a
 * question answered with only white space is not answered. A choice takes one
 * of its options exactly as written.
 */
export function answerFaults(
  questions: readonly AgentQuestion[],
  answers: Readonly<Record<string, string>>,
): AnswerFault[] {
  const entries = Object.entries(answers);
  const shape: AnswerFault[] = [];
  if (entries.length > MAX_QUESTIONS_PER_REQUEST)
    shape.push({ id: "", kind: "too_many" });
  for (const [id, answer] of entries) {
    if (!identifier(id, MAX_QUESTION_ID_CHARS))
      shape.push({ id, kind: "invalid_id" });
    if (characters(answer) > MAX_ANSWER_CHARS)
      shape.push({ id, kind: "too_long" });
    if (!isLineSafe(answer)) shape.push({ id, kind: "control_characters" });
  }
  if (shape.length > 0) return shape;
  const faults: AnswerFault[] = [];
  const declared = new Set(questions.map((question) => question.id));
  for (const [id] of entries)
    if (!declared.has(id)) faults.push({ id, kind: "unknown_question" });
  for (const question of questions) {
    // An own entry only: an id such as `__proto__` is a name like another.
    const answer = Object.hasOwn(answers, question.id)
      ? answers[question.id]
      : undefined;
    if (answer === undefined || isBlank(answer)) {
      if (question.required !== false)
        faults.push({ id: question.id, kind: "missing" });
    } else if (
      question.kind === "choice" &&
      !(question.options ?? []).includes(answer)
    )
      faults.push({ id: question.id, kind: "not_an_option" });
  }
  return faults;
}

/** Why cadrumo-agent would refuse `prompt` as the new message that continues
 * a run in place of the answers, or null when it would take it. */
export function continuationFault(prompt: string): "blank" | "too_long" | null {
  if (isBlank(prompt)) return "blank";
  return characters(prompt) > MAX_CONTINUATION_CHARS ? "too_long" : null;
}
