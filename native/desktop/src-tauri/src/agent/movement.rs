//! One Libro movement handed to a conversation as an attachment: what the
//! registered `ledger.view` read serves of it for the signed-in profile,
//! written unchanged as JSON and stored from memory in the conversation's own
//! storage. Nothing is sent to a model here: the person sends the message
//! that names it, or removes it.

use super::Refused;
use crate::shell::relay::Failure;
use serde::Serialize;
use serde_json::Value;

/// Why a movement was not stored, as the column words it: the agent's own
/// refusal code, or the ledger read's refusal with the sentence the
/// application served for it, where it served one.
#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct MovementRefused {
    pub code: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub refusal_words: Option<String>,
}

/// The ledger read gave no movement to store.
pub const UNREADABLE: &str = "agent_movement_unreadable";

impl From<Refused> for MovementRefused {
    fn from(refused: Refused) -> Self {
        Self {
            code: refused.code,
            refusal_words: None,
        }
    }
}

impl MovementRefused {
    fn unreadable(refusal_words: Option<String>) -> Self {
        Self {
            code: UNREADABLE.to_owned(),
            refusal_words,
        }
    }
}

/// Why the ledger read did not serve the movement, with the sentence the
/// application served for it, where it served one.
pub fn ledger_refusal(failure: Failure) -> MovementRefused {
    MovementRefused::unreadable(failure.refusal_words.or_else(|| {
        failure
            .terminal_failure
            .and_then(|terminal| terminal.refusal_words)
    }))
}

/// A movement handle as the window may name one: what a ledger row's id is.
pub fn handle(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 128
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

/// A calendar date as the ledger serves one: `YYYY-MM-DD`.
fn served_date(date: &str) -> bool {
    let bytes = date.as_bytes();
    bytes.len() == 10
        && bytes.iter().enumerate().all(|(at, b)| {
            if at == 4 || at == 7 {
                *b == b'-'
            } else {
                b.is_ascii_digit()
            }
        })
}

/// The file the served read is stored as, named from its own date and
/// movement id, and its bytes: the read unchanged, as UTF-8 JSON.
pub fn attachment(served: &Value) -> Result<(String, Vec<u8>), MovementRefused> {
    let transaction = &served["transaction"];
    let date = transaction["date"]
        .as_str()
        .filter(|date| served_date(date));
    let id = transaction["transaction_id"]
        .as_str()
        .filter(|id| handle(id) && id.len() >= 8);
    let (Some(date), Some(id)) = (date, id) else {
        return Err(MovementRefused::unreadable(None));
    };
    let name = format!("movimiento-{date}-{}.json", &id[..8]);
    let bytes = serde_json::to_vec_pretty(served).map_err(|_| MovementRefused::unreadable(None))?;
    Ok((name, bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::shell::relay::{TerminalFailure, TerminalFailureEffect};
    use serde_json::json;

    fn served() -> Value {
        json!({
            "profile_id": "perfil-sintetico",
            "transaction_prefix": "3f9a0c21",
            "transaction": {
                "transaction_id": "3f9a0c21d4e5f6a7b8c9",
                "date": "2026-10-03",
                "amount": "42.10",
                "description": "Suministro sintético",
            },
            "review_status": "needs_review",
            "latest_llm_rejection": null,
        })
    }

    #[test]
    fn the_movement_is_stored_as_the_read_served_it_and_named_from_its_own_fields() {
        let (name, bytes) = attachment(&served()).unwrap();
        assert_eq!(name, "movimiento-2026-10-03-3f9a0c21.json");
        let written: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(written, served());
        assert!(std::str::from_utf8(&bytes).is_ok());
    }

    #[test]
    fn a_read_without_its_date_or_id_is_not_stored() {
        for (field, value) in [
            ("date", json!(null)),
            ("date", json!("03/10/2026")),
            ("transaction_id", json!("short")),
            ("transaction_id", json!("../../3f9a0c21d4")),
        ] {
            let mut read = served();
            read["transaction"][field] = value;
            assert_eq!(
                attachment(&read).unwrap_err(),
                MovementRefused {
                    code: UNREADABLE.to_owned(),
                    refusal_words: None
                },
                "{field}"
            );
        }
    }

    #[test]
    fn a_handle_is_what_a_row_id_is() {
        assert!(handle("3f9a0c21d4e5f6a7b8c9"));
        for bad in ["", "a/b", "a b", "..", &"a".repeat(129)] {
            assert!(!handle(bad), "{bad}");
        }
    }

    #[test]
    fn a_ledger_refusal_carries_the_sentence_the_application_served() {
        let words = "Este movimiento ya no existe.";
        let mut failure = Failure::new("refused");
        failure.refusal_words = Some(words.to_owned());
        assert_eq!(
            ledger_refusal(failure).refusal_words.as_deref(),
            Some(words)
        );
        let mut failure = Failure::new("failed");
        failure.terminal_failure = Some(Box::new(TerminalFailure {
            operation_id: "op".to_owned(),
            definition_id: "ledger.view".to_owned(),
            effect: TerminalFailureEffect::Unknown,
            refusal_words: Some(words.to_owned()),
        }));
        let refused = ledger_refusal(failure);
        assert_eq!(refused.code, UNREADABLE);
        assert_eq!(refused.refusal_words.as_deref(), Some(words));
        assert_eq!(
            ledger_refusal(Failure::new("unavailable")).refusal_words,
            None
        );
    }

    #[test]
    fn an_agent_refusal_keeps_its_code() {
        let refused: MovementRefused = Refused::new("agent_attachment_too_large".to_owned()).into();
        assert_eq!(refused.code, "agent_attachment_too_large");
        assert_eq!(
            serde_json::to_value(&refused).unwrap(),
            json!({"code": "agent_attachment_too_large"})
        );
    }
}
