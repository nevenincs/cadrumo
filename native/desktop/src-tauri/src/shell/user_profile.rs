//! Profile presentation over the held person's registered-operation relay.
//! No repository, credential or profile policy lives in the desktop host.
pub(crate) mod censo;
mod wire;
use super::sign_in::{Presence, SignIn};
use crate::agent::person::{HeldPerson, PersonEvent};
use cadrumo_application::error::application::ApplicationError;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::Duration,
};
use tauri::{State, ipc::Channel};
use wire::{Overview, Pages};

// Bound the complete read, including admission, queueing and every page.
// A per-operation timeout alone leaves admission and queue waits unbounded.
const PROFILE_READ_LIMIT: Duration = Duration::from_secs(140);

#[derive(Debug, Serialize)]
pub struct Failure {
    code: &'static str,
    operation_id: Option<String>,
}
impl Failure {
    fn new(code: &'static str) -> Self {
        Self {
            code,
            operation_id: None,
        }
    }
}
impl From<ApplicationError> for Failure {
    fn from(_: ApplicationError) -> Self {
        Self::new("unavailable")
    }
}
type Result<T> = std::result::Result<T, Failure>;
fn lock<T>(value: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|e| e.into_inner())
}
fn protocol() -> Failure {
    Failure::new("unavailable")
}

pub struct ProfileHost {
    sign_in: Arc<SignIn>,
    operation: tokio::sync::Mutex<()>,
    observer: Mutex<Option<(u32, tauri::async_runtime::JoinHandle<()>)>>,
    censo_observer: Mutex<Option<(u32, tauri::async_runtime::JoinHandle<()>)>>,
    held: Mutex<Option<HeldPerson>>,
    closed: AtomicBool,
    censo: tokio::sync::Mutex<Option<censo::Session>>,
}
impl ProfileHost {
    pub fn new(sign_in: Arc<SignIn>) -> Self {
        Self {
            sign_in,
            operation: tokio::sync::Mutex::new(()),
            observer: Mutex::new(None),
            censo_observer: Mutex::new(None),
            held: Mutex::new(None),
            closed: AtomicBool::new(false),
            censo: tokio::sync::Mutex::new(None),
        }
    }
    pub fn close(&self) {
        self.closed.store(true, Ordering::Release);
        if let Some((_, task)) = lock(&self.observer).take() {
            task.abort();
        }
        if let Some((_, task)) = lock(&self.censo_observer).take() {
            task.abort();
        }
        *lock(&self.held) = None;
    }
    async fn person(&self, expected: Option<&str>) -> Result<HeldPerson> {
        if self.closed.load(Ordering::Acquire) {
            return Err(protocol());
        }
        let status = self.sign_in.read_status().await?;
        if status.state != Presence::Present || !status.runtime_ready() {
            *lock(&self.held) = None;
            return Err(Failure::new("not_signed_in"));
        }
        let label = status.active_profile.ok_or_else(protocol)?;
        let owner = self.sign_in.clone();
        let person = super::blocking(move || owner.person(&owner.profile_id(&label)?)).await?;
        if let Some(expected) = expected
            && Self::identity(&person).await?["profile_id"] != expected
        {
            return Err(Failure::new("not_signed_in"));
        }
        let mut held = lock(&self.held);
        if self.closed.load(Ordering::Acquire) {
            return Err(protocol());
        }
        *held = Some(person.clone());
        Ok(person)
    }
    async fn identity(person: &HeldPerson) -> Result<Value> {
        let person = person.clone();
        // The same mutex is held by blocking IPC exchanges. Never wait on it
        // on a Tokio executor thread: that can also starve the read's timer.
        Ok(super::blocking(move || Ok(lock(&person).identity.clone())).await?)
    }
    async fn call(person: &HeldPerson, request: Value) -> Result<Value> {
        let person = person.clone();
        Ok(super::blocking(move || lock(&person).exchange(request)).await?)
    }
    async fn run(
        &self,
        person: &HeldPerson,
        definition: &str,
        payload: Value,
        mutation: bool,
    ) -> Result<Value> {
        let mut events = self.sign_in.person_events();
        let profile = Self::identity(person).await?["profile_id"]
            .as_str()
            .ok_or_else(protocol)?
            .to_owned();
        let subject = format!("profile:{profile}");
        let submitted = Self::call(
            person,
            json!({"action":"operation_submit", "definition_id":definition,
            "subject_ref":subject, "payload":payload}),
        )
        .await
        .map_err(|_| Failure::new(if mutation { "unknown" } else { "unavailable" }))?;
        if submitted["kind"] == "operation_refused" {
            return Err(Failure::new("refused"));
        }
        let operation = submitted["operation_id"]
            .as_str()
            .filter(|id| super::setup::wire::is_hex64(id))
            .ok_or_else(|| Failure::new(if mutation { "unknown" } else { "unavailable" }))?
            .to_owned();
        let result = tokio::time::timeout(Duration::from_secs(90), async {
            loop {
                let reply = Self::call(person, json!({"action":"operation_observe", "operation_id":operation, "after_cursor":0})).await?;
                let p = &reply["observation"]["projection"];
                if reply["kind"] != "operation_observed" || p["operation_id"] != operation || p["definition_id"] != definition || p["subject_ref"] != subject {
                    return Err(protocol());
                }
                if p["lifecycle"] == "terminal" {
                    if p["terminal_condition"] != "succeeded" {
                        return Err(Failure::new(wire::mutation_failure(p)));
                    }
                    let result = Self::call(person, json!({"action":"operation_result", "operation_id":operation})).await
                        .map_err(|_| Failure::new(if mutation {"saved_unread"} else {"unavailable"}))?;
                    if result["kind"] != "operation_result" || result["operation_id"] != operation || result["definition_id"] != definition {
                        return Err(Failure::new(if mutation {"saved_unread"} else {"unavailable"}));
                    }
                    return Ok(result["document"]["projection"].clone());
                }
                // The observe request installs the watch before answering. Subscribe
                // before that request so a fast settlement cannot lose its wake.
                loop {
                    match events.recv().await {
                        Ok(PersonEvent::OperationChanged) | Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => break,
                        Ok(PersonEvent::Retired) | Err(tokio::sync::broadcast::error::RecvError::Closed) => return Err(protocol()),
                        _ => {},
                    }
                }
            }
        }).await.unwrap_or_else(|_| Err(Failure::new(if mutation {"unknown"} else {"unavailable"})));
        result.map_err(|mut failure| {
            if mutation && failure.code == "unavailable" {
                failure.code = "unknown";
            }
            failure.operation_id = Some(operation);
            failure
        })
    }
    async fn read(&self, language: String) -> Result<Overview> {
        self.read_with_budget(language, PROFILE_READ_LIMIT).await
    }
    async fn read_with_budget(&self, language: String, budget: Duration) -> Result<Overview> {
        tokio::time::timeout(budget, self.read_overview(language))
            .await
            .unwrap_or_else(|_| Err(protocol()))
    }
    async fn read_overview(&self, language: String) -> Result<Overview> {
        if !super::language::supported(&language) {
            return Err(protocol());
        }
        let _serial = self.operation.lock().await;
        let person = self.person(None).await?;
        let profile = Self::identity(&person).await?["profile_id"]
            .as_str()
            .ok_or_else(protocol)?
            .to_owned();
        let mut pages = Pages::new(profile.clone());
        loop {
            let result = self
                .run(
                    &person,
                    "user-profile.view",
                    pages.request(&language),
                    false,
                )
                .await?;
            if pages.accept(result)? {
                break;
            }
        }
        // Runtime disclosure already checks the exact session. Also reject a
        // result whose window switched accounts while pages were collected.
        let current = self.person(Some(&profile)).await?;
        let identity = Self::identity(&person).await?;
        if Self::identity(&current).await? != identity {
            return Err(Failure::new("not_signed_in"));
        }
        let overview = pages.finish()?;
        Ok(overview)
    }
    async fn change(&self, change: Change) -> Result<()> {
        let _serial = self.operation.lock().await;
        let person = self.person(Some(&change.profile_id)).await?;
        if change.expected_revision == 0
            || !super::setup::wire::is_hex64(&change.expected_content_digest)
        {
            return Err(protocol());
        }
        let (definition, fields) = change.edit.payload()?;
        let mut payload = json!({"profile_id":change.profile_id, "expected_revision":change.expected_revision,
            "expected_content_digest":change.expected_content_digest});
        payload
            .as_object_mut()
            .ok_or_else(protocol)?
            .extend(fields.as_object().ok_or_else(protocol)?.clone());
        let result = self.run(&person, definition, payload, true).await?;
        if result["profile_id"] != change.profile_id
            || result["record_revision"]
                .as_u64()
                .is_none_or(|r| r < change.expected_revision)
        {
            return Err(Failure::new("saved_unread"));
        }
        Ok(())
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Change {
    profile_id: String,
    expected_revision: u64,
    expected_content_digest: String,
    edit: Edit,
}
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Edit {
    Field {
        path: String,
        value: String,
    },
    AddRow {
        section_key: String,
        values: Vec<RowValue>,
    },
    UpdateRow {
        section_key: String,
        row_key: String,
        values: Vec<RowValue>,
        clear_fields: Vec<String>,
    },
    RemoveRow {
        section_key: String,
        row_key: String,
    },
    Complete,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct RowValue {
    field_key: String,
    value: String,
}
impl Edit {
    fn payload(self) -> Result<(&'static str, Value)> {
        // Authentication and secrets keep their dedicated protected editor.
        // The product validates every remaining path, value and row under CAS.
        let answer = match self {
            Self::Field { path, value } if !path.starts_with("auth.") && value.len() <= 4096 => (
                "user-profile.field-mutation",
                json!({"path":path,"value":value}),
            ),
            Self::AddRow {
                section_key,
                values,
            } if section_key != "auth" => (
                "user-profile.repeatable-row-mutation",
                json!({"section_key":section_key,"values":values}),
            ),
            Self::UpdateRow {
                section_key,
                row_key,
                values,
                clear_fields,
            } if section_key != "auth" => (
                "user-profile.repeatable-row-update",
                json!({"section_key":section_key,"row_key":row_key,"values":values,"clear_fields":clear_fields}),
            ),
            Self::RemoveRow {
                section_key,
                row_key,
            } if section_key != "auth" => (
                "user-profile.repeatable-row-remove",
                json!({"section_key":section_key,"row_key":row_key}),
            ),
            Self::Complete => ("user-profile.complete-setup", json!({})),
            _ => return Err(Failure::new("refused")),
        };
        if answer.1.to_string().len() > 10_000 {
            return Err(Failure::new("refused"));
        }
        Ok(answer)
    }
}

#[tauri::command]
async fn user_profile_read(
    host: State<'_, Arc<ProfileHost>>,
    language: String,
) -> Result<Overview> {
    host.read(language).await
}
#[tauri::command]
async fn user_profile_change(host: State<'_, Arc<ProfileHost>>, change: Change) -> Result<()> {
    host.change(change).await
}
#[tauri::command]
fn user_profile_observe(host: State<'_, Arc<ProfileHost>>, updates: Channel<()>) -> u32 {
    let mut observer = lock(&host.observer);
    if let Some((_, task)) = observer.take() {
        task.abort();
    }
    let subscription = updates.id();
    if host.closed.load(Ordering::Acquire) {
        return subscription;
    }
    let owner = host.sign_in.clone();
    let mut events = owner.person_events();
    // Synchronous commands run on the webview thread, outside Tokio. Spawn
    // through the application's runtime rather than a thread-local handle.
    let task = tauri::async_runtime::spawn(async move {
        loop {
            tokio::select! {
                () = owner.observation_changed() => {},
                event = events.recv() => match event {
                    Ok(PersonEvent::RecordsChanged | PersonEvent::LanguageChanged | PersonEvent::Retired) |
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {},
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    _ => continue,
                }
            }
            if updates.send(()).is_err() {
                break;
            }
        }
    });
    *observer = Some((subscription, task));
    subscription
}
#[tauri::command]
fn user_profile_unobserve(host: State<'_, Arc<ProfileHost>>, subscription: u32) {
    let mut observer = lock(&host.observer);
    if observer.as_ref().is_some_and(|(id, _)| *id == subscription)
        && let Some((_, task)) = observer.take()
    {
        task.abort();
    }
}
pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        user_profile_read,
        user_profile_change,
        user_profile_observe,
        user_profile_unobserve
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn a_queued_profile_read_expires_without_waiting_for_the_previous_operation() {
        let host = ProfileHost::new(Arc::new(
            SignIn::new(&crate::terminal::tests::unit_launch()),
        ));
        let serial = host.operation.lock().await;
        let result = host
            .read_with_budget("en".into(), Duration::from_millis(1))
            .await;
        assert!(matches!(
            result,
            Err(Failure {
                code: "unavailable",
                ..
            })
        ));
        drop(serial);
        assert!(host.operation.try_lock().is_ok());
        host.close();
    }

    #[test]
    fn profile_observation_from_the_webview_thread_owns_and_replaces_its_task() {
        use tauri::{
            WebviewWindowBuilder,
            ipc::{CallbackFn, InvokeBody},
            test::{INVOKE_KEY, get_ipc_response, mock_builder, mock_context, noop_assets},
            webview::InvokeRequest,
        };

        // No #[tokio::test] or entered handle: that hid the main-thread panic.
        assert!(tokio::runtime::Handle::try_current().is_err());
        let host = Arc::new(ProfileHost::new(Arc::new(SignIn::new(
            &crate::terminal::tests::unit_launch(),
        ))));
        let app = mock_builder()
            .manage(host.clone())
            .invoke_handler(tauri::generate_handler![
                user_profile_observe,
                user_profile_unobserve
            ])
            .build(mock_context(noop_assets()))
            .unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let invoke = |cmd: &str, body: Value| {
            get_ipc_response(
                &window,
                InvokeRequest {
                    cmd: cmd.into(),
                    callback: CallbackFn(0),
                    error: CallbackFn(1),
                    url: if cfg!(windows) {
                        "http://tauri.localhost"
                    } else {
                        "tauri://localhost"
                    }
                    .parse()
                    .unwrap(),
                    body: InvokeBody::Json(body),
                    headers: Default::default(),
                    invoke_key: INVOKE_KEY.to_owned(),
                },
            )
            .unwrap()
            .deserialize::<Value>()
            .unwrap()
        };
        let first = invoke("user_profile_observe", json!({"updates":"__CHANNEL__:7"}));
        assert_eq!(first, 7);
        let second = invoke("user_profile_observe", json!({"updates":"__CHANNEL__:8"}));
        assert_eq!(second, 8);
        invoke("user_profile_unobserve", json!({"subscription":first}));
        assert_eq!(lock(&host.observer).as_ref().unwrap().0, 8);
        invoke("user_profile_unobserve", json!({"subscription":second}));
        assert!(lock(&host.observer).is_none());
        invoke("user_profile_observe", json!({"updates":"__CHANNEL__:9"}));
        host.close();
        assert!(lock(&host.observer).is_none());
        invoke("user_profile_observe", json!({"updates":"__CHANNEL__:10"}));
        assert!(lock(&host.observer).is_none());
    }

    #[test]
    fn profile_edits_cannot_send_credentials_through_the_generic_relay() {
        for edit in [
            json!({"kind":"field","path":"auth.clave.password","value":"secret"}),
            json!({"kind":"add_row","section_key":"auth","values":[]}),
            json!({"kind":"update_row","section_key":"auth","row_key":"0","values":[],"clear_fields":[]}),
            json!({"kind":"remove_row","section_key":"auth","row_key":"0"}),
            json!({"kind":"field","path":"identity.name","value":"a".repeat(4097)}),
        ] {
            assert_eq!(
                serde_json::from_value::<Edit>(edit)
                    .unwrap()
                    .payload()
                    .unwrap_err()
                    .code,
                "refused"
            );
        }
        assert!(
            serde_json::from_value::<Edit>(json!({"kind":"execute","command":"anything"})).is_err()
        );
    }
}
