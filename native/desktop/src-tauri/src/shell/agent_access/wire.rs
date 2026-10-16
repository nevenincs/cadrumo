//! The agent-access answers, parsed into the closed shapes the window reads.
//! A value outside a closed set is a protocol failure, never passed on, and
//! nothing the product's inventory carries beyond the named fields is
//! forwarded.
use crate::shell::sign_in::wire::Outcome;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// More keys than a person issues by hand; a listing beyond it is not read.
const CREDENTIAL_LIMIT: usize = 512;

fn protocol() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
}

/// Why a call was refused, as the stable code the window words.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Refusal {
    NotSignedIn,
    ProfileLocked,
    NotFound,
    /// The host did not hear how a change ended: it may have been made.
    OutcomeUnknown,
    PersonActRequired,
    /// Issuing a key is not offered by this host yet.
    IssueUnavailable,
    Unknown,
}

/// What a command refuses with. Only the code crosses to the window.
#[derive(Debug, Serialize)]
pub struct Refused {
    pub code: Refusal,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum CommandFailure {
    Host(ApplicationError),
    Refused(Refused),
}
impl From<ApplicationError> for CommandFailure {
    fn from(error: ApplicationError) -> Self {
        Self::Host(error)
    }
}
impl From<Refusal> for CommandFailure {
    fn from(code: Refusal) -> Self {
        Self::Refused(Refused { code })
    }
}

/// The refusal a product reason names. The reasons are the product's own:
/// the sign-in gate's, the runtime's access denials and the person-only
/// acts. A reason outside the ones listed is a refusal all the same, and the
/// window is told only that it is an unknown one.
pub fn refusal(reason: &str) -> Refusal {
    match reason {
        "authentication_required"
        | "PROFILE_LOGIN_REQUIRED"
        | "absent"
        | "expired_idle"
        | "expired_absolute"
        | "keychain_entry_missing"
        | "session_inactive"
        | "session_expired" => Refusal::NotSignedIn,
        "profile_locked" => Refusal::ProfileLocked,
        "person_act_required" | "human_authority_required" | "administration_denied" => {
            Refusal::PersonActRequired
        }
        _ => Refusal::Unknown,
    }
}

/// Where a grant stands in the profile.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    Pending,
    Active,
    Suspended,
    Revoked,
}

/// What a key lets its agent see.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Category {
    ProfileValues,
    OperationMetadata,
    TaxValues,
}

/// One grant as the window lists it. No field is, or is derived from, a key.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct Record {
    pub id: String,
    pub state: State,
    pub issued_at: String,
    pub expires_at: String,
    pub last_used_at: Option<String>,
    pub categories: Vec<Category>,
    pub all_operations: bool,
}

#[derive(Debug, Eq, PartialEq, Serialize)]
pub struct Answer {
    pub credentials: Vec<Record>,
}

/// A revoke that reached the product and was answered.
#[derive(Debug, Eq, PartialEq, Serialize)]
pub struct Revoked {
    pub cleanup_pending: bool,
}

#[derive(Deserialize)]
struct ListResult {
    inventory: Inventory,
}
#[derive(Deserialize)]
struct Inventory {
    grants: Vec<Grant>,
    keys: Vec<Key>,
}
#[derive(Deserialize)]
struct Grant {
    grant_id: String,
    state: State,
    scope: Scope,
    valid_from: String,
    expires_at: String,
}
#[derive(Deserialize)]
struct Scope {
    #[serde(default)]
    all_agent_operations: bool,
    #[serde(default)]
    disclosure_categories: Vec<CategoryGrant>,
}
#[derive(Deserialize)]
struct CategoryGrant {
    category: Category,
}
#[derive(Deserialize)]
struct Key {
    grant_id: String,
    last_used_at: Option<String>,
}

/// The latest use seen of a grant's keys: when, and the text that said it.
type LastUse = Option<((i64, u32), String)>;

/// A grant's identifier as the product prints it: a hyphenated UUID, which
/// the product's command line reads as itself.
pub fn is_uuid(text: &str) -> bool {
    text.len() == 36
        && text.bytes().enumerate().all(|(at, byte)| match at {
            8 | 13 | 18 | 23 => byte == b'-',
            _ => byte.is_ascii_hexdigit(),
        })
}

/// An instant as seconds and nanoseconds since the epoch, read from RFC 3339
/// text: `2026-10-13T09:30:00.123456Z`, or with a numeric offset. Anything
/// else is not an instant.
fn instant(text: &str) -> Option<(i64, u32)> {
    let bytes = text.as_bytes();
    if !text.is_ascii() || bytes.len() < 20 {
        return None;
    }
    let digits = |from: usize, to: usize| -> Option<i64> {
        let part = text.get(from..to)?;
        if part.bytes().all(|b| b.is_ascii_digit()) {
            part.parse().ok()
        } else {
            None
        }
    };
    let fixed = [(4, b'-'), (7, b'-'), (10, b'T'), (13, b':'), (16, b':')];
    if fixed.iter().any(|(at, byte)| bytes[*at] != *byte) {
        return None;
    }
    let (year, month, day) = (digits(0, 4)?, digits(5, 7)?, digits(8, 10)?);
    let (hour, minute, second) = (digits(11, 13)?, digits(14, 16)?, digits(17, 19)?);
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let month_days = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap => 29,
        2 => 28,
        _ => return None,
    };
    if !(1..=month_days).contains(&day) || hour > 23 || minute > 59 || second > 59 {
        return None;
    }
    let mut rest = &text[19..];
    let mut nanos = 0u32;
    if let Some(fraction) = rest.strip_prefix('.') {
        let length = fraction.bytes().take_while(u8::is_ascii_digit).count();
        if !(1..=9).contains(&length) {
            return None;
        }
        nanos = fraction[..length].parse::<u32>().ok()? * 10u32.pow(9 - length as u32);
        rest = &fraction[length..];
    }
    let offset = match rest.as_bytes() {
        b"Z" => 0,
        [sign @ (b'+' | b'-'), _, _, b':', _, _] => {
            let (h, m) = (
                digits(text.len() - 5, text.len() - 3)?,
                digits(text.len() - 2, text.len())?,
            );
            if h > 23 || m > 59 {
                return None;
            }
            let seconds = h * 3600 + m * 60;
            if *sign == b'+' { seconds } else { -seconds }
        }
        _ => return None,
    };
    // Days from the civil date, by the standard era arithmetic.
    let shifted = if month <= 2 { year - 1 } else { year };
    let era = shifted.div_euclid(400);
    let year_of_era = shifted - era * 400;
    let day_of_year = (153 * (month + if month > 2 { -3 } else { 9 }) + 2) / 5 + day - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    let days = era * 146_097 + day_of_era - 719_468;
    Some((
        days * 86_400 + hour * 3600 + minute * 60 + second - offset,
        nanos,
    ))
}

/// Every grant the profile lists, each with the latest use of its keys.
pub fn list(outcome: Outcome) -> Result<Answer, CommandFailure> {
    let result = match outcome {
        Outcome::Refused { refusal: row, .. } => return Err(refusal(&row.code).into()),
        Outcome::Success { result, .. } => result,
    };
    let ListResult { inventory } = serde_json::from_value(result).map_err(|_| protocol())?;
    if inventory.grants.len() > CREDENTIAL_LIMIT || inventory.keys.len() > CREDENTIAL_LIMIT * 8 {
        return Err(protocol().into());
    }
    let mut used: BTreeMap<String, LastUse> = BTreeMap::new();
    for key in inventory.keys {
        if !is_uuid(&key.grant_id) {
            return Err(protocol().into());
        }
        let seen = match key.last_used_at {
            None => None,
            Some(text) => Some((instant(&text).ok_or_else(protocol)?, text)),
        };
        let latest = used.entry(key.grant_id.to_ascii_lowercase()).or_default();
        if seen.as_ref().map(|s| s.0) > latest.as_ref().map(|s| s.0) {
            *latest = seen;
        }
    }
    let mut credentials: Vec<Record> = Vec::with_capacity(inventory.grants.len());
    for grant in inventory.grants {
        let id = grant.grant_id.to_ascii_lowercase();
        if !is_uuid(&id)
            || instant(&grant.valid_from).is_none()
            || instant(&grant.expires_at).is_none()
            || credentials.iter().any(|record| record.id == id)
        {
            return Err(protocol().into());
        }
        let mut categories: Vec<Category> = Vec::new();
        for item in grant.scope.disclosure_categories {
            if !categories.contains(&item.category) {
                categories.push(item.category);
            }
        }
        credentials.push(Record {
            last_used_at: used.remove(&id).flatten().map(|(_, text)| text),
            id,
            state: grant.state,
            issued_at: grant.valid_from,
            expires_at: grant.expires_at,
            categories,
            all_operations: grant.scope.all_agent_operations,
        });
    }
    Ok(Answer { credentials })
}

#[derive(Deserialize)]
struct DenyResult {
    kind: String,
    target_id: Option<String>,
    receipt: Receipt,
}
#[derive(Deserialize)]
struct Receipt {
    access_denied: bool,
    cleanup_pending: bool,
}

/// What a revoke of `grant` was answered. Once the product has been asked,
/// an answer that cannot be read as that revoke's is no proof it did not
/// happen: it is an outcome the host did not hear.
pub fn revoked(outcome: Outcome, grant: &str) -> Result<Revoked, CommandFailure> {
    let result = match outcome {
        Outcome::Refused { refusal: row, .. } => return Err(refusal(&row.code).into()),
        Outcome::Success { result, .. } => result,
    };
    let unheard = || CommandFailure::from(Refusal::OutcomeUnknown);
    let answer: DenyResult = serde_json::from_value(result).map_err(|_| unheard())?;
    let named = answer
        .target_id
        .as_deref()
        .is_some_and(|id| id.eq_ignore_ascii_case(grant));
    if answer.kind != "grant" || !named || !answer.receipt.access_denied {
        return Err(unheard());
    }
    Ok(Revoked {
        cleanup_pending: answer.receipt.cleanup_pending,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    const GRANT: &str = "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b";
    const OTHER: &str = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";

    fn grant(id: &str) -> Value {
        json!({
            "grant_id": id, "profile_id": OTHER, "client_id": OTHER, "state": "active",
            "scope": {
                "operations": ["a"], "actions": ["read"], "disclosure_count": 1,
                "all_agent_operations": true,
                "disclosure_categories": [
                    {"category": "profile_values", "destination_id": OTHER},
                    {"category": "tax_values", "destination_id": OTHER}
                ]
            },
            "valid_from": "2026-10-13T09:30:00Z", "expires_at": "2027-10-13T09:30:00Z",
            "unattended": false, "allow_os_lock": false
        })
    }

    fn key(grant: &str, used: Value) -> Value {
        json!({
            "key_id": OTHER, "grant_id": grant, "profile_id": OTHER, "state": "active",
            "valid_from": "2026-10-13T09:30:00Z", "expires_at": "2027-10-13T09:30:00Z",
            "last_used_at": used
        })
    }

    fn success(result: Value) -> Outcome {
        Outcome::Success {
            result,
            active_profile: None,
        }
    }

    fn inventory(grants: &[Value], keys: &[Value]) -> Outcome {
        success(json!({
            "profile_id": OTHER, "operation_id": "op-1",
            "inventory": {"grants": grants, "keys": keys, "requests": []}
        }))
    }

    fn failed<T: std::fmt::Debug>(result: Result<T, CommandFailure>) -> Value {
        serde_json::to_value(result.unwrap_err()).unwrap()
    }

    fn refused(code: &str) -> Outcome {
        use crate::shell::sign_in::wire::Refusal as Row;
        Outcome::Refused {
            refusal: Row {
                code: code.into(),
                retry_after_seconds: None,
            },
        }
    }

    #[test]
    fn a_listing_is_read_into_the_closed_shapes_the_window_reads() {
        let answer = list(inventory(
            &[grant(GRANT)],
            &[key(GRANT, json!("2026-10-14T10:00:00Z"))],
        ))
        .unwrap();
        assert_eq!(answer.credentials.len(), 1);
        let sent = serde_json::to_value(&answer).unwrap();
        assert_eq!(
            sent,
            json!({"credentials": [{
                "id": GRANT, "state": "active",
                "issued_at": "2026-10-13T09:30:00Z", "expires_at": "2027-10-13T09:30:00Z",
                "last_used_at": "2026-10-14T10:00:00Z",
                "categories": ["profile_values", "tax_values"],
                "all_operations": true
            }]})
        );
    }

    #[test]
    fn an_empty_inventory_is_a_listing_and_a_grant_never_used_has_no_last_use() {
        assert!(list(inventory(&[], &[])).unwrap().credentials.is_empty());
        let mut bare = grant(GRANT);
        bare["scope"] = json!({});
        let sent =
            serde_json::to_value(list(inventory(&[bare], &[key(GRANT, Value::Null)])).unwrap())
                .unwrap();
        assert_eq!(sent["credentials"][0]["last_used_at"], Value::Null);
        assert_eq!(sent["credentials"][0]["categories"], json!([]));
        assert_eq!(sent["credentials"][0]["all_operations"], false);
    }

    #[test]
    fn the_latest_use_of_a_grants_keys_is_the_one_shown_by_instant_not_by_text() {
        let keys = [
            key(GRANT, json!("2026-10-14T10:00:00Z")),
            // Later, though it sorts earlier as text.
            key(GRANT, json!("2026-10-14T11:30:00+02:00")),
            key(GRANT, json!("2026-10-14T09:59:59.999999Z")),
            key(OTHER, json!("2030-01-01T00:00:00Z")),
            key(GRANT, Value::Null),
        ];
        let sent = serde_json::to_value(list(inventory(&[grant(GRANT)], &keys)).unwrap()).unwrap();
        // 11:30 at +02:00 is 09:30Z, before 10:00Z: the first stays.
        assert_eq!(
            sent["credentials"][0]["last_used_at"],
            "2026-10-14T10:00:00Z"
        );
        let keys = [
            key(GRANT, json!("2026-10-14T10:00:00Z")),
            key(GRANT, json!("2026-10-14T13:30:00+02:00")),
        ];
        let sent = serde_json::to_value(list(inventory(&[grant(GRANT)], &keys)).unwrap()).unwrap();
        assert_eq!(
            sent["credentials"][0]["last_used_at"],
            "2026-10-14T13:30:00+02:00"
        );
    }

    #[test]
    fn instants_are_read_to_the_second_and_a_malformed_one_is_not_an_instant() {
        assert_eq!(instant("1970-01-01T00:00:00Z"), Some((0, 0)));
        assert_eq!(instant("2000-03-01T00:00:00Z"), Some((951_868_800, 0)));
        assert_eq!(
            instant("2024-02-29T12:00:00.5Z"),
            Some((1_709_208_000, 500_000_000))
        );
        assert_eq!(
            instant("2026-10-13T11:30:00+02:00"),
            instant("2026-10-13T09:30:00Z")
        );
        assert_eq!(
            instant("2026-10-13T07:00:00-02:30"),
            instant("2026-10-13T09:30:00Z")
        );
        for bad in [
            "",
            "2026-10-13",
            "2026-10-13 09:30:00Z",
            "2026-10-13T09:30:00",
            "2026-13-13T09:30:00Z",
            "2026-02-29T09:30:00Z",
            "2026-04-31T09:30:00Z",
            "2026-10-13T24:00:00Z",
            "2026-10-13T09:60:00Z",
            "2026-10-13T09:30:60Z",
            "2026-10-13T09:30:00.Z",
            "2026-10-13T09:30:00.1234567890Z",
            "2026-10-13T09:30:00+0200",
            "2026-10-13T09:30:00+24:00",
            "2026-10-13T09:30:00Zjunk",
            "２０２６-10-13T09:30:00Z",
            "2026-10-13T09:30:0xZ",
        ] {
            assert_eq!(instant(bad), None, "{bad:?}");
        }
    }

    #[test]
    fn a_value_outside_a_closed_set_or_a_malformed_row_is_a_protocol_failure() {
        let mut state = grant(GRANT);
        state["state"] = json!("expired");
        let mut category = grant(GRANT);
        category["scope"]["disclosure_categories"] = json!([{"category": "source_evidence"}]);
        let mut id = grant("not-a-uuid");
        id["grant_id"] = json!("not-a-uuid");
        let mut instant_bad = grant(GRANT);
        instant_bad["expires_at"] = json!("tomorrow");
        let mut flag = grant(GRANT);
        flag["scope"]["all_agent_operations"] = json!("yes");
        let mut no_state = grant(GRANT);
        no_state.as_object_mut().unwrap().remove("state");
        let mut no_issue = grant(GRANT);
        no_issue.as_object_mut().unwrap().remove("valid_from");
        for row in [state, category, id, instant_bad, flag, no_state, no_issue] {
            assert_eq!(
                failed(list(inventory(std::slice::from_ref(&row), &[])))["code"],
                "read_failed",
                "{row}"
            );
        }
        assert_eq!(
            failed(list(inventory(
                &[grant(GRANT), grant(&GRANT.to_uppercase())],
                &[]
            )))["code"],
            "read_failed"
        );
        assert_eq!(
            failed(list(inventory(&[grant(GRANT)], &[key("x", Value::Null)])))["code"],
            "read_failed"
        );
        assert_eq!(
            failed(list(inventory(
                &[grant(GRANT)],
                &[key(GRANT, json!("soon"))]
            )))["code"],
            "read_failed"
        );
        for result in [json!({}), json!({"inventory": {"grants": []}}), json!([])] {
            assert_eq!(failed(list(success(result)))["code"], "read_failed");
        }
    }

    #[test]
    fn a_listing_larger_than_the_bound_is_not_read() {
        let many: Vec<Value> = (0..=CREDENTIAL_LIMIT)
            .map(|n| grant(&format!("00000000-0000-4000-8000-{n:012x}")))
            .collect();
        assert_eq!(failed(list(inventory(&many, &[])))["code"], "read_failed");
        assert_eq!(
            list(inventory(&many[..CREDENTIAL_LIMIT], &[]))
                .unwrap()
                .credentials
                .len(),
            CREDENTIAL_LIMIT
        );
    }

    #[test]
    fn a_field_the_contract_does_not_name_is_not_forwarded() {
        let mut row = grant(GRANT);
        row["secret"] = json!("agent-key-must-not-travel");
        row["label"] = json!("laptop");
        let mut used = key(GRANT, Value::Null);
        used["verifier"] = json!("also-private");
        let sent = serde_json::to_string(&list(inventory(&[row], &[used])).unwrap()).unwrap();
        assert!(!sent.contains("must-not-travel") && !sent.contains("laptop"));
        assert!(!sent.contains("also-private") && !sent.contains("destination"));
    }

    #[test]
    fn grant_identifiers_are_hyphenated_uuids_and_nothing_else() {
        assert!(is_uuid(GRANT) && is_uuid(&GRANT.to_uppercase()));
        for bad in [
            "",
            "-6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5",
            "6f1b0c1e2a3d4e5f8a9b0c1d2e3f4a5b",
            "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5g",
            "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b ",
            "{6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b}",
            "--help",
        ] {
            assert!(!is_uuid(bad), "{bad:?}");
        }
    }

    #[test]
    fn a_refusal_envelope_keeps_its_meaning_and_an_unlisted_reason_is_unknown() {
        for (reason, code) in [
            ("authentication_required", "not_signed_in"),
            ("absent", "not_signed_in"),
            ("expired_idle", "not_signed_in"),
            ("PROFILE_LOGIN_REQUIRED", "not_signed_in"),
            ("profile_locked", "profile_locked"),
            ("person_act_required", "person_act_required"),
            ("human_authority_required", "person_act_required"),
            ("administration_denied", "person_act_required"),
            ("conflict", "unknown"),
            ("runtime_unavailable", "unknown"),
            ("ERROR_CALCULATIONS_REGISTRY", "unknown"),
            ("", "unknown"),
        ] {
            assert_eq!(
                failed(list(refused(reason))),
                json!({"code": code}),
                "{reason}"
            );
            assert_eq!(
                failed(revoked(refused(reason), GRANT)),
                json!({"code": code}),
                "{reason}"
            );
        }
    }

    fn denial(kind: &str, target: Option<&str>, denied: bool, pending: bool) -> Outcome {
        success(json!({
            "profile_id": OTHER, "kind": kind, "target_id": target,
            "receipt": {
                "request_id": OTHER, "profile_id": OTHER, "access_denied": denied,
                "cleanup_pending": pending, "revision": 4, "profile_lock_generation": 0
            }
        }))
    }

    #[test]
    fn a_revoke_answers_whether_the_stored_key_is_still_to_be_removed() {
        assert_eq!(
            revoked(denial("grant", Some(GRANT), true, false), GRANT).unwrap(),
            Revoked {
                cleanup_pending: false
            }
        );
        assert_eq!(
            revoked(denial("grant", Some(GRANT), true, true), GRANT).unwrap(),
            Revoked {
                cleanup_pending: true
            }
        );
        // The product prints lower case; the window may hold either.
        assert!(
            revoked(
                denial("grant", Some(GRANT), true, false),
                &GRANT.to_uppercase()
            )
            .is_ok()
        );
    }

    #[test]
    fn an_answer_that_is_not_this_revokes_is_an_outcome_unheard() {
        for answer in [
            denial("key", Some(GRANT), true, false),
            denial("all", None, true, false),
            denial("grant", Some(OTHER), true, false),
            denial("grant", None, true, false),
            denial("grant", Some(GRANT), false, false),
            success(json!({})),
            success(json!({"kind": "grant", "target_id": GRANT})),
            success(json!({
                "kind": "grant", "target_id": GRANT,
                "receipt": {"access_denied": "yes", "cleanup_pending": false}
            })),
        ] {
            assert_eq!(
                failed(revoked(answer, GRANT)),
                json!({"code": "outcome_unknown"})
            );
        }
    }
}
