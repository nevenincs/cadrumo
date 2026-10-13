//! The agent session the column is served: the closed list of commands
//! behind `AgentSession` and `AgentViews`, each answered from the gateway or
//! refused with a typed code where nothing honest can answer.
//!
//! Every run starts in the profile's one agent workspace, which the launcher
//! reports when it is ready, and the provider catalog is read for it. A
//! conversation is a chain of runs there; until the column's contract names
//! a conversation by its first run, every read and act that names one is
//! refused with a code that says so. A reply is one gateway run, and only a
//! run this host is watching can be stopped or answered.

use super::{
    Refused,
    gateway::{self, Client},
    sse,
    stream::{Mapping, Settled, Step, StreamEvent},
    supervisor::{Gateway, State, Supervisor},
};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    io::Read,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::Duration,
};
use tauri::ipc::Channel;

/// How often a stream that broke is reopened from its cursor before it is
/// reported lost.
const RECONNECTS: usize = 3;
/// `MAX_RUN_MESSAGE_CHARS`.
const MESSAGE_LIMIT: usize = 65_536;

fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn refused(code: &str) -> Refused {
    Refused::new(code.to_owned())
}

/// The selection a send names: a catalog lane and one of its models.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Selection {
    pub provider: String,
    pub execution_mode: String,
    pub entry_id: String,
    pub model: String,
    pub effort: Option<String>,
    /// Native controls by id; a run start takes none.
    pub controls: Option<Vec<Value>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SendRequest {
    pub conversation_id: String,
    pub text: String,
    pub selection: Selection,
    pub document_ids: Option<Vec<String>>,
}

/// Which pending request of which reply an answer is for.
#[derive(Deserialize)]
pub struct RequestRef {
    pub reply_id: String,
    pub request_id: String,
}

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Answer {
    Answers {
        answers: HashMap<String, String>,
    },
    /// The text is never sent: see [`clarification_body`].
    Message {
        #[serde(rename = "text")]
        _text: String,
    },
    Decline,
}

/// The body `clarifications/{id}/respond` takes for an answer this host can
/// report back honestly. A message answer would add a person turn whose id
/// the gateway does not return.
pub fn clarification_body(answer: &Answer) -> Result<Value, Refused> {
    match answer {
        Answer::Answers { answers } => Ok(json!({ "answers": answers })),
        Answer::Decline => Ok(json!({ "decline": true })),
        Answer::Message { .. } => Err(refused("agent_person_turn_unavailable")),
    }
}

/// A send's checks before anything is asked of the gateway.
pub fn admit_send(request: &SendRequest) -> Result<(), Refused> {
    let invalid = || refused("agent_invalid_request");
    let text_len = request.text.chars().count();
    if request.text.trim().is_empty() || text_len > MESSAGE_LIMIT {
        return Err(invalid());
    }
    let selection = &request.selection;
    for field in [
        &selection.provider,
        &selection.execution_mode,
        &selection.entry_id,
        &selection.model,
    ] {
        if field.is_empty() || field.len() > 512 || field.chars().any(char::is_control) {
            return Err(invalid());
        }
    }
    if selection.effort.as_deref().is_some_and(|effort| {
        !matches!(
            effort,
            "low" | "medium" | "high" | "xhigh" | "max" | "ultra"
        )
    }) {
        return Err(invalid());
    }
    // A run names a provider, a model and an effort; the gateway's run start
    // takes no native control, so one chosen cannot be applied.
    if selection.controls.as_ref().is_some_and(|c| !c.is_empty()) {
        return Err(refused("agent_controls_unsupported"));
    }
    if request.document_ids.as_ref().is_some_and(|d| !d.is_empty()) {
        return Err(refused("agent_documents_unavailable"));
    }
    Ok(())
}

/// The questionnaires and approvals a run waits on, from its status and its
/// history, which alone lists pending permissions.
pub fn pending_of(run: &str, status: &Value, history: &Value) -> Value {
    let mut mapping = Mapping::new(run);
    let questionnaires: Vec<Value> = status
        .get("pending_clarification")
        .and_then(|pending| pending.get("request_id"))
        .and_then(Value::as_str)
        .map(str::to_owned)
        .and_then(|request| mapping.questionnaire(&request, status))
        .and_then(|event| match event {
            StreamEvent::Questions { questionnaire, .. } => {
                serde_json::to_value(questionnaire).ok()
            }
            _ => None,
        })
        .into_iter()
        .collect();
    let approvals: Vec<Value> = history
        .get("state")
        .and_then(|state| state.get("pending_permissions"))
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|permission| {
            let mut frame = permission.clone();
            frame["api_version"] = json!("v1");
            frame["type"] = json!("permission_request");
            let mut fresh = Mapping::new(run);
            fresh
                .frame(&frame.to_string())
                .into_iter()
                .find_map(|step| match step {
                    Step::Emit(StreamEvent::Approval { approval, .. }) => {
                        serde_json::to_value(approval).ok()
                    }
                    _ => None,
                })
        })
        .collect();
    json!({ "questionnaires": questionnaires, "approvals": approvals })
}

struct Watch {
    run: String,
    mapping: Arc<Mutex<Mapping>>,
    channel: Channel<StreamEvent>,
    stopped: Arc<AtomicBool>,
}

/// The session state one host holds.
#[derive(Default)]
pub struct Session {
    watches: Mutex<HashMap<u32, Watch>>,
}

impl Session {
    /// The gateway, while the service is ready.
    fn gateway(supervisor: &Supervisor) -> Result<Gateway, Refused> {
        match (supervisor.gateway(), supervisor.status().state) {
            (Some(gateway), State::Ready { .. }) => Ok(gateway),
            (_, State::Refused { code }) => Err(Refused::new(
                serde_json::to_value(code)
                    .ok()
                    .and_then(|code| code.as_str().map(str::to_owned))
                    .unwrap_or_else(|| "agent_service_failed".to_owned()),
            )),
            _ => Err(refused("agent_service_not_ready")),
        }
    }

    /// The workspace of a conversation. Every run is in the profile's one
    /// workspace, and a conversation is a chain of runs there, but the
    /// column's contract does not yet name a conversation by its first run,
    /// so no conversation id resolves.
    fn workspace(_conversation: &str) -> Result<String, Refused> {
        Err(refused("agent_conversation_unavailable"))
    }

    /// Every watch of `reply` this host streams: its mapping and channel.
    fn watched(&self, reply: &str) -> Vec<(Arc<Mutex<Mapping>>, Channel<StreamEvent>)> {
        lock(&self.watches)
            .values()
            .filter(|watch| watch.run == reply)
            .map(|watch| (watch.mapping.clone(), watch.channel.clone()))
            .collect()
    }

    fn known(&self, reply: &str) -> Result<(), Refused> {
        if self.watched(reply).is_empty() {
            Err(refused("agent_reply_unknown"))
        } else {
            Ok(())
        }
    }

    pub fn provider_catalog(&self, supervisor: &Supervisor) -> Result<Value, Refused> {
        let gateway = Self::gateway(supervisor)?;
        // Relayed as served, for the workspace every run starts in: every
        // lane, runnable or not.
        Client::new(&gateway).provider_catalog(&gateway.workspace_root)
    }

    pub fn send(&self, supervisor: &Supervisor, request: &SendRequest) -> Result<Value, Refused> {
        admit_send(request)?;
        Self::gateway(supervisor)?;
        Self::workspace(&request.conversation_id)?;
        // The gateway returns no id for the person's turn, and the result
        // must carry the turn as history will keep it.
        Err(refused("agent_person_turn_unavailable"))
    }

    pub fn pending(&self, supervisor: &Supervisor, conversation: &str) -> Result<Value, Refused> {
        let gateway = Self::gateway(supervisor)?;
        let workspace = Self::workspace(conversation)?;
        let client = Client::new(&gateway);
        let Some(run) = client.live_run(&workspace)? else {
            return Ok(json!({ "questionnaires": [], "approvals": [] }));
        };
        Ok(pending_of(
            &run,
            &client.run_status(&run)?,
            &client.history(&run)?,
        ))
    }

    pub fn cancel(&self, supervisor: &Supervisor, reply: &str) -> Result<(), Refused> {
        let gateway = Self::gateway(supervisor)?;
        self.known(reply)?;
        Client::new(&gateway).cancel(reply).map(|_| ())
    }

    fn resolved(&self, reply: &str, request: &str) {
        for (mapping, channel) in self.watched(reply) {
            let event = lock(&mapping).resolve(request);
            if let Some(event) = event {
                let _ = channel.send(event);
            }
        }
    }

    pub fn answer(
        &self,
        supervisor: &Supervisor,
        target: &RequestRef,
        answer: &Answer,
    ) -> Result<Value, Refused> {
        let gateway = Self::gateway(supervisor)?;
        self.known(&target.reply_id)?;
        if !gateway::request_id(&target.request_id) {
            return Err(refused("agent_invalid_request"));
        }
        let body = clarification_body(answer)?;
        let answered =
            Client::new(&gateway).clarification(&target.reply_id, &target.request_id, &body)?;
        if answered.get("accepted").and_then(Value::as_bool) != Some(true) {
            return Err(refused("agent_answer_not_accepted"));
        }
        self.resolved(&target.reply_id, &target.request_id);
        Ok(json!({}))
    }

    pub fn decide(
        &self,
        supervisor: &Supervisor,
        target: &RequestRef,
        option: &str,
    ) -> Result<(), Refused> {
        let gateway = Self::gateway(supervisor)?;
        self.known(&target.reply_id)?;
        if target.request_id.is_empty()
            || target.request_id.len() > 256
            || option.is_empty()
            || option.len() > 64
        {
            return Err(refused("agent_invalid_request"));
        }
        let decided =
            Client::new(&gateway).permission(&target.reply_id, &target.request_id, option)?;
        if decided.get("accepted").and_then(Value::as_bool) != Some(true) {
            return Err(refused("agent_answer_not_accepted"));
        }
        self.resolved(&target.reply_id, &target.request_id);
        Ok(())
    }

    /// Watches the conversation's live run, if it has one, on `channel`.
    pub fn observe(
        &self,
        supervisor: &Supervisor,
        conversation: &str,
        channel: Channel<StreamEvent>,
    ) -> Result<u32, Refused> {
        let gateway = Self::gateway(supervisor)?;
        let workspace = Self::workspace(conversation)?;
        let id = channel.id();
        let client = Client::new(&gateway);
        let Some(run) = client.live_run(&workspace)? else {
            return Ok(id);
        };
        // Each watch maps its own stream from the run's first frame.
        let mapping = Arc::new(Mutex::new(Mapping::new(&run)));
        let stopped = Arc::new(AtomicBool::new(false));
        lock(&self.watches).insert(
            id,
            Watch {
                run: run.clone(),
                mapping: mapping.clone(),
                channel: channel.clone(),
                stopped: stopped.clone(),
            },
        );
        thread::spawn(move || pump(&client, &run, &mapping, &channel, &stopped));
        Ok(id)
    }

    /// Ends the watch `subscription`, never a newer one.
    pub fn unobserve(&self, subscription: u32) {
        if let Some(watch) = lock(&self.watches).remove(&subscription) {
            watch.stopped.store(true, Ordering::Release);
        }
    }

    /// Ends every watch, as the service stops or the window closes.
    pub fn close(&self) {
        for (_, watch) in lock(&self.watches).drain() {
            watch.stopped.store(true, Ordering::Release);
        }
    }
}

/// Reads one run's stream onto `channel` until it settles, is lost, or the
/// watch ends. A broken connection is reopened after the last numbered frame.
fn pump(
    client: &Client,
    run: &str,
    mapping: &Mutex<Mapping>,
    channel: &Channel<StreamEvent>,
    stopped: &AtomicBool,
) {
    let mut attempts = 0;
    while !stopped.load(Ordering::Acquire) && !lock(mapping).ended() {
        let cursor = lock(mapping).resume_cursor();
        let Ok(mut body) = client.stream(run, cursor.as_deref()) else {
            attempts += 1;
            if attempts > RECONNECTS {
                break;
            }
            thread::sleep(Duration::from_millis(500));
            continue;
        };
        let mut decoder = sse::Decoder::default();
        let mut buffer = vec![0u8; 16 * 1024];
        loop {
            if stopped.load(Ordering::Acquire) {
                return;
            }
            let count = match body.read(&mut buffer) {
                Ok(0) | Err(_) => break,
                Ok(count) => count,
            };
            let Ok(events) = decoder.feed(&buffer[..count]) else {
                emit(channel, lock(mapping).interrupted());
                return;
            };
            let mut resume = false;
            for event in events {
                if resume {
                    break;
                }
                let steps = lock(mapping).frame(&event.data);
                for step in steps {
                    match step {
                        Step::Emit(event) => {
                            let _ = channel.send(event);
                        }
                        Step::ReadQuestionnaire(request) => {
                            let event = client
                                .run_status(run)
                                .ok()
                                .and_then(|status| lock(mapping).questionnaire(&request, &status));
                            if let Some(event) = event {
                                let _ = channel.send(event);
                            }
                        }
                        Step::Settle(state) => {
                            let reason = (state == Settled::Failed)
                                .then(|| client.run_status(run).ok())
                                .flatten()
                                .and_then(|status| {
                                    status
                                        .get("provider_condition")?
                                        .as_str()
                                        .map(str::to_owned)
                                });
                            let _ = channel.send(lock(mapping).settled(state, reason));
                        }
                        Step::End => return,
                        Step::Resume => resume = true,
                    }
                }
            }
            if resume {
                break;
            }
            attempts = 0;
        }
        attempts += 1;
        if attempts > RECONNECTS {
            break;
        }
    }
    if !stopped.load(Ordering::Acquire) {
        emit(channel, lock(mapping).interrupted());
    }
}

fn emit(channel: &Channel<StreamEvent>, steps: Vec<Step>) {
    for step in steps {
        if let Step::Emit(event) = step {
            let _ = channel.send(event);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn send(value: Value) -> SendRequest {
        serde_json::from_value(value).unwrap()
    }

    fn request() -> Value {
        json!({
            "conversation_id": "c1",
            "text": "¿Cuánto IVA declaré?",
            "selection": {"provider": "anthropic", "execution_mode": "api", "entry_id": "e1", "model": "m1", "effort": "high"}
        })
    }

    #[test]
    fn a_send_is_checked_before_anything_reaches_the_gateway() {
        assert!(admit_send(&send(request())).is_ok());
        let mut controls = request();
        controls["selection"]["controls"] = json!([{"control_id": "tier", "option_id": "fast"}]);
        assert_eq!(
            admit_send(&send(controls)).unwrap_err().code,
            "agent_controls_unsupported"
        );
        let mut documents = request();
        documents["document_ids"] = json!(["d1"]);
        assert_eq!(
            admit_send(&send(documents)).unwrap_err().code,
            "agent_documents_unavailable"
        );
        for (field, value) in [
            ("text", json!("   ")),
            ("text", json!("x".repeat(MESSAGE_LIMIT + 1))),
        ] {
            let mut bad = request();
            bad[field] = value;
            assert_eq!(
                admit_send(&send(bad)).unwrap_err().code,
                "agent_invalid_request"
            );
        }
        let mut effort = request();
        effort["selection"]["effort"] = json!("extreme");
        assert_eq!(
            admit_send(&send(effort)).unwrap_err().code,
            "agent_invalid_request"
        );
        let mut bad = request();
        bad["selection"]["model"] = json!("");
        assert_eq!(
            admit_send(&send(bad)).unwrap_err().code,
            "agent_invalid_request"
        );
        // The selection is the catalog's; an unknown field is refused at the wire.
        let mut unknown = request();
        unknown["selection"]["provider_id"] = json!("anthropic");
        assert!(serde_json::from_value::<SendRequest>(unknown).is_err());
        // No conversation has a workspace the launcher reported.
        assert_eq!(
            Session::workspace("c1").unwrap_err().code,
            "agent_conversation_unavailable"
        );
    }

    #[test]
    fn questionnaire_answers_map_onto_the_respond_body() {
        let answers: Answer =
            serde_json::from_value(json!({"kind": "answers", "answers": {"year": "2025"}}))
                .unwrap();
        assert_eq!(
            clarification_body(&answers).unwrap(),
            json!({"answers": {"year": "2025"}})
        );
        let decline: Answer = serde_json::from_value(json!({"kind": "decline"})).unwrap();
        assert_eq!(
            clarification_body(&decline).unwrap(),
            json!({"decline": true})
        );
        let message: Answer =
            serde_json::from_value(json!({"kind": "message", "text": "otra cosa"})).unwrap();
        assert_eq!(
            clarification_body(&message).unwrap_err().code,
            "agent_person_turn_unavailable"
        );
    }

    #[test]
    fn pending_requests_come_from_status_and_history_together() {
        let status = json!({"run_id": "run-1", "pending_clarification": {
            "type": "clarification_request", "request_id": "clar-1",
            "questions": [{"id": "q", "prompt": "¿Año?", "kind": "text", "options": null, "required": true}]
        }});
        let history = json!({"state": {"pending_permissions": [
            {"request_id": "perm-1", "description": "Read the ledger", "tool_call": "ledger_list", "tool_kind": "read",
             "options": [{"option_id": "ok", "name": "Allow", "kind": "allow_once"}]}
        ]}});
        assert_eq!(
            pending_of("run-1", &status, &history),
            json!({
                "questionnaires": [{"request_id": "clar-1", "reply_id": "run-1", "questions": [
                    {"id": "q", "prompt": "¿Año?", "kind": "text", "required": true}
                ]}],
                "approvals": [{"request_id": "perm-1", "reply_id": "run-1", "source": "agent_tool",
                    "title": "ledger_list", "description": "Read the ledger",
                    "options": [{"option_id": "ok", "name": "Allow", "kind": "allow_once"}]}]
            })
        );
        assert_eq!(
            pending_of(
                "run-1",
                &json!({"pending_clarification": null}),
                &json!({"state": {}})
            ),
            json!({"questionnaires": [], "approvals": []})
        );
    }
}
