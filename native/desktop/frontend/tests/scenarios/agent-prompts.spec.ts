import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  agentColumn,
  agentTurns,
  approvalPrompt,
  ask,
  conversation,
  live,
  personTurns,
  questionsPrompt,
  recordedAnswers,
  refusalOfAnswer,
  refusalOfDecision,
  scenarioOnly,
  send,
  settled,
  toolRow,
  toolRows,
  waitingOn,
} from "../support/agent";
import { label } from "../support/strings";

// What a reply waits on: questions the agent asks, and decisions only the
// person makes. Each message asks for what it needs in words, as an agent
// would be asked; the scenario host stops every reply for it, by `asks`.
// What the agent then writes is the host's own, so these specs check what
// the column does, and only the scenario host's replies by their words.
//
// The first few also run against the desktop and the real agent. The rest
// read what the scenario host was asked, its call log, or the options and
// bounds it serves, and are left to it.

const open = (target: Page, asks: "questions" | "approval" | "review") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&asks=${asks}`,
  );

const button = (target: Page, key: string) =>
  agentColumn(target).getByRole("button", { name: label(key), exact: true });

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("questions are answered by choosing, and Answer waits for the required ones", async ({
  page: target,
}) => {
  await open(target, "questions");
  await send(target, "Antes de preparar el 303, pregúntame qué trimestre.");
  const prompt = questionsPrompt(target);
  await expect(prompt).toBeVisible();
  // The reply says it waits for the person, not that it is working.
  await expect(conversation(target)).toContainText(
    label("desktop.agent.waiting_on_you"),
  );
  await expect(conversation(target)).not.toContainText(
    label("desktop.agent.working"),
  );
  // The required choice has no answer yet, and Answer says so. It is named
  // alone, or with why it waits.
  const answer = prompt.getByRole("button", {
    name: new RegExp(`^${label("desktop.agent.questions_answer")}\\s*(,|$)`),
  });
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  const choice = prompt.getByRole("radiogroup").first();
  await choice.getByRole("radio").last().click();
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  const chosen = await choice.getByRole("radio").last().innerText();
  await answer.click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
  // The scenario host goes on with what was chosen.
  if (!live()) await expect(agentTurns(target).last()).toContainText(chosen);
});

test("questions answered by a message go on with the same reply", async ({
  page: target,
}) => {
  await open(target, "questions");
  await send(target, "Antes de seguir, pregúntame si aplico la prorrata.");
  await expect(questionsPrompt(target)).toBeVisible();
  // Send stays while questions are asked: a message answers them.
  await ask(target, "No aplico la prorrata.");
  await expect(questionsPrompt(target)).toHaveCount(0);
  await expect(
    personTurns(target).filter({ hasText: "No aplico la prorrata." }),
  ).toBeVisible();
  await settled(target);
  // The person's words are shown once, however they reach the history.
  await expect(
    personTurns(target).filter({ hasText: "No aplico la prorrata." }),
  ).toHaveCount(1);
  if (live()) return;
  await expect(agentTurns(target).last()).toContainText(
    "No aplico la prorrata.",
  );
  // An answer, not a new message: one send, one answer, and one run.
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => call.startsWith("agentSend "))).toHaveLength(1);
  expect(
    calls.filter((call) => call.startsWith("agentAnswerQuestions ")),
  ).toEqual([expect.stringMatching(/ message$/)]);
});

test("declined questions are gone, and the reply goes on without them", async ({
  page: target,
}) => {
  await open(target, "questions");
  await send(target, "Pregúntame lo que necesites del 303.");
  await questionsPrompt(target)
    .getByRole("button", { name: label("desktop.agent.questions_decline") })
    .click();
  await expect(questionsPrompt(target)).toHaveCount(0);
  await settled(target);
});

test("questions still waiting are asked again when the conversation is opened again", async ({
  page: target,
}) => {
  await open(target, "questions");
  const text = "Pregúntame qué trimestre antes de nada.";
  await send(target, text);
  await expect(questionsPrompt(target)).toBeVisible();
  await button(target, "desktop.agent.new_conversation").click();
  await expect(questionsPrompt(target)).toHaveCount(0);
  await button(target, "desktop.agent.history").click();
  await agentColumn(target).getByText(text).click();
  await expect(questionsPrompt(target)).toBeVisible();
  await expect(conversation(target)).toContainText(text);
});

// What the scenario host's agent calls the options of a tool, which are not
// the column's own words for them.
const TOOL = {
  allow_once: "Allow this read",
  reject_once: "Skip this read",
};

test("a tool waits for the person to allow it, once", async ({
  page: target,
}) => {
  scenarioOnly("the options are the scenario host's");
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  // Every way of deciding is offered, under the agent's own name, and none
  // is chosen beforehand.
  for (const name of Object.values(TOOL))
    await expect(
      prompt.getByRole("button", { name, exact: true }),
    ).toBeVisible();
  await prompt
    .getByRole("button", { name: TOOL.allow_once, exact: true })
    .click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
  // The tool it allowed ran, and the row says where it got to.
  const row = toolRow(target, "Leer los apuntes del libro");
  await expect(row).toContainText(label("desktop.agent.tool_done"));
  await expect(row).toContainText(label("desktop.agent.tool_kind_read"));
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("agentDecideApproval ")),
  ).toEqual([expect.stringMatching(/ allow-once$/)]);
});

test("a tool refused does not run", async ({ page: target }) => {
  scenarioOnly("the options are the scenario host's");
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  await approvalPrompt(target)
    .getByRole("button", { name: TOOL.reject_once, exact: true })
    .click();
  await expect(approvalPrompt(target)).toHaveCount(0);
  await settled(target);
  await expect(conversation(target)).not.toContainText(
    "Leer los apuntes del libro",
  );
  await expect(toolRows(target)).toHaveCount(0);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("agentDecideApproval ")),
  ).toEqual([expect.stringMatching(/ reject-once$/)]);
});

test("a Cadrumo operation is reviewed before it commits", async ({
  page: target,
}) => {
  scenarioOnly("the review is the scenario host's");
  await open(target, "review");
  await send(target, "Registra la factura 2026-031.");
  const prompt = approvalPrompt(target, "cadrumo_review");
  await expect(prompt).toBeVisible();
  await expect(prompt).toContainText("Registrar la factura 2026-031");
  await prompt
    .getByRole("button", { name: "Registrar la factura", exact: true })
    .click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
});

// The bounds and rules below are cadrumo-agent's own. The expected values are
// written out here, from its contract, and not taken from the column or the
// scenario host's code that is under test.

// A message that asks the scenario host for the most the agent can ask: four
// questions, a prompt of 512 characters, an option of 128, four options.
const MOST = "Hazme cuatro preguntas antes de seguir.";
const QUESTIONS = {
  quarter: "q-trimestre",
  nif: "q.nif_2",
  prorrata: "q-prorrata",
  notes: "q-notas",
};

const answerButton = (prompt: Locator) =>
  prompt.getByRole("button", {
    name: new RegExp(`^${label("desktop.agent.questions_answer")}\\s*(,|$)`),
  });

/** Asks the most, and returns the questions as the agent asked them. */
async function mostQuestions(target: Page) {
  await open(target, "questions");
  await send(target, MOST);
  const prompt = questionsPrompt(target);
  await expect(prompt).toBeVisible();
  const [questionnaire] = (await waitingOn(target)).questionnaires;
  if (!questionnaire) throw new Error("The agent asked nothing");
  return { prompt, questionnaire, questions: questionnaire.questions };
}

/** The fields of the most-asked questionnaire, by what each is. */
const fields = (prompt: Locator) => ({
  quarter: prompt.getByRole("radiogroup").nth(0),
  nif: prompt.getByRole("textbox").nth(0),
  prorrata: prompt.getByRole("radiogroup").nth(1),
  notes: prompt.getByRole("textbox").nth(1),
});

/** Answers what a person must give: a quarter and a tax number. */
async function answerRequired(prompt: Locator) {
  const { quarter, nif } = fields(prompt);
  await quarter.getByRole("radio").first().click();
  await nif.fill("B12345678");
}

test("the most the agent can ask is shown as it was written", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt, questions } = await mostQuestions(target);
  // The scenario host really asks at the agent's limits.
  expect(questions).toHaveLength(4);
  expect(questions.map((question) => question.id)).toEqual(
    Object.values(QUESTIONS),
  );
  const [quarter] = questions;
  expect(quarter?.prompt).toHaveLength(512);
  expect(quarter?.options).toHaveLength(4);
  expect(quarter?.options?.at(-1)).toHaveLength(128);
  // Nothing of it is cut, reworded or left out.
  for (const question of questions)
    await expect(prompt).toContainText(question.prompt);
  const radios = fields(prompt).quarter.getByRole("radio");
  await expect(radios).toHaveCount(4);
  for (const [index, option] of (quarter?.options ?? []).entries())
    await expect(radios.nth(index)).toHaveText(option);
  await expect(fields(prompt).prorrata.getByRole("radio")).toHaveText([
    "Sí",
    "No",
  ]);
  // A choice is answered by choosing; only a text question takes writing.
  await expect(prompt.getByRole("textbox")).toHaveCount(2);
  // And what is long wraps inside the card.
  expect(
    await prompt.evaluate((card) => card.scrollWidth <= card.clientWidth),
  ).toBe(true);
});

test("Answer waits until every required question says something", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt } = await mostQuestions(target);
  const answer = answerButton(prompt);
  const { quarter, nif, notes } = fields(prompt);
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  await expect(answer).toContainText(label("desktop.agent.questions_missing"));
  // Optional questions do not count: answering one leaves the rest to do.
  await notes.fill("Una nota");
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  await quarter.getByRole("radio").nth(1).click();
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  // White space says nothing.
  await nif.fill("   ");
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  await nif.fill("B12345678");
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  // And it is held again when the answer is taken back.
  await nif.fill("");
  await expect(answer).toHaveAttribute("aria-disabled", "true");
});

test("answers go as written, by question id, and an unanswered question is left out", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt, questions } = await mostQuestions(target);
  const { quarter, nif, notes } = fields(prompt);
  const last = questions[0]?.options?.at(-1);
  await quarter.getByRole("radio").last().click();
  // Written as it is, spaces and all; the person's words are not tidied.
  await nif.fill("  B12345678 ");
  await notes.fill("   ");
  await answerButton(prompt).click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
  expect(await recordedAnswers(target)).toEqual([
    {
      kind: "answers",
      answers: { [QUESTIONS.quarter]: last, [QUESTIONS.nif]: "  B12345678 " },
    },
  ]);
});

test("an optional choice can be left unanswered again", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt } = await mostQuestions(target);
  const { prorrata } = fields(prompt);
  await answerRequired(prompt);
  const clear = prompt.getByRole("button", {
    name: label("desktop.agent.questions_clear"),
  });
  // Nothing to take back until something is chosen, and only an optional
  // question can be taken back.
  await expect(clear).toHaveCount(0);
  await prorrata.getByRole("radio", { name: "No", exact: true }).click();
  await expect(clear).toHaveCount(1);
  await clear.click();
  await expect(clear).toHaveCount(0);
  await expect(prorrata.getByRole("radio", { checked: true })).toHaveCount(0);
  await answerButton(prompt).click();
  await expect(prompt).toHaveCount(0);
  const [resolution] = await recordedAnswers(target);
  expect(resolution).toEqual({
    kind: "answers",
    answers: {
      [QUESTIONS.quarter]: "Primer trimestre",
      [QUESTIONS.nif]: "B12345678",
    },
  });
});

test("a text answer holds at 2048 characters, counted as the agent counts them", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt } = await mostQuestions(target);
  const { notes } = fields(prompt);
  const answer = answerButton(prompt);
  await answerRequired(prompt);
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  const tooLong = (count: number) =>
    label("desktop.agent.questions_too_long", { count, max: 2048 });
  // The most it can be.
  await notes.fill("a".repeat(2048));
  await expect(prompt.getByRole("alert")).toHaveCount(0);
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  // One more is said, and nothing is cut: the person decides what goes.
  await notes.fill("a".repeat(2049));
  await expect(prompt.getByRole("alert")).toHaveText(tooLong(2049));
  await expect(notes).toHaveAttribute("aria-invalid", "true");
  await expect(notes).toHaveValue("a".repeat(2049));
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  await expect(answer).toContainText(label("desktop.agent.questions_invalid"));
  // A character is a code point: an emoji is one, though it takes two units.
  await notes.fill("😀".repeat(2048));
  await expect(prompt.getByRole("alert")).toHaveCount(0);
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  await notes.fill("😀".repeat(2049));
  await expect(prompt.getByRole("alert")).toHaveText(tooLong(2049));
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  // Declining is not an answer, and is not held by one.
  await expect(
    prompt.getByRole("button", {
      name: label("desktop.agent.questions_decline"),
    }),
  ).not.toHaveAttribute("aria-disabled", "true");
  // Back within the limit it goes, and the whole of it.
  await notes.fill("b".repeat(2048));
  await answer.click();
  await expect(prompt).toHaveCount(0);
  const [resolution] = await recordedAnswers(target);
  expect(resolution).toMatchObject({
    kind: "answers",
    answers: { [QUESTIONS.notes]: "b".repeat(2048) },
  });
});

test("an answer with a control character is not sent, and Enter makes no line break", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt } = await mostQuestions(target);
  const { notes } = fields(prompt);
  const answer = answerButton(prompt);
  await answerRequired(prompt);
  // Control characters are the whole of Unicode Cc: a tab, a line break, DEL
  // and the C1 range alike.
  for (const text of ["a\tb", "a\nb", "a\u007fb", "a\u0085b", "a\u0000b"]) {
    await notes.fill(text);
    await expect(prompt.getByRole("alert")).toHaveText(
      label("desktop.agent.questions_control"),
    );
    await expect(answer).toHaveAttribute("aria-disabled", "true");
    await expect(answer).toContainText(
      label("desktop.agent.questions_invalid"),
    );
  }
  // Other white space and format characters are not control characters.
  await notes.fill("a\u00a0b\u200bc\u2028d😀ñ");
  await expect(prompt.getByRole("alert")).toHaveCount(0);
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  // Enter, which would break the line, does nothing to the answer.
  await notes.fill("ab");
  await notes.press("Enter");
  await notes.press("Shift+Enter");
  await expect(notes).toHaveValue("ab");
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  // A control character in a required answer holds that one too.
  await fields(prompt).nif.fill("B1\t2");
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  await fields(prompt).nif.fill("B12345678");
  await answer.click();
  await expect(prompt).toHaveCount(0);
  const [resolution] = await recordedAnswers(target);
  expect(resolution).toMatchObject({
    answers: { [QUESTIONS.notes]: "ab", [QUESTIONS.nif]: "B12345678" },
  });
});

test("declining sends only a decline, and a message only its words", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "questions");
  await send(target, "Pregúntame lo que necesites del 303.");
  await questionsPrompt(target)
    .getByRole("button", { name: label("desktop.agent.questions_decline") })
    .click();
  await expect(questionsPrompt(target)).toHaveCount(0);
  await settled(target);
  await send(target, "Pregúntame lo que necesites del 130.");
  await expect(questionsPrompt(target)).toBeVisible();
  await ask(target, "Hazlo del segundo trimestre. Gracias.");
  await expect(questionsPrompt(target)).toHaveCount(0);
  await settled(target);
  expect(await recordedAnswers(target)).toEqual([
    { kind: "decline" },
    { kind: "message", text: "Hazlo del segundo trimestre. Gracias." },
  ]);
});

test("the agent refuses an answer it would not take, as the column would not send it", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { questions, questionnaire } = await mostQuestions(target);
  const options = questions[0]?.options ?? [];
  const first = options[0] ?? "";
  const good = { [QUESTIONS.quarter]: first, [QUESTIONS.nif]: "B12345678" };
  const refused = async (answers: Record<string, string>) =>
    refusalOfAnswer(target, { kind: "answers", answers }, questionnaire);
  // The agent explains a refusal in a sentence and the host passes on only the
  // status: every refusal is the same 422, and the sentence tells which rule.
  const unprocessable = (prose?: string) => ({
    code: "agent_gateway_422",
    ...(prose === undefined ? {} : { message: prose }),
  });
  // An option the question did not offer, or another question's.
  for (const wrong of ["Quinto trimestre", "Sí", first.toLowerCase()])
    expect(
      await refused({ ...good, [QUESTIONS.quarter]: wrong }),
    ).toMatchObject(
      unprocessable(
        "answer to question 'q-trimestre' is not one of its declared options",
      ),
    );
  // An optional choice is held to its options when it is answered at all.
  expect(
    await refused({ ...good, [QUESTIONS.prorrata]: "Quizá" }),
  ).toMatchObject(
    unprocessable(
      "answer to question 'q-prorrata' is not one of its declared options",
    ),
  );
  // A required question left out, or answered with nothing.
  expect(await refused({ [QUESTIONS.quarter]: first })).toMatchObject(
    unprocessable("question 'q.nif_2' is required and unanswered"),
  );
  expect(await refused({ ...good, [QUESTIONS.nif]: " \u00a0 " })).toMatchObject(
    unprocessable("question 'q.nif_2' is required and unanswered"),
  );
  expect(await refused({ ...good, [QUESTIONS.quarter]: "" })).toMatchObject(
    unprocessable("question 'q-trimestre' is required and unanswered"),
  );
  // An answer to a question nobody asked.
  expect(await refused({ ...good, "q-otra": "x" })).toMatchObject(
    unprocessable("unknown question id 'q-otra'"),
  );
  // Too long, by characters; the shape is judged before the questions.
  expect(
    await refused({ ...good, [QUESTIONS.notes]: "a".repeat(2049) }),
  ).toMatchObject(unprocessable());
  expect(await refused({ [QUESTIONS.notes]: "😀".repeat(2049) })).toMatchObject(
    unprocessable(),
  );
  // A control character anywhere, in a required answer too.
  for (const text of ["a\tb", "a\nb", "a\u007fb", "a\u0085b"]) {
    expect(await refused({ ...good, [QUESTIONS.notes]: text })).toMatchObject(
      unprocessable("clarification text must not contain control characters"),
    );
    expect(await refused({ ...good, [QUESTIONS.nif]: text })).toMatchObject(
      unprocessable("clarification text must not contain control characters"),
    );
  }
  // More answers than there can be questions, or an id that is no identifier.
  expect(
    await refused({
      ...good,
      [QUESTIONS.prorrata]: "No",
      [QUESTIONS.notes]: "x",
      "q-5": "x",
    }),
  ).toMatchObject(unprocessable());
  expect(await refused({ ...good, "q otra": "x" })).toMatchObject(
    unprocessable(),
  );
  // None of that answered anything: the questions still wait.
  await expect(questionsPrompt(target)).toBeVisible();
  expect((await waitingOn(target)).questionnaires).toHaveLength(1);
  // What the agent takes is taken: an optional question left blank is fine.
  expect(await refused({ ...good, [QUESTIONS.notes]: "" })).toBeNull();
  await expect(questionsPrompt(target)).toHaveCount(0);
  // And the questions are no longer pending: the agent's 404.
  expect(await refused(good)).toMatchObject({ code: "agent_gateway_404" });
});

test("a message that continues the run is held to the agent's message limits", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "questions");
  await send(target, "Pregúntame lo que necesites del 303.");
  await expect(questionsPrompt(target)).toBeVisible();
  const continued = (text: string) =>
    refusalOfAnswer(target, { kind: "message", text });
  // It says something.
  expect(await continued("")).toMatchObject({
    code: "agent_gateway_422",
    message: "prompt must not be blank",
  });
  expect(await continued(" \n\t \u00a0")).toMatchObject({
    code: "agent_gateway_422",
  });
  // And is at most 65536 characters, counted as code points.
  expect(await continued("a".repeat(65537))).toMatchObject({
    code: "agent_gateway_422",
  });
  expect(await continued("😀".repeat(65537))).toMatchObject({
    code: "agent_gateway_422",
  });
  await expect(questionsPrompt(target)).toBeVisible();
  // Unlike an answer, it keeps its line breaks, and may be as long as that.
  expect(await continued(`${"😀".repeat(65533)}\n\t.`)).toBeNull();
  await expect(questionsPrompt(target)).toHaveCount(0);
});

test("a decline is taken whatever was asked", async ({ page: target }) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  const { prompt } = await mostQuestions(target);
  expect(await refusalOfAnswer(target, { kind: "decline" })).toBeNull();
  await expect(prompt).toHaveCount(0);
});

/** The names of the card's options, in the order it shows them. */
const shownOptions = (prompt: Locator) =>
  prompt.getByRole("button").allTextContents();

test("a tool's options are named as the agent names them, refusals first, allowing once last and primary", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  // The agent lists allowing once first, and offers nothing it would
  // remember; the card puts the refusal first.
  const [approval] = (await waitingOn(target)).approvals;
  expect(approval?.options.map((option) => option.kind)).toEqual([
    "allow_once",
    "reject_once",
  ]);
  expect(await shownOptions(prompt)).toEqual([
    TOOL.reject_once,
    TOOL.allow_once,
  ]);
  // Of the tool, the agent says its name and a line that repeats it: no
  // input of the call is served, and none is shown.
  await expect(prompt).toContainText("ledger_list");
  await expect(prompt.locator("p")).toHaveText([
    "ledger_list",
    "Permission required: ledger_list",
  ]);
  // Of what kind of tool it is, the agent says one of ten words, and the card
  // says it in ours.
  await expect(prompt.locator("[data-slot=badge]")).toHaveText(
    label("desktop.agent.tool_kind_read"),
  );
  // Allowing once is the primary action, and the only one.
  const buttons = prompt.getByRole("button");
  await expect(buttons).toHaveCount(2);
  await expect(buttons.nth(0)).toHaveAttribute("data-variant", "outline");
  await expect(buttons.nth(1)).toHaveAttribute("data-variant", "primary");
});

test("nothing is chosen for the person, and no key decides", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  const buttons = prompt.getByRole("button");
  const count = await buttons.count();
  expect(count).toBeGreaterThan(1);
  for (let index = 0; index < count; index++) {
    await expect(buttons.nth(index)).not.toBeFocused();
    await expect(buttons.nth(index)).not.toHaveAttribute("aria-pressed", /.*/);
  }
  expect(
    await prompt.evaluate((card) => card.contains(document.activeElement)),
  ).toBe(false);
  // With nothing in the page focused, neither Enter nor Space answers.
  await target.evaluate(() => {
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await target.keyboard.press("Enter");
  await target.keyboard.press("Space");
  await expect(prompt).toBeVisible();
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("agentDecideApproval ")),
  ).toEqual([]);
});

test("options the agent gives no name are worded by what they do", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "approval");
  await send(target, "Lee mis apuntes, sin nombres.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  // Absent, null, empty and white space all name nothing; the kind decides
  // the order, as it does for any option, and the agent's order holds within
  // a kind.
  expect(await shownOptions(prompt)).toEqual([
    label("desktop.agent.approval_reject_once"),
    label("desktop.agent.approval_reject_once"),
    label("desktop.agent.approval_allow_once"),
    label("desktop.agent.approval_allow_once"),
  ]);
  // A tool and a description the agent does not give are not made up.
  await expect(prompt.locator("p")).toHaveCount(0);
  await expect(
    prompt.getByRole("heading", {
      name: label("desktop.agent.approval_tool_title"),
    }),
  ).toBeVisible();
  // A decision is the option's id, whatever it was called.
  await prompt.getByRole("button").first().click();
  await expect(prompt).toHaveCount(0);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("agentDecideApproval ")),
  ).toEqual([expect.stringMatching(/ b$/)]);
});

test("options the agent would remember, when it offers nothing else, promise no more than they do", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "approval");
  await send(target, "Lee mis apuntes, solo recuerdos.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  const [approval] = (await waitingOn(target)).approvals;
  expect(approval?.options.map((option) => option.kind)).toEqual([
    "allow_always",
    "reject_always",
  ]);
  // The agent keeps no grant: it applies an answer to the call it was asked
  // about. The words say neither always nor never.
  const words = await shownOptions(prompt);
  expect(words).toEqual([
    label("desktop.agent.approval_reject_always"),
    label("desktop.agent.approval_allow_always"),
  ]);
  expect(words).toEqual(["Don't allow", "Allow"]);
  for (const locale of ["es", "ca", "hu"])
    for (const key of [
      "desktop.agent.approval_allow_always",
      "desktop.agent.approval_reject_always",
    ])
      expect(label(key, {}, locale)).not.toMatch(
        /siempre|nunca|sempre|mai|mindig|soha/i,
      );
});

test("the most an approval can say is shown whole, in the agent's order within each kind", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "approval");
  await send(target, "Lee todo, con los detalles extremos.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  const [approval] = (await waitingOn(target)).approvals;
  expect(approval?.options).toHaveLength(16);
  expect(approval?.tool_call).toHaveLength(128);
  expect(approval?.description).toHaveLength(4096);
  await expect(prompt).toContainText(approval?.tool_call ?? "");
  await expect(prompt).toContainText(approval?.description ?? "");
  // Eight of each kind, refusals first, each kind in the order it was listed.
  const names = (kind: string) =>
    (approval?.options ?? [])
      .filter((option) => option.kind === kind)
      .map((option) => option.name);
  expect(names("reject_once")).toHaveLength(8);
  expect(await shownOptions(prompt)).toEqual([
    ...names("reject_once"),
    ...names("allow_once"),
  ]);
  expect(
    (approval?.options ?? []).some((option) => option.name?.length === 128),
  ).toBe(true);
  // Nothing runs over the card's edge.
  expect(
    await prompt.evaluate((card) => card.scrollWidth <= card.clientWidth),
  ).toBe(true);
});

test("a Cadrumo review offers the same choices in the same order", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "review");
  await send(target, "Registra la factura 2026-031.");
  const prompt = approvalPrompt(target, "cadrumo_review");
  await expect(prompt).toBeVisible();
  expect(await shownOptions(prompt)).toEqual([
    "No registrar",
    "Registrar la factura",
  ]);
  await expect(
    prompt.getByRole("button", { name: "Registrar la factura", exact: true }),
  ).toHaveAttribute("data-variant", "primary");
  await expect(
    prompt.getByRole("button", { name: "No registrar", exact: true }),
  ).toHaveAttribute("data-variant", "outline");
});

test("the agent refuses a decision it did not offer", async ({
  page: target,
}) => {
  scenarioOnly("what is checked is what the scenario host asked and served");
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  await expect(approvalPrompt(target)).toBeVisible();
  const [approval] = (await waitingOn(target)).approvals;
  // An option the request did not offer, its name, its kind, or one it would
  // have remembered: the agent's conflict.
  for (const wrong of [
    "allow-forever",
    "allow-always",
    TOOL.allow_once,
    "allow_once",
  ])
    expect(await refusalOfDecision(target, wrong)).toMatchObject({
      code: "agent_gateway_409",
    });
  // An id of no length, or of more than 64, which the host does not send.
  expect(await refusalOfDecision(target, "")).toMatchObject({
    code: "agent_invalid_request",
  });
  expect(await refusalOfDecision(target, "a".repeat(65))).toMatchObject({
    code: "agent_invalid_request",
  });
  // None of that decided it.
  await expect(approvalPrompt(target)).toBeVisible();
  expect(await refusalOfDecision(target, "reject-once")).toBeNull();
  await expect(approvalPrompt(target)).toHaveCount(0);
  // And it is no longer pending: the agent's 404.
  expect(
    await refusalOfDecision(target, "reject-once", approval),
  ).toMatchObject({ code: "agent_gateway_404" });
});
