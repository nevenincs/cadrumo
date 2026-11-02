/** One read response; failure never implies an unknown write outcome. */
export type ScheduledReadReply<Result> =
  { kind: "answer"; result: Result } | { kind: "failed" };

export type ScheduledReadView<Answer> = {
  shown: Answer | null;
  current: Answer | null;
  updating: boolean;
  failed: boolean;
};

/** One in-flight read, with debounced latest-question delivery and retained display data.
 * Owners supply request identity, result indexing, empty answers and view projection. */
export class ReadSessionScheduler<Question, Key, Result, Answer, View> {
  private view: View;
  private readonly listeners = new Set<() => void>();
  private wanted: { key: Key; request: Question } | null = null;
  private answer: Answer | null = null;
  private answeredKey: Key | null = null;
  private failedKey: Key | null = null;
  private sending = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = true;

  constructor(
    private readonly policy: {
      ask(request: Question): Promise<ScheduledReadReply<Result>>;
      keyOf(request: Question): Key;
      answer(result: Result): Answer;
      present(view: ScheduledReadView<Answer>): View;
      initial: View;
      pauseMs: number;
      empty?(request: Question): { answer: Answer } | null;
    },
  ) {
    this.view = policy.initial;
  }

  readonly subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  readonly snapshot = () => this.view;

  want(request: Question): void {
    const key = this.policy.keyOf(request);
    this.wanted = { key, request };
    this.clearTimer();
    const empty = this.policy.empty?.(request);
    if (empty) {
      this.answer = empty.answer;
      this.answeredKey = key;
      this.failedKey = null;
      this.publish();
      return;
    }
    this.publish();
    if (this.settledFor(key)) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.send();
    }, this.policy.pauseMs);
  }

  /** A field commitment ends a pending typing pause. */
  commit(): void {
    if (this.timer === null) return;
    this.clearTimer();
    this.send();
  }

  retry(): void {
    this.failedKey = null;
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
  }

  private settledFor(key: Key): boolean {
    return key === this.answeredKey || key === this.failedKey;
  }
  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }
  private send(): void {
    const asked = this.wanted;
    if (!this.running || this.sending || !asked || this.settledFor(asked.key))
      return;
    this.sending = true;
    void this.policy
      .ask(asked.request)
      .catch((): ScheduledReadReply<Result> => ({ kind: "failed" }))
      .then((reply) => {
        this.sending = false;
        if (!this.running) return;
        if (asked.key !== this.wanted?.key) {
          if (this.timer === null) this.send();
          return;
        }
        this.answer =
          reply.kind === "answer" ? this.policy.answer(reply.result) : null;
        this.answeredKey = reply.kind === "answer" ? asked.key : null;
        this.failedKey = reply.kind === "answer" ? null : asked.key;
        this.publish();
      });
  }
  private publish(): void {
    const key = this.wanted?.key ?? null;
    const answered = key !== null && key === this.answeredKey;
    const failed = key !== null && key === this.failedKey;
    this.view = this.policy.present({
      shown: this.answer,
      current: answered ? this.answer : null,
      updating: key !== null && !answered && !failed,
      failed,
    });
    this.listeners.forEach((listener) => listener());
  }
}
