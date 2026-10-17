//! Shared language comes only from the verified person's canonical profile fact.
use super::sign_in::{Presence, SignIn};
use crate::agent::person::{HeldPerson, PersonEvent};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Serialize;
use serde_json::json;
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};
use tauri::{State, ipc::Channel};

pub(crate) fn supported(language: &str) -> bool {
    matches!(language, "en" | "es" | "ca" | "hu")
}

fn failed() -> ApplicationError {
    ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
}

fn lock<T>(value: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|error| error.into_inner())
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct DesktopLanguage {
    language: String,
    persisted: bool,
    profile: Option<String>,
    revision: u64,
}

struct Current {
    value: DesktopLanguage,
    // A record change can matter even when its language is unchanged.
    record_revision: u64,
    listener: Option<Channel<DesktopLanguage>>,
}

impl Current {
    fn unobserve(&mut self, subscription: u32) {
        if self
            .listener
            .as_ref()
            .is_some_and(|channel| channel.id() == subscription)
        {
            self.listener = None;
        }
    }

    fn update(
        &mut self,
        language: String,
        persisted: bool,
        profile: Option<String>,
        record_revision: u64,
    ) -> DesktopLanguage {
        if self.value.language != language
            || self.value.persisted != persisted
            || self.value.profile != profile
            || self.record_revision != record_revision
        {
            self.value = DesktopLanguage {
                language,
                persisted,
                profile,
                revision: self.value.revision.saturating_add(1),
            };
            self.record_revision = record_revision;
            if self
                .listener
                .as_ref()
                .is_some_and(|channel| channel.send(self.value.clone()).is_err())
            {
                self.listener = None;
            }
        }
        self.value.clone()
    }
}

pub struct LanguageHost {
    sign_in: Arc<SignIn>,
    fallback: String,
    current: Mutex<Current>,
    person: Arc<Mutex<Option<HeldPerson>>>,
    operation: tokio::sync::Mutex<()>,
    worker: Mutex<Option<tokio::task::JoinHandle<()>>>,
    closed: AtomicBool,
    wake: tokio::sync::Notify,
}

impl LanguageHost {
    pub fn new(sign_in: Arc<SignIn>, fallback: String) -> Self {
        let fallback = if supported(&fallback) {
            fallback
        } else {
            "en".to_owned()
        };
        Self {
            sign_in,
            fallback: fallback.clone(),
            current: Mutex::new(Current {
                value: DesktopLanguage {
                    language: fallback,
                    persisted: false,
                    profile: None,
                    revision: 0,
                },
                record_revision: 0,
                listener: None,
            }),
            person: Arc::new(Mutex::new(None)),
            operation: tokio::sync::Mutex::new(()),
            worker: Mutex::new(None),
            closed: AtomicBool::new(false),
            wake: tokio::sync::Notify::new(),
        }
    }

    async fn refresh(&self, language: Option<String>, observe: bool) -> Result<DesktopLanguage> {
        let _operation = self.operation.lock().await;
        if self.closed.load(Ordering::Acquire) {
            return Err(failed());
        }
        let status = self.sign_in.read_status().await?;
        if status.state != Presence::Present {
            // Unknown/unavailable is not evidence that a signed-in mutation can
            // safely become a transient selection.
            if status.supported && status.state == Presence::Unknown {
                return Err(failed());
            }
            self.release_person().await?;
            let mut current = lock(&self.current);
            let selected = language.unwrap_or_else(|| {
                if current.value.profile.is_none() {
                    current.value.language.clone()
                } else {
                    self.fallback.clone()
                }
            });
            return Ok(current.update(selected, false, None, 0));
        }
        let profile = status.active_profile.ok_or_else(failed)?;
        if !status.runtime_available || status.refusal.is_some() {
            return Err(failed());
        }
        let sign_in = self.sign_in.clone();
        let bridge = self.person.clone();
        let label = profile.clone();
        let reply = super::blocking(move || {
            let profile_id = sign_in.profile_id(&label)?;
            let mut held = lock(&bridge);
            // Replacing, not clearing first: the session stays held while it is shared.
            let person = sign_in.person(&profile_id)?;
            *held = Some(person.clone());
            let request = match language {
                Some(language) => json!({"action":"language_set", "language":language}),
                None => {
                    json!({"action": if observe { "language_observe" } else { "language_read" }})
                }
            };
            let reply = lock(&person).exchange(request);
            if reply.is_err() {
                *held = None;
            }
            reply
        })
        .await?;
        let after = self.sign_in.read_status().await?;
        if after.state != Presence::Present
            || !after.runtime_ready()
            || after.active_profile.as_deref() != Some(&profile)
        {
            self.release_person().await?;
            return Err(failed());
        }
        let selected = reply["language"]
            .as_str()
            .unwrap_or(&self.fallback)
            .to_owned();
        Ok(lock(&self.current).update(
            selected,
            !reply["language"].is_null(),
            Some(profile),
            reply["record_revision"].as_u64().ok_or_else(failed)?,
        ))
    }

    async fn release_person(&self) -> Result<()> {
        let bridge = self.person.clone();
        super::blocking(move || {
            *lock(&bridge) = None;
            Ok(())
        })
        .await
    }

    fn observe(self: &Arc<Self>, updates: Channel<DesktopLanguage>) -> Result<u32> {
        let mut worker = lock(&self.worker);
        if self.closed.load(Ordering::Acquire) {
            return Err(failed());
        }
        let subscription = updates.id();
        let mut current = lock(&self.current);
        updates.send(current.value.clone()).map_err(|_| failed())?;
        current.listener = Some(updates);
        drop(current);
        if worker.is_none() {
            let owner = self.clone();
            *worker = Some(tokio::spawn(async move {
                let mut events = owner.sign_in.person_events();
                loop {
                    // Register every wake before reading, so none arriving meanwhile is lost.
                    let wake = owner.wake.notified();
                    tokio::pin!(wake);
                    wake.as_mut().enable();
                    let signed_in = owner.sign_in.observation_changed();
                    tokio::pin!(signed_in);
                    if owner.closed.load(Ordering::Acquire) {
                        break;
                    }
                    if lock(&owner.current).listener.is_some() {
                        // Failed reads publish no authoritative language. The
                        // next sign-in or language change reads again.
                        let _ = owner.refresh(None, true).await;
                    }
                    tokio::select! {
                        _ = &mut wake => {},
                        () = &mut signed_in => {},
                        () = language_pushed(&mut events) => {},
                    }
                }
            }));
        } else {
            self.wake.notify_one();
        }
        Ok(subscription)
    }

    pub async fn close(&self) -> Result<()> {
        self.closed.store(true, Ordering::Release);
        lock(&self.current).listener = None;
        self.wake.notify_one();
        let worker = lock(&self.worker).take();
        if let Some(worker) = worker {
            worker.await.map_err(|_| failed())?;
        }
        let _operation = self.operation.lock().await;
        self.release_person().await
    }
}

/// Resolves when the held person session hears that the profile language may
/// have changed, or ended; other pushes are not this host's.
async fn language_pushed(events: &mut tokio::sync::broadcast::Receiver<PersonEvent>) {
    use tokio::sync::broadcast::error::RecvError;
    loop {
        match events.recv().await {
            Ok(PersonEvent::LanguageChanged | PersonEvent::Retired) | Err(RecvError::Lagged(_)) => {
                return;
            }
            Ok(PersonEvent::AttendanceChanged) => {}
            // The window is closing; nothing more will be pushed.
            Err(RecvError::Closed) => std::future::pending::<()>().await,
        }
    }
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        desktop_language_read,
        desktop_language_set,
        desktop_language_observe,
        desktop_language_unobserve
    ]
}

#[tauri::command]
async fn desktop_language_read(host: State<'_, Arc<LanguageHost>>) -> Result<DesktopLanguage> {
    host.refresh(None, false).await
}

#[tauri::command]
async fn desktop_language_set(
    host: State<'_, Arc<LanguageHost>>,
    language: String,
) -> Result<DesktopLanguage> {
    if !supported(&language) {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Cli,
        ));
    }
    host.refresh(Some(language), false).await
}

#[tauri::command]
async fn desktop_language_observe(
    host: State<'_, Arc<LanguageHost>>,
    updates: Channel<DesktopLanguage>,
) -> Result<u32> {
    host.inner().observe(updates)
}

#[tauri::command]
fn desktop_language_unobserve(host: State<'_, Arc<LanguageHost>>, subscription: u32) {
    lock(&host.current).unobserve(subscription);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn revisions_follow_canonical_changes_and_account_switches() {
        let mut current = Current {
            value: DesktopLanguage {
                language: "en".into(),
                persisted: false,
                profile: None,
                revision: 0,
            },
            record_revision: 0,
            listener: None,
        };
        assert_eq!(
            current
                .update("es".into(), true, Some("A".into()), 3)
                .revision,
            1
        );
        assert_eq!(
            current
                .update("es".into(), true, Some("A".into()), 3)
                .revision,
            1
        );
        assert_eq!(
            current
                .update("ca".into(), true, Some("A".into()), 4)
                .revision,
            2
        );
        assert_eq!(
            current
                .update("hu".into(), true, Some("B".into()), 1)
                .revision,
            3
        );
        let signed_out = current.update("en".into(), false, None, 0);
        assert_eq!(signed_out.revision, 4);
        assert!(!signed_out.persisted);
        assert!(signed_out.profile.is_none());
    }

    #[test]
    fn only_canonical_language_codes_are_admitted() {
        for language in ["en", "es", "ca", "hu"] {
            assert!(supported(language));
        }
        for language in ["", "EN", "fr", "es-ES", " es"] {
            assert!(!supported(language));
        }
    }

    #[test]
    fn replacement_subscription_survives_old_cleanup_and_stops_on_its_own_cleanup() {
        let frames = Arc::new(Mutex::new(Vec::new()));
        let first = Channel::new(|_| Ok(()));
        let first_id = first.id();
        let capture = frames.clone();
        let replacement = Channel::new(move |body| {
            let tauri::ipc::InvokeResponseBody::Json(body) = body else {
                panic!("language is JSON")
            };
            lock(&capture).push(serde_json::from_str::<serde_json::Value>(&body).unwrap());
            Ok(())
        });
        let replacement_id = replacement.id();
        let mut current = Current {
            value: DesktopLanguage {
                language: "en".into(),
                persisted: false,
                profile: None,
                revision: 0,
            },
            record_revision: 0,
            listener: Some(first),
        };
        current.listener = Some(replacement);
        current.unobserve(first_id);
        current.update("es".into(), true, Some("A".into()), 1);
        assert_eq!(lock(&frames).len(), 1);
        assert_eq!(lock(&frames)[0]["language"], "es");
        current.unobserve(replacement_id);
        current.update("hu".into(), true, Some("A".into()), 2);
        assert_eq!(lock(&frames).len(), 1);
        assert!(current.listener.is_none());
    }
}
