//! A failed presentation of this window's own stored person proof. Runtime
//! presence remains independent; no receipt or profile is changed here.
use super::{failure, watch::Observed, wire};
use cadrumo_application::{
    error::application::{ApplicationError, ChildRefusal, ErrorCode},
    runtime_client::{refusal::Refusal, stored_proof::ResumeRefusal},
};

/// A proof may itself cue a fresh observation. Recheck the admitted session
/// against that observation before publishing it; a cue during that check
/// still invalidates the candidate.
pub(super) fn observation_after_proof(
    before: &Observed,
    mut current: impl FnMut() -> cadrumo_application::error::application::Result<Observed>,
    verify: impl FnOnce() -> cadrumo_application::error::application::Result<()>,
) -> cadrumo_application::error::application::Result<Observed> {
    let latest = current()?;
    if latest == *before {
        return Ok(latest);
    }
    let changed =
        || failure(ErrorCode::SessionUnavailable).with_reason("person_observation_changed");
    if latest.profile_id != before.profile_id
        || latest.status.state != wire::Presence::Present
        || !latest.status.runtime_ready()
    {
        return Err(changed());
    }
    verify()?;
    if current()? != latest {
        return Err(changed());
    }
    Ok(latest)
}

#[derive(Clone)]
pub(super) struct Failed {
    pub error: Box<ApplicationError>,
    pub refusal: wire::Refusal,
    terminal: bool,
}

impl Failed {
    pub fn resume(refusal: ResumeRefusal) -> Self {
        match refusal {
            ResumeRefusal::Runtime(refusal) => Self::runtime(refusal),
            ResumeRefusal::Receipt(reason) => {
                // This is the producer's closed persisted-session vocabulary,
                // not merely an identifier-shape test. Unknown text stays local.
                let admitted = match reason.as_str() {
                    "absent"
                    | "malformed"
                    | "schema_version_mismatch"
                    | "expired_idle"
                    | "expired_absolute"
                    | "keychain_entry_missing"
                    | "keyring_unavailable"
                    | "custody_changed"
                    | "tampered" => Some(reason.as_str()),
                    _ => None,
                };
                let code = admitted.unwrap_or("receipt_refused");
                let public = match code {
                    "absent" => "RECEIPT_ABSENT",
                    "expired_idle" | "expired_absolute" => "RECEIPT_EXPIRED",
                    "keychain_entry_missing" => "SESSION_NOT_PERSISTED",
                    "keyring_unavailable" => "KEYRING_UNAVAILABLE",
                    "custody_changed" => "CUSTODY_CHANGED",
                    other => other,
                };
                Self {
                    error: Box::new(
                        failure(ErrorCode::SessionUnavailable)
                            .with_reason("person_resume_refused")
                            .caused_by(ChildRefusal {
                                code: Some("receipt_refused".into()),
                                reason: admitted.map(str::to_owned),
                                ..ChildRefusal::default()
                            }),
                    ),
                    refusal: wire::Refusal {
                        code: public.to_owned(),
                        retry_after_seconds: None,
                    },
                    terminal: true,
                }
            }
        }
    }

    pub fn runtime(refusal: Refusal) -> Self {
        let terminal = !matches!(
            &refusal,
            Refusal::Unavailable
                | Refusal::EndpointNotReady
                | Refusal::ConnectionClosed
                | Refusal::Timeout
                | Refusal::Io(_)
        );
        let original_code = refusal.code().to_owned();
        let public = wire::sign_in_refusal(
            refusal.code(),
            refusal.sign_in_reason(),
            refusal.remaining_seconds(),
        )
        .unwrap_or_else(|_| wire::Refusal {
            code: "person_resume_unavailable".into(),
            retry_after_seconds: None,
        });
        let diagnostic_code = if public.code == "person_resume_unavailable" {
            public.code.clone()
        } else {
            original_code
        };
        // Preserve only the runtime's shape-admitted code, never its document, receipt,
        // credential-store payload or exception string in diagnostics.
        let error = match refusal {
            Refusal::Io(error) => failure(ErrorCode::SessionUnavailable)
                .with_reason("person_resume_unavailable")
                .caused_by(error),
            _ => failure(ErrorCode::SessionUnavailable)
                .with_reason("person_resume_unavailable")
                .caused_by(ChildRefusal {
                    code: Some(diagnostic_code),
                    ..ChildRefusal::default()
                }),
        };
        Self {
            error: Box::new(error),
            refusal: public,
            terminal,
        }
    }

    pub fn unavailable(error: ApplicationError) -> Self {
        Self {
            error: Box::new(error),
            refusal: wire::Refusal {
                code: "person_resume_unavailable".into(),
                retry_after_seconds: None,
            },
            terminal: false,
        }
    }
}

#[derive(Default)]
pub(super) struct Restoration {
    failed: Option<(Observed, Failed)>,
}
impl Restoration {
    pub fn current(&mut self, observed: &Observed) -> Option<Failed> {
        if self.failed.as_ref().is_some_and(|(previous, _)| {
            previous.sequence != observed.sequence
                || previous.profile_id != observed.profile_id
                || previous.status != observed.status
        }) {
            self.failed = None;
        }
        self.failed.as_ref().map(|(_, failure)| failure.clone())
    }
    pub fn refusal(&mut self, observed: &Observed) -> Option<Failed> {
        self.current(observed).filter(|failure| failure.terminal)
    }
    /// Run a serialized restoration once for a known receipt refusal. Only
    /// transport loss permits another attempt against the unchanged status.
    pub fn attempt<T>(
        &mut self,
        observed: &Observed,
        restore: impl FnOnce() -> std::result::Result<T, Failed>,
    ) -> cadrumo_application::error::application::Result<T> {
        if let Some(refused) = self.refusal(observed) {
            return Err(*refused.error);
        }
        restore().map_err(|refused| {
            let error = (*refused.error).clone();
            self.failed(observed, refused);
            error
        })
    }
    pub fn failed(&mut self, observed: &Observed, failure: Failed) {
        self.failed = Some((observed.clone(), failure));
    }
    pub fn restored(&mut self) {
        self.failed = None;
    }
}

#[cfg(test)]
mod tests {
    use super::super::wire::{Presence, SignInStatus};
    use super::*;
    fn observed() -> Observed {
        Observed {
            sequence: 1,
            status: SignInStatus {
                supported: true,
                state: Presence::Present,
                active_profile: Some("Selected profile".into()),
                runtime_available: true,
                refusal: None,
                reconnecting: None,
            },
            profile_id: Some("exact-profile".into()),
            profiles: None,
        }
    }

    #[test]
    fn a_proofs_own_cue_rechecks_the_exact_session_before_accepting_fresh_values() {
        let before = observed();
        let mut after = before.clone();
        after.sequence += 1;
        let mut checked = 0;
        let admitted = observation_after_proof(
            &before,
            || Ok(after.clone()),
            || {
                checked += 1;
                Ok(())
            },
        )
        .unwrap();
        assert_eq!(admitted, after);
        assert_eq!(checked, 1);
    }

    #[test]
    fn a_second_cue_during_session_verification_still_rejects_the_candidate() {
        let before = observed();
        let mut after = before.clone();
        after.sequence += 1;
        let mut later = after.clone();
        later.sequence += 1;
        let mut observations = [after, later].into_iter();
        let mut checked = 0;
        let refused = observation_after_proof(
            &before,
            || Ok(observations.next().unwrap()),
            || {
                checked += 1;
                Ok(())
            },
        )
        .unwrap_err();
        assert_eq!(
            refused.reason.as_deref(),
            Some("person_observation_changed")
        );
        assert_eq!(checked, 1);
    }

    #[test]
    fn a_fresh_observation_never_replaces_the_admitted_sessions_authority() {
        let before = observed();
        let mut after = before.clone();
        after.sequence += 1;
        let refused = observation_after_proof(
            &before,
            || Ok(after.clone()),
            || Err(failure(ErrorCode::ReadFailed).with_reason("person_reply_identity_mismatch")),
        )
        .unwrap_err();
        assert_eq!(
            refused.reason.as_deref(),
            Some("person_reply_identity_mismatch")
        );
    }

    #[test]
    fn another_profile_sign_out_or_unavailability_cannot_revalidate_the_candidate() {
        let before = observed();
        for invalidation in 0..3 {
            let mut after = before.clone();
            after.sequence += 1;
            match invalidation {
                0 => after.profile_id = Some("other-profile".into()),
                1 => after.status.state = wire::Presence::Absent,
                _ => after.status.runtime_available = false,
            }
            let refused = observation_after_proof(
                &before,
                || Ok(after.clone()),
                || panic!("an invalidated observation cannot revalidate a session"),
            )
            .unwrap_err();
            assert_eq!(
                refused.reason.as_deref(),
                Some("person_observation_changed")
            );
        }
    }

    #[test]
    fn an_unchanged_observation_needs_no_extra_session_exchange() {
        let before = observed();
        assert_eq!(
            observation_after_proof(
                &before,
                || Ok(before.clone()),
                || { panic!("unchanged observation already brackets this proof") }
            )
            .unwrap(),
            before
        );
    }

    #[test]
    fn revalidation_requires_the_admitted_persons_exact_authenticated_status() {
        use cadrumo_application::runtime_client::{
            connection::SessionExchange, events::Pushed, session::Admitted,
        };
        use serde_json::{Map, Value, json};
        use std::{
            sync::{Arc, Mutex, mpsc},
            time::Instant,
        };

        struct Status {
            reply: Value,
            subscribers: Mutex<Vec<mpsc::Sender<Pushed>>>,
        }
        impl SessionExchange for Status {
            fn exchange(&self, request: &Value, _: Instant) -> Result<Map<String, Value>, Refusal> {
                assert_eq!(request["action"], "session_status");
                let mut reply = self.reply.clone();
                reply["request_id"] = request["request_id"].clone();
                Ok(reply.as_object().unwrap().clone())
            }
            fn exchange_with_secret(
                &self,
                _: &Value,
                _: &[u8],
                _: Instant,
            ) -> Result<Map<String, Value>, Refusal> {
                panic!("status revalidation presents no new proof")
            }
            fn exchange_streamed(
                &self,
                _: &Value,
                _: &[u8],
                _: Instant,
            ) -> Result<Map<String, Value>, Refusal> {
                panic!("status revalidation sends no payload")
            }
            fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
                let (sender, receiver) = mpsc::channel();
                self.subscribers.lock().unwrap().push(sender);
                receiver
            }
            fn close(&self) {}
        }

        let profile = "11111111-1111-4111-8111-111111111111";
        let session = "22222222-2222-4222-8222-222222222222";
        let boot = "33333333-3333-4333-8333-333333333333";
        let connection = "44444444-4444-4444-8444-444444444444";
        let other = "55555555-5555-4555-8555-555555555555";
        let valid = json!({
            "kind": "profile_status", "runtime_boot_id": boot, "connection_id": connection,
            "status": {"profile_id": profile, "session_id": session, "connected": true,
                "credential_authenticated": true, "profile_bound": true,
                "session_expires_at": "2026-11-03T23:59:00Z", "denial": null}
        });
        for invalidation in 0..10 {
            let mut reply = valid.clone();
            match invalidation {
                0 => {}
                1 => reply["runtime_boot_id"] = json!(other),
                2 => reply["connection_id"] = json!(other),
                3 => reply["status"]["profile_id"] = json!(other),
                4 => reply["status"]["session_id"] = json!(other),
                5 => reply["status"]["connected"] = json!(false),
                6 => reply["status"]["credential_authenticated"] = json!(false),
                7 => reply["status"]["profile_bound"] = json!(false),
                8 => reply["status"]["session_expires_at"] = Value::Null,
                _ => reply["status"]["denial"] = json!({"code": "custody_recovering"}),
            }
            let exchange = Arc::new(Status {
                reply,
                subscribers: Mutex::new(Vec::new()),
            });
            let pushed = exchange.subscribe_scoped();
            let mut person = crate::agent::person::Person::native(
                exchange,
                pushed,
                Admitted {
                    profile_id: profile.into(),
                    session_id: session.into(),
                    runtime_boot_id: boot.into(),
                    connection_id: connection.into(),
                    expires_at: None,
                    session_persisted: None,
                    signed_out_profile_ids: Vec::new(),
                },
                None,
                crate::agent::recovery::rebind::Recovery {
                    custody: crate::agent::recovery::Custody::default(),
                    proof: Arc::new(crate::agent::recovery::rebind::StoredReceipt {
                        storage_root: "unused-status-only".into(),
                    }),
                },
            )
            .unwrap();
            let mut before = observed();
            before.profile_id = Some(profile.into());
            let mut after = before.clone();
            after.sequence += 1;
            let result = observation_after_proof(
                &before,
                || Ok(after.clone()),
                || person.exchange(json!({"action": "status"})).map(|_| ()),
            );
            assert_eq!(
                result.is_ok(),
                invalidation == 0,
                "status case {invalidation}"
            );
        }
    }

    #[test]
    fn known_receipt_refusal_is_reused_until_status_or_password_changes() {
        let mut restoration = Restoration::default();
        let observed = observed();
        restoration.failed(
            &observed,
            Failed::resume(ResumeRefusal::Receipt("expired_idle".into())),
        );
        assert_eq!(
            restoration.refusal(&observed).unwrap().refusal.code,
            "RECEIPT_EXPIRED"
        );
        assert_eq!(
            restoration.refusal(&observed).unwrap().refusal.code,
            "RECEIPT_EXPIRED"
        );
        restoration.restored();
        assert!(restoration.current(&observed).is_none());
        restoration.failed(
            &observed,
            Failed::resume(ResumeRefusal::Receipt("tampered".into())),
        );
        let mut changed = observed.clone();
        changed.status.state = Presence::Absent;
        assert!(restoration.refusal(&changed).is_none());
    }
    #[test]
    fn a_failed_receipt_is_not_presented_again_before_fresh_proof() {
        let mut restoration = Restoration::default();
        let observed = observed();
        let mut attempts = 0;
        for _ in 0..2 {
            let result: cadrumo_application::error::application::Result<()> =
                restoration.attempt(&observed, || {
                    attempts += 1;
                    Err(Failed::resume(ResumeRefusal::Receipt("tampered".into())))
                });
            assert!(result.is_err());
        }
        assert_eq!(attempts, 1);
        restoration.restored();
        assert_eq!(
            restoration
                .attempt(&observed, || {
                    attempts += 1;
                    Ok("restored")
                })
                .unwrap(),
            "restored"
        );
        assert_eq!(attempts, 2);
    }
    #[test]
    fn a_lapsed_sign_in_is_never_presented_again_whichever_way_it_is_refused() {
        // After an idle lapse the stored sign-in is refused, by the receipt or
        // by the runtime's admission. Either way the person signs in again:
        // the window neither retries nor holds a session in the meantime.
        for refused in [
            Failed::resume(ResumeRefusal::Receipt("expired_idle".into())),
            Failed::runtime(Refusal::Denied {
                code: "session_expired".into(),
                sign_in: None,
                holder_operation_id: None,
                recovery_remaining_seconds: None,
            }),
        ] {
            let mut restoration = Restoration::default();
            let observed = observed();
            let mut attempts = 0;
            for _ in 0..3 {
                let result: cadrumo_application::error::application::Result<()> = restoration
                    .attempt(&observed, || {
                        attempts += 1;
                        Err(refused.clone())
                    });
                assert!(result.is_err());
            }
            assert_eq!(attempts, 1);
            assert!(restoration.refusal(&observed).is_some());
        }
    }
    #[test]
    fn a_transient_failure_permits_a_later_successful_restoration() {
        let mut restoration = Restoration::default();
        let observed = observed();
        let first: cadrumo_application::error::application::Result<()> = restoration
            .attempt(&observed, || {
                Err(Failed::runtime(Refusal::ConnectionClosed))
            });
        assert!(first.is_err());
        assert_eq!(
            restoration.attempt(&observed, || Ok("session")).unwrap(),
            "session"
        );
        restoration.restored();
        assert!(restoration.current(&observed).is_none());
    }
    #[test]
    fn receipt_failure_never_changes_runtime_presence_or_active_profile() {
        let observed = observed();
        let mut restoration = Restoration::default();
        restoration.failed(
            &observed,
            Failed::resume(ResumeRefusal::Receipt("absent".into())),
        );
        assert_eq!(observed.status.state, Presence::Present);
        assert_eq!(
            observed.status.active_profile.as_deref(),
            Some("Selected profile")
        );
        assert_eq!(
            restoration.current(&observed).unwrap().refusal.code,
            "RECEIPT_ABSENT"
        );
    }
    #[test]
    fn connection_loss_is_retryable_without_treating_the_receipt_as_invalid() {
        for refusal in [
            Refusal::ConnectionClosed,
            Refusal::Timeout,
            Refusal::Unavailable,
            Refusal::EndpointNotReady,
            Refusal::Io(std::io::ErrorKind::BrokenPipe.into()),
        ] {
            let mut restoration = Restoration::default();
            let observed = observed();
            restoration.failed(&observed, Failed::runtime(refusal));
            assert!(restoration.current(&observed).is_some());
            assert!(restoration.refusal(&observed).is_none());
        }
    }
    #[test]
    fn a_new_observation_generation_retries_receipt_proof_even_with_identical_public_values() {
        let mut restoration = Restoration::default();
        let observed = observed();
        let first: cadrumo_application::error::application::Result<()> = restoration
            .attempt(&observed, || {
                Err(Failed::resume(ResumeRefusal::Receipt("tampered".into())))
            });
        assert!(first.is_err());
        let mut repaired = observed.clone();
        repaired.sequence += 1;
        assert_eq!(observed.status, repaired.status);
        assert_eq!(observed.profile_id, repaired.profile_id);
        assert_eq!(
            restoration
                .attempt(&repaired, || Ok("repaired proof"))
                .unwrap(),
            "repaired proof"
        );
        assert!(restoration.current(&repaired).is_none());
    }

    #[test]
    fn failure_for_another_profile_cannot_block_new_proof() {
        let mut restoration = Restoration::default();
        let observed = observed();
        restoration.failed(
            &observed,
            Failed::resume(ResumeRefusal::Receipt("tampered".into())),
        );
        let mut changed = observed.clone();
        changed.profile_id = Some("other-profile".into());
        assert!(restoration.refusal(&changed).is_none());
    }
    #[test]
    fn diagnostics_keep_closed_receipt_and_runtime_codes_without_payloads() {
        let receipt = Failed::resume(ResumeRefusal::Receipt("tampered".into()));
        let serialized = serde_json::to_value(receipt.error).unwrap();
        assert!(serialized.to_string().contains("receipt_refused"));
        assert!(serialized.to_string().contains("tampered"));
        assert!(!serialized.to_string().contains("opaque"));
        let runtime = Failed::runtime(Refusal::denied("authentication_required"));
        let serialized = serde_json::to_value(runtime.error).unwrap();
        assert!(serialized.to_string().contains("authentication_required"));
        for private in ["private/path or payload", "private_canary_identifier"] {
            let failure = Failed::resume(ResumeRefusal::Receipt(private.into()));
            assert_eq!(failure.refusal.code, "receipt_refused");
            assert!(
                !serde_json::to_value(failure.error)
                    .unwrap()
                    .to_string()
                    .contains("private")
            );
        }
    }
}
