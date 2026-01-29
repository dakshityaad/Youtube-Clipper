"""
YouTube video downloader using yt-dlp.
Downloads full videos or specific time ranges.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def download_clip(
    url: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Download a YouTube video or clip.
    
    Args:
        url: YouTube video URL
        start_time: Start timestamp (e.g., "1:30" or "90")
        end_time: End timestamp (e.g., "3:45" or "225")
        output_path: Where to save the video. If None, uses temp file.
    
    Returns:
        Path to the downloaded video file.
    """
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".mp4"))
    
    # Build yt-dlp command
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_path),
    ]
    
    # Add time range if specified (uses ffmpeg postprocessor)
    if start_time or end_time:
        postprocessor_args = []
        if start_time:
            postprocessor_args.extend(["-ss", _normalize_time(start_time)])
        if end_time:
            postprocessor_args.extend(["-to", _normalize_time(end_time)])
        
        if postprocessor_args:
            # Use download sections for more efficient clipping
            section = f"*{_normalize_time(start_time or '0')}-{_normalize_time(end_time) if end_time else 'inf'}"
            cmd.extend(["--download-sections", section])
    
    cmd.append(url)
    
    print(f"Downloading: {url}")
    if start_time or end_time:
        print(f"  Time range: {start_time or 'start'} → {end_time or 'end'}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")
    
    # yt-dlp may add extensions, find the actual file
    if not output_path.exists():
        # Check for file with video ID in name
        possible_files = list(output_path.parent.glob(f"{output_path.stem}*"))
        if possible_files:
            output_path = possible_files[0]
        else:
            raise FileNotFoundError(f"Download completed but file not found: {output_path}")
    
    print(f"  Saved to: {output_path}")
    return output_path


def _normalize_time(time_str: str) -> str:
    """
    Normalize time string to HH:MM:SS format.
    Accepts: "90", "1:30", "01:30", "0:01:30"
    """
    time_str = str(time_str).strip()
    
    # If it's just seconds
    if time_str.isdigit():
        total_seconds = int(time_str)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # If it has colons, pad to HH:MM:SS
    parts = time_str.split(":")
    if len(parts) == 2:
        # MM:SS
        return f"00:{int(parts[0]):02d}:{int(parts[1]):02d}"
    elif len(parts) == 3:
        # HH:MM:SS
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    
    return time_str


def get_video_info(url: str) -> dict:
    """Get video metadata without downloading."""
    cmd = ["yt-dlp", "--dump-json", "--no-download", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get video info: {result.stderr}")
    
    import json
    return json.loads(result.stdout)


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        info = get_video_info(sys.argv[1])
        print(f"Title: {info['title']}")
        print(f"Duration: {info['duration']}s")
