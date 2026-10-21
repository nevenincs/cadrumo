//! Cross-thread notifications that let native host loops wait on events, not ticks.

use std::sync::{Arc, OnceLock};

#[cfg(windows)]
pub mod windows;

/// Tells a host loop that an observation is queued for it.
pub type Notify = Arc<dyn Fn() + Send + Sync>;

/// A producer-side slot the consumer fills after the producer starts. Earlier
/// notifications are not delivered, so a consumer drains once after installing it.
#[derive(Clone, Default)]
pub struct Slot(Arc<OnceLock<Notify>>);

impl Slot {
    pub fn install(&self, notify: Notify) {
        let _ = self.0.set(notify);
    }

    pub fn notify(&self) {
        if let Some(notify) = self.0.get() {
            notify();
        }
    }
}

/// Notifies when dropped, so a producer thread's exit wakes its consumer even
/// when the thread unwinds before reporting.
pub struct NotifyOnDrop(pub Slot);

impl Drop for NotifyOnDrop {
    fn drop(&mut self) {
        self.0.notify();
    }
}
