//! A failed presentation of this window's own stored person proof. Runtime
//! presence remains independent; no receipt or profile is changed here.
use super::{failure, watch::Observed, wire};
use cadrumo_application::{
    error::application::{ApplicationError, ChildRefusal, ErrorCode},
    runtime_client::{refusal::Refusal, stored_proof::ResumeRefusal},
};

#[derive(Clone)]
pub(super) struct Failed {
    pub error: ApplicationError,
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
                    error: failure(ErrorCode::SessionUnavailable)
                        .with_reason("person_resume_refused")
                        .caused_by(ChildRefusal {
                            code: Some("receipt_refused".into()),
                            reason: admitted.map(str::to_owned),
                            ..ChildRefusal::default()
                        }),
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
            error,
            refusal: public,
            terminal,
        }
    }

    pub fn unavailable(error: ApplicationError) -> Self {
        Self {
            error,
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
            return Err(refused.error);
        }
        restore().map_err(|refused| {
            let error = refused.error.clone();
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
