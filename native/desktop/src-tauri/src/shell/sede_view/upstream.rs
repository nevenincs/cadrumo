//! What the window sends a view that has no answer to wait for, in the order
//! the window sent it.
//!
//! The window's commands run on the host's main thread and must never wait on
//! the runtime's pipe, yet a press must reach the page before its release.
//! Each command queues here and one writer thread per view sends the queue in
//! order.
use cadrumo_application::view_stream::documents::{
    PointerAction, ViewInputEvent, ViewNavigateVerb,
};
use std::{
    collections::VecDeque,
    sync::{Condvar, Mutex, MutexGuard},
};

/// How many commands may wait. A window that outruns the runtime this far is
/// refused, not buffered without bound.
const LIMIT: usize = 1024;

pub(super) enum Command {
    Input(ViewInputEvent),
    Navigate(ViewNavigateVerb),
    Resize {
        css_width: u32,
        css_height: u32,
        scale: f64,
    },
    Dialog {
        dialog_id: u32,
        accept: bool,
        prompt_text: Option<String>,
    },
    Credit(u8),
}

impl Command {
    /// A pointer move carries the whole pointer state, so a newer one makes an
    /// older one that was never sent pointless.
    fn is_move(&self) -> bool {
        matches!(
            self,
            Self::Input(ViewInputEvent::Pointer(pointer)) if pointer.action == PointerAction::Move
        )
    }
}

#[derive(Default)]
struct State {
    items: VecDeque<Command>,
    closed: bool,
}

#[derive(Default)]
pub(super) struct Upstream {
    state: Mutex<State>,
    ready: Condvar,
}

impl Upstream {
    fn state(&self) -> MutexGuard<'_, State> {
        self.state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// Queues a command; `false` when the view ended or the queue is full.
    pub(super) fn push(&self, command: Command) -> bool {
        let mut state = self.state();
        if state.closed {
            return false;
        }
        if command.is_move()
            && let Some(last) = state.items.back_mut()
            && last.is_move()
        {
            *last = command;
            return true;
        }
        if state.items.len() >= LIMIT {
            return false;
        }
        state.items.push_back(command);
        self.ready.notify_one();
        true
    }

    /// The next command, waiting for one; `None` once the view ended.
    pub(super) fn next(&self) -> Option<Command> {
        let mut state = self.state();
        loop {
            if state.closed {
                return None;
            }
            if let Some(command) = state.items.pop_front() {
                return Some(command);
            }
            state = self
                .ready
                .wait(state)
                .unwrap_or_else(|poisoned| poisoned.into_inner());
        }
    }

    /// Ends the queue: what waits is dropped and the writer stops.
    pub(super) fn close(&self) {
        let mut state = self.state();
        state.closed = true;
        state.items.clear();
        self.ready.notify_all();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::view_stream::documents::{
        PointerButton, PointerInput, TextInput, ViewInputEvent,
    };

    fn pointer(action: PointerAction, x: u32) -> Command {
        let press = action != PointerAction::Move;
        Command::Input(ViewInputEvent::Pointer(PointerInput {
            action,
            x,
            y: 5,
            button: if press {
                PointerButton::Left
            } else {
                PointerButton::None
            },
            click_count: u8::from(press),
            modifiers: 0,
        }))
    }

    fn text(value: &str) -> Command {
        Command::Input(ViewInputEvent::Text(TextInput {
            text: value.to_owned(),
        }))
    }

    fn drain(queue: &Upstream) -> Vec<String> {
        let mut seen = Vec::new();
        loop {
            let next = {
                let mut state = queue.state();
                state.items.pop_front()
            };
            let Some(command) = next else { break };
            seen.push(match command {
                Command::Input(ViewInputEvent::Pointer(p)) => format!("{:?}@{}", p.action, p.x),
                Command::Input(ViewInputEvent::Text(t)) => format!("text:{}", t.text),
                Command::Credit(n) => format!("credit:{n}"),
                _ => "other".to_owned(),
            });
        }
        seen
    }

    #[test]
    fn commands_leave_in_the_order_they_arrived() {
        let queue = Upstream::default();
        for command in [
            pointer(PointerAction::Down, 1),
            text("a"),
            pointer(PointerAction::Up, 1),
            Command::Credit(1),
        ] {
            assert!(queue.push(command));
        }
        assert_eq!(drain(&queue), ["Down@1", "text:a", "Up@1", "credit:1"]);
    }

    #[test]
    fn a_newer_pointer_move_replaces_an_unsent_one_and_nothing_else() {
        let queue = Upstream::default();
        for command in [
            pointer(PointerAction::Move, 1),
            pointer(PointerAction::Move, 2),
            pointer(PointerAction::Down, 2),
            pointer(PointerAction::Move, 3),
            pointer(PointerAction::Move, 4),
            text("b"),
            pointer(PointerAction::Move, 5),
        ] {
            assert!(queue.push(command));
        }
        assert_eq!(
            drain(&queue),
            ["Move@2", "Down@2", "Move@4", "text:b", "Move@5"]
        );
    }

    #[test]
    fn a_full_queue_refuses_and_a_closed_one_ends_the_writer() {
        let queue = Upstream::default();
        for _ in 0..LIMIT {
            assert!(queue.push(Command::Credit(1)));
        }
        assert!(!queue.push(Command::Credit(1)), "full");
        assert!(
            !queue.push(pointer(PointerAction::Move, 1)),
            "a move needs room unless it replaces one"
        );
        queue.close();
        assert!(!queue.push(Command::Credit(1)), "closed");
        assert!(queue.next().is_none());
        assert!(drain(&queue).is_empty(), "closing drops what waited");
    }
}
