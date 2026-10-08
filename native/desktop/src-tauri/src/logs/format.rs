//! Matches `cadrumo.log` lines against the Python line format the projection
//! reports. The host holds no copy of that format: it compiles whatever
//! `%`-style mapping format Python configured.
use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Level {
    Debug,
    Info,
    Warning,
    Error,
    Critical,
}

impl Level {
    fn parse(name: &str) -> Option<Self> {
        Some(match name {
            "DEBUG" => Self::Debug,
            "INFO" => Self::Info,
            "WARNING" => Self::Warning,
            "ERROR" => Self::Error,
            "CRITICAL" => Self::Critical,
            _ => return None,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Field {
    Time,
    Level,
    Logger,
    Message,
    Context,
    Other,
}

#[derive(Clone, Debug, Eq, PartialEq)]
enum Piece {
    Literal(String),
    Field(Field),
}

/// The fields of one line that starts a record.
#[derive(Debug, Default, Eq, PartialEq)]
pub struct Head<'a> {
    pub time: Option<&'a str>,
    pub level: Option<Level>,
    pub logger: Option<&'a str>,
    pub message: &'a str,
    pub context: BTreeMap<String, Value>,
}

#[derive(Debug)]
pub struct LinePattern {
    pieces: Vec<Piece>,
}

#[derive(Debug, Eq, PartialEq)]
pub struct FormatError;

impl LinePattern {
    /// Compiles a `logging.PercentStyle` mapping format. Formats a line cannot
    /// be split by unambiguously are refused: no `message` field, a repeated
    /// one, or two fields with no literal text between them.
    pub fn compile(format: &str) -> Result<Self, FormatError> {
        let mut pieces = Vec::new();
        let mut literal = String::new();
        let mut rest = format;
        while let Some(start) = rest.find('%') {
            literal.push_str(&rest[..start]);
            rest = &rest[start + 1..];
            if let Some(after) = rest.strip_prefix('%') {
                literal.push('%');
                rest = after;
                continue;
            }
            let after = rest.strip_prefix('(').ok_or(FormatError)?;
            let close = after.find(')').ok_or(FormatError)?;
            let name = &after[..close];
            if name.is_empty() || !name.chars().all(|c| c.is_alphanumeric() || c == '_') {
                return Err(FormatError);
            }
            let spec = &after[close + 1..];
            let flags = spec.trim_start_matches(['#', '0', '+', ' ', '-']);
            let width = flags.trim_start_matches(|c: char| c.is_ascii_digit());
            let precision = match width.strip_prefix('.') {
                Some(digits) => digits.trim_start_matches(|c: char| c.is_ascii_digit()),
                None => width,
            };
            let mut conversion = precision.chars();
            if !conversion
                .next()
                .is_some_and(|c| "diouxXeEfFgGcrsa".contains(c))
            {
                return Err(FormatError);
            }
            rest = conversion.as_str();
            if !literal.is_empty() {
                pieces.push(Piece::Literal(std::mem::take(&mut literal)));
            } else if matches!(pieces.last(), Some(Piece::Field(_))) {
                return Err(FormatError);
            }
            pieces.push(Piece::Field(match name {
                "asctime" => Field::Time,
                "levelname" => Field::Level,
                "name" => Field::Logger,
                "message" => Field::Message,
                "diagnostic_context" => Field::Context,
                _ => Field::Other,
            }));
        }
        literal.push_str(rest);
        if !literal.is_empty() {
            pieces.push(Piece::Literal(literal));
        }
        let messages = pieces
            .iter()
            .filter(|piece| **piece == Piece::Field(Field::Message))
            .count();
        if messages != 1 {
            return Err(FormatError);
        }
        Ok(Self { pieces })
    }

    /// Splits `line` when it starts a record. A field takes the text up to the
    /// first occurrence of the literal that follows it; the last field takes
    /// the rest of the line. A line whose level is not a standard level name,
    /// or whose time carries characters no timestamp has, continues the
    /// previous record instead, as traceback lines do.
    pub fn head<'a>(&self, line: &'a str) -> Option<Head<'a>> {
        let mut head = Head::default();
        let mut position = 0;
        for (index, piece) in self.pieces.iter().enumerate() {
            let rest = &line[position..];
            match piece {
                Piece::Literal(text) => {
                    if !rest.starts_with(text.as_str()) {
                        return None;
                    }
                    position += text.len();
                }
                Piece::Field(field) => {
                    // The projected context suffix may be absent in older
                    // rotations or cut off by the bounded line reader. Only
                    // a complete scalar object claims a suffix; delimiters
                    // in the message or a JSON string remain ordinary text.
                    if *field == Field::Message
                        && let Some(Piece::Literal(delimiter)) = self.pieces.get(index + 1)
                        && self.pieces.get(index + 2) == Some(&Piece::Field(Field::Context))
                        && index + 3 == self.pieces.len()
                    {
                        if let Some((at, context)) =
                            rest.rmatch_indices(delimiter.as_str()).find_map(|(at, _)| {
                                context(&rest[at + delimiter.len()..]).map(|context| (at, context))
                            })
                        {
                            head.message = &rest[..at];
                            head.context = context;
                        } else {
                            head.message = rest;
                        }
                        return Some(head);
                    }
                    let length = match self.pieces.get(index + 1) {
                        Some(Piece::Literal(next)) => rest.find(next.as_str())?,
                        _ => rest.len(),
                    };
                    let value = &rest[..length];
                    position += length;
                    match field {
                        Field::Time => {
                            let time = value.trim();
                            if !time.starts_with(|c: char| c.is_ascii_digit())
                                || !time
                                    .chars()
                                    .all(|c| c.is_ascii_digit() || "-:,. T+Z".contains(c))
                            {
                                return None;
                            }
                            head.time = Some(time);
                        }
                        Field::Level => head.level = Some(Level::parse(value.trim())?),
                        Field::Logger => head.logger = Some(value.trim()),
                        Field::Message => head.message = value,
                        Field::Context => head.context = context(value)?,
                        Field::Other => {}
                    }
                }
            }
        }
        (position == line.len()).then_some(head)
    }
}

fn context(text: &str) -> Option<BTreeMap<String, Value>> {
    if !text.starts_with('{') {
        return None;
    }
    let Value::Object(values) = serde_json::from_str(text).ok()? else {
        return None;
    };
    if values.len() > 32
        || values.iter().any(|(key, value)| {
            key.is_empty()
                || key.len() > 64
                || !key
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
                || match value {
                    Value::String(text) => text.chars().count() > 512,
                    Value::Array(_) | Value::Object(_) => true,
                    _ => false,
                }
        })
    {
        return None;
    }
    Some(values.into_iter().collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    // The configured format is only known at runtime; tests use the shape the
    // Python owner configures today and a few other valid mapping formats.
    const CONFIGURED: &str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s";

    #[test]
    fn configured_format_splits_a_record_line() {
        let pattern = LinePattern::compile(CONFIGURED).unwrap();
        assert_eq!(
            pattern.head("2026-10-04 12:30:01,042 [WARNING] cadrumo.tui.app: lost [x]: y"),
            Some(Head {
                time: Some("2026-10-04 12:30:01,042"),
                level: Some(Level::Warning),
                logger: Some("cadrumo.tui.app"),
                message: "lost [x]: y",
                context: BTreeMap::new(),
            })
        );
        assert_eq!(
            pattern
                .head("2026-10-04 12:30:01,042 [INFO] root: ")
                .map(|h| h.message),
            Some("")
        );
    }

    #[test]
    fn traceback_lines_are_not_record_starts() {
        let pattern = LinePattern::compile(CONFIGURED).unwrap();
        for line in [
            "Traceback (most recent call last):",
            "  File \"x.py\", line 3, in <module>",
            "KeyError: [x] foo: bar",
            "ValueError: 1 [INFO] a: b",
            "2026-10-04 12:30:01,042 [NOTICE] cadrumo: custom level",
            "2026-10-04 12:30:01,042 INFO cadrumo: no brackets",
            "",
        ] {
            assert_eq!(pattern.head(line), None, "{line}");
        }
    }

    #[test]
    fn projected_context_suffix_preserves_delimiters_and_legacy_records() {
        let pattern =
            LinePattern::compile(&format!("{CONFIGURED} | %(diagnostic_context)s")).unwrap();
        let head = pattern.head(r#"2026-10-04T12:30:01.042Z [INFO] cadrumo: before | after | {"diagnostic_id":"attempt-7","note":"a | b","process_id":412,"process_role":"runtime_worker","ready":true}"#).unwrap();
        assert_eq!(head.message, "before | after");
        assert_eq!(head.context["diagnostic_id"], "attempt-7");
        assert_eq!(head.context["note"], "a | b");
        assert_eq!(head.context["process_id"], 412);
        for message in [
            "legacy record",
            "truncated | {\"process_id\":",
            "body | {\"nested\":{\"value\":1}}",
        ] {
            let text = format!("2026-10-04 12:30:01,042 [INFO] cadrumo: {message}");
            let head = pattern.head(&text).unwrap();
            assert_eq!(head.message, message);
            assert!(head.context.is_empty());
        }
    }

    #[test]
    fn widths_flags_other_fields_and_escaped_percent_compile() {
        let pattern =
            LinePattern::compile("%(levelname)-8s|%(process)5d|100%% %(name)s> %(message)s")
                .unwrap();
        let head = pattern.head("ERROR   |  412|100% cadrumo.x> boom").unwrap();
        assert_eq!(head.level, Some(Level::Error));
        assert_eq!(head.logger, Some("cadrumo.x"));
        assert_eq!(head.message, "boom");
        assert_eq!(head.time, None);
        let suffixed = LinePattern::compile("%(message)s <%(levelname)s>").unwrap();
        assert_eq!(
            suffixed.head("hi <DEBUG>").map(|h| (h.message, h.level)),
            Some(("hi", Some(Level::Debug)))
        );
        assert_eq!(suffixed.head("hi <DEBUG> tail"), None);
    }

    #[test]
    fn ambiguous_or_invalid_formats_are_refused() {
        for format in [
            "",
            "%(asctime)s %(name)s",
            "%(message)s %(message)s",
            "%(asctime)s%(message)s",
            "%(message)",
            "%s %(message)s",
            "%(message)q",
            "%(mes sage)s",
            "%(message",
        ] {
            assert_eq!(
                LinePattern::compile(format).err(),
                Some(FormatError),
                "{format}"
            );
        }
    }
}
