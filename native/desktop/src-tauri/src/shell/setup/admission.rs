//! The local models the desktop hands its component engine before every command.
//!
//! The engine provisions the local AI only once the desktop admits it with the models the
//! person selected for the roles that read on this computer: each as a role, a model name
//! and the download size the model's catalogue entry states. Both facts are the agent
//! service's. The person's per-role choice of lane and model is its `model_roles`
//! record; a lane's kind comes from the provider status and a model's size from
//! cadrumo-agent's catalogue. This module reads them over the service's administration
//! channel at the moment a command runs and invents nothing:
//!
//! - a role with no selection has nothing to pull, and with no selection at all the local
//!   AI is its program alone;
//! - a selection on a lane that takes a key or a sign-in reads off this computer, and the
//!   engine pulls nothing for it;
//! - a selection on a keyless lane the person turned off is not admitted, so turning the
//!   lane off stops setup pulling its models;
//! - a selected local model whose catalogue entry is missing or states no size, or a zero
//!   one, refuses the command, because neither the plan nor the hardware check can be
//!   sized from nothing;
//! - a service that does not answer, or answers outside its contract, refuses the
//!   command as unavailable, and an unreadable selection record is never read as empty.
//!
//! A keyless lane is a lane on this computer: the service's catalogue admits a keyless
//! lane only with a loopback address. The catalogue's `reads_off_host` flag is not part
//! of the provider status, the one record that names a lane's kind whether or not an
//! agent is ready, so this module does not read it.
use super::wire::Refusal;
use crate::{
    agent::{
        AgentHost,
        model_roles::{self, ModelRoles},
    },
    shell::provider_settings::{
        read_status,
        wire::{AuthKind, CommandFailure, Entry, Mode, Refusal as ProviderRefusal, Transport},
    },
};
use cadrumo_application::{
    error::application::ApplicationError,
    provisioning::local_ai::models::{LocalModels, SelectedModel},
};
use serde_json::{Value, json};
use std::{sync::Arc, time::Duration};

/// How long a status read that the service answered with `busy` waits before it asks again.
const STATUS_PAUSE: Duration = Duration::from_millis(250);

/// The agent service as admission reads it: one administration exchange per read.
pub trait Agent: Send + Sync {
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError>;
}

impl Agent for AgentHost {
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError> {
        self.administer(request, None)
    }
}

/// One role's selection.
struct Pick {
    role: String,
    lane: String,
    model: String,
}

/// Reads the selection and the catalogue the engine is admitted with.
pub struct Admission {
    agent: Arc<dyn Agent>,
}

impl Admission {
    pub fn new(agent: Arc<dyn Agent>) -> Self {
        Self { agent }
    }

    /// The models to admit the engine with, as read now, or why none can be.
    pub fn local_models(&self) -> Result<LocalModels, Refusal> {
        let picks = self.picks()?;
        if picks.is_empty() {
            return Ok(LocalModels::default());
        }
        let lanes = self.lanes()?;
        let local: Vec<(Pick, &Entry)> = picks
            .into_iter()
            .filter_map(|pick| {
                let lane = lanes.iter().find(|lane| lane.id == pick.lane)?;
                (lane.auth_kind == AuthKind::Keyless && lane.mode != Mode::Disabled)
                    .then_some((pick, lane))
            })
            .collect();
        if local.is_empty() {
            return Ok(LocalModels::default());
        }
        let catalogue = self.catalogue()?;
        let models = local
            .iter()
            .map(|(pick, lane)| {
                let size = stated_size(&catalogue, lane, &pick.model)
                    .filter(|size| *size > 0)
                    .ok_or(Refusal::ModelSizeUnstated)?;
                SelectedModel::new(&pick.role, &pick.model, size)
                    .map_err(|_| Refusal::ModelSelectionUnusable)
            })
            .collect::<Result<Vec<_>, _>>()?;
        LocalModels::new(models).map_err(|_| Refusal::ModelSelectionUnusable)
    }

    /// Admits only the requested catalogue model, without reading or changing roles.
    pub fn download(&self, request: &super::wire::ModelDownload) -> Result<LocalModels, Refusal> {
        let lanes = self.lanes()?;
        let lane = lanes
            .iter()
            .find(|lane| {
                lane.id == request.lane
                    && lane.auth_kind == AuthKind::Keyless
                    && lane.mode != Mode::Disabled
            })
            .ok_or(Refusal::ModelSelectionUnusable)?;
        let catalogue = self.catalogue()?;
        let size = stated_size(&catalogue, lane, &request.model)
            .filter(|size| *size > 0)
            .ok_or(Refusal::ModelSizeUnstated)?;
        // This part identifies the transfer in the engine plan, never a stored task.
        let model = SelectedModel::new("download", &request.model, size)
            .map_err(|_| Refusal::ModelSelectionUnusable)?;
        LocalModels::new(vec![model]).map_err(|_| Refusal::ModelSelectionUnusable)
    }

    /// Every role the person selected a lane and model for.
    fn picks(&self) -> Result<Vec<Pick>, Refusal> {
        let answer = self
            .agent
            .exchange(json!({"action": "model_roles"}))
            .map_err(|error| unanswered(&error))?;
        if let Some(code) = model_roles::refusal(&answer) {
            return Err(refused_by(code == "agent_signed_out"));
        }
        match model_roles::parse(&answer) {
            Some(ModelRoles::Readable { roles, .. }) => Ok(roles
                .into_iter()
                .filter_map(|entry| {
                    Some(Pick {
                        role: entry.role,
                        lane: entry.lane?,
                        model: entry.model?,
                    })
                })
                .collect()),
            // A record nobody can read says nothing about what the person selected.
            Some(ModelRoles::Unreadable { .. }) => Err(Refusal::ModelSelectionUnusable),
            None => Err(Refusal::Unavailable),
        }
    }

    /// Every lane the profile lists, with the kind of access it takes.
    fn lanes(&self) -> Result<Vec<Entry>, Refusal> {
        read_status(
            || self.agent.exchange(json!({"action": "status"})),
            STATUS_PAUSE,
        )
        .map(|status| status.providers)
        .map_err(|failure| match failure {
            CommandFailure::Host(error) => unanswered(&error),
            CommandFailure::Refused(refused) => refused_by(matches!(
                refused.code,
                ProviderRefusal::NotSignedIn | ProviderRefusal::ProfileLocked
            )),
        })
    }

    /// cadrumo-agent's catalogue, as the service relays it.
    fn catalogue(&self) -> Result<Value, Refusal> {
        let answer = self
            .agent
            .exchange(json!({"action": "catalog"}))
            .map_err(|error| unanswered(&error))?;
        if answer["kind"] == "refused" {
            return Err(refused_by(answer["code"] == "signed_out"));
        }
        Ok(answer)
    }
}

/// What a service that did not answer is to the window.
fn unanswered(error: &ApplicationError) -> Refusal {
    refused_by(error.reason.as_deref() == Some("person_not_signed_in"))
}

/// What a service that refused is to the window: nobody is signed in, or it is not ready.
fn refused_by(signed_out: bool) -> Refusal {
    if signed_out {
        Refusal::NotSignedIn
    } else {
        Refusal::Unavailable
    }
}

/// The download size the catalogue states for `model` on `lane`; `None` when it lists no
/// such lane or model, or its entry states no size. A ready agent serves a lane's record
/// by provider and transport, and names a model `model`; while none is ready the declared
/// catalogue arrives in an envelope, lists its lanes by id and names a model `id`.
fn stated_size(catalogue: &Value, lane: &Entry, model: &str) -> Option<u64> {
    let (models, key) = if catalogue["kind"] == "declared" {
        let record = catalogue["catalog"]["providers"]
            .as_array()?
            .iter()
            .find(|record| record["id"] == lane.id)?;
        (&record["models"], "id")
    } else {
        let transport = match lane.transport {
            Transport::Api => "api",
            Transport::Cli => "cli",
        };
        let record = catalogue["providers"].as_array()?.iter().find(|record| {
            record["provider_id"] == lane.provider && record["transport"] == transport
        })?;
        (&record["catalog"]["models"], "model")
    };
    models
        .as_array()?
        .iter()
        .find(|entry| entry[key] == model)?["size_bytes"]
        .as_u64()
}

#[cfg(test)]
#[path = "admission_tests.rs"]
pub(super) mod tests;
