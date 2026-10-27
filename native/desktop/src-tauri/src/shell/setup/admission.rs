//! The local model the desktop hands its component engine for one download.
//!
//! General setup admits the local AI as its program alone; a model is pulled only when
//! the person downloads it from a local lane's model list. That list is the models
//! cadrumo-agent's catalogue recommends for the lane and the models the person added to it
//! by name. Both facts are the agent service's: a lane's kind comes from the provider
//! status, its recommended models and a model's size from cadrumo-agent's catalogue, and
//! the added models from the service's `local_models` record. This module reads them over
//! the service's administration channel at the moment a download starts and invents
//! nothing:
//!
//! - a lane that takes a key or a sign-in reads off this computer, a keyless lane the
//!   person turned off is not to be used, and a lane the status does not list is unknown;
//!   none of them admits a download;
//! - a model on neither of the lane's lists is not one the person can download, and an
//!   unreadable record of added models admits no added model;
//! - the size is the one the catalogue states for the model, and unknown when it states
//!   none or a zero one, as for a model the person named;
//! - a service that does not answer or refuses refuses the download as unavailable, with
//!   what it answered kept for diagnostics;
//! - a list reply outside the service's contract is a host failure, not a service that is
//!   not answering.
//!
//! A keyless lane is a lane on this computer: the service's catalogue admits a keyless
//! lane only with a loopback address. The catalogue's `reads_off_host` flag is not part
//! of the provider status, the one record that names a lane's kind whether or not an
//! agent is ready, so this module does not read it.
use super::wire::{ModelDownload, Refusal, Stop};
use crate::{
    agent::{AgentHost, local_models},
    shell::provider_settings::{
        read_status,
        wire::{AuthKind, CommandFailure, Entry, Mode, Refusal as ProviderRefusal, Transport},
    },
};
use cadrumo_application::{
    error::application::{ApplicationError, ChildRefusal, ErrorCode, Operation},
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

/// Reads what a download is admitted with.
pub struct Admission {
    agent: Arc<dyn Agent>,
}

impl Admission {
    pub fn new(agent: Arc<dyn Agent>) -> Self {
        Self { agent }
    }

    /// Admits the requested model alone, if it is on the requested local lane's list.
    pub fn download(&self, request: &ModelDownload) -> Result<LocalModels, Stop> {
        let unusable = || Stop::Refused(Refusal::ModelSelectionUnusable);
        let lanes = self.lanes()?;
        let lane = lanes
            .iter()
            .find(|lane| {
                lane.id == request.lane
                    && lane.auth_kind == AuthKind::Keyless
                    && lane.mode != Mode::Disabled
            })
            .ok_or_else(unusable)?;
        let catalogue = self.catalogue()?;
        let record = lane_record(&catalogue, lane);
        let recommended = record.is_some_and(|record| record.recommends(&request.model));
        if !recommended && !self.added(&lane.id, &request.model)? {
            return Err(unusable());
        }
        let size = record
            .and_then(|record| record.stated_size(&request.model))
            .filter(|size| *size > 0);
        // This part identifies the transfer in the engine plan, never a stored task.
        let model = SelectedModel::new("download", &request.model, size).map_err(|_| unusable())?;
        LocalModels::new(vec![model]).map_err(|_| unusable())
    }

    /// Whether the person added `model` to `lane`'s list.
    fn added(&self, lane: &str, model: &str) -> Result<bool, Stop> {
        let answer = self
            .agent
            .exchange(json!({"action": "local_models"}))
            .map_err(|error| unanswered(error, "setup_local_models_unanswered"))?;
        if let Some(code) = local_models::refusal(&answer) {
            return Err(refused_by(
                code == "agent_signed_out",
                "setup_local_models_refused",
                &answer,
            ));
        }
        match local_models::parse(&answer) {
            // A record nobody can read lists no model, so it admits none.
            Some(listed) => Ok(listed.added_to(lane).any(|added| added == model)),
            // The service answered, so "not answering" would misname it.
            None => Err(Stop::Host(
                ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                    .with_reason("setup_local_models_contract"),
            )),
        }
    }

    /// Every lane the profile lists, with the kind of access it takes.
    fn lanes(&self) -> Result<Vec<Entry>, Stop> {
        read_status(
            || self.agent.exchange(json!({"action": "status"})),
            STATUS_PAUSE,
        )
        .map(|status| status.providers)
        .map_err(|failure| match failure {
            CommandFailure::Host(error) => unanswered(error, "setup_provider_status_unanswered"),
            CommandFailure::Refused(refused) => refused_by(
                matches!(
                    refused.code,
                    ProviderRefusal::NotSignedIn | ProviderRefusal::ProfileLocked
                ),
                "setup_provider_status_refused",
                &json!({"code": refused.code}),
            ),
        })
    }

    /// cadrumo-agent's catalogue, as the service relays it.
    fn catalogue(&self) -> Result<Value, Stop> {
        let answer = self
            .agent
            .exchange(json!({"action": "catalog"}))
            .map_err(|error| unanswered(error, "setup_catalogue_unanswered"))?;
        if answer["kind"] == "refused" {
            return Err(refused_by(
                answer["code"] == "signed_out",
                "setup_catalogue_refused",
                &answer,
            ));
        }
        Ok(answer)
    }
}

/// What a service that did not answer is to the window, and to diagnostics: nobody is
/// signed in, or the failure of the exchange named `reason`.
fn unanswered(error: ApplicationError, reason: &'static str) -> Stop {
    if error.reason.as_deref() == Some("person_not_signed_in") {
        return Refusal::NotSignedIn.into();
    }
    Stop::unavailable(reason).because(error)
}

/// What a service that refused with `answer` is to the window: nobody is signed in, or it
/// is not ready for the reason named. The refusal code the service gave is kept.
fn refused_by(signed_out: bool, reason: &'static str, answer: &Value) -> Stop {
    if signed_out {
        Refusal::NotSignedIn.into()
    } else {
        Stop::unavailable(reason).because(ChildRefusal::answered(answer))
    }
}

/// A lane's record in the catalogue: its recommended models and its model entries, each
/// entry named under the key the catalogue's shape uses.
#[derive(Clone, Copy)]
struct LaneRecord<'a> {
    recommended: &'a Value,
    models: &'a Value,
    key: &'static str,
}

impl LaneRecord<'_> {
    /// Whether the catalogue recommends `model` for any capability of the lane.
    fn recommends(self, model: &str) -> bool {
        self.recommended
            .as_object()
            .is_some_and(|recommended| recommended.values().any(|named| named == model))
    }

    /// The download size the catalogue states for `model`; `None` when it lists no such
    /// model or its entry states no size.
    fn stated_size(self, model: &str) -> Option<u64> {
        self.models
            .as_array()?
            .iter()
            .find(|entry| entry[self.key] == model)?["size_bytes"]
            .as_u64()
    }
}

/// `lane`'s record in `catalogue`. A ready agent serves a lane's record by provider and
/// transport, and names a model `model`; while none is ready the declared catalogue
/// arrives in an envelope, lists its lanes by id and names a model `id`.
fn lane_record<'a>(catalogue: &'a Value, lane: &Entry) -> Option<LaneRecord<'a>> {
    if catalogue["kind"] == "declared" {
        let record = catalogue["catalog"]["providers"]
            .as_array()?
            .iter()
            .find(|record| record["id"] == lane.id)?;
        return Some(LaneRecord {
            recommended: &record["recommended"],
            models: &record["models"],
            key: "id",
        });
    }
    let transport = match lane.transport {
        Transport::Api => "api",
        Transport::Cli => "cli",
    };
    let record = catalogue["providers"].as_array()?.iter().find(|record| {
        record["provider_id"] == lane.provider && record["transport"] == transport
    })?;
    Some(LaneRecord {
        recommended: &record["catalog"]["recommended"],
        models: &record["catalog"]["models"],
        key: "model",
    })
}

#[cfg(test)]
#[path = "admission_tests.rs"]
pub(super) mod tests;
