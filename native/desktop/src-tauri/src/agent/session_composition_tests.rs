//! The typed composition against the `json!` composition it replaced: for
//! the same gateway reads, both serialize to the same bytes, malformed reads
//! included.

use super::{Pending, Snapshot, answer, history_records, pending_of};
use serde_json::{Value, json};

/// The composition as the host wrote it before its answers were typed, kept
/// as the oracle the typed composition must serialize exactly as.
mod before {
    use super::super::{DETAIL_BLOCKS, DETAIL_LIMIT, digest, plain_name, seeded, skill_name, text};
    use crate::agent::stream::{Mapping, Step, StreamEvent};
    use serde_json::{Value, json};

    fn echoed_documents(message: &Value) -> Value {
        Value::Array(
            message
                .get("attachments")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(|item| {
                    let name = text(item, "name").filter(|name| plain_name(name))?;
                    Some(json!({
                        "name": name,
                        "sha256": text(item, "sha256").filter(|sha| digest(sha)),
                        "media_type": text(item, "media_type"),
                    }))
                })
                .collect(),
        )
    }

    /// The skills a user message loaded, as its history echoes them: names of
    /// the skill grammar only.
    fn echoed_skills(message: &Value) -> Value {
        Value::Array(
            message
                .get("skills")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
                .filter(|name| skill_name(name))
                .map(|name| json!(name))
                .collect(),
        )
    }

    /// What a tool call's history says of it, as text to preview: its text
    /// blocks, the call's input and its result as the agent worded them, each cut
    /// to `DETAIL_LIMIT` characters, then the places it touched. Diffs and
    /// terminals are named by their path only.
    fn tool_details(call: &Value) -> Value {
        let blocks = call
            .get("content")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|block| match text(block, "content_type") {
                Some("text") => text(block, "text").filter(|text| !text.trim().is_empty()),
                Some("diff") => text(block, "path"),
                _ => None,
            });
        let places = call
            .get("locations")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|place| {
                let path = text(place, "path").filter(|path| !path.is_empty())?;
                Some(match place.get("line").and_then(Value::as_u64) {
                    Some(line) => format!("{path}:{line}"),
                    None => path.to_owned(),
                })
            });
        Value::Array(
            blocks
                .map(str::to_owned)
                .chain(places)
                .take(DETAIL_BLOCKS)
                .map(|detail| match detail.char_indices().nth(DETAIL_LIMIT) {
                    Some((cut, _)) => json!(format!("{}…", &detail[..cut])),
                    None => json!(detail),
                })
                .collect(),
        )
    }

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
                        Step::Emit(event) => match *event {
                            StreamEvent::Approval { approval, .. } => {
                                serde_json::to_value(approval).ok()
                            }
                            _ => None,
                        },
                        _ => None,
                    })
            })
            .collect();
        json!({ "questionnaires": questionnaires, "approvals": approvals })
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
                    "attachments": echoed_documents(message),
                    "skills": echoed_skills(message),
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
                    "details": tool_details(call),
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
}

const SHA: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

fn message(id: Value, role: &str, content: Value, timestamp: Value) -> Value {
    json!({"message_id": id, "role": role, "content": content, "timestamp": timestamp})
}

/// Chains of run reads: a seeded successor whose repeat is dropped, a
/// complete reply, and reads that leave out or mistype what the gateway's
/// schema requires.
fn chains() -> Vec<Vec<(String, Value, Value)>> {
    let at = json!("2026-10-13T12:00:00Z");
    let first = json!({"state": {"status": "completed",
        "messages": [message(json!("u1"), "user", json!("Hola"), at.clone()),
                     message(json!("a1"), "assistant", json!("¿Qué tal?"), Value::Null)],
        "tool_calls": [{"tool_call_id": "t1", "title": "ledger_list", "kind": "read", "status": "completed",
                        "locations": [{"path": "libro.csv", "line": 3}, {"path": ""}, {"path": "b.md", "line": "x"}],
                        "content": [{"content_type": "text", "text": "{\"year\":2026}"},
                                    {"content_type": "diff", "path": "notas.md"},
                                    {"content_type": "text", "text": "r".repeat(super::DETAIL_LIMIT + 1)}]}]},
        "usage": {"total": {"input_tokens": 10, "output_tokens": 4, "cache_read_tokens": 2}}});
    let seeded = json!({"state": {"status": "failed",
        "messages": [message(json!("s1"), "user", json!("Hola"), at.clone()),
                     message(json!("s2"), "assistant", json!("¿Qué tal?"), Value::Null),
                     message(json!("tool"), "tool", json!("private"), Value::Null),
                     {"message_id": "u2", "role": "user", "content": "Otra", "timestamp": at,
                      "attachments": [{"name": "factura.pdf", "sha256": SHA, "media_type": "application/pdf"},
                                      {"name": "notas.txt", "sha256": "short"}, {"name": "../escape"}, "x"],
                      "skills": ["cadrumo-facturas", "../escape", 7]}]},
        "usage": null});
    let completed = json!({"status": "completed", "queued_messages": 2,
        "agent": {"provider": "claude", "model": "m1", "effort": null, "transport": "api"},
        "selection": {"provider_display_name": "Claude", "model_display_name": "Model One", "effort": "high"}});
    let failed = json!({"status": "failed", "provider_condition": "throttled",
        "failure_reason": "rate limited", "agent": null});
    // What the gateway's schema requires, left out or of another type.
    let malformed_history = json!({"state": {"status": "running",
        "messages": [message(json!(7), "user", json!(null), json!(12)),
                     {"role": "assistant"}, {"role": 3, "content": "x"}],
        "tool_calls": [{"tool_call_id": 4, "kind": ["read"], "content": "x", "locations": [{"line": 2}]}, {}]},
        "usage": {"total": {"output_tokens": "many"}}});
    let malformed_status = json!({"queued_messages": null, "provider_condition": 5,
        "agent": {"transport": "cli", "provider": null}, "selection": {"provider": "codex", "model": 9}});
    let no_transport =
        json!({"status": "completed", "agent": {"provider": "claude", "transport": 1}});
    vec![
        vec![
            ("c1".into(), completed.clone(), first.clone()),
            ("c2".into(), failed, seeded),
        ],
        vec![("m1".into(), malformed_status, malformed_history)],
        vec![
            ("e1".into(), no_transport, json!({})),
            ("e2".into(), json!({}), json!(null)),
        ],
        vec![("a1".into(), completed, first)],
        vec![],
    ]
}

/// Reads a run waits on: a questionnaire, approvals with and without a
/// server, ones the mapping refuses, and none.
fn waits() -> Vec<(Value, Value)> {
    let status = json!({"pending_clarification": {"request_id": "clar-1", "questions": [
        {"id": "q", "prompt": "¿Año?", "kind": "text", "options": null, "required": true},
        {"id": "c", "prompt": "¿Cuál?", "kind": "choice", "options": ["a", "b"]}]}});
    let history = json!({"state": {"pending_permissions": [
        {"request_id": "perm-1", "description": "Read", "tool_call": "ledger_list", "tool_kind": "read",
         "options": [{"option_id": "ok", "name": "Allow", "kind": "allow_once"},
                     {"option_id": "no", "kind": "reject_once"}]},
        {"request_id": "perm-2", "tool_server": "cadrumo", "tool_kind": "unheard",
         "options": [{"option_id": "s", "name": null, "kind": "allow_session"}]},
        {"request_id": "perm-3", "options": [{"option_id": "x", "kind": "allow_always"}]},
        {"request_id": "perm-4", "options": []}]}});
    vec![
        (status.clone(), history),
        (
            json!({"pending_clarification": {"request_id": "clar-2", "questions": [{"id": "q", "kind": "other"}]}}),
            json!({"state": {"pending_permissions": "none"}}),
        ),
        (status, json!({})),
        (json!({}), json!({})),
    ]
}

fn bytes(value: &Value) -> String {
    serde_json::to_string(value).unwrap()
}

#[test]
fn history_serializes_as_the_composition_it_replaced() {
    for runs in chains() {
        let typed = answer(&history_records(&runs)).unwrap();
        assert_eq!(
            bytes(&typed),
            bytes(&Value::Array(before::history_records(&runs)))
        );
    }
}

#[test]
fn pending_serializes_as_the_composition_it_replaced() {
    for (status, history) in waits() {
        let typed = answer(&pending_of("run-1", &status, &history)).unwrap();
        assert_eq!(
            bytes(&typed),
            bytes(&before::pending_of("run-1", &status, &history))
        );
    }
    assert_eq!(
        bytes(&answer(&Pending::default()).unwrap()),
        bytes(&json!({ "questionnaires": [], "approvals": [] }))
    );
}

#[test]
fn a_snapshot_serializes_as_the_composition_it_replaced() {
    let (status, history) = waits().swap_remove(0);
    for runs in chains() {
        let newest = runs.last().map(|(id, _, _)| id.as_str());
        let typed = answer(&Snapshot {
            history: history_records(&runs),
            pending: newest.map_or_else(Pending::default, |id| pending_of(id, &status, &history)),
        })
        .unwrap();
        let earlier = json!({
            "history": before::history_records(&runs),
            "pending": newest.map_or_else(
                || json!({ "questionnaires": [], "approvals": [] }),
                |id| before::pending_of(id, &status, &history),
            ),
        });
        assert_eq!(bytes(&typed), bytes(&earlier));
    }
}
