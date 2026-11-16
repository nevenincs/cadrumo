//! The keys the held profile issued to agents, read as the person over the
//! profile relay: one registered inventory read, whose settlement must report
//! no effect and whose every grant, key and request must be the held
//! profile's. The runtime's refusal reason is kept, so the caller can tell a
//! person-only act from a lost sign-in.
use super::{
    Failure, PROFILE_CHANGE_ADMISSION_LIMIT, PROFILE_READ_LIMIT, ProfileHost, Result, protocol,
};
use crate::agent::person::{HeldPerson, request_id};
use crate::shell::relay::{self, Relayed};
use serde_json::{Value, json};

/// The registered read the inventory comes from.
const INVENTORY_DEFINITION: &str = "user-profile.automation-inventory";

/// The inventory request: the held profile and a fresh request identity,
/// with no disclosure page.
fn inventory_request(profile: &str, request: &str) -> Value {
    json!({"profile_id": profile, "request_id": request})
}

/// Whether a settled read answered with nothing changed. A refusal keeps the
/// runtime's closed reason; a success or a stop that reports an effect is not
/// a read the host can pass on.
fn settled_read(p: &Value) -> Result<()> {
    if p["effect"] != "none" {
        return Err(protocol());
    }
    if p["terminal_condition"] == "succeeded" {
        return Ok(());
    }
    let mut refused = Failure::new("refused");
    refused.reason = p["refusal_ref"]
        .as_str()
        .or_else(|| p["failure_error_code"].as_str())
        .map(str::to_owned);
    Err(refused)
}

/// Whether `rows[*].<path>` names exactly `profile`, for every row.
fn rows_name(projection: &Value, rows: &str, path: &[&str], profile: &str) -> bool {
    projection[rows].as_array().is_some_and(|found| {
        found.iter().all(|row| {
            path.iter()
                .fold(row, |value, field| &value[*field])
                .as_str()
                == Some(profile)
        })
    })
}

/// The projection passed on only when every grant, key and request in it is
/// the held profile's.
fn admit_inventory(projection: Value, profile: &str) -> Result<Value> {
    if rows_name(&projection, "grants", &["profile_id"], profile)
        && rows_name(&projection, "keys", &["profile_id"], profile)
        && rows_name(&projection, "requests", &["receipt", "profile_id"], profile)
    {
        Ok(projection)
    } else {
        Err(protocol())
    }
}

impl ProfileHost {
    /// The held profile's agent keys, grants and pending requests, as the
    /// product projects them. Waiting behind another profile operation is
    /// bounded like an edit's admission: queueing is not submission, so a
    /// read that cannot start promptly answers unavailable.
    pub(crate) async fn automation_inventory(&self) -> Result<Value> {
        tokio::time::timeout(PROFILE_READ_LIMIT, async {
            let (_serial, person) = tokio::time::timeout(PROFILE_CHANGE_ADMISSION_LIMIT, async {
                let serial = self.serial().await;
                let person = self.person(None).await?;
                Ok::<_, Failure>((serial, person))
            })
            .await
            .map_err(|_| protocol())??;
            let profile = Self::profile_of(&person).await?;
            let projection = self
                .read_keeping_reason(
                    &person,
                    &profile,
                    inventory_request(&profile, &request_id()?),
                )
                .await?;
            self.still_held(&person, &profile).await?;
            admit_inventory(projection, &profile)
        })
        .await
        .unwrap_or_else(|_| Err(protocol()))
    }
    /// Submits the inventory read and follows it to its terminal receipt,
    /// keeping the runtime's refusal reason at submission and at settlement.
    async fn read_keeping_reason(
        &self,
        person: &HeldPerson,
        profile: &str,
        payload: Value,
    ) -> Result<Value> {
        let mut events = self.sign_in().person_events();
        let subject = relay::subject(profile);
        let operation =
            relay::submit(person, INVENTORY_DEFINITION, &subject, payload, false).await?;
        let relayed = Relayed {
            person,
            operation,
            definition: INVENTORY_DEFINITION,
            subject,
        };
        tokio::time::timeout(relay::SETTLE_LIMIT, async {
            let p = relay::follow(&mut events, &relayed, |_| false).await?;
            settled_read(&p)?;
            let document = relay::result(&relayed).await.map_err(|_| protocol())?;
            Ok(document["projection"].clone())
        })
        .await
        .unwrap_or_else(|_| Err(protocol()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROFILE: &str = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    const OTHER: &str = "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b";

    fn projection(grant: &str, key: &str, request: &str) -> Value {
        json!({
            "grants": [{"grant_id": OTHER, "profile_id": grant, "state": "active"}],
            "keys": [{"key_id": OTHER, "grant_id": OTHER, "profile_id": key}],
            "requests": [{"receipt": {"request_id": OTHER, "profile_id": request}}]
        })
    }

    #[test]
    fn an_inventory_of_the_held_profile_passes_unchanged() {
        let held = projection(PROFILE, PROFILE, PROFILE);
        assert_eq!(admit_inventory(held.clone(), PROFILE).unwrap(), held);
        let empty = json!({"grants": [], "keys": [], "requests": []});
        assert_eq!(admit_inventory(empty.clone(), PROFILE).unwrap(), empty);
    }

    /// The listing the window read before, now as the product's inventory
    /// projection for the held profile: one grant releasing tax values, with
    /// one key never used.
    #[test]
    fn the_held_profiles_projection_reaches_the_window_as_the_same_answer() {
        let served = json!({
            "grants": [{
                "grant_id": OTHER, "profile_id": PROFILE, "client_id": PROFILE,
                "state": "active",
                "scope": {
                    "operations": [], "actions": ["read"], "disclosure_count": 0,
                    "disclosure_summary": {}, "disclosure_digest": "0".repeat(64),
                    "periods": null, "allow_period_independent": false,
                    "allow_delegation": false,
                    "disclosure_categories": [{"destination_id": PROFILE, "category": "tax_values"}]
                },
                "valid_from": "2026-10-13T09:30:00Z", "expires_at": "2027-10-13T09:30:00Z",
                "unattended": false, "allow_os_lock": false, "label": "laptop", "use": "agent"
            }],
            "keys": [{
                "key_id": PROFILE, "grant_id": OTHER, "profile_id": PROFILE, "state": "active",
                "valid_from": "2026-10-13T09:30:00Z", "expires_at": "2027-10-13T09:30:00Z",
                "last_used_at": null
            }],
            "requests": [],
            "disclosure_page": null
        });
        let admitted = admit_inventory(served, PROFILE).unwrap();
        let answer = crate::shell::agent_access::wire::inventory(admitted).unwrap();
        assert_eq!(
            serde_json::to_value(answer).unwrap(),
            json!({"credentials": [{
                "id": OTHER, "state": "active",
                "issued_at": "2026-10-13T09:30:00Z", "expires_at": "2027-10-13T09:30:00Z",
                "last_used_at": null, "categories": ["tax_values"], "all_operations": false
            }]})
        );
    }

    #[test]
    fn an_inventory_naming_another_profile_anywhere_is_refused() {
        for foreign in [
            projection(OTHER, PROFILE, PROFILE),
            projection(PROFILE, OTHER, PROFILE),
            projection(PROFILE, PROFILE, OTHER),
            projection(&PROFILE.to_uppercase(), PROFILE, PROFILE),
        ] {
            assert_eq!(
                admit_inventory(foreign.clone(), PROFILE).unwrap_err().code,
                "unavailable",
                "{foreign}"
            );
        }
        let mut unnamed = projection(PROFILE, PROFILE, PROFILE);
        unnamed["keys"][0]
            .as_object_mut()
            .unwrap()
            .remove("profile_id");
        let mut missing = projection(PROFILE, PROFILE, PROFILE);
        missing.as_object_mut().unwrap().remove("requests");
        for malformed in [unnamed, missing, json!([]), Value::Null] {
            assert_eq!(
                admit_inventory(malformed.clone(), PROFILE)
                    .unwrap_err()
                    .code,
                "unavailable",
                "{malformed}"
            );
        }
    }

    #[test]
    fn a_settled_read_passes_only_without_effect_and_a_refusal_keeps_its_reason() {
        let settled = |condition: &str, effect: &str, refusal: Value, failure: Value| {
            json!({"lifecycle": "terminal", "terminal_condition": condition, "effect": effect,
                "refusal_ref": refusal, "failure_error_code": failure})
        };
        assert!(settled_read(&settled("succeeded", "none", Value::Null, Value::Null)).is_ok());
        for changed in ["updated", "partial", "unknown"] {
            let failure =
                settled_read(&settled("succeeded", changed, Value::Null, Value::Null)).unwrap_err();
            assert_eq!((failure.code, failure.reason), ("unavailable", None));
        }
        let refused = settled_read(&settled(
            "refused",
            "none",
            json!("human_authority_required"),
            Value::Null,
        ))
        .unwrap_err();
        assert_eq!(refused.code, "refused");
        assert_eq!(refused.reason.as_deref(), Some("human_authority_required"));
        let failed = settled_read(&settled(
            "failed",
            "none",
            Value::Null,
            json!("FAIL_PROFILE_LOCKED"),
        ))
        .unwrap_err();
        assert_eq!(failed.reason.as_deref(), Some("FAIL_PROFILE_LOCKED"));
        let stopped_with_effect = settled_read(&settled(
            "refused",
            "unknown",
            json!("profile_locked"),
            Value::Null,
        ))
        .unwrap_err();
        assert_eq!(stopped_with_effect.code, "unavailable");
    }

    /// The product's inventory request requires exactly a profile and a
    /// request identity; its review digest and disclosure paging are
    /// optional, and a listing names none of them.
    #[test]
    fn the_request_names_the_held_profile_and_a_fresh_request_and_nothing_else() {
        let request = inventory_request(PROFILE, &request_id().unwrap());
        let mut named: Vec<&String> = request.as_object().unwrap().keys().collect();
        named.sort();
        assert_eq!(named, ["profile_id", "request_id"]);
        assert_eq!(request["profile_id"], PROFILE);
        let identity = request["request_id"].as_str().unwrap();
        assert!(crate::shell::agent_access::wire::is_uuid(identity));
        // A version 4 identity, as the product's UUID field reads it.
        assert_eq!(identity.as_bytes()[14], b'4');
    }
}
