//! A run's progress frames, as `streaming/sse_frames.py` declares them,
//! mapped onto the column's stream events.
//!
//! Frames are droppable and carry less than the column's contract asks for,
//! so this maps only what the stream proves. Text offsets are counted here,
//! per message, from the run's first frame: the stream must be contiguous
//! from sequence 1 and every chunk uncut. A gap in the sequence is not a
//! loss yet: the stream is reopened after the last frame mapped, and the
//! gateway's replay fills it. Only what a replay cannot cover ends the
//! stream as lost: a drop notice, a refused stream, a first frame after
//! sequence 1, an unnumbered chunk, or a chunk at the frame's text cap. cadrumo-agent keeps one message
//! across a reply's tool rounds; text that resumes after a tool frame is a new
//! agent turn, named here `<message id>#<n>`, since the frames name none.

use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeSet, HashMap};

/// The gateway's frame version.
const FRAME_VERSION: &str = "v1";
/// `MAX_PROGRESS_CONTENT_CHARS`: a chunk this long may have been cut.
const CONTENT_CAP: usize = 16 * 1024;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ToolState {
    Running,
    Done,
    Refused,
}

/// A tool turn, whole.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ToolTurn {
    pub kind: &'static str,
    pub id: String,
    /// The tool as cadrumo-agent names it.
    pub label: String,
    pub state: ToolState,
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

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Settled {
    Complete,
    Stopped,
    Failed,
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
        turn_id: String,
        offset: usize,
        delta: String,
    },
    Tool {
        reply_id: String,
        tool: ToolTurn,
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
        state: Settled,
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
    /// The run settled; a failed one's reason is read from its status.
    Settle(Settled),
    /// A frame was skipped: reopen the stream after the last frame mapped,
    /// whose replay serves what was missed.
    Resume,
    /// Nothing more is read from this stream.
    End,
}

struct Text {
    segment: u32,
    length: usize,
    after_tool: bool,
}

/// One run's stream, mapped frame by frame.
pub struct Mapping {
    reply_id: String,
    started: bool,
    last_sequence: u64,
    from_start: bool,
    texts: HashMap<String, Text>,
    tools: HashMap<String, ToolTurn>,
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
            from_start: false,
            texts: HashMap::new(),
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
        if let Some(sequence) = frame.get("sequence") {
            let Some(sequence) = sequence.as_u64().filter(|s| *s > 0) else {
                return self.lost();
            };
            if sequence <= self.last_sequence {
                // A replayed frame this stream already mapped.
                return Vec::new();
            }
            if self.last_sequence == 0 {
                self.from_start = sequence == 1;
            } else if sequence != self.last_sequence + 1 {
                return vec![Step::Resume];
            }
            self.last_sequence = sequence;
        }
        let mut steps = Vec::new();
        if !self.started {
            self.started = true;
            steps.push(Step::Emit(StreamEvent::ReplyStarted {
                reply_id: self.reply_id.clone(),
            }));
        }
        let mapped = match kind.as_str() {
            "message_chunk" => self.message_chunk(&frame),
            "tool_call_start" | "tool_call_update" => {
                self.tool_call(&frame, kind == "tool_call_start")
            }
            "permission_request" => self.permission(&frame),
            "clarification_pending" => match text(&frame, "request_id") {
                Some(request) if !request.is_empty() => {
                    Ok(vec![Step::ReadQuestionnaire(request.to_owned())])
                }
                _ => Err(()),
            },
            "thread_terminal" => self.terminal(&frame),
            "progress_dropped" | "stream_rejected" => Err(()),
            // Snapshots, heartbeats, thoughts, plans, artifacts, agent
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

    fn message_chunk(&mut self, frame: &Value) -> Result<Vec<Step>, ()> {
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
        if !self.from_start || content.chars().count() >= CONTENT_CAP {
            return Err(());
        }
        let turn = self.texts.entry(message.to_owned()).or_insert(Text {
            segment: 0,
            length: 0,
            after_tool: false,
        });
        if turn.after_tool {
            turn.after_tool = false;
            turn.segment += 1;
            turn.length = 0;
        }
        let offset = turn.length;
        turn.length += content.encode_utf16().count();
        let turn_id = if turn.segment == 0 {
            message.to_owned()
        } else {
            format!("{message}#{}", turn.segment)
        };
        Ok(vec![Step::Emit(StreamEvent::Text {
            reply_id: self.reply_id.clone(),
            turn_id,
            offset,
            delta: content.clone(),
        })])
    }

    fn tool_call(&mut self, frame: &Value, start: bool) -> Result<Vec<Step>, ()> {
        let id = text(frame, "tool_call_id")
            .filter(|id| !id.is_empty())
            .ok_or(())?;
        let state = match text(frame, "status") {
            None => None,
            Some("pending" | "in_progress") => Some(ToolState::Running),
            Some("completed") => Some(ToolState::Done),
            Some("failed") => Some(ToolState::Refused),
            Some(_) => return Err(()),
        };
        let title = text(frame, "title").filter(|title| !title.is_empty());
        let tool = match self.tools.get_mut(id) {
            Some(tool) => {
                if let Some(title) = title {
                    title.clone_into(&mut tool.label);
                }
                if let Some(state) = state {
                    tool.state = state;
                }
                tool.clone()
            }
            None => {
                // A tool first seen without its name cannot be shown.
                let label = title.ok_or(())?.to_owned();
                let tool = ToolTurn {
                    kind: "tool",
                    id: id.to_owned(),
                    label,
                    state: state.unwrap_or(if start {
                        ToolState::Running
                    } else {
                        return Err(());
                    }),
                };
                self.tools.insert(id.to_owned(), tool.clone());
                tool
            }
        };
        for turn in self.texts.values_mut() {
            turn.after_tool = true;
        }
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
                    "allow_once" | "allow_always" | "reject_once" | "reject_always"
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
                    .filter(|kind| {
                        matches!(
                            *kind,
                            "read"
                                | "edit"
                                | "delete"
                                | "move"
                                | "search"
                                | "execute"
                                | "think"
                                | "fetch"
                                | "switch_mode"
                                | "other"
                        )
                    })
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
        let settled = match text(frame, "status") {
            Some("completed" | "archived") => Settled::Complete,
            Some("cancelled") => Settled::Stopped,
            Some("failed") => Settled::Failed,
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
        steps.push(Step::Settle(settled));
        steps.push(Step::End);
        Ok(steps)
    }

    /// The settled event, with a failed run's typed provider condition.
    pub fn settled(&self, state: Settled, failure_reason: Option<String>) -> StreamEvent {
        StreamEvent::Settled {
            reply_id: self.reply_id.clone(),
            state,
            failure_reason: if state == Settled::Failed {
                failure_reason
            } else {
                None
            },
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
    fn a_reply_streams_as_ordered_turns_with_counted_offsets() {
        let mut mapping = Mapping::new("run-1");
        let mut seen = events(mapping.frame(&frame(
            "stream_snapshot",
            None,
            json!({"status": "running"}),
        )));
        seen.extend(events(mapping.frame(&chunk(1, "m1", "Hola, "))));
        // UTF-16 code units, as the column counts them: one astral character is two.
        seen.extend(events(mapping.frame(&chunk(2, "m1", "😀 a"))));
        seen.extend(events(mapping.frame(&frame(
            "tool_call_start",
            Some(3),
            json!({"tool_call_id": "t1", "title": "ledger_list", "kind": "read", "status": "pending", "locations": []}),
        ))));
        seen.extend(events(mapping.frame(&frame(
            "tool_call_update",
            Some(4),
            json!({"tool_call_id": "t1", "status": "completed"}),
        ))));
        seen.extend(events(mapping.frame(&chunk(5, "m1", "\n\nListo."))));
        seen.extend(events(mapping.frame(&frame(
            "heartbeat",
            None,
            json!({"server_uptime_seconds": 3.0}),
        ))));
        assert_eq!(
            serde_json::to_value(&seen).unwrap(),
            json!([
                {"type": "reply_started", "reply_id": "run-1"},
                {"type": "text", "reply_id": "run-1", "turn_id": "m1", "offset": 0, "delta": "Hola, "},
                {"type": "text", "reply_id": "run-1", "turn_id": "m1", "offset": 6, "delta": "😀 a"},
                {"type": "tool", "reply_id": "run-1", "tool": {"kind": "tool", "id": "t1", "label": "ledger_list", "state": "running"}},
                {"type": "tool", "reply_id": "run-1", "tool": {"kind": "tool", "id": "t1", "label": "ledger_list", "state": "done"}},
                {"type": "text", "reply_id": "run-1", "turn_id": "m1#1", "offset": 0, "delta": "\n\nListo."},
            ])
        );
        let steps = mapping.frame(&frame(
            "thread_terminal",
            Some(6),
            json!({"status": "completed", "replay": false}),
        ));
        assert_eq!(steps, [Step::Settle(Settled::Complete), Step::End]);
        assert!(mapping.ended());
        assert_eq!(
            serde_json::to_value(mapping.settled(Settled::Complete, Some("unknown".into())))
                .unwrap(),
            json!({"type": "settled", "reply_id": "run-1", "state": "complete"})
        );
        assert!(mapping.frame(&chunk(7, "m1", "late")).is_empty());
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
                turn_id: "m1".into(),
                offset: 2,
                delta: "c".into()
            }]
        );
    }

    #[test]
    fn what_one_stream_cannot_prove_ends_it_as_lost() {
        let lost = [
            Step::Emit(StreamEvent::Lost {
                reply_id: Some("run-1".into()),
            }),
            Step::End,
        ];
        let cut = "x".repeat(CONTENT_CAP);
        for (name, frames) in [
            // Attached after the run's first frame: earlier text is unknown.
            ("late attach", vec![chunk(4, "m1", "a")]),
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
                    json!({"tool_call_id": "t1", "status": "pending"}),
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
                StreamEvent::Text { offset, delta, .. } => Some((*offset, delta.as_str())),
                _ => None,
            })
            .collect();
        assert_eq!(texts, [(0, "ab"), (2, "cd"), (4, "ef"), (6, "gh")]);
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
                Step::Settle(Settled::Failed),
                Step::End
            ]
        );
        assert_eq!(
            serde_json::to_value(mapping.settled(Settled::Failed, Some("throttled".into())))
                .unwrap(),
            json!({"type": "settled", "reply_id": "run-1", "state": "failed", "failure_reason": "throttled"})
        );
    }

    #[test]
    fn a_stopped_run_settles_as_stopped() {
        let mut mapping = Mapping::new("run-1");
        let steps = mapping.frame(&frame(
            "thread_terminal",
            None,
            json!({"status": "cancelled"}),
        ));
        assert_eq!(
            events(steps),
            [StreamEvent::ReplyStarted {
                reply_id: "run-1".into()
            }]
        );
        assert_eq!(
            serde_json::to_value(StreamEvent::Lost { reply_id: None }).unwrap(),
            json!({"type": "lost"})
        );
    }
}
