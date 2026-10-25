//! The person's per-role model selection, read from the agent service and
//! parsed into the closed snapshot the window shows. The service owns the role
//! vocabulary; a role here is only checked against its grammar. A value
//! outside the contract is a protocol failure, never passed on.

use serde::Serialize;
use serde_json::Value;

const ROLE_LIMIT: usize = 64;
const MODEL_LIMIT: usize = 256;
const ROLES_LIMIT: usize = 16;

/// One role and the lane and model selected for it; both absent when none is.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ModelRoleSelection {
    pub role: String,
    pub lane: Option<String>,
    pub model: Option<String>,
}

/// Every role's selection with the guard a change sends back, or a record
/// nobody can read, which lists no role and carries the guard of its reset.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum ModelRoles {
    Readable {
        roles: Vec<ModelRoleSelection>,
        revision: String,
    },
    Unreadable {
        revision: Option<String>,
    },
}

/// Why the read gave no snapshot, as the stable code the column words.
pub fn refusal(answer: &Value) -> Option<&'static str> {
    let refused = answer["kind"] == "refused"
        || answer
            .as_object()
            .is_some_and(|object| object.len() == 1 && object.contains_key("code"));
    if !refused {
        return None;
    }
    Some(match answer["code"].as_str() {
        Some("busy") => "agent_service_busy",
        Some("signed_out" | "not_signed_in" | "profile_locked") => "agent_signed_out",
        Some("service_stopping" | "catalog_unavailable" | "runtime_unavailable") => {
            "agent_service_not_ready"
        }
        _ => "agent_service_failed",
    })
}

/// The snapshot in `answer`, or `None` when it breaks the contract.
pub fn parse(answer: &Value) -> Option<ModelRoles> {
    let object = answer.as_object()?;
    if object.len() != 3 {
        return None;
    }
    let roles = object.get("roles")?.as_array()?;
    let revision = object.get("revision")?;
    if object.get("unreadable")?.as_bool()? {
        let revision = optional(revision, is_revision)?;
        return roles
            .is_empty()
            .then_some(ModelRoles::Unreadable { revision });
    }
    let revision = revision
        .as_str()
        .filter(|text| is_revision(text))?
        .to_owned();
    if roles.is_empty() || roles.len() > ROLES_LIMIT {
        return None;
    }
    let roles = roles.iter().map(selection).collect::<Option<Vec<_>>>()?;
    let mut names: Vec<&str> = roles.iter().map(|entry| entry.role.as_str()).collect();
    names.sort_unstable();
    names.dedup();
    if names.len() != roles.len() {
        return None;
    }
    Some(ModelRoles::Readable { roles, revision })
}

fn selection(entry: &Value) -> Option<ModelRoleSelection> {
    let object = entry.as_object()?;
    if object.len() != 3 {
        return None;
    }
    let role = object.get("role")?.as_str().filter(|text| is_role(text))?;
    let lane = optional(object.get("lane")?, is_lane)?;
    let model = optional(object.get("model")?, is_model)?;
    (lane.is_some() == model.is_some()).then(|| ModelRoleSelection {
        role: role.to_owned(),
        lane,
        model,
    })
}

/// `Some(None)` for null, `Some(Some(text))` for an accepted string, `None` otherwise.
fn optional(value: &Value, accepted: fn(&str) -> bool) -> Option<Option<String>> {
    match value {
        Value::Null => Some(None),
        Value::String(text) if accepted(text) => Some(Some(text.clone())),
        _ => None,
    }
}

fn is_revision(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn is_role(text: &str) -> bool {
    (1..=ROLE_LIMIT).contains(&text.len())
        && text.starts_with(|c: char| c.is_ascii_lowercase())
        && text
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

fn is_lane(text: &str) -> bool {
    crate::shell::provider_settings::wire::is_provider_id(text)
}

fn is_model(text: &str) -> bool {
    (1..=MODEL_LIMIT).contains(&text.len()) && text.bytes().all(|b| (0x21..=0x7e).contains(&b))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn revision() -> String {
        "a".repeat(64)
    }

    #[test]
    fn a_readable_answer_becomes_every_role_with_its_selection() {
        let answer = json!({
            "unreadable": false,
            "roles": [
                {"role": "vision_transcription", "lane": "example_api", "model": "synthetic-vision-1"},
                {"role": "text_extraction", "lane": null, "model": null},
            ],
            "revision": revision(),
        });
        assert_eq!(
            parse(&answer),
            Some(ModelRoles::Readable {
                roles: vec![
                    ModelRoleSelection {
                        role: "vision_transcription".to_owned(),
                        lane: Some("example_api".to_owned()),
                        model: Some("synthetic-vision-1".to_owned()),
                    },
                    ModelRoleSelection {
                        role: "text_extraction".to_owned(),
                        lane: None,
                        model: None,
                    },
                ],
                revision: revision(),
            })
        );
        assert_eq!(refusal(&answer), None);
    }

    #[test]
    fn an_unreadable_record_lists_no_role_and_keeps_its_reset_guard() {
        let answer = json!({"unreadable": true, "roles": [], "revision": revision()});
        assert_eq!(
            parse(&answer),
            Some(ModelRoles::Unreadable {
                revision: Some(revision())
            })
        );
        let unguarded = json!({"unreadable": true, "roles": [], "revision": null});
        assert_eq!(
            parse(&unguarded),
            Some(ModelRoles::Unreadable { revision: None })
        );
    }

    #[test]
    fn an_answer_outside_the_contract_is_refused() {
        let role = |lane: Value, model: Value| json!({"role": "text_extraction", "lane": lane, "model": model});
        for answer in [
            json!({"unreadable": false, "roles": [], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!(null), json!(null))], "revision": null}),
            json!({"unreadable": false, "roles": [role(json!("example_api"), json!(null))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!("Example"), json!("m"))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!("example_api"), json!("has space"))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!(null), json!(null)), role(json!(null), json!(null))], "revision": revision()}),
            json!({"unreadable": true, "roles": [role(json!(null), json!(null))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!(null), json!(null))], "revision": revision(), "extra": 1}),
            json!({"unreadable": false, "roles": [{"role": "Text", "lane": null, "model": null}], "revision": revision()}),
        ] {
            assert_eq!(parse(&answer), None, "{answer}");
        }
    }

    #[test]
    fn a_refusal_crosses_as_its_column_code() {
        for (code, expected) in [
            ("busy", "agent_service_busy"),
            ("signed_out", "agent_signed_out"),
            ("not_signed_in", "agent_signed_out"),
            ("profile_locked", "agent_signed_out"),
            ("service_stopping", "agent_service_not_ready"),
            ("unknown", "agent_service_failed"),
        ] {
            assert_eq!(
                refusal(&json!({"kind": "refused", "code": code})),
                Some(expected)
            );
            assert_eq!(refusal(&json!({"code": code})), Some(expected));
        }
    }
}
