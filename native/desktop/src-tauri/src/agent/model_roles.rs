//! The person's per-role model selection, read from and changed through the
//! agent service and parsed into the closed snapshot the window shows. The
//! service owns the role vocabulary; a role here is only checked against its
//! grammar. A value outside the contract is a protocol failure, never passed on.

use serde::Serialize;
use serde_json::Value;

const ROLE_LIMIT: usize = 64;
/// A model id is 1 to 512 characters, none a C0 control or DEL, as the
/// agent's catalogues carry it.
const MODEL_LIMIT: usize = 512;
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

/// Why a change gave no snapshot, as the stable code the window words: the
/// service's own reason a selection was not stored, or what a read refusal
/// crosses as.
pub fn change_refusal(answer: &Value) -> Option<&'static str> {
    let crossed = refusal(answer)?;
    Some(match answer["code"].as_str() {
        Some("unknown_role") => "agent_model_role_unknown_role",
        Some("model_not_in_catalogue") => "agent_model_role_model_not_in_catalogue",
        Some("lane_not_runnable") => "agent_model_role_lane_not_runnable",
        Some("vision_required") => "agent_model_role_vision_required",
        Some("revision_conflict") => "agent_model_role_revision_conflict",
        Some("committed_readback_failed") => "agent_model_role_committed_readback_failed",
        Some("catalog_unavailable") => "agent_model_role_catalog_unavailable",
        Some("unknown") => "agent_model_role_unknown",
        _ => crossed,
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

pub fn is_revision(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

pub fn is_role(text: &str) -> bool {
    (1..=ROLE_LIMIT).contains(&text.len())
        && text.starts_with(|c: char| c.is_ascii_lowercase())
        && text
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

pub fn is_lane(text: &str) -> bool {
    crate::shell::provider_settings::wire::is_provider_id(text)
}

pub fn is_model(text: &str) -> bool {
    (1..=MODEL_LIMIT).contains(&text.chars().count())
        && !text.chars().any(|c| c <= '\u{1f}' || c == '\u{7f}')
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
            json!({"unreadable": false, "roles": [role(json!("example_api"), json!("tab\there"))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!("example_api"), json!("m".repeat(513)))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!("example_api"), json!(""))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!(null), json!(null)), role(json!(null), json!(null))], "revision": revision()}),
            json!({"unreadable": true, "roles": [role(json!(null), json!(null))], "revision": revision()}),
            json!({"unreadable": false, "roles": [role(json!(null), json!(null))], "revision": revision(), "extra": 1}),
            json!({"unreadable": false, "roles": [{"role": "Text", "lane": null, "model": null}], "revision": revision()}),
        ] {
            assert_eq!(parse(&answer), None, "{answer}");
        }
    }

    #[test]
    fn a_model_id_is_any_512_characters_without_a_control() {
        let longest = "m".repeat(512);
        let widest = "é".repeat(512);
        for accepted in [
            "synthetic-vision:1",
            "has space",
            "ñandú/modelo",
            &longest,
            &widest,
        ] {
            assert!(is_model(accepted), "{accepted}");
        }
        let longer = "m".repeat(513);
        for refused in ["", "line\nbreak", "nul\u{0}", "del\u{7f}", &longer] {
            assert!(!is_model(refused), "{refused:?}");
        }
    }

    #[test]
    fn a_change_refusal_keeps_the_services_reason_a_selection_was_not_stored() {
        for (code, expected) in [
            ("unknown_role", "agent_model_role_unknown_role"),
            (
                "model_not_in_catalogue",
                "agent_model_role_model_not_in_catalogue",
            ),
            ("lane_not_runnable", "agent_model_role_lane_not_runnable"),
            ("vision_required", "agent_model_role_vision_required"),
            ("revision_conflict", "agent_model_role_revision_conflict"),
            (
                "committed_readback_failed",
                "agent_model_role_committed_readback_failed",
            ),
            (
                "catalog_unavailable",
                "agent_model_role_catalog_unavailable",
            ),
            ("unknown", "agent_model_role_unknown"),
            ("busy", "agent_service_busy"),
            ("profile_locked", "agent_signed_out"),
            ("service_stopping", "agent_service_not_ready"),
        ] {
            assert_eq!(change_refusal(&json!({"code": code})), Some(expected));
            assert_eq!(
                change_refusal(&json!({"kind": "refused", "code": code})),
                Some(expected)
            );
        }
        let snapshot = json!({"unreadable": false, "roles": [], "revision": revision()});
        assert_eq!(change_refusal(&snapshot), None);
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
