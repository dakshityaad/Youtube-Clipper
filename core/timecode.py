"""
Shared timestamp parsing helpers.

These were originally private helpers inside cli.py. They're pulled out here,
unchanged in behavior, so the Textual batch wizard (core/tui.py) can reuse the
exact same parsing/padding rules as the CLI without a circular import.
"""

import re
from typing import Tuple


def parse_timestamp(value: str) -> float:
    """Convert seconds, MM:SS, or HH:MM:SS into seconds."""
    value = value.strip()
    if not value:
        raise ValueError("timestamp is empty")

    parts = value.split(":")
    if len(parts) > 3:
        raise ValueError("use seconds, MM:SS, or HH:MM:SS")

    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError("timestamp must contain only numbers and colons") from exc

    if any(number < 0 for number in numbers):
        raise ValueError("timestamps cannot be negative")

    if len(numbers) == 1:
        return numbers[0]
    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            raise ValueError("seconds must be less than 60")
        return minutes * 60 + seconds

    hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        raise ValueError("minutes and seconds must be less than 60")
    return hours * 3600 + minutes * 60 + seconds


def parse_clip_range(value: str) -> Tuple[float, float]:
    """Parse an interactive range such as '1:24 - 2:03' or 'full'."""
    value = value.strip().strip("()")
    if value.lower() == "full":
        return 0.0, 0.0

    match = re.fullmatch(r"\s*(.+?)\s*(?:-|–|—)\s*(.+?)\s*", value)
    if not match:
        raise ValueError("use START - END, for example 1:24 - 2:03, or type FULL for the whole video")

    start = parse_timestamp(match.group(1))
    end = parse_timestamp(match.group(2))
    if end <= start:
        raise ValueError("the end time must be after the start time")
    return start, end


def is_full_video_marker(value: str) -> bool:
    """Return True when the user entered the special 'full video' marker."""
    return value.strip().lower() == "full"


def format_ffmpeg_timestamp(seconds: float) -> str:
    """Return the whole-second HH:MM:SS format expected by trim_video."""
    whole_seconds = int(seconds)
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
