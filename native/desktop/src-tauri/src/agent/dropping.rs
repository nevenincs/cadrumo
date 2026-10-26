//! Native file drops. Only coordinates, counts and a single-use handle cross
//! to the page; paths stay bound to the observer and its exact gateway.

use super::{Refused, supervisor::Gateway};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{Mutex, atomic::AtomicBool},
    time::{Duration, Instant},
};
use tauri::ipc::Channel;

#[derive(Clone, Debug, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Signal {
    Over {
        x: f64,
        y: f64,
        count: usize,
        shift: Option<bool>,
    },
    Left,
    Dropped {
        x: f64,
        y: f64,
        count: usize,
        shift: Option<bool>,
        drop_id: String,
    },
}

struct Pending {
    id: String,
    paths: Vec<PathBuf>,
    since: Instant,
}

struct Target {
    updates: Channel<Signal>,
    gateway: Gateway,
    count: usize,
    pending: Option<Pending>,
}

#[derive(Default)]
pub struct Drops {
    target: Mutex<Option<Target>>,
    pub listening: AtomicBool,
}

impl Drops {
    pub fn observe(&self, updates: Channel<Signal>, gateway: Gateway) -> u32 {
        let subscription = updates.id();
        *self.target.lock().unwrap_or_else(|e| e.into_inner()) = Some(Target {
            updates,
            gateway,
            count: 0,
            pending: None,
        });
        subscription
    }

    pub fn clear(&self, subscription: Option<u32>) {
        let mut target = self.target.lock().unwrap_or_else(|e| e.into_inner());
        if target
            .as_ref()
            .is_some_and(|held| subscription.is_none_or(|id| held.updates.id() == id))
        {
            *target = None;
        }
    }

    pub fn take(&self, id: &str, gateway: &Gateway) -> Result<Vec<PathBuf>, Refused> {
        let mut target = self.target.lock().unwrap_or_else(|e| e.into_inner());
        let target = target
            .as_mut()
            .filter(|held| held.gateway.same_instance(gateway));
        let pending = target.and_then(|held| {
            if held
                .pending
                .as_ref()
                .is_some_and(|pending| pending.id == id)
            {
                held.pending.take()
            } else {
                None
            }
        });
        claim(pending, id)
    }

    pub fn event(&self, event: &tauri::DragDropEvent, scale: f64) {
        let mut target = self.target.lock().unwrap_or_else(|e| e.into_inner());
        let Some(target) = target.as_mut() else {
            return;
        };
        #[cfg(windows)]
        let shift = Some(cadrumo_platform::desktop::shift_pressed());
        #[cfg(not(windows))]
        let shift = None;
        let signal = match event {
            tauri::DragDropEvent::Enter { paths, position } => {
                target.count = paths.len();
                target.pending = None;
                Signal::Over {
                    x: position.x / scale,
                    y: position.y / scale,
                    count: target.count,
                    shift,
                }
            }
            tauri::DragDropEvent::Over { position } => Signal::Over {
                x: position.x / scale,
                y: position.y / scale,
                count: target.count,
                shift,
            },
            tauri::DragDropEvent::Leave => {
                target.pending = None;
                Signal::Left
            }
            tauri::DragDropEvent::Drop { paths, position } => {
                let mut random = [0u8; 16];
                if getrandom::fill(&mut random).is_err() {
                    return;
                }
                let id: String = random.iter().map(|byte| format!("{byte:02x}")).collect();
                target.pending = Some(Pending {
                    id: id.clone(),
                    paths: paths.iter().take(200).cloned().collect(),
                    since: Instant::now(),
                });
                Signal::Dropped {
                    x: position.x / scale,
                    y: position.y / scale,
                    count: paths.len(),
                    shift,
                    drop_id: id,
                }
            }
            _ => return,
        };
        if target.updates.send(signal).is_err() {
            target.pending = None;
        }
    }
}

fn claim(pending: Option<Pending>, id: &str) -> Result<Vec<PathBuf>, Refused> {
    pending
        .filter(|held| held.id == id && held.since.elapsed() <= Duration::from_secs(60))
        .map(|held| held.paths)
        .ok_or_else(|| Refused::new("agent_invalid_request".to_owned()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_a_matching_unexpired_drop_can_be_claimed() {
        let make = |id: &str, age| Pending {
            id: id.to_owned(),
            paths: vec![PathBuf::from("private/invoice.pdf")],
            since: Instant::now() - age,
        };
        assert_eq!(
            claim(Some(make("a", Duration::ZERO)), "a").unwrap(),
            vec![PathBuf::from("private/invoice.pdf")]
        );
        for pending in [
            None,
            Some(make("b", Duration::ZERO)),
            Some(make("a", Duration::from_secs(61))),
        ] {
            assert_eq!(
                claim(pending, "a").unwrap_err().code,
                "agent_invalid_request"
            );
        }
    }
}
