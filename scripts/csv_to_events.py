#!/usr/bin/env python3
"""
Canonical pipeline: CSV (Sheet export) -> data/events.json (top-level array).

Europe/Budapest wall-clock parity with EVENT_TIMEZONE in index.html.

If a row's duration cell is empty or whitespace, it defaults to DEFAULT_DURATION_STR (1 hour).
Each substitution is logged to stderr for auditing.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from zoneinfo import ZoneInfo

EVENT_TIMEZONE = ZoneInfo("Europe/Budapest")
DEFAULT_DURATION_STR = "1:00:00"


def norm_header(raw: str) -> str:
    return raw.replace("\ufeff", "").strip().lower()


def normalize_stage(raw: str) -> str:
    s = " ".join(str(raw or "").split())
    if not s:
        return ""
    return s.upper()


def parse_sheet_date_dots(s: str) -> Optional[date]:
    parts = [p.strip() for p in re.split(r"[.\-/]", str(s or "")) if p.strip()]
    if len(parts) < 3:
        return None
    try:
        y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, mo, d)
    except ValueError:
        return None


def parse_time_cell(s: str) -> Optional[Tuple[int, int]]:
    """12-hour: '7:30:00 PM'. Also accepts 24-hour 'HH:MM' or 'H:MM'."""
    x = str(s or "").strip()
    if not x:
        return None
    try:
        t = datetime.strptime(x, "%I:%M:%S %p").time()
        return t.hour, t.minute
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*", x)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi
    return None


def parse_duration_hmmss(s: str) -> timedelta:
    """Parses H:MM:SS (hours may exceed 99)."""
    x = str(s).strip()
    parts = x.split(":")
    if len(parts) != 3:
        raise ValueError(f"expected H:MM:SS, got {x!r}")
    h_str, mi_str, s_str = parts
    hours = int(h_str)
    mins = int(mi_str)
    secs = int(s_str)
    if mins < 0 or mins > 59 or secs < 0 or secs > 59 or hours < 0:
        raise ValueError(f"bad duration components: {x!r}")
    return timedelta(hours=hours, minutes=mins, seconds=secs)


def parse_tags(cell: Optional[str]) -> List[str]:
    if not cell or not str(cell).strip():
        return []
    return [t.strip().lower() for t in str(cell).split(",") if t.strip()]


def iso_duration_from_span_ms(span_ms: float) -> str:
    """Match index.html isoDurationBetweenMs (nearest-minute, non-negative)."""
    mins = max(0, int(round(span_ms / 60000)))
    h = mins // 60
    m = mins % 60
    parts: List[str] = []
    if h:
        parts.append(f"{h}H")
    if m:
        parts.append(f"{m}M")
    body = "".join(parts)
    return f"PT{body}" if body else "PT0M"


def local_naive_iso_from_utc_ms(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(EVENT_TIMEZONE)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def utc_ms_wall_clock(d: date, hour: int, minute: int) -> int:
    aware = datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=EVENT_TIMEZONE)
    return int(aware.timestamp() * 1000)


def find_column_exact(header_row: Sequence[str], name: str, required_desc: str) -> int:
    for i, h in enumerate(header_row):
        if norm_header(h) == name:
            return i
    raise SystemExit(f"Missing required CSV column ({required_desc}).")


def find_optional_column_exact(header_row: Sequence[str], name: str) -> Optional[int]:
    for i, h in enumerate(header_row):
        if norm_header(h) == name:
            return i
    return None


def find_sample_column(header_row: Sequence[str]) -> Optional[int]:
    for i, h in enumerate(header_row):
        nh = norm_header(h)
        if ("sample" in nh and "url" in nh) or ("samlpe" in nh and "url" in nh):
            return i
    for i, h in enumerate(header_row):
        nh = norm_header(h)
        if "sample" in nh or "samlpe" in nh:
            return i
    return None


def build_col_map(header_row: Sequence[str]) -> Dict[str, int]:
    return {
        "id": find_column_exact(header_row, "id", "id"),
        "stage": find_column_exact(header_row, "stage", "stage"),
        "band": find_column_exact(header_row, "band", "band"),
        "date": find_column_exact(header_row, "date", "date"),
        "time": find_column_exact(header_row, "time", "time"),
        "duration": find_column_exact(
            header_row, "duration", "duration (header required; cells may be empty)"
        ),
    }


def parse_row(
    row: Sequence[str],
    col: Dict[str, int],
    lineno: int,
    tags_i: Optional[int],
    sample_i: Optional[int],
) -> dict:

    def cell(key: str) -> str:
        j = col[key]
        if j < len(row):
            return str(row[j]).strip()
        return ""

    sid = cell("id")
    band = cell("band")
    stage_raw = cell("stage")
    date_cell = cell("date")
    time_cell = cell("time")
    dj = col["duration"]
    dur_cell_raw = row[dj].strip() if dj < len(row) else ""

    if not sid:
        raise SystemExit(f"Row {lineno}: missing id.")

    try:
        eid = int(sid)
    except ValueError as e:
        raise SystemExit(f"Row {lineno}: id must be integer, got {sid!r}") from e

    if not band:
        raise SystemExit(f"Row {lineno} (id {eid}): missing band.")

    location = normalize_stage(stage_raw)
    if not location:
        raise SystemExit(f"Row {lineno} (id {eid}): missing stage.")

    d_part = parse_sheet_date_dots(date_cell)
    if d_part is None:
        raise SystemExit(f"Row {lineno} (id {eid}): invalid date {date_cell!r}.")

    t_part = parse_time_cell(time_cell)
    if t_part is None:
        raise SystemExit(f"Row {lineno} (id {eid}): invalid time {time_cell!r}.")

    if not dur_cell_raw:
        dur_use = DEFAULT_DURATION_STR
        print(
            f"csv_to_events.py: row id {eid}: empty duration — using default {DEFAULT_DURATION_STR}",
            file=sys.stderr,
        )
    else:
        dur_use = dur_cell_raw

    try:
        td = parse_duration_hmmss(dur_use)
    except ValueError as e:
        raise SystemExit(f"Row {lineno} (id {eid}): invalid duration {dur_cell_raw!r}") from e

    hour, minute = t_part
    start_ms = utc_ms_wall_clock(d_part, hour, minute)
    end_ms = start_ms + int(td.total_seconds() * 1000)
    iso_dur = iso_duration_from_span_ms(end_ms - start_ms)
    day_key = f"{d_part.year}-{d_part.month:02d}-{d_part.day:02d}"

    tags = parse_tags(row[tags_i].strip()) if tags_i is not None and tags_i < len(row) else []
    sample = ""
    if sample_i is not None and sample_i < len(row):
        sample = str(row[sample_i]).strip()

    return {
        "id": eid,
        "summary": band,
        "location": location,
        "startUtcMs": start_ms,
        "endUtcMs": end_ms,
        "dayKey": day_key,
        "duration": iso_dur,
        "startTime": local_naive_iso_from_utc_ms(start_ms),
        "endTime": local_naive_iso_from_utc_ms(end_ms),
        "description": "",
        "sampleSetUrl": sample,
        "tags": tags,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Convert lineup CSV -> data/events.json")
    repo = Path(__file__).resolve().parent.parent
    default_csv = repo / "data" / "events.csv"
    default_out = repo / "data" / "events.json"
    p.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=default_csv,
        help=f"CSV file (default: {default_csv})",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=default_out,
        help=f"JSON output path (default: {default_out})",
    )
    ns = p.parse_args(list(argv) if argv is not None else None)

    csv_path = ns.csv_path
    out_path = ns.out

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise SystemExit("Empty CSV.")

    header = rows[0]
    col = build_col_map(header)
    tags_i = find_optional_column_exact(header, "tags")
    sample_i = find_sample_column(header)

    seen_ids: Dict[int, int] = {}
    events: List[dict] = []
    for i, row in enumerate(rows[1:], start=2):
        if not row or not any(str(c).strip() for c in row):
            continue
        ev = parse_row(row, col, i, tags_i, sample_i)
        eid = ev["id"]
        if eid in seen_ids:
            raise SystemExit(f"Duplicate id {eid}: rows {seen_ids[eid]} and {i}.")
        seen_ids[eid] = i
        events.append(ev)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(events)} events -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
