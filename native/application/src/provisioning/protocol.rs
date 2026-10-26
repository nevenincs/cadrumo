//! The `components` role's protocol: one command on the command line, one JSON object per
//! line on standard output, and the client's answers as JSON lines on standard input.
//!
//! `cadrumo --role components <command> [options]` runs one command of the engine:
//!
//! | command  | options                                   | does                               |
//! | -------- | ----------------------------------------- | ---------------------------------- |
//! | `status` | `--full`, `--item <id>`...                | every item's row, quick by default |
//! | `plan`   | `--item <id>`...                          | the plan a setup would ask for     |
//! | `setup`  | `--item <id>`..., `--approve <digest>`    | sets the items up                  |
//! | `verify` | `--item <id>`...                          | a full check, every item by default|
//! | `cancel` |                                           | stops setups in other processes    |
//! | `remove` | `--item <id>`... (at least one)           | removes the items                  |
//!
//! The role serves the local AI read-only: its engine is never admitted to provision it,
//! so `status` and `verify` report it with the recovery `set_up_in_desktop`, a `plan`,
//! `setup` or `remove` that names it is refused, and a setup of every item leaves it out.
//! Only the desktop, which links the engine and admits the models the person selected,
//! plans, pulls and removes the local AI.
//!
//! Output lines carry a `type`: `started` first, then any `phase`, `progress`, `notice`
//! and `review` events, and one `result` last. Every value is a closed code or a
//! locale-neutral fact (item ids, step and category codes, byte counts, versions,
//! digests); no line carries words, so each surface words the codes from its catalogue.
//!
//! A setup of an item another process is already setting up follows that setup: it sends
//! a `following` notice with the item and the digest of the plan that setup was approved
//! under, then that setup's phases, progress and notices as it publishes them, and its
//! result for the item. It sends no review and downloads nothing. A `cancel` line, or the
//! end of input, stops only the following, which then ends `busy`; to stop the setup it
//! follows, the client runs the `cancel` command, the person's act wherever it is asked.
//!
//! A setup without `--approve` sends a `review` with the plan and its digest and waits
//! for one input line: `{"type":"approve","plan_digest":"<digest>"}` approves exactly
//! that plan, and `{"type":"decline"}` declines it. `{"type":"cancel"}` stops a running
//! setup or check at its next transfer chunk and is acknowledged by a `cancel_requested`
//! notice. Closing standard input before the result declines a review and cancels a
//! running setup, so a setup never outlives the client that started it.
//!
//! The exit status is 0 when the result's outcome succeeded, 1 when it did not, and 64
//! when the command line names no command this protocol has; that answer is a lone
//! `result` line with the outcome `invalid_request`.

use super::{
    engine::{Answer, Engine, Event, Report, SetupRequest},
    items::ItemId,
    plan::SetupPlan,
    state::{self, CheckMode},
};
use crate::{component::Cancellation, error::Error, value::Sha256Digest};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    ffi::{OsStr, OsString},
    io::{BufRead, BufReader, Read, Write},
    sync::{Arc, Mutex, mpsc},
};

/// The protocol version the `started` line announces.
pub const PROTOCOL_VERSION: u32 = 1;

/// The exit status of a command line this protocol cannot read.
pub const INVALID_REQUEST: i32 = 64;

/// One command of the role.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Command {
    Status { mode: CheckMode, items: Vec<ItemId> },
    Plan { items: Option<Vec<ItemId>> },
    Setup(SetupRequest),
    Verify { items: Vec<ItemId> },
    Cancel,
    Remove { items: Vec<ItemId> },
}

impl Command {
    pub fn name(&self) -> &'static str {
        match self {
            Self::Status { .. } => "status",
            Self::Plan { .. } => "plan",
            Self::Setup(_) => "setup",
            Self::Verify { .. } => "verify",
            Self::Cancel => "cancel",
            Self::Remove { .. } => "remove",
        }
    }
}

/// One command line of the role.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CommandLine {
    pub command: Command,
}

impl CommandLine {
    /// The command line `arguments`, after the role's own, name; `None` for anything else.
    pub fn parse<T: AsRef<OsStr>>(arguments: &[T]) -> Option<Self> {
        let mut words = arguments.iter().map(|argument| argument.as_ref().to_str());
        let name = words.next()??;
        let mut items = Vec::new();
        let mut full = false;
        let mut approve = None;
        while let Some(word) = words.next() {
            match word? {
                "--item" => {
                    let item = ItemId::parse(words.next()??)?;
                    if !items.contains(&item) {
                        items.push(item);
                    }
                }
                "--full" if name == "status" && !full => full = true,
                "--approve" if name == "setup" && approve.is_none() => {
                    approve = Some(Sha256Digest::new(words.next()??).ok()?);
                }
                _ => return None,
            }
        }
        items.sort();
        let some = |items: Vec<ItemId>| (!items.is_empty()).then_some(items);
        let command = match name {
            "status" => Command::Status {
                mode: if full {
                    CheckMode::Full
                } else {
                    CheckMode::Quick
                },
                items: some(items).unwrap_or_else(|| ItemId::ALL.to_vec()),
            },
            "plan" => Command::Plan { items: some(items) },
            "setup" => Command::Setup(SetupRequest {
                items: some(items),
                approved: approve,
            }),
            "verify" => Command::Verify { items },
            "cancel" if items.is_empty() => Command::Cancel,
            "remove" if !items.is_empty() => Command::Remove { items },
            _ => return None,
        };
        Some(Self { command })
    }
}

/// One line the client sends.
#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum Input {
    Approve { plan_digest: Sha256Digest },
    Decline,
    Cancel,
}

/// The output stream, shared by the command and the input reader. A line that cannot be
/// written means the client is gone, which stops the command at its next chunk.
#[derive(Clone)]
struct Lines {
    output: Arc<Mutex<dyn Write + Send>>,
    cancellation: Arc<Cancellation>,
}

impl Lines {
    fn send(&self, line: &Value) {
        let mut output = self
            .output
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let written = serde_json::to_writer(&mut *output, line)
            .map_err(std::io::Error::from)
            .and_then(|()| output.write_all(b"\n"))
            .and_then(|()| output.flush());
        if written.is_err() {
            self.cancellation.cancel();
        }
    }
}

/// The JSON a plan is reviewed as: the digested document, which is every entry in order
/// with its parts, plus the totals and the free-space reading the digest leaves out.
pub fn plan_value(plan: &SetupPlan) -> Value {
    let mut value = plan.digest_document();
    value["known_download_bytes"] = json!(plan.known_download_bytes());
    value["has_unknown_size"] = json!(plan.has_unknown_size());
    value["installs_outside_program"] = json!(plan.installs_outside_program());
    value["space"] = json!({
        "free_bytes": plan.space.free_bytes,
        "required_bytes": plan.space.required_bytes,
        "sufficient": plan.space.sufficient(),
    });
    value
}

/// The line an engine event is sent as.
pub fn event_value(event: Event) -> Value {
    match event {
        Event::Phase { item, step } => json!({
            "type": "phase",
            "phase_code": step.phase_code(item),
            "item_id": item,
            "step": step,
        }),
        Event::Progress {
            item,
            completed,
            total,
        } => json!({
            "type": "progress",
            "subject_code": item,
            "unit_code": "bytes",
            "completed": completed,
            "total": total,
        }),
        Event::Retrying {
            item,
            attempt,
            delay,
        } => json!({
            "type": "notice",
            "notice_code": "retrying",
            "subject_code": item,
            "attempt": attempt,
            "delay_ms": u64::try_from(delay.as_millis()).unwrap_or(u64::MAX),
        }),
        Event::WaitingForServer { item } => json!({
            "type": "notice",
            "notice_code": "waiting_for_server",
            "subject_code": item,
        }),
        Event::Following { item, plan_digest } => json!({
            "type": "notice",
            "notice_code": "following",
            "subject_code": item,
            "plan_digest": plan_digest,
        }),
    }
}

/// The line a review is sent as.
pub fn review_value(plan: &SetupPlan) -> Value {
    json!({
        "type": "review",
        "plan_digest": plan.digest(),
        "plan": plan_value(plan),
    })
}

/// The last line of a command.
pub fn result_value(command: Option<&Command>, report: &Report) -> Value {
    let mut value = json!({
        "type": "result",
        "command": command.map(Command::name),
        "outcome": report.outcome,
        "mode": report.mode,
        "rows": report.rows,
        "setup_complete": state::setup_complete(&report.rows),
    });
    if let Some(plan) = &report.plan {
        value["plan"] = plan_value(plan);
        value["plan_digest"] = json!(plan.digest());
    }
    if let Some(item) = report.item {
        value["item_id"] = json!(item);
    }
    if let Some(failure) = report.failure {
        value["failure_category"] = json!(failure);
    }
    if matches!(command, Some(Command::Cancel | Command::Remove { .. })) {
        value["items"] = json!(report.items);
    }
    value
}

/// Reads the client's lines until its input ends: answers go to the waiting review,
/// a cancel sets the command's cancellation. The end of input declines a review still
/// waiting and, when `cancel_at_end`, cancels the running command.
fn read_input(
    input: impl Read,
    lines: &Lines,
    answers: &mpsc::Sender<Answer>,
    cancel_at_end: bool,
) {
    let mut reader = BufReader::new(input);
    let mut line = String::new();
    loop {
        line.clear();
        match (&mut reader).take(64 * 1024).read_line(&mut line) {
            Ok(0) | Err(_) => break,
            Ok(_) => {}
        }
        match serde_json::from_str::<Input>(line.trim()) {
            Ok(Input::Approve { plan_digest }) => {
                let _ = answers.send(Answer::Approve(plan_digest));
            }
            Ok(Input::Decline) => {
                let _ = answers.send(Answer::Decline);
            }
            Ok(Input::Cancel) => {
                lines.cancellation.cancel();
                lines.send(&json!({"type": "notice", "notice_code": "cancel_requested"}));
            }
            Err(_) => lines.send(&json!({"type": "notice", "notice_code": "input_refused"})),
        }
    }
    let _ = answers.send(Answer::Decline);
    if cancel_at_end {
        lines.cancellation.cancel();
    }
}

/// Runs the command `arguments` name against the engine `engine` makes, reading the
/// client's lines from `input` and writing the protocol to `output`, and returns the
/// exit status.
pub fn serve(
    arguments: &[OsString],
    input: impl Read + Send + 'static,
    output: impl Write + Send + 'static,
    engine: impl FnOnce() -> Result<Engine, Error>,
) -> i32 {
    let cancellation = Arc::new(Cancellation::default());
    let lines = Lines {
        output: Arc::new(Mutex::new(output)),
        cancellation: cancellation.clone(),
    };
    let Some(CommandLine { command }) = CommandLine::parse(arguments) else {
        lines.send(&json!({
            "type": "result",
            "command": null,
            "outcome": "invalid_request",
        }));
        return INVALID_REQUEST;
    };
    lines.send(&json!({
        "type": "started",
        "protocol": PROTOCOL_VERSION,
        "command": command.name(),
    }));
    let (answer, answers) = mpsc::channel();
    let reader = {
        let lines = lines.clone();
        let cancel_at_end = matches!(command, Command::Setup(_));
        std::thread::Builder::new()
            .name("cadrumo-components-input".into())
            .spawn(move || read_input(input, &lines, &answer, cancel_at_end))
    };
    if reader.is_err() {
        cancellation.cancel();
    }
    let mut engine = match engine() {
        Ok(engine) => engine,
        Err(error) => {
            // A setting the engine cannot use is a classified refusal of its own, not a
            // protocol fault: the surfaces word the category they are given.
            lines.send(&json!({
                "type": "result",
                "command": command.name(),
                "outcome": "failed",
                "failure_category": super::browser::failure_category(&error),
            }));
            return 1;
        }
    };
    let mut events = |event| lines.send(&event_value(event));
    let report = match &command {
        Command::Status { mode, items } => engine.status(*mode, items, &mut events, &cancellation),
        Command::Plan { items } => engine.plan(items.as_deref()),
        Command::Setup(request) => {
            let mut review = |plan: &SetupPlan| {
                lines.send(&review_value(plan));
                answers.recv().unwrap_or(Answer::Decline)
            };
            engine.setup(request, &mut review, &mut events, &cancellation)
        }
        Command::Verify { items } => engine.verify(items, &mut events, &cancellation),
        Command::Cancel => engine.request_cancel(),
        Command::Remove { items } => engine.remove(items, &mut events),
    };
    lines.send(&result_value(Some(&command), &report));
    if report.outcome.succeeded() { 0 } else { 1 }
}

#[cfg(test)]
mod tests;
