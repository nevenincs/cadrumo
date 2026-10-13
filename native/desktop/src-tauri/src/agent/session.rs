//! The agent session the column is served: the closed list of commands
//! behind `AgentSession` and `AgentViews`, each answered from the gateway or
//! refused with a typed code where nothing honest can answer.
//!
//! cadrumo-agent has no conversation: its unit is the run. A conversation
//! here is a chain of runs, each continuing the one before, named by its
//! first run's id. Every run starts in the profile's one agent workspace,
//! which the launcher reports when it is ready, and the provider catalog is
//! read for it. A reply is one run.

use super::{
    Refused,
    gateway::{self, Client},
    sse,
    stream::{Mapping, Step, StreamEvent},
    supervisor::{Gateway, State, Supervisor},
};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::{HashMap, HashSet},
    io::Read,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tauri::ipc::Channel;

/// How often a stream that broke is reopened from its cursor before it is
/// reported lost.
const RECONNECTS: usize = 3;
/// `MAX_RUN_MESSAGE_CHARS`.
const MESSAGE_LIMIT: usize = 65_536;
/// `MAX_RUN_TITLE_CHARS`.
const TITLE_LIMIT: usize = 200;
/// The largest page the run listing serves, and how many runs are read.
const PAGE: usize = 100;
const LISTED: usize = 2_000;
/// How many messages a continuing run is seeded with, at most.
const SEEDED: usize = 20;
/// The run statuses a run does not leave.
const SETTLED: &[&str] = &["completed", "failed", "cancelled", "archived"];

fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn refused(code: &str) -> Refused {
    Refused::new(code.to_owned())
}

fn text<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value.get(key).and_then(Value::as_str)
}

/// The selection a send names: a catalog lane, by provider and transport,
/// and one of its models, as a run start takes them.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Selection {
    pub provider: String,
    pub transport: String,
    pub model: String,
    pub effort: Option<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SendRequest {
    pub conversation_id: String,
    pub text: String,
    pub selection: Selection,
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
    Answers { answers: HashMap<String, String> },
    Message { text: String },
    Decline,
}

/// The body `clarifications/{id}/respond` takes: the answers, a message
/// that continues the run as the continuation's prompt, or a decline.
pub fn clarification_body(answer: &Answer) -> Result<Value, Refused> {
    match answer {
        Answer::Answers { answers } => Ok(json!({ "answers": answers })),
        Answer::Decline => Ok(json!({ "decline": true })),
        Answer::Message { text } => {
            if text.trim().is_empty() || text.chars().count() > MESSAGE_LIMIT {
                return Err(refused("agent_invalid_request"));
            }
            Ok(json!({ "prompt": text }))
        }
    }
}

/// A send's checks before anything is asked of the gateway.
pub fn admit_send(request: &SendRequest) -> Result<(), Refused> {
    let invalid = || refused("agent_invalid_request");
    let text_len = request.text.chars().count();
    if request.text.trim().is_empty() || text_len > MESSAGE_LIMIT {
        return Err(invalid());
    }
    if !gateway::run_id(&request.conversation_id) {
        return Err(invalid());
    }
    let selection = &request.selection;
    if !matches!(selection.transport.as_str(), "api" | "cli") {
        return Err(invalid());
    }
    for field in [&selection.provider, &selection.model] {
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
    Ok(())
}

/// The run start a send makes: its run, its message, its agent in the
/// profile's workspace, the predecessor it continues, and for a
/// conversation's first run a title from the message's first line.
pub fn start_body(
    run_id: &str,
    request: &SendRequest,
    workspace_root: &str,
    continues: Option<&str>,
) -> Value {
    let selection = &request.selection;
    let mut agent = json!({
        "provider": selection.provider,
        "transport": selection.transport,
        "model": selection.model,
        "workspace_root": workspace_root,
    });
    if let Some(effort) = &selection.effort {
        agent["effort"] = json!(effort);
    }
    let mut body = json!({ "run_id": run_id, "message": request.text, "agent": agent });
    match continues {
        Some(predecessor) => body["continues_run_id"] = json!(predecessor),
        None => {
            let title: String = request
                .text
                .lines()
                .map(str::trim)
                .find(|line| !line.is_empty())
                .unwrap_or_default()
                .chars()
                .take(TITLE_LIMIT)
                .collect();
            if !title.is_empty() {
                body["title"] = json!(title);
            }
        }
    }
    body
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

/// One run as the listing names it, with the run it continues.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Run {
    pub id: String,
    pub status: String,
    pub title: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub predecessor: Option<String>,
}

impl Run {
    fn live(&self) -> bool {
        !SETTLED.contains(&self.status.as_str())
    }
}

/// The runs grouped into chains, each from its first run to its last.
pub fn chains(runs: &[Run]) -> Vec<Vec<Run>> {
    let by_id: HashMap<&str, &Run> = runs.iter().map(|run| (run.id.as_str(), run)).collect();
    let head = |run: &Run| {
        let mut current = run;
        for _ in 0..runs.len() {
            match current
                .predecessor
                .as_deref()
                .and_then(|predecessor| by_id.get(predecessor))
            {
                Some(predecessor) => current = predecessor,
                None => break,
            }
        }
        current.id.clone()
    };
    let mut grouped: Vec<(String, Vec<Run>)> = Vec::new();
    for run in runs {
        let head = head(run);
        match grouped.iter_mut().find(|(id, _)| *id == head) {
            Some((_, chain)) => chain.push(run.clone()),
            None => grouped.push((head, vec![run.clone()])),
        }
    }
    grouped
        .into_iter()
        .map(|(head, mut chain)| {
            // The head first, then by creation: ISO instants of one format
            // order as text.
            chain.sort_by(|a, b| {
                (a.id != head)
                    .cmp(&(b.id != head))
                    .then_with(|| a.created_at.cmp(&b.created_at))
            });
            chain
        })
        .collect()
}

/// A conversation as the column lists it.
pub fn conversation_record(chain: &[Run]) -> Value {
    json!({
        "id": chain[0].id,
        "title": chain[0].title.clone().unwrap_or_default(),
        "last_active_at": chain.iter().map(|run| run.updated_at.as_str()).max().unwrap_or_default(),
        "archived": chain.iter().all(|run| run.status == "archived"),
    })
}

/// How many of a continuing run's first messages repeat the end of the run
/// it continues: the seed it was started with.
pub fn seeded(previous: &[(String, String)], messages: &[(String, String)]) -> usize {
    (1..=SEEDED.min(messages.len()).min(previous.len()))
        .rev()
        .find(|&count| messages[..count] == previous[previous.len() - count..])
        .unwrap_or(0)
}

fn ran_with(status: &Value) -> Value {
    let (Some(agent), selection) = (status.get("agent"), status.get("selection")) else {
        return Value::Null;
    };
    let field = |key: &str| {
        agent
            .get(key)
            .filter(|value| !value.is_null())
            .or_else(|| selection.and_then(|selection| selection.get(key)))
            .cloned()
            .unwrap_or(Value::Null)
    };
    let transport = field("transport");
    if !transport.is_string() {
        return Value::Null;
    }
    json!({
        "provider": field("provider"),
        "transport": transport,
        "provider_display_name": selection.and_then(|s| s.get("provider_display_name")).cloned().unwrap_or(Value::Null),
        "model": field("model"),
        "model_display_name": selection.and_then(|s| s.get("model_display_name")).cloned().unwrap_or(Value::Null),
        "effort": field("effort"),
    })
}

/// A conversation's records, oldest first: per run, the person's messages,
/// its tool calls, the agent's messages, and the run's own record. Each
/// message is listed once: a continuing run's seed is left out. Messages are
/// listed under the ids cadrumo-agent gives them.
pub fn history_records(runs: &[(String, Value, Value)]) -> Vec<Value> {
    let mut records = Vec::new();
    let mut previous: Vec<(String, String)> = Vec::new();
    for (run, status, history) in runs {
        let state = history.get("state").cloned().unwrap_or(Value::Null);
        let messages: Vec<&Value> = state
            .get("messages")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter(|message| matches!(text(message, "role"), Some("user" | "assistant")))
            .collect();
        let transcript: Vec<(String, String)> = messages
            .iter()
            .map(|message| {
                (
                    text(message, "role").unwrap_or_default().to_owned(),
                    text(message, "content").unwrap_or_default().to_owned(),
                )
            })
            .collect();
        let skip = seeded(&previous, &transcript);
        let own = &messages[skip..];
        for message in own.iter().filter(|m| text(m, "role") == Some("user")) {
            records.push(json!({
                "kind": "person",
                "id": text(message, "message_id"),
                "reply_id": run,
                "text": text(message, "content").unwrap_or_default(),
                "sent_at": message.get("timestamp").cloned().unwrap_or(Value::Null),
            }));
        }
        for call in state
            .get("tool_calls")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            records.push(json!({
                "kind": "tool",
                "reply_id": run,
                "id": text(call, "tool_call_id"),
                "title": text(call, "title"),
                "tool_kind": text(call, "kind"),
                "status": text(call, "status"),
            }));
        }
        for message in own.iter().filter(|m| text(m, "role") == Some("assistant")) {
            records.push(json!({
                "kind": "agent",
                "id": text(message, "message_id"),
                "reply_id": run,
                "text": text(message, "content").unwrap_or_default(),
            }));
        }
        let usage = history
            .get("usage")
            .and_then(|usage| usage.get("total"))
            .map(|total| {
                json!({
                    "input_tokens": total.get("input_tokens"),
                    "output_tokens": total.get("output_tokens"),
                })
            })
            .unwrap_or(Value::Null);
        records.push(json!({
            "kind": "reply",
            "id": run,
            "status": status.get("status").or_else(|| state.get("status")),
            "provider_condition": status.get("provider_condition").cloned().unwrap_or(Value::Null),
            "failure_reason": status.get("failure_reason").cloned().unwrap_or(Value::Null),
            "queued_messages": status.get("queued_messages").cloned().unwrap_or(json!(0)),
            "selection": ran_with(status),
            "usage": usage,
        }));
        previous = transcript;
    }
    records
}

/// Now, as an ISO instant in UTC.
fn now() -> String {
    let seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |elapsed| elapsed.as_secs());
    let days = i64::try_from(seconds / 86_400).unwrap_or_default();
    let rest = seconds % 86_400;
    // Days to a civil date (Howard Hinnant's algorithm).
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        rest / 3_600,
        rest % 3_600 / 60,
        rest % 60
    )
}

/// A fresh run id, in the gateway's grammar.
fn mint_run_id() -> Result<String, Refused> {
    let mut bytes = [0u8; 12];
    getrandom::fill(&mut bytes).map_err(|_| refused("agent_host_failed"))?;
    Ok(bytes
        .iter()
        .fold(String::from("r"), |id, byte| id + &format!("{byte:02x}")))
}

struct Pump {
    run: String,
    mapping: Arc<Mutex<Mapping>>,
    stopped: Arc<AtomicBool>,
}

struct Watch {
    conversation: String,
    channel: Channel<StreamEvent>,
    pumps: Vec<Pump>,
}

/// The session state one host holds.
#[derive(Default)]
pub struct Session {
    watches: Mutex<HashMap<u32, Watch>>,
    /// Every run the host has seen, and the run it continues.
    known: Mutex<HashMap<String, Option<String>>>,
    /// Conversations started here whose first run has not been sent yet.
    reserved: Mutex<Vec<(String, String)>>,
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

    fn known(&self, reply: &str) -> Result<(), Refused> {
        if lock(&self.known).contains_key(reply) {
            Ok(())
        } else {
            Err(refused("agent_reply_unknown"))
        }
    }

    /// Every run, with the run each continues, read once per run.
    fn runs(&self, client: &Client) -> Result<Vec<Run>, Refused> {
        let mut runs = Vec::new();
        let mut offset = 0;
        while offset < LISTED {
            let page = client.runs(offset, PAGE)?;
            let listed = page
                .get("runs")
                .and_then(Value::as_array)
                .ok_or_else(|| refused("agent_gateway_unreadable"))?;
            for run in listed {
                let id = text(run, "run_id")
                    .filter(|id| gateway::run_id(id))
                    .ok_or_else(|| refused("agent_gateway_unreadable"))?;
                let cached = lock(&self.known).get(id).cloned();
                let predecessor = match cached {
                    Some(predecessor) => predecessor,
                    None => {
                        let status = client.run_status(id)?;
                        let predecessor = text(&status, "continues_run_id")
                            .filter(|id| gateway::run_id(id))
                            .map(str::to_owned);
                        lock(&self.known).insert(id.to_owned(), predecessor.clone());
                        predecessor
                    }
                };
                runs.push(Run {
                    id: id.to_owned(),
                    status: text(run, "status").unwrap_or_default().to_owned(),
                    title: text(run, "title").map(str::to_owned),
                    created_at: text(run, "created_at").unwrap_or_default().to_owned(),
                    updated_at: text(run, "updated_at").unwrap_or_default().to_owned(),
                    predecessor,
                });
            }
            offset += listed.len();
            if listed.is_empty() || page.get("truncated").and_then(Value::as_bool) != Some(true) {
                break;
            }
        }
        Ok(runs)
    }

    /// The runs of one conversation, first to last; none for one started
    /// here and not sent yet.
    fn chain(&self, client: &Client, conversation: &str) -> Result<Vec<Run>, Refused> {
        if !gateway::run_id(conversation) {
            return Err(refused("agent_invalid_request"));
        }
        let chain = chains(&self.runs(client)?)
            .into_iter()
            .find(|chain| chain[0].id == conversation);
        match chain {
            Some(chain) => Ok(chain),
            None if lock(&self.reserved)
                .iter()
                .any(|(id, _)| id == conversation) =>
            {
                Ok(Vec::new())
            }
            None => Err(refused("agent_conversation_unknown")),
        }
    }

    pub fn provider_catalog(&self, supervisor: &Supervisor) -> Result<Value, Refused> {
        let gateway = Self::gateway(supervisor)?;
        // Relayed as served, for the workspace every run starts in: every
        // lane, runnable or not.
        Client::new(&gateway).provider_catalog(&gateway.workspace_root)
    }

    /// Reserves the id the conversation's first run will have.
    pub fn start_conversation(&self, supervisor: &Supervisor) -> Result<Value, Refused> {
        Self::gateway(supervisor)?;
        let id = mint_run_id()?;
        let at = now();
        lock(&self.reserved).push((id.clone(), at.clone()));
        Ok(json!({ "id": id, "title": "", "last_active_at": at, "archived": false }))
    }

    pub fn conversations(&self, supervisor: &Supervisor) -> Result<Value, Refused> {
        let client = Client::new(&Self::gateway(supervisor)?);
        let chains = chains(&self.runs(&client)?);
        let mut records: Vec<Value> = chains
            .iter()
            .map(|chain| conversation_record(chain))
            .collect();
        let started: HashSet<&str> = chains.iter().map(|chain| chain[0].id.as_str()).collect();
        for (id, at) in lock(&self.reserved).iter() {
            if !started.contains(id.as_str()) {
                records.push(
                    json!({ "id": id, "title": "", "last_active_at": at, "archived": false }),
                );
            }
        }
        Ok(Value::Array(records))
    }

    pub fn history(&self, supervisor: &Supervisor, conversation: &str) -> Result<Value, Refused> {
        let client = Client::new(&Self::gateway(supervisor)?);
        let runs = self
            .chain(&client, conversation)?
            .into_iter()
            .map(|run| {
                Ok((
                    run.id.clone(),
                    client.run_status(&run.id)?,
                    client.history(&run.id)?,
                ))
            })
            .collect::<Result<Vec<_>, Refused>>()?;
        Ok(Value::Array(history_records(&runs)))
    }

    /// Starts the conversation's next run with the person's message. A
    /// conversation whose last run is live takes no message: nothing is
    /// queued behind it.
    pub fn send(&self, supervisor: &Supervisor, request: &SendRequest) -> Result<Value, Refused> {
        admit_send(request)?;
        let gateway = Self::gateway(supervisor)?;
        let client = Client::new(&gateway);
        let chain = self.chain(&client, &request.conversation_id)?;
        let (run_id, continues) = match chain.last() {
            None => (request.conversation_id.clone(), None),
            Some(last) => {
                let status = client.run_status(&last.id)?;
                let current = text(&status, "status").unwrap_or(&last.status);
                if !SETTLED.contains(&current) {
                    return Err(refused("agent_reply_in_progress"));
                }
                (mint_run_id()?, Some(last.id.clone()))
            }
        };
        let started = client.start_run(&start_body(
            &run_id,
            request,
            &gateway.workspace_root,
            continues.as_deref(),
        ))?;
        if text(&started, "run_id") != Some(run_id.as_str()) {
            return Err(refused("agent_gateway_unreadable"));
        }
        lock(&self.known).insert(run_id.clone(), continues);
        lock(&self.reserved).retain(|(id, _)| *id != request.conversation_id);
        // Every watch of the conversation follows the new reply.
        let mut watches = lock(&self.watches);
        for watch in watches
            .values_mut()
            .filter(|watch| watch.conversation == request.conversation_id)
        {
            watch
                .pumps
                .push(pump_run(&gateway, &run_id, watch.channel.clone()));
        }
        Ok(json!({ "reply_id": run_id }))
    }

    pub fn pending(&self, supervisor: &Supervisor, conversation: &str) -> Result<Value, Refused> {
        let client = Client::new(&Self::gateway(supervisor)?);
        let Some(last) = self
            .chain(&client, conversation)?
            .into_iter()
            .last()
            .filter(Run::live)
        else {
            return Ok(json!({ "questionnaires": [], "approvals": [] }));
        };
        Ok(pending_of(
            &last.id,
            &client.run_status(&last.id)?,
            &client.history(&last.id)?,
        ))
    }

    pub fn cancel(&self, supervisor: &Supervisor, reply: &str) -> Result<(), Refused> {
        let gateway = Self::gateway(supervisor)?;
        self.known(reply)?;
        Client::new(&gateway).cancel(reply).map(|_| ())
    }

    fn resolved(&self, reply: &str, request: &str) {
        for watch in lock(&self.watches).values() {
            for pump in watch.pumps.iter().filter(|pump| pump.run == reply) {
                let event = lock(&pump.mapping).resolve(request);
                if let Some(event) = event {
                    let _ = watch.channel.send(event);
                }
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
        Client::new(&gateway).clarification(&target.reply_id, &target.request_id, &body)?;
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
        Client::new(&gateway).permission(&target.reply_id, &target.request_id, option)?;
        self.resolved(&target.reply_id, &target.request_id);
        Ok(())
    }

    /// Watches the conversation on `channel`: its live run now, and every
    /// run a later send starts.
    pub fn observe(
        &self,
        supervisor: &Supervisor,
        conversation: &str,
        channel: Channel<StreamEvent>,
    ) -> Result<u32, Refused> {
        let gateway = Self::gateway(supervisor)?;
        let chain = self.chain(&Client::new(&gateway), conversation)?;
        let id = channel.id();
        let pumps = chain
            .last()
            .filter(|run| run.live())
            .map(|run| pump_run(&gateway, &run.id, channel.clone()))
            .into_iter()
            .collect();
        lock(&self.watches).insert(
            id,
            Watch {
                conversation: conversation.to_owned(),
                channel,
                pumps,
            },
        );
        Ok(id)
    }

    /// Ends the watch `subscription`, never a newer one.
    pub fn unobserve(&self, subscription: u32) {
        if let Some(watch) = lock(&self.watches).remove(&subscription) {
            for pump in watch.pumps {
                pump.stopped.store(true, Ordering::Release);
            }
        }
    }

    /// Ends every watch, as the service stops or the window closes.
    pub fn close(&self) {
        for (_, watch) in lock(&self.watches).drain() {
            for pump in watch.pumps {
                pump.stopped.store(true, Ordering::Release);
            }
        }
    }
}

/// Streams one run onto `channel` from a thread of its own.
fn pump_run(gateway: &Gateway, run: &str, channel: Channel<StreamEvent>) -> Pump {
    let mapping = Arc::new(Mutex::new(Mapping::new(run)));
    let stopped = Arc::new(AtomicBool::new(false));
    let client = Client::new(gateway);
    let (thread_run, thread_mapping, thread_stopped) =
        (run.to_owned(), mapping.clone(), stopped.clone());
    thread::spawn(move || {
        pump(
            &client,
            &thread_run,
            &thread_mapping,
            &channel,
            &thread_stopped,
        );
    });
    Pump {
        run: run.to_owned(),
        mapping,
        stopped,
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
                        Step::Settle(end) => {
                            let status = client.run_status(run).ok();
                            let _ = channel.send(lock(mapping).settled(end, status.as_ref()));
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
            "conversation_id": "r00ff",
            "text": "\n  ¿Cuánto IVA declaré?\nen 2025",
            "selection": {"provider": "claude", "transport": "api", "model": "m1", "effort": "high"}
        })
    }

    #[test]
    fn a_send_is_checked_before_anything_reaches_the_gateway() {
        assert!(admit_send(&send(request())).is_ok());
        let mut transport = request();
        transport["selection"]["transport"] = json!("web");
        assert_eq!(
            admit_send(&send(transport)).unwrap_err().code,
            "agent_invalid_request"
        );
        // Native controls and documents are no part of a send.
        for (key, value) in [
            (
                "controls",
                json!([{"control_id": "tier", "option_id": "fast"}]),
            ),
            ("entry_id", json!("e1")),
        ] {
            let mut extra = request();
            extra["selection"][key] = value;
            assert!(
                serde_json::from_value::<SendRequest>(extra).is_err(),
                "{key}"
            );
        }
        let mut documents = request();
        documents["document_ids"] = json!(["d1"]);
        assert!(serde_json::from_value::<SendRequest>(documents).is_err());
        for (field, value) in [
            ("text", json!("   ")),
            ("text", json!("x".repeat(MESSAGE_LIMIT + 1))),
            ("conversation_id", json!("../x")),
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
    }

    #[test]
    fn a_send_starts_its_run_as_the_gateway_takes_one() {
        let first = start_body("r00ff", &send(request()), r"C:\agent\ws\main", None);
        assert_eq!(
            first,
            json!({
                "run_id": "r00ff",
                "message": "\n  ¿Cuánto IVA declaré?\nen 2025",
                "agent": {"provider": "claude", "transport": "api", "model": "m1", "effort": "high",
                          "workspace_root": r"C:\agent\ws\main"},
                "title": "¿Cuánto IVA declaré?"
            })
        );
        let mut plain = request();
        plain["selection"].as_object_mut().unwrap().remove("effort");
        let next = start_body("r0100", &send(plain), r"C:\ws", Some("r00ff"));
        assert_eq!(next["continues_run_id"], "r00ff");
        assert!(next.get("title").is_none());
        assert!(next["agent"].get("effort").is_none());
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
            clarification_body(&message).unwrap(),
            json!({"prompt": "otra cosa"})
        );
        for text in [json!("  \n "), json!("x".repeat(MESSAGE_LIMIT + 1))] {
            let message: Answer =
                serde_json::from_value(json!({"kind": "message", "text": text})).unwrap();
            assert_eq!(
                clarification_body(&message).unwrap_err().code,
                "agent_invalid_request"
            );
        }
    }

    fn run(id: &str, predecessor: Option<&str>, created: &str, status: &str) -> Run {
        Run {
            id: id.into(),
            status: status.into(),
            title: (predecessor.is_none()).then(|| format!("title {id}")),
            created_at: created.into(),
            updated_at: created.into(),
            predecessor: predecessor.map(str::to_owned),
        }
    }

    #[test]
    fn runs_chain_into_conversations_named_by_their_first_run() {
        // Newest created first, as the listing serves them.
        let runs = [
            run("c3", Some("c2"), "2026-10-13T12:03:00Z", "running"),
            run("x1", None, "2026-10-13T12:02:30Z", "archived"),
            run("c2", Some("c1"), "2026-10-13T12:02:00Z", "completed"),
            run("c1", None, "2026-10-13T12:01:00Z", "completed"),
        ];
        let chains = chains(&runs);
        let ids: Vec<Vec<&str>> = chains
            .iter()
            .map(|chain| chain.iter().map(|run| run.id.as_str()).collect())
            .collect();
        assert_eq!(ids, [vec!["c1", "c2", "c3"], vec!["x1"]]);
        assert_eq!(
            conversation_record(&chains[0]),
            json!({"id": "c1", "title": "title c1", "last_active_at": "2026-10-13T12:03:00Z", "archived": false})
        );
        assert_eq!(conversation_record(&chains[1])["archived"], true);
        assert!(chains[0][2].live() && !chains[0][1].live());
    }

    #[test]
    fn history_lists_each_message_once_in_reply_order() {
        let message = |id: &str, role: &str, content: &str| {
            json!({"message_id": id, "role": role, "content": content, "agent_id": null,
                   "timestamp": if role == "user" { json!("2026-10-13T12:00:00Z") } else { Value::Null }})
        };
        let first = json!({"state": {"status": "completed",
            "messages": [message("u1", "user", "Hola"), message("a1", "assistant", "¿Qué tal?")],
            "tool_calls": [{"tool_call_id": "t1", "title": "ledger_list", "kind": "read", "status": "completed",
                            "locations": [], "content": []}]},
            "usage": {"total": {"input_tokens": 10, "output_tokens": 4}}});
        // The successor is seeded with the predecessor's messages under new ids.
        let second = json!({"state": {"status": "failed",
            "messages": [message("s1", "user", "Hola"), message("s2", "assistant", "¿Qué tal?"),
                         message("tool", "tool", "private result"),
                         message("u2", "user", "Otra")],
            "tool_calls": []},
            "usage": null});
        let status = json!({"status": "completed", "queued_messages": 0,
            "agent": {"provider": "claude", "model": "m1", "effort": null, "transport": "api"},
            "selection": {"provider_display_name": "Claude", "model_display_name": "Model One"}});
        let failed = json!({"status": "failed", "provider_condition": "throttled",
            "failure_reason": "rate limited", "agent": null});
        let records =
            history_records(&[("c1".into(), status, first), ("c2".into(), failed, second)]);
        assert_eq!(
            Value::Array(records),
            json!([
                {"kind": "person", "id": "u1", "reply_id": "c1", "text": "Hola", "sent_at": "2026-10-13T12:00:00Z"},
                {"kind": "tool", "reply_id": "c1", "id": "t1", "title": "ledger_list", "tool_kind": "read", "status": "completed"},
                {"kind": "agent", "id": "a1", "reply_id": "c1", "text": "¿Qué tal?"},
                {"kind": "reply", "id": "c1", "status": "completed", "provider_condition": null,
                 "failure_reason": null, "queued_messages": 0,
                 "selection": {"provider": "claude", "transport": "api", "provider_display_name": "Claude",
                               "model": "m1", "model_display_name": "Model One", "effort": null},
                 "usage": {"input_tokens": 10, "output_tokens": 4}},
                {"kind": "person", "id": "u2", "reply_id": "c2", "text": "Otra", "sent_at": "2026-10-13T12:00:00Z"},
                {"kind": "reply", "id": "c2", "status": "failed", "provider_condition": "throttled",
                 "failure_reason": "rate limited", "queued_messages": 0, "selection": null, "usage": null},
            ])
        );
    }

    #[test]
    fn a_seed_is_the_longest_repeat_of_the_previous_end() {
        let pair = |role: &str, content: &str| (role.to_owned(), content.to_owned());
        let previous = [pair("user", "a"), pair("assistant", "b"), pair("user", "a")];
        assert_eq!(
            seeded(&previous, &[pair("user", "a"), pair("user", "c")]),
            1
        );
        assert_eq!(
            seeded(
                &previous,
                &[pair("assistant", "b"), pair("user", "a"), pair("user", "c")]
            ),
            2
        );
        assert_eq!(seeded(&previous, &[pair("user", "z")]), 0);
        assert_eq!(seeded(&[], &[pair("user", "a")]), 0);
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
                    {"id": "q", "prompt": "¿Año?", "kind": "text", "options": null, "required": true}
                ]}],
                "approvals": [{"request_id": "perm-1", "reply_id": "run-1", "source": "agent_tool",
                    "tool_call": "ledger_list", "description": "Read the ledger", "tool_kind": "read",
                    "options": [{"option_id": "ok", "name": "Allow", "kind": "allow_once"}]}]
            })
        );
    }

    #[test]
    fn instants_and_run_ids_follow_their_grammars() {
        let at = now();
        assert_eq!(at.len(), 20);
        assert!(at.starts_with("20") && at.ends_with('Z') && &at[10..11] == "T");
        let id = mint_run_id().unwrap();
        assert!(gateway::run_id(&id));
        assert_ne!(id, mint_run_id().unwrap());
    }
}
