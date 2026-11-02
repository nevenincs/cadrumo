use std::time::SystemTime;

/// A UTC instant as Python's `datetime.isoformat` spells it once parsed:
/// `YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00`. Only a zero offset is accepted.
pub(super) fn utc_isoformat(value: &str) -> Option<String> {
    let bytes = value.as_bytes();
    if bytes.len() < 20 || !value.is_ascii() {
        return None;
    }
    let number = |range: std::ops::Range<usize>| -> Option<u32> {
        let part = &value[range];
        part.bytes()
            .all(|byte| byte.is_ascii_digit())
            .then(|| part.parse().ok())
            .flatten()
    };
    let year = number(0..4)?;
    let month = number(5..7)?;
    let day = number(8..10)?;
    let hour = number(11..13)?;
    let minute = number(14..16)?;
    let second = number(17..19)?;
    let separated = bytes[4] == b'-'
        && bytes[7] == b'-'
        && matches!(bytes[10], b'T' | b't' | b' ' | b'_')
        && bytes[13] == b':'
        && bytes[16] == b':';
    let leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    let days = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap => 29,
        2 => 28,
        _ => return None,
    };
    if !separated
        || year == 0
        || !(1..=days).contains(&day)
        || hour > 23
        || minute > 59
        || second > 59
    {
        return None;
    }
    let mut rest = &value[19..];
    let mut micros = 0u32;
    if let Some(fraction) = rest.strip_prefix('.') {
        let digits = fraction.bytes().take_while(u8::is_ascii_digit).count();
        if !(1..=6).contains(&digits) {
            return None;
        }
        let padded = format!("{:0<6}", &fraction[..digits]);
        micros = padded.parse().ok()?;
        rest = &fraction[digits..];
    }
    if !matches!(rest, "Z" | "z" | "+00:00" | "-00:00") {
        return None;
    }
    Some(isoformat(year, month, day, hour, minute, second, micros))
}

pub(super) fn isoformat(
    year: u32,
    month: u32,
    day: u32,
    hour: u32,
    minute: u32,
    second: u32,
    micros: u32,
) -> String {
    let fraction = if micros == 0 {
        String::new()
    } else {
        format!(".{micros:06}")
    };
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}{fraction}+00:00")
}

/// `seconds` and `micros` after the Unix epoch as the product's models spell
/// a UTC instant on the wire: `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`.
pub(super) fn utc_text(seconds: u64, micros: u32) -> String {
    let days = (seconds / 86_400) as i64;
    let of_day = seconds % 86_400;
    // Days to a civil date in the proleptic Gregorian calendar.
    let shifted = days + 719_468;
    let era = shifted.div_euclid(146_097);
    let of_era = shifted.rem_euclid(146_097);
    let year_of_era = (of_era - of_era / 1_460 + of_era / 36_524 - of_era / 146_096) / 365;
    let of_year = of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let shifted_month = (5 * of_year + 2) / 153;
    let day = of_year - (153 * shifted_month + 2) / 5 + 1;
    let month = if shifted_month < 10 {
        shifted_month + 3
    } else {
        shifted_month - 9
    };
    let year = year_of_era + era * 400 + i64::from(month <= 2);
    let iso = isoformat(
        year as u32,
        month as u32,
        day as u32,
        (of_day / 3_600) as u32,
        (of_day % 3_600 / 60) as u32,
        (of_day % 60) as u32,
        micros,
    );
    format!("{}Z", iso.trim_end_matches("+00:00"))
}

pub(super) fn utc_now() -> String {
    let elapsed = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    utc_text(elapsed.as_secs(), elapsed.subsec_micros())
}
