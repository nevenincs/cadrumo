//! A run's progress frames, as `streaming/sse_frames.py` declares them,
//! mapped onto the column's stream events.
//!
//! Frames are droppable, and the column applies a reply's text by each
//! chunk's sequence, so this passes on only numbered text from a stream that
//! starts at sequence 1. A gap in the sequence is not a loss yet: the stream
//! is reopened after the last frame mapped, and the gateway's replay fills
//! it. Only what a replay cannot cover ends the stream as lost: a drop
//! notice, a refused stream, a first numbered frame after sequence 1, an
//! unnumbered chunk, or a chunk at the frame's text cap, which may have been
//! cut. A reply's text is one message however many tool calls come between
//! its parts, as cadrumo-agent keeps it. The agent's own reasoning is passed
//! on beside it, numbered the same way; what a subagent thinks is not.

use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeSet, HashMap};

/// The gateway's frame version.
const FRAME_VERSION: &str = "v1";
/// `MAX_PROGRESS_CONTENT_CHARS`: a chunk this long may have been cut.
const CONTENT_CAP: usize = 16 * 1024;
/// cadrumo-agent's `ToolKind`.
pub const TOOL_KINDS: &[&str] = &[
    "read",
    "edit",
    "delete",
    "move",
    "search",
    "execute",
    "think",
    "fetch",
    "switch_mode",
    "other",
];
/// cadrumo-agent's `ToolCallStatus`.
pub const TOOL_STATUSES: &[&str] = &["pending", "in_progress", "completed", "failed"];
/// cadrumo-agent's bound on a refusal's code and recovery action identifier.
const REFUSAL_TOKEN_CAP: usize = 128;
/// The prefix every operator action identifier carries.
const ACTION_PREFIX: &str = "operator.";

/// Why the product refused a failed tool call, as the agent read it from the
/// tool's result: the refusal's closed token and, where the refusal names
/// one, the operator action that recovers from it. Identifiers for routing,
/// never shown.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ToolRefusal {
    pub code: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recovery_action_id: Option<String>,
}

/// A refusal token: lower-case letters, digits, `_` and `.`, within the cap.
fn refusal_token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= REFUSAL_TOKEN_CAP
        && value
            .bytes()
            .all(|byte| matches!(byte, b'a'..=b'z' | b'0'..=b'9' | b'_' | b'.'))
}

/// A failed update's refusal, checked again here: anything not exactly the
/// declared shape is no refusal, and the call is shown without one.
fn refusal(frame: &Value) -> Option<ToolRefusal> {
    let refusal = frame.get("refusal")?.as_object()?;
    if refusal
        .keys()
        .any(|key| key != "code" && key != "recovery_action_id")
    {
        return None;
    }
    let code = refusal
        .get("code")?
        .as_str()
        .filter(|code| refusal_token(code))?;
    let recovery_action_id = match refusal.get("recovery_action_id") {
        None => None,
        Some(action) => Some(action.as_str().filter(|action| {
            refusal_token(action)
                && action
                    .strip_prefix(ACTION_PREFIX)
                    .is_some_and(|rest| !rest.is_empty())
        })?),
    };
    Some(ToolRefusal {
        code: code.to_owned(),
        recovery_action_id: recovery_action_id.map(str::to_owned),
    })
}

/// A tool call as the agent reports it.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ToolCall {
    pub id: String,
    /// The tool's name, as the agent gives it.
    pub title: String,
    pub tool_kind: String,
    pub status: String,
    /// Present only on a call that failed because the product refused it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub refusal: Option<ToolRefusal>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Question {
    pub id: String,
    pub prompt: String,
    pub kind: String,
    /// A choice's options; null for a text question.
    pub options: Option<Vec<String>>,
    pub required: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Questionnaire {
    pub request_id: String,
    pub reply_id: String,
    pub questions: Vec<Question>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ApprovalOption {
    pub option_id: String,
    /// The option's own name, which may be absent: the card words an option
    /// by its kind.
    pub name: Option<String>,
    pub kind: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Approval {
    pub request_id: String,
    pub reply_id: String,
    pub source: &'static str,
    /// The tool the agent wants to call, as the agent names it.
    pub tool_call: Option<String>,
    pub description: Option<String>,
    /// One of the agent's ten tool kinds.
    pub tool_kind: Option<String>,
    pub options: Vec<ApprovalOption>,
}

/// How a run ended, as its terminal frame names it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RunEnd {
    Completed,
    Failed,
    Cancelled,
}

/// One change to a watched conversation, as `AgentStreamEvent` names it.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum StreamEvent {
    ReplyStarted {
        reply_id: String,
    },
    Text {
        reply_id: String,
        message_id: String,
        sequence: u64,
        delta: String,
    },
    Thought {
        reply_id: String,
        message_id: String,
        sequence: u64,
        delta: String,
    },
    Tool {
        reply_id: String,
        tool: ToolCall,
    },
    Questions {
        reply_id: String,
        questionnaire: Questionnaire,
    },
    Approval {
        reply_id: String,
        approval: Approval,
    },
    Resolved {
        reply_id: String,
        request_id: String,
    },
    Settled {
        reply_id: String,
        status: RunEnd,
        #[serde(skip_serializing_if = "Option::is_none")]
        provider_condition: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        failure_reason: Option<String>,
    },
    Lost {
        #[serde(skip_serializing_if = "Option::is_none")]
        reply_id: Option<String>,
    },
}

/// What the stream's owner does next.
#[derive(Debug, PartialEq, Eq)]
pub enum Step {
    Emit(StreamEvent),
    /// Read the run's status for the questionnaire `request_id` names: the
    /// frame carries only the handle.
    ReadQuestionnaire(String),
    /// The run ended; a failed one's condition and reason are read from its
    /// status.
    Settle(RunEnd),
    /// A frame was skipped: reopen the stream after the last frame mapped,
    /// whose replay serves what was missed.
    Resume,
    /// Nothing more is read from this stream.
    End,
}

/// One run's stream, mapped frame by frame.
pub struct Mapping {
    reply_id: String,
    started: bool,
    last_sequence: u64,
    tools: HashMap<String, ToolCall>,
    pending: BTreeSet<String>,
    ended: bool,
}

fn text<'a>(frame: &'a Value, key: &str) -> Option<&'a str> {
    frame.get(key).and_then(Value::as_str)
}

impl Mapping {
    /// The run's id is the reply's handle: one run is one reply.
    pub fn new(run_id: &str) -> Self {
        Self {
            reply_id: run_id.to_owned(),
            started: false,
            last_sequence: 0,
            tools: HashMap::new(),
            pending: BTreeSet::new(),
            ended: false,
        }
    }

    pub fn ended(&self) -> bool {
        self.ended
    }

    /// The id of the last numbered frame, to resume after it.
    pub fn resume_cursor(&self) -> Option<String> {
        (self.last_sequence > 0).then(|| format!("{}:{}", self.reply_id, self.last_sequence))
    }

    fn lost(&mut self) -> Vec<Step> {
        self.ended = true;
        vec![
            Step::Emit(StreamEvent::Lost {
                reply_id: Some(self.reply_id.clone()),
            }),
            Step::End,
        ]
    }

    /// Ends the stream as lost: its connection could not go on.
    pub fn interrupted(&mut self) -> Vec<Step> {
        if self.ended {
            return Vec::new();
        }
        self.lost()
    }

    /// The request answered here, if it is still pending.
    pub fn resolve(&mut self, request_id: &str) -> Option<StreamEvent> {
        self.pending
            .remove(request_id)
            .then(|| StreamEvent::Resolved {
                reply_id: self.reply_id.clone(),
                request_id: request_id.to_owned(),
            })
    }

    /// Maps one SSE event's data.
    pub fn frame(&mut self, data: &str) -> Vec<Step> {
        if self.ended {
            return Vec::new();
        }
        let Ok(frame) = serde_json::from_str::<Value>(data) else {
            return self.lost();
        };
        if !frame.is_object() || text(&frame, "api_version") != Some(FRAME_VERSION) {
            return self.lost();
        }
        let kind = text(&frame, "type")
            .filter(|kind| !kind.is_empty())
            .or_else(|| text(&frame, "event_type"))
            .unwrap_or_default()
            .to_owned();
        let mut sequence = None;
        if let Some(numbered) = frame.get("sequence") {
            let Some(numbered) = numbered.as_u64().filter(|s| *s > 0) else {
                return self.lost();
            };
            if numbered <= self.last_sequence {
                // A replayed frame this stream already mapped.
                return Vec::new();
            }
            if self.last_sequence == 0 && numbered != 1 {
                // What came before the first retained frame is gone.
                return self.lost();
            }
            if self.last_sequence > 0 && numbered != self.last_sequence + 1 {
                return vec![Step::Resume];
            }
            self.last_sequence = numbered;
            sequence = Some(numbered);
        }
        let mut steps = Vec::new();
        if !self.started {
            self.started = true;
            steps.push(Step::Emit(StreamEvent::ReplyStarted {
                reply_id: self.reply_id.clone(),
            }));
        }
        let mapped = match kind.as_str() {
            "message_chunk" => self.message_chunk(&frame, sequence),
            "thought_chunk" => Ok(self.thought_chunk(&frame, sequence)),
            "tool_call_start" => self.tool_call(&frame, false),
            "tool_call_update" => self.tool_call(&frame, true),
            "permission_request" => self.permission(&frame),
            "clarification_pending" => match text(&frame, "request_id") {
                Some(request) if !request.is_empty() => {
                    Ok(vec![Step::ReadQuestionnaire(request.to_owned())])
                }
                _ => Err(()),
            },
            "thread_terminal" => self.terminal(&frame),
            "progress_dropped" | "stream_rejected" => Err(()),
            // Snapshots, heartbeats, plans, artifacts, agent
            // status and errors carry nothing the column shows; a kind
            // nobody declared is the catalog moving ahead.
            _ => Ok(Vec::new()),
        };
        match mapped {
            Ok(mapped) => {
                steps.extend(mapped);
                steps
            }
            Err(()) => {
                steps.extend(self.lost());
                steps
            }
        }
    }

    fn message_chunk(&mut self, frame: &Value, sequence: Option<u64>) -> Result<Vec<Step>, ()> {
        let content = match frame.get("content") {
            None | Some(Value::Null) => return Ok(Vec::new()),
            Some(Value::String(content)) => content,
            Some(_) => return Err(()),
        };
        if content.is_empty() {
            return Ok(Vec::new());
        }
        let message = text(frame, "message_id")
            .filter(|id| !id.is_empty())
            .ok_or(())?;
        // Text is applied by its sequence: unnumbered or possibly cut text
        // cannot be applied faithfully.
        let sequence = sequence.ok_or(())?;
        if content.chars().count() >= CONTENT_CAP {
            return Err(());
        }
        Ok(vec![Step::Emit(StreamEvent::Text {
            reply_id: self.reply_id.clone(),
            message_id: message.to_owned(),
            sequence,
            delta: content.clone(),
        })])
    }

    /// The agent's reasoning, shown only as a preview: a chunk that cannot be
    /// placed by its sequence, or that a subagent thought, is left out rather
    /// than ending the stream, and one at the cap is shown as it came.
    fn thought_chunk(&self, frame: &Value, sequence: Option<u64>) -> Vec<Step> {
        let (Some(sequence), Some(content)) = (sequence, text(frame, "content")) else {
            return Vec::new();
        };
        let message = text(frame, "message_id").filter(|id| !id.is_empty());
        let subagent = text(frame, "subagent_id").is_some_and(|id| !id.is_empty());
        match message {
            Some(message) if !content.is_empty() && !subagent => {
                vec![Step::Emit(StreamEvent::Thought {
                    reply_id: self.reply_id.clone(),
                    message_id: message.to_owned(),
                    sequence,
                    delta: content.to_owned(),
                })]
            }
            _ => Vec::new(),
        }
    }

    fn tool_call(&mut self, frame: &Value, update: bool) -> Result<Vec<Step>, ()> {
        let id = text(frame, "tool_call_id")
            .filter(|id| !id.is_empty())
            .ok_or(())?;
        let status = match text(frame, "status") {
            None => None,
            Some(status) if TOOL_STATUSES.contains(&status) => Some(status),
            Some(_) => return Err(()),
        };
        let kind = match text(frame, "kind") {
            None => None,
            Some(kind) if TOOL_KINDS.contains(&kind) => Some(kind),
            Some(_) => return Err(()),
        };
        let title = text(frame, "title").filter(|title| !title.is_empty());
        // Only an update that ends the call failed may say the product
        // refused it.
        let refused = if update && status == Some("failed") {
            refusal(frame)
        } else {
            None
        };
        let tool = match self.tools.get_mut(id) {
            Some(tool) => {
                if let Some(title) = title {
                    title.clone_into(&mut tool.title);
                }
                if let Some(kind) = kind {
                    kind.clone_into(&mut tool.tool_kind);
                }
                if let Some(status) = status {
                    status.clone_into(&mut tool.status);
                    tool.refusal.clone_from(&refused);
                }
                tool.clone()
            }
            None => {
                // A call first seen without its name, kind or status cannot
                // be shown as it is.
                let tool = ToolCall {
                    id: id.to_owned(),
                    title: title.ok_or(())?.to_owned(),
                    tool_kind: kind.ok_or(())?.to_owned(),
                    status: status.ok_or(())?.to_owned(),
                    refusal: refused,
                };
                self.tools.insert(id.to_owned(), tool.clone());
                tool
            }
        };
        Ok(vec![Step::Emit(StreamEvent::Tool {
            reply_id: self.reply_id.clone(),
            tool,
        })])
    }

    fn permission(&mut self, frame: &Value) -> Result<Vec<Step>, ()> {
        let request_id = text(frame, "request_id")
            .filter(|id| !id.is_empty())
            .ok_or(())?;
        let options: Vec<ApprovalOption> = frame
            .get("options")
            .and_then(Value::as_array)
            .ok_or(())?
            .iter()
            .filter_map(|option| {
                let kind = text(option, "kind")?;
                if !matches!(
                    kind,
                    "allow_once"
                        | "allow_session"
                        | "allow_always"
                        | "reject_once"
                        | "reject_always"
                ) {
                    return None;
                }
                Some(ApprovalOption {
                    option_id: text(option, "option_id")
                        .filter(|id| !id.is_empty())?
                        .to_owned(),
                    name: text(option, "name").map(str::to_owned),
                    kind: kind.to_owned(),
                })
            })
            .collect();
        // An option the column cannot word is left out; none at all cannot be answered.
        if options.is_empty() {
            return Err(());
        }
        self.pending.insert(request_id.to_owned());
        Ok(vec![Step::Emit(StreamEvent::Approval {
            reply_id: self.reply_id.clone(),
            approval: Approval {
                request_id: request_id.to_owned(),
                reply_id: self.reply_id.clone(),
                source: "agent_tool",
                tool_call: text(frame, "tool_call").map(str::to_owned),
                description: text(frame, "description").map(str::to_owned),
                // A kind the agent's vocabulary does not hold is not shown.
                tool_kind: text(frame, "tool_kind")
                    .filter(|kind| TOOL_KINDS.contains(kind))
                    .map(str::to_owned),
                options,
            },
        })])
    }

    /// The questionnaire run-status discloses, if it is the one `request_id`
    /// names and is well formed.
    pub fn questionnaire(&mut self, request_id: &str, status: &Value) -> Option<StreamEvent> {
        let pending = status.get("pending_clarification")?;
        if text(pending, "request_id") != Some(request_id) || self.ended {
            return None;
        }
        let questions = pending
            .get("questions")?
            .as_array()?
            .iter()
            .map(|question| {
                let kind = text(question, "kind").filter(|k| matches!(*k, "choice" | "text"))?;
                Some(Question {
                    id: text(question, "id")?.to_owned(),
                    prompt: text(question, "prompt")?.to_owned(),
                    kind: kind.to_owned(),
                    options: match question.get("options") {
                        None | Some(Value::Null) => None,
                        Some(options) => Some(
                            options
                                .as_array()?
                                .iter()
                                .map(|o| o.as_str().map(str::to_owned))
                                .collect::<Option<Vec<_>>>()?,
                        ),
                    },
                    required: question
                        .get("required")
                        .map_or(Some(true), Value::as_bool)?,
                })
            })
            .collect::<Option<Vec<_>>>()?;
        if questions.is_empty() {
            return None;
        }
        self.pending.insert(request_id.to_owned());
        Some(StreamEvent::Questions {
            reply_id: self.reply_id.clone(),
            questionnaire: Questionnaire {
                request_id: request_id.to_owned(),
                reply_id: self.reply_id.clone(),
                questions,
            },
        })
    }

    fn terminal(&mut self, frame: &Value) -> Result<Vec<Step>, ()> {
        let end = match text(frame, "status") {
            Some("completed" | "archived") => RunEnd::Completed,
            Some("cancelled") => RunEnd::Cancelled,
            Some("failed") => RunEnd::Failed,
            _ => return Err(()),
        };
        self.ended = true;
        // A settled run expires whatever it still waited on.
        let mut steps: Vec<Step> = std::mem::take(&mut self.pending)
            .into_iter()
            .map(|request_id| {
                Step::Emit(StreamEvent::Resolved {
                    reply_id: self.reply_id.clone(),
                    request_id,
                })
            })
            .collect();
        steps.push(Step::Settle(end));
        steps.push(Step::End);
        Ok(steps)
    }

    /// The settled event. A failed run carries its provider condition and
    /// the agent's one line about it, read from its status.
    pub fn settled(&self, end: RunEnd, status: Option<&Value>) -> StreamEvent {
        let read = |key: &str| {
            (end == RunEnd::Failed)
                .then(|| {
                    status
                        .and_then(|status| text(status, key))
                        .map(str::to_owned)
                })
                .flatten()
        };
        StreamEvent::Settled {
            reply_id: self.reply_id.clone(),
            status: end,
            provider_condition: read("provider_condition"),
            failure_reason: read("failure_reason"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    /// A frame as `encode_sse_frame` emits it: the kind under both keys, the
    /// version, the identity keys, and the catalogued fields.
    fn frame(kind: &str, sequence: Option<u64>, fields: Value) -> String {
        let mut body = json!({
            "api_version": "v1",
            "type": kind,
            "event_type": kind,
            "thread_id": "run-1",
        });
        if let Some(sequence) = sequence {
            body["sequence"] = json!(sequence);
        }
        for (key, value) in fields.as_object().unwrap() {
            body[key] = value.clone();
        }
        body.to_string()
    }

    fn events(steps: Vec<Step>) -> Vec<StreamEvent> {
        steps
            .into_iter()
            .filter_map(|step| match step {
                Step::Emit(event) => Some(event),
                _ => None,
            })
            .collect()
    }

    fn chunk(sequence: u64, message: &str, content: &str) -> String {
        frame(
            "message_chunk",
            Some(sequence),
            json!({"message_id": message, "timestamp": 1.5, "content": content, "finish_reason": null}),
        )
    }

    #[test]
    fn a_reply_streams_text_by_sequence_and_tool_calls_whole() {
        let mut mapping = Mapping::new("run-1");
        let mut seen = events(mapping.frame(&frame(
            "stream_snapshot",
            None,
            json!({"status": "running"}),
        )));
        seen.extend(events(mapping.frame(&chunk(1, "m1", "Hola, "))));
        seen.extend(events(mapping.frame(&frame(
            "tool_call_start",
            Some(2),
            json!({"tool_call_id": "t1", "title": "ledger_list", "kind": "read", "status": "pending", "locations": []}),
        ))));
        seen.extend(events(mapping.frame(&frame(
            "tool_call_update",
            Some(3),
            json!({"tool_call_id": "t1", "status": "completed"}),
        ))));
        // Text after a tool is more of the same message.
        seen.extend(events(mapping.frame(&chunk(4, "m1", "\n\nListo."))));
        seen.extend(events(mapping.frame(&frame(
            "heartbeat",
            None,
            json!({"server_uptime_seconds": 3.0}),
        ))));
        assert_eq!(
            serde_json::to_value(&seen).unwrap(),
            json!([
                {"type": "reply_started", "reply_id": "run-1"},
                {"type": "text", "reply_id": "run-1", "message_id": "m1", "sequence": 1, "delta": "Hola, "},
                {"type": "tool", "reply_id": "run-1", "tool": {"id": "t1", "title": "ledger_list", "tool_kind": "read", "status": "pending"}},
                {"type": "tool", "reply_id": "run-1", "tool": {"id": "t1", "title": "ledger_list", "tool_kind": "read", "status": "completed"}},
                {"type": "text", "reply_id": "run-1", "message_id": "m1", "sequence": 4, "delta": "\n\nListo."},
            ])
        );
        let steps = mapping.frame(&frame(
            "thread_terminal",
            Some(5),
            json!({"status": "completed", "replay": false}),
        ));
        assert_eq!(steps, [Step::Settle(RunEnd::Completed), Step::End]);
        assert!(mapping.ended());
        assert_eq!(
            serde_json::to_value(mapping.settled(
                RunEnd::Completed,
                Some(&json!({"provider_condition": "unknown"}))
            ))
            .unwrap(),
            json!({"type": "settled", "reply_id": "run-1", "status": "completed"})
        );
        assert!(mapping.frame(&chunk(6, "m1", "late")).is_empty());
    }

    #[test]
    fn the_agents_own_thoughts_stream_beside_its_text() {
        let mut mapping = Mapping::new("run-1");
        let thought = |sequence, fields: Value| {
            let mut body = json!({"message_id": "m1", "timestamp": 1.5});
            for (key, value) in fields.as_object().unwrap() {
                body[key] = value.clone();
            }
            frame("thought_chunk", Some(sequence), body)
        };
        let mut seen = events(mapping.frame(&thought(1, json!({"content": "Leo el libro."}))));
        // A subagent's thought and an empty one are left out, and the stream
        // goes on.
        seen.extend(events(mapping.frame(&thought(
            2,
            json!({"content": "otro", "subagent_id": "sub-1", "parent_tool_call_id": "t1"}),
        ))));
        seen.extend(events(mapping.frame(&thought(3, json!({"content": ""})))));
        seen.extend(events(mapping.frame(&chunk(4, "m2", "Listo."))));
        assert_eq!(
            serde_json::to_value(&seen).unwrap(),
            json!([
                {"type": "reply_started", "reply_id": "run-1"},
                {"type": "thought", "reply_id": "run-1", "message_id": "m1", "sequence": 1, "delta": "Leo el libro."},
                {"type": "text", "reply_id": "run-1", "message_id": "m2", "sequence": 4, "delta": "Listo."},
            ])
        );
        assert!(!mapping.ended());
    }

    /// The tool event a failed update of `t1` maps to, after its start.
    fn failed_update(fields: Value) -> Vec<StreamEvent> {
        let mut mapping = Mapping::new("run-1");
        mapping.frame(&frame(
            "tool_call_start",
            Some(1),
            json!({"tool_call_id": "t1", "title": "browser_capture", "kind": "fetch", "status": "in_progress"}),
        ));
        let mut body = json!({"tool_call_id": "t1", "status": "failed"});
        for (key, value) in fields.as_object().unwrap() {
            body[key] = value.clone();
        }
        events(mapping.frame(&frame("tool_call_update", Some(2), body)))
    }

    fn refusal_of(events: &[StreamEvent]) -> Option<ToolRefusal> {
        match events {
            [StreamEvent::Tool { tool, .. }] => {
                assert_eq!(tool.status, "failed");
                tool.refusal.clone()
            }
            other => panic!("expected one tool event, got {other:?}"),
        }
    }

    #[test]
    fn a_refused_tool_call_carries_its_code_and_recovery_action() {
        let seen = failed_update(json!({
            "refusal": {"code": "operation_not_successful", "recovery_action_id": "operator.provision.browser"}
        }));
        assert_eq!(
            refusal_of(&seen),
            Some(ToolRefusal {
                code: "operation_not_successful".into(),
                recovery_action_id: Some("operator.provision.browser".into()),
            })
        );
        assert_eq!(
            serde_json::to_value(&seen[0]).unwrap()["tool"]["refusal"],
            json!({"code": "operation_not_successful", "recovery_action_id": "operator.provision.browser"})
        );
        // A refusal that names no recovery is still a refusal.
        let bare = failed_update(json!({"refusal": {"code": "person_act_required"}}));
        assert_eq!(
            refusal_of(&bare),
            Some(ToolRefusal {
                code: "person_act_required".into(),
                recovery_action_id: None,
            })
        );
        assert_eq!(
            serde_json::to_value(&bare[0]).unwrap()["tool"]["refusal"],
            json!({"code": "person_act_required"})
        );
    }

    #[test]
    fn a_failed_tool_call_without_a_refusal_has_none() {
        let seen = failed_update(json!({}));
        assert_eq!(refusal_of(&seen), None);
        assert!(
            serde_json::to_value(&seen[0]).unwrap()["tool"]
                .get("refusal")
                .is_none()
        );
    }

    #[test]
    fn a_malformed_refusal_is_dropped_and_the_call_still_shown() {
        let long = format!("operator.{}", "a".repeat(REFUSAL_TOKEN_CAP));
        for (name, refusal) in [
            ("not an object", json!("operator.provision.browser")),
            (
                "no code",
                json!({"recovery_action_id": "operator.provision.browser"}),
            ),
            ("empty code", json!({"code": ""})),
            (
                "upper-case code",
                json!({"code": "OPERATION_NOT_SUCCESSFUL"}),
            ),
            ("code with a space", json!({"code": "not successful"})),
            ("code not text", json!({"code": 7})),
            (
                "code over the cap",
                json!({"code": "a".repeat(REFUSAL_TOKEN_CAP + 1)}),
            ),
            (
                "action without the operator prefix",
                json!({"code": "x", "recovery_action_id": "provision.browser"}),
            ),
            (
                "bare operator prefix",
                json!({"code": "x", "recovery_action_id": "operator."}),
            ),
            (
                "upper-case action",
                json!({"code": "x", "recovery_action_id": "operator.Provision.browser"}),
            ),
            (
                "action over the cap",
                json!({"code": "x", "recovery_action_id": long}),
            ),
            (
                "action null",
                json!({"code": "x", "recovery_action_id": null}),
            ),
            (
                "undeclared field",
                json!({"code": "x", "recovery_action_id": "operator.provision.browser", "message": "m"}),
            ),
        ] {
            let seen = failed_update(json!({ "refusal": refusal }));
            assert_eq!(refusal_of(&seen), None, "{name}");
        }
    }

    #[test]
    fn a_refusal_on_a_call_that_did_not_fail_is_dropped() {
        let refusal = json!({"code": "operation_not_successful", "recovery_action_id": "operator.provision.model"});
        for status in ["pending", "in_progress", "completed"] {
            let mut mapping = Mapping::new("run-1");
            mapping.frame(&frame(
                "tool_call_start",
                Some(1),
                json!({"tool_call_id": "t1", "title": "x", "kind": "read", "status": "pending"}),
            ));
            let seen = events(mapping.frame(&frame(
                "tool_call_update",
                Some(2),
                json!({"tool_call_id": "t1", "status": status, "refusal": refusal}),
            )));
            match &seen[..] {
                [StreamEvent::Tool { tool, .. }] => assert_eq!(tool.refusal, None, "{status}"),
                other => panic!("{status}: {other:?}"),
            }
        }
        // An update that names no status says nothing about how the call ended.
        let mut mapping = Mapping::new("run-1");
        mapping.frame(&frame(
            "tool_call_start",
            Some(1),
            json!({"tool_call_id": "t1", "title": "x", "kind": "read", "status": "pending"}),
        ));
        let seen = events(mapping.frame(&frame(
            "tool_call_update",
            Some(2),
            json!({"tool_call_id": "t1", "refusal": refusal}),
        )));
        assert!(matches!(&seen[..], [StreamEvent::Tool { tool, .. }] if tool.refusal.is_none()));
        // A start frame is not where a refusal is carried, even a failed one.
        let mut mapping = Mapping::new("run-1");
        let seen = events(mapping.frame(&frame(
            "tool_call_start",
            Some(1),
            json!({"tool_call_id": "t1", "title": "x", "kind": "read", "status": "failed", "refusal": refusal}),
        )));
        assert!(matches!(&seen[..], [_, StreamEvent::Tool { tool, .. }] if tool.refusal.is_none()));
        // A failed call that later reports another status no longer carries it.
        let mut mapping = Mapping::new("run-1");
        mapping.frame(&frame(
            "tool_call_start",
            Some(1),
            json!({"tool_call_id": "t1", "title": "x", "kind": "read", "status": "pending"}),
        ));
        mapping.frame(&frame(
            "tool_call_update",
            Some(2),
            json!({"tool_call_id": "t1", "status": "failed", "refusal": refusal}),
        ));
        let seen = events(mapping.frame(&frame(
            "tool_call_update",
            Some(3),
            json!({"tool_call_id": "t1", "status": "completed"}),
        )));
        assert!(matches!(&seen[..], [StreamEvent::Tool { tool, .. }] if tool.refusal.is_none()));
    }

    #[test]
    fn replayed_frames_are_mapped_once_and_the_cursor_resumes_after_the_last() {
        let mut mapping = Mapping::new("run-1");
        assert_eq!(events(mapping.frame(&chunk(1, "m1", "ab"))).len(), 2);
        assert_eq!(mapping.resume_cursor().as_deref(), Some("run-1:1"));
        assert!(mapping.frame(&chunk(1, "m1", "ab")).is_empty());
        assert_eq!(
            events(mapping.frame(&chunk(2, "m1", "c"))),
            [StreamEvent::Text {
                reply_id: "run-1".into(),
                message_id: "m1".into(),
                sequence: 2,
                delta: "c".into()
            }]
        );
    }

    #[test]
    fn what_a_replay_cannot_cover_ends_the_stream_as_lost() {
        let lost = [
            Step::Emit(StreamEvent::Lost {
                reply_id: Some("run-1".into()),
            }),
            Step::End,
        ];
        let cut = "x".repeat(CONTENT_CAP);
        for (name, frames) in [
            // The retained window starts after the run's first frame.
            ("first frame after sequence 1", vec![chunk(4, "m1", "a")]),
            (
                "unnumbered chunk",
                vec![frame(
                    "message_chunk",
                    None,
                    json!({"message_id": "m1", "content": "a"}),
                )],
            ),
            ("chunk at the cap", vec![chunk(1, "m1", &cut)]),
            (
                "drop notice",
                vec![frame(
                    "progress_dropped",
                    None,
                    json!({"reason": "replay_window_exceeded", "first_sequence": 40}),
                )],
            ),
            (
                "rejected",
                vec![frame(
                    "stream_rejected",
                    None,
                    json!({"reason": "too_many"}),
                )],
            ),
            (
                "other version",
                vec![r#"{"api_version":"v2","type":"heartbeat"}"#.to_owned()],
            ),
            ("not json", vec!["{".to_owned()]),
            (
                "unknown terminal",
                vec![frame(
                    "thread_terminal",
                    Some(1),
                    json!({"status": "repair_needed"}),
                )],
            ),
            (
                "unnamed tool",
                vec![frame(
                    "tool_call_start",
                    Some(1),
                    json!({"tool_call_id": "t1", "kind": "read", "status": "pending"}),
                )],
            ),
            (
                "unknown tool kind",
                vec![frame(
                    "tool_call_start",
                    Some(1),
                    json!({"tool_call_id": "t1", "title": "x", "kind": "teleport", "status": "pending"}),
                )],
            ),
            (
                "unanswerable approval",
                vec![frame(
                    "permission_request",
                    Some(1),
                    json!({"request_id": "p1", "options": [{"option_id": "x", "name": "X", "kind": "maybe"}]}),
                )],
            ),
        ] {
            let mut mapping = Mapping::new("run-1");
            let mut last = Vec::new();
            for data in &frames {
                last = mapping.frame(data);
            }
            assert_eq!(last[last.len() - 2..], lost[..], "{name}");
            assert!(mapping.ended(), "{name}");
        }
    }

    #[test]
    fn a_gap_resumes_after_the_last_frame_and_the_replay_fills_it() {
        let mut mapping = Mapping::new("run-1");
        let mut seen = events(mapping.frame(&chunk(1, "m1", "ab")));
        seen.extend(events(mapping.frame(&chunk(2, "m1", "cd"))));
        // Frame 3 never arrived on this connection.
        assert_eq!(mapping.frame(&chunk(4, "m1", "gh")), [Step::Resume]);
        assert!(!mapping.ended());
        assert_eq!(mapping.resume_cursor().as_deref(), Some("run-1:2"));
        // The reopened stream: its snapshot, then the replay from sequence 3.
        seen.extend(events(mapping.frame(&frame(
            "stream_snapshot",
            None,
            json!({"status": "running"}),
        ))));
        seen.extend(events(mapping.frame(&chunk(3, "m1", "ef"))));
        seen.extend(events(mapping.frame(&chunk(4, "m1", "gh"))));
        let texts: Vec<_> = seen
            .iter()
            .filter_map(|event| match event {
                StreamEvent::Text {
                    sequence, delta, ..
                } => Some((*sequence, delta.as_str())),
                _ => None,
            })
            .collect();
        assert_eq!(texts, [(1, "ab"), (2, "cd"), (3, "ef"), (4, "gh")]);
        // A replay that cannot reach back far enough says so, and that is a loss.
        let steps = mapping.frame(&frame(
            "progress_dropped",
            None,
            json!({"reason": "replay_window_exceeded", "dropped_type": null, "first_sequence": 9}),
        ));
        assert_eq!(
            steps,
            [
                Step::Emit(StreamEvent::Lost {
                    reply_id: Some("run-1".into())
                }),
                Step::End
            ]
        );
    }

    #[test]
    fn approvals_and_questionnaires_wait_until_answered_or_settled() {
        let mut mapping = Mapping::new("run-1");
        let raised = events(mapping.frame(&frame(
            "permission_request",
            Some(1),
            json!({
                "request_id": "perm-1",
                "tool_call": "cadrumo.ledger_import",
                "tool_kind": "edit",
                "description": "Import the statement",
                "options": [
                    {"option_id": "allow", "name": "Allow once", "kind": "allow_once"},
                    {"option_id": "session", "name": "Allow for this session", "kind": "allow_session"},
                    {"option_id": "never", "kind": "reject_always"},
                    {"option_id": "odd", "name": "Odd", "kind": "sometimes"}
                ]
            }),
        )));
        assert_eq!(
            serde_json::to_value(&raised[1]).unwrap(),
            json!({"type": "approval", "reply_id": "run-1", "approval": {
                "request_id": "perm-1", "reply_id": "run-1", "source": "agent_tool",
                "tool_call": "cadrumo.ledger_import", "description": "Import the statement",
                "tool_kind": "edit",
                "options": [
                    {"option_id": "allow", "name": "Allow once", "kind": "allow_once"},
                    {"option_id": "session", "name": "Allow for this session", "kind": "allow_session"},
                    {"option_id": "never", "name": null, "kind": "reject_always"}
                ]
            }})
        );
        assert_eq!(
            mapping.frame(&frame(
                "clarification_pending",
                Some(2),
                json!({"request_id": "clar-1"})
            )),
            [Step::ReadQuestionnaire("clar-1".into())]
        );
        let status = json!({"pending_clarification": {
            "type": "clarification_request",
            "request_id": "clar-1",
            "questions": [
                {"id": "year", "prompt": "Which year?", "kind": "choice", "options": ["2024", "2025"], "required": true},
                {"id": "note", "prompt": "Anything else?", "kind": "text", "options": null, "required": false}
            ]
        }});
        assert_eq!(mapping.questionnaire("other", &status), None);
        assert_eq!(
            serde_json::to_value(mapping.questionnaire("clar-1", &status).unwrap()).unwrap(),
            json!({"type": "questions", "reply_id": "run-1", "questionnaire": {
                "request_id": "clar-1", "reply_id": "run-1", "questions": [
                    {"id": "year", "prompt": "Which year?", "kind": "choice", "options": ["2024", "2025"], "required": true},
                    {"id": "note", "prompt": "Anything else?", "kind": "text", "options": null, "required": false}
                ]
            }})
        );
        assert_eq!(
            mapping.resolve("perm-1"),
            Some(StreamEvent::Resolved {
                reply_id: "run-1".into(),
                request_id: "perm-1".into()
            })
        );
        assert_eq!(mapping.resolve("perm-1"), None);
        let steps = mapping.frame(&frame(
            "thread_terminal",
            Some(3),
            json!({"status": "failed", "error_detail": "prose"}),
        ));
        assert_eq!(
            steps,
            [
                Step::Emit(StreamEvent::Resolved {
                    reply_id: "run-1".into(),
                    request_id: "clar-1".into()
                }),
                Step::Settle(RunEnd::Failed),
                Step::End
            ]
        );
        assert_eq!(
            serde_json::to_value(mapping.settled(
                RunEnd::Failed,
                Some(&json!({"provider_condition": "throttled", "failure_reason": "rate limited"}))
            ))
            .unwrap(),
            json!({"type": "settled", "reply_id": "run-1", "status": "failed",
                   "provider_condition": "throttled", "failure_reason": "rate limited"})
        );
    }

    #[test]
    fn a_cancelled_run_settles_as_cancelled() {
        let mut mapping = Mapping::new("run-1");
        let steps = mapping.frame(&frame(
            "thread_terminal",
            None,
            json!({"status": "cancelled"}),
        ));
        assert_eq!(
            steps,
            [
                Step::Emit(StreamEvent::ReplyStarted {
                    reply_id: "run-1".into()
                }),
                Step::Settle(RunEnd::Cancelled),
                Step::End
            ]
        );
        assert_eq!(
            serde_json::to_value(StreamEvent::Lost { reply_id: None }).unwrap(),
            json!({"type": "lost"})
        );
    }
}
