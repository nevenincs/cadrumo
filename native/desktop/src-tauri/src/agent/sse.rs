//! The Server-Sent Events grammar, read the way the gateway's own decoder
//! reads it: `data` lines join with a newline, `event` names the type,
//! `id` is taken unless it holds a NUL, comments and other fields are
//! ignored, and a blank line dispatches. Lines end on CRLF, LF or CR.

/// The longest event this host buffers: the gateway caps a frame at 1 MiB.
pub const EVENT_LIMIT: usize = 1024 * 1024 + 4096;

/// One dispatched event.
#[derive(Debug, PartialEq, Eq)]
pub struct Event {
    pub event: String,
    pub id: Option<String>,
    pub data: String,
}

/// An event longer than [`EVENT_LIMIT`], or bytes that are not UTF-8.
#[derive(Debug, PartialEq, Eq)]
pub struct Malformed;

#[derive(Default)]
pub struct Decoder {
    line: Vec<u8>,
    /// A CR ended the last line; an LF right after it ends nothing.
    after_cr: bool,
    data: Vec<String>,
    event: String,
    id: Option<String>,
    held: usize,
}

impl Decoder {
    /// Feeds bytes as they arrive and returns the events they complete.
    pub fn feed(&mut self, bytes: &[u8]) -> Result<Vec<Event>, Malformed> {
        let mut events = Vec::new();
        for &byte in bytes {
            if self.after_cr {
                self.after_cr = false;
                if byte == b'\n' {
                    continue;
                }
            }
            match byte {
                b'\n' | b'\r' => {
                    self.after_cr = byte == b'\r';
                    let line = std::mem::take(&mut self.line);
                    let line = String::from_utf8(line).map_err(|_| Malformed)?;
                    if let Some(event) = self.line_ended(&line) {
                        events.push(event);
                    }
                }
                _ => {
                    self.line.push(byte);
                    self.held += 1;
                    if self.held > EVENT_LIMIT {
                        return Err(Malformed);
                    }
                }
            }
        }
        Ok(events)
    }

    fn line_ended(&mut self, line: &str) -> Option<Event> {
        if line.is_empty() {
            return self.dispatch();
        }
        if line.starts_with(':') {
            return None;
        }
        let (name, value) = line.split_once(':').unwrap_or((line, ""));
        let value = value.strip_prefix(' ').unwrap_or(value);
        match name {
            "data" => self.data.push(value.to_owned()),
            "event" => self.event = value.to_owned(),
            "id" if !value.contains('\0') => self.id = Some(value.to_owned()),
            _ => {}
        }
        None
    }

    fn dispatch(&mut self) -> Option<Event> {
        self.held = 0;
        let data = std::mem::take(&mut self.data);
        let event = std::mem::take(&mut self.event);
        let id = self.id.take();
        if data.is_empty() {
            return None;
        }
        Some(Event {
            event: if event.is_empty() {
                "message".to_owned()
            } else {
                event
            },
            id,
            data: data.join("\n"),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frames_as_the_gateway_encodes_them_dispatch_whole_across_any_split() {
        // `_encode` writes `id`, `event`, then one `data` line, and a blank line.
        let wire = b"id: run-1:7\nevent: message_chunk\ndata: {\"api_version\":\"v1\",\"type\":\"message_chunk\"}\n\n\
event: heartbeat\ndata: {\"type\":\"heartbeat\"}\n\n";
        for split in 0..wire.len() {
            let mut decoder = Decoder::default();
            let mut events = decoder.feed(&wire[..split]).unwrap();
            events.extend(decoder.feed(&wire[split..]).unwrap());
            assert_eq!(
                events,
                [
                    Event {
                        event: "message_chunk".into(),
                        id: Some("run-1:7".into()),
                        data: "{\"api_version\":\"v1\",\"type\":\"message_chunk\"}".into()
                    },
                    Event {
                        event: "heartbeat".into(),
                        id: None,
                        data: "{\"type\":\"heartbeat\"}".into()
                    }
                ],
                "split at {split}"
            );
        }
    }

    #[test]
    fn the_grammar_joins_data_skips_comments_and_reads_every_line_end() {
        let mut decoder = Decoder::default();
        let events = decoder
            .feed(b": keepalive\r\ndata: a\r\ndata:b\rretry: 5\nid: x\0y\n\nevent: e\n\ndata\n\n")
            .unwrap();
        assert_eq!(
            events,
            [
                Event {
                    event: "message".into(),
                    id: None,
                    data: "a\nb".into()
                },
                Event {
                    event: "message".into(),
                    id: None,
                    data: String::new()
                }
            ]
        );
    }

    #[test]
    fn an_unbounded_or_undecodable_event_is_refused() {
        let mut decoder = Decoder::default();
        let mut flood = b"data: ".to_vec();
        flood.extend(std::iter::repeat_n(b'x', EVENT_LIMIT));
        assert_eq!(decoder.feed(&flood), Err(Malformed));
        assert_eq!(Decoder::default().feed(b"data: \xff\n\n"), Err(Malformed));
    }
}
