//! The desktop's verified agent service host.
//!
//! It runs the dedicated installed service image while the
//! person's sign-in allows it, supervised in a kill-on-close job, and serves
//! the agent column a closed list of token-checked commands over the
//! launcher's loopback gateway, with each run's stream on a Tauri channel.
//! The launcher admits the agent bundled by CMake or returns a typed refusal.

mod admin;
mod gateway;
mod launcher;
pub(crate) mod person;
mod runner;
mod session;
mod sse;
mod stream;
mod supervisor;

use crate::{
    app::Commands,
    environment::Launch,
    shell::sign_in::{Presence, SignIn},
};
use cadrumo_application::{diagnostics::Diagnostics, error::application::Result};
use serde::Serialize;
use serde_json::Value;
use session::{Answer, RequestRef, SendRequest, Session};
use std::sync::Arc;
use stream::StreamEvent;
use supervisor::{Observation, Status, Supervisor};
use tauri::{Manager, Runtime, State, ipc::Channel, plugin::TauriPlugin};

/// A refusal the column words from its stable code.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Refused {
    pub code: String,
}

impl Refused {
    pub fn new(code: String) -> Self {
        Self { code }
    }
}

/// The agent host one window serves.
pub struct AgentHost {
    supervisor: Supervisor,
    session: Session,
}

impl AgentHost {
    fn new(sign_in: Arc<SignIn>, diagnostics: Arc<Diagnostics>) -> Self {
        let observed = sign_in.clone();
        let observe = Arc::new(move || {
            let sign_in = observed.clone();
            Box::pin(async move {
                sign_in.read_status().await.map(|status| Observation {
                    supported: status.supported,
                    present: status.state == Presence::Present,
                    runtime_available: status.runtime_available,
                    refused: status.refusal.is_some(),
                    active_profile: status.active_profile,
                })
            }) as std::pin::Pin<Box<dyn Future<Output = Result<Observation>> + Send>>
        });
        let launch: supervisor::Launch = Arc::new(move |_bearer: &str, profile: &str| {
            let profile_id = sign_in.profile_id(profile)?;
            let person = Arc::new(std::sync::Mutex::new(person::Person::hold(
                sign_in.runtime()?.command(),
                &profile_id,
            )?));
            let mut command = sign_in.service()?.command();
            command.args(["serve", "--profile-id", &profile_id]);
            Ok(supervisor::Prepared {
                command,
                person: Some(person),
            })
        });
        Self {
            supervisor: Supervisor::new(observe, Some(launch), diagnostics),
            session: Session::default(),
        }
    }

    /// Stops the launcher and everything it started, for good.
    pub async fn close(&self) -> Result<()> {
        self.session.close();
        self.supervisor.close().await
    }

    pub(crate) fn administer(
        &self,
        request: Value,
        secret: Option<zeroize::Zeroizing<Vec<u8>>>,
    ) -> Result<Value> {
        if !matches!(request["action"].as_str(), Some("catalog" | "status")) {
            self.require_person()?;
        }
        self.supervisor.administer(request, secret)
    }

    fn require_person(&self) -> Result<()> {
        let reply = self
            .supervisor
            .person_request(serde_json::json!({"action":"status"}))?;
        if reply["kind"] != "profile_status"
            || reply["status"]["credential_authenticated"] != true
            || reply["status"]["session_id"].is_null()
            || !reply["status"]["denial"].is_null()
        {
            return Err(
                cadrumo_application::error::application::ApplicationError::new(
                    cadrumo_application::error::application::ErrorCode::ReadFailed,
                    cadrumo_application::error::application::Operation::Cli,
                ),
            );
        }
        Ok(())
    }
}

/// Registers the host once the shell's sign-in owner exists.
pub fn plugin<R: Runtime>(launch: &Launch) -> TauriPlugin<R> {
    let diagnostics = launch.diagnostics.clone();
    tauri::plugin::Builder::new("cadrumo-agent")
        .setup(move |app, _| {
            let sign_in = app.state::<Arc<SignIn>>().inner().clone();
            app.manage(Arc::new(AgentHost::new(sign_in, diagnostics.clone())));
            Ok(())
        })
        .build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![
        agent_status,
        agent_retry,
        agent_status_subscribe,
        agent_status_unsubscribe,
        agent_provider_catalog,
        agent_conversation_start,
        agent_send,
        agent_cancel,
        agent_pending,
        agent_questions_answer,
        agent_approval_decide,
        agent_observe,
        agent_unobserve,
        agent_conversations,
        agent_history,
        agent_documents,
        runtime_attendance_inventory,
        runtime_attendance_decide
    ]
}

#[tauri::command]
async fn runtime_attendance_inventory(host: State<'_, Arc<AgentHost>>) -> Result<Value> {
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        host.supervisor
            .person_request(serde_json::json!({"action":"attendance_inventory"}))
    })
    .await
    .map_err(|_| {
        cadrumo_application::error::application::ApplicationError::new(
            cadrumo_application::error::application::ErrorCode::Panic,
            cadrumo_application::error::application::Operation::Cli,
        )
    })?
}

#[tauri::command]
async fn runtime_attendance_decide(
    host: State<'_, Arc<AgentHost>>,
    attendance_id: String,
    approve: bool,
) -> Result<Value> {
    if !crate::shell::agent_access::wire::is_uuid(&attendance_id) {
        return Err(
            cadrumo_application::error::application::ApplicationError::new(
                cadrumo_application::error::application::ErrorCode::InvalidArguments,
                cadrumo_application::error::application::Operation::Cli,
            ),
        );
    }
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || host.supervisor.person_request(serde_json::json!({"action":"attendance_decision", "attendance_id":attendance_id,"approve":approve})))
        .await.map_err(|_| cadrumo_application::error::application::ApplicationError::new(cadrumo_application::error::application::ErrorCode::Panic, cadrumo_application::error::application::Operation::Cli))?
}

/// Runs a gateway call off the async workers.
async fn blocking<T: Send + 'static>(
    host: &State<'_, Arc<AgentHost>>,
    work: impl FnOnce(&AgentHost) -> std::result::Result<T, Refused> + Send + 'static,
) -> std::result::Result<T, Refused> {
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        host.require_person()
            .map_err(|_| Refused::new("agent_signed_out".to_owned()))?;
        work(&host)
    })
    .await
    .map_err(|_| Refused::new("agent_host_failed".to_owned()))?
}

fn refused<T>(code: &str) -> std::result::Result<T, Refused> {
    Err(Refused::new(code.to_owned()))
}

#[tauri::command]
async fn agent_status(host: State<'_, Arc<AgentHost>>) -> Result<Status> {
    Ok(host.supervisor.status())
}

#[tauri::command]
async fn agent_retry(host: State<'_, Arc<AgentHost>>) -> Result<()> {
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || host.supervisor.restart_agent())
        .await
        .map_err(|_| {
            cadrumo_application::error::application::ApplicationError::new(
                cadrumo_application::error::application::ErrorCode::Panic,
                cadrumo_application::error::application::Operation::Cli,
            )
        })?
}

#[tauri::command]
async fn agent_status_subscribe(
    host: State<'_, Arc<AgentHost>>,
    updates: Channel<Status>,
) -> Result<u32> {
    Ok(host.supervisor.subscribe(updates))
}

#[tauri::command]
async fn agent_status_unsubscribe(
    host: State<'_, Arc<AgentHost>>,
    subscription: u32,
) -> Result<()> {
    host.supervisor.unsubscribe(subscription);
    Ok(())
}

/// cadrumo-agent's provider catalog, relayed unchanged and unfiltered.
#[tauri::command]
async fn agent_provider_catalog(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| {
        host.administer(serde_json::json!({"action":"catalog"}), None)
            .map_err(|_| Refused::new("agent_service_failed".to_owned()))
    })
    .await
}

/// Reserves a conversation: the id its first run will have.
#[tauri::command]
async fn agent_conversation_start(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| {
        host.session.start_conversation(&host.supervisor)
    })
    .await
}

#[tauri::command]
async fn agent_send(
    host: State<'_, Arc<AgentHost>>,
    request: SendRequest,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.send(&host.supervisor, &request)
    })
    .await
}

#[tauri::command]
async fn agent_cancel(
    host: State<'_, Arc<AgentHost>>,
    reply_id: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session.cancel(&host.supervisor, &reply_id)
    })
    .await
}

#[tauri::command]
async fn agent_pending(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.pending(&host.supervisor, &conversation_id)
    })
    .await
}

#[tauri::command]
async fn agent_questions_answer(
    host: State<'_, Arc<AgentHost>>,
    questionnaire: RequestRef,
    answer: Answer,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session
            .answer(&host.supervisor, &questionnaire, &answer)
    })
    .await
}

/// Answers a tool approval. Cadrumo reviews are not served.
#[tauri::command]
async fn agent_approval_decide(
    host: State<'_, Arc<AgentHost>>,
    approval: RequestRef,
    option_id: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session.decide(&host.supervisor, &approval, &option_id)
    })
    .await
}

#[tauri::command]
async fn agent_observe(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
    events: Channel<StreamEvent>,
) -> std::result::Result<u32, Refused> {
    blocking(&host, move |host| {
        host.session
            .observe(&host.supervisor, &conversation_id, events)
    })
    .await
}

#[tauri::command]
async fn agent_unobserve(
    host: State<'_, Arc<AgentHost>>,
    subscription: u32,
) -> std::result::Result<(), Refused> {
    host.session.unobserve(subscription);
    Ok(())
}

/// Every conversation: each chain of runs, and those reserved here.
#[tauri::command]
async fn agent_conversations(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| host.session.conversations(&host.supervisor)).await
}

/// A conversation's records, composed from its runs.
#[tauri::command]
async fn agent_history(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.history(&host.supervisor, &conversation_id)
    })
    .await
}

/// Conversation documents are not built in Cadrumo custody.
#[tauri::command]
async fn agent_documents(conversation_id: String) -> std::result::Result<Value, Refused> {
    let _ = conversation_id;
    refused("agent_documents_unavailable")
}
