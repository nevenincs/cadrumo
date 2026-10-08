/// Epoch milliseconds for a canonical UTC timestamp. Older offset-free
/// timestamps remain text because they do not identify a unique instant.
pub fn milliseconds(timestamp: &str) -> Option<u64> {
    let bytes = timestamp.as_bytes();
    if bytes.len() != 24
        || bytes[4] != b'-'
        || bytes[7] != b'-'
        || bytes[10] != b'T'
        || bytes[13] != b':'
        || bytes[16] != b':'
        || bytes[19] != b'.'
        || bytes[23] != b'Z'
    {
        return None;
    }
    let number = |start: usize, end: usize| -> Option<i64> {
        bytes[start..end].iter().try_fold(0, |value, digit| {
            digit
                .is_ascii_digit()
                .then(|| value * 10 + i64::from(digit - b'0'))
        })
    };
    let year = number(0, 4)?;
    let month = number(5, 7)?;
    let day = number(8, 10)?;
    let hour = number(11, 13)?;
    let minute = number(14, 16)?;
    let second = number(17, 19)?;
    let millisecond = number(20, 23)?;
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let days_in_month = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if leap {
                29
            } else {
                28
            }
        }
        _ => return None,
    };
    if !(1..=days_in_month).contains(&day) || hour > 23 || minute > 59 || second > 59 {
        return None;
    }
    // Civil date to days since 1970-01-01 (Howard Hinnant's algorithm).
    let year = year - i64::from(month <= 2);
    let era = year.div_euclid(400);
    let yoe = year - era * 400;
    let mp = month + if month > 2 { -3 } else { 9 };
    let doy = (153 * mp + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146_097 + doe - 719_468;
    u64::try_from((((days * 24 + hour) * 60 + minute) * 60 + second) * 1000 + millisecond).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn utc_timestamps_name_known_instants() {
        for (text, expected) in [
            ("1970-01-01T00:00:00.000Z", 0),
            ("2000-02-29T00:00:00.000Z", 951_782_400_000),
            ("2026-10-04T12:30:01.042Z", 1_791_117_001_042),
            ("2100-02-28T23:59:59.999Z", 4_107_542_399_999),
        ] {
            assert_eq!(milliseconds(text), Some(expected), "{text}");
        }
    }

    #[test]
    fn legacy_and_invalid_timestamps_remain_unparsed() {
        for text in [
            "2026-10-04 12:30:01,042",
            "2026-10-04T12:30:01.042+02:00",
            "2026-10-04T12:30:01Z",
            "2026-02-29T12:30:01.042Z",
            "2100-02-29T12:30:01.042Z",
            "2026-13-04T12:30:01.042Z",
            "2026-10-00T12:30:01.042Z",
            "2026-10-04T24:30:01.042Z",
            "2026-10-04T12:60:01.042Z",
            "2026-10-04T12:30:60.042Z",
            "1969-12-31T23:59:59.999Z",
            "2026-10-04T12:30:0x.042Z",
            "",
        ] {
            assert_eq!(milliseconds(text), None, "{text}");
        }
    }
}
