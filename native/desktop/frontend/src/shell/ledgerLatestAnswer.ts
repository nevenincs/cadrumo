// A read asked about what is being typed. An answer belongs to the exact
// question asked. One question is out at a time, because the backend refuses a
// second while the first runs: the latest is asked once the running one
// settles, a stale reply says nothing, and with no answer the work waits.

export type LatestAnswer<Result> =
  { kind: "waiting" } | { kind: "failed" } | { kind: "answer"; result: Result };

const WAITING = { kind: "waiting" } as const;

export class LatestAnswerSession<Question, Result> {
  private view: LatestAnswer<Result> = WAITING;
  private readonly listeners = new Set<() => void>();
  private wanted: Question | null = null;
  private settled: { question: Question; answer: LatestAnswer<Result> } | null =
    null;
  private sending = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = true;

  constructor(
    private readonly ask: (question: Question) => Promise<LatestAnswer<Result>>,
    private readonly same: (one: Question, other: Question) => boolean,
    private readonly restMs: number,
    /** A question not worth asking: it stays waiting. */
    private readonly blank: (question: Question) => boolean = () => false,
  ) {}

  readonly subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  readonly snapshot = () => this.view;

  want(question: Question): void {
    if (this.wanted !== null && this.same(question, this.wanted)) return;
    this.clearTimer();
    this.wanted = this.blank(question) ? null : question;
    this.publish();
    if (this.wanted === null || this.isSettled(this.wanted)) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.send();
    }, this.restMs);
  }

  /** Asks again about a question whose answer failed. */
  retry(): void {
    if (this.settled?.answer.kind === "failed") this.settled = null;
    this.clearTimer();
    this.publish();
    this.send();
  }

  start(): void {
    this.running = true;
  }
  stop(): void {
    this.running = false;
    this.clearTimer();
    // A later start asks again rather than waiting on a timer now gone.
    this.wanted = null;
  }

  private isSettled(question: Question): boolean {
    return this.settled !== null && this.same(question, this.settled.question);
  }

  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  private send(): void {
    const asked = this.wanted;
    if (
      !this.running ||
      this.sending ||
      asked === null ||
      this.isSettled(asked)
    )
      return;
    this.sending = true;
    void this.ask(asked)
      .catch((): LatestAnswer<Result> => ({ kind: "failed" }))
      .then((answer) => this.settle(asked, answer));
  }

  private settle(asked: Question, answer: LatestAnswer<Result>): void {
    this.sending = false;
    if (!this.running) return;
    // Only the latest question's reply counts; the one that overtook it is
    // asked about now unless typing is still resting.
    if (this.wanted === null || !this.same(asked, this.wanted)) {
      if (this.timer === null) this.send();
      return;
    }
    this.settled = { question: asked, answer };
    this.publish();
  }

  private publish(): void {
    this.view =
      this.wanted !== null && this.isSettled(this.wanted)
        ? this.settled!.answer
        : WAITING;
    this.listeners.forEach((listener) => listener());
  }
}
