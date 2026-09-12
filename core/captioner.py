"""
Caption generation and rendering.
Uses Whisper for transcription and FFmpeg for burning captions.
"""

import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum


class CaptionStyle(Enum):
    CLEAN = "clean"          # Modern sans-serif
    BOLD = "bold"            # Impact-style
    TYPEWRITER = "typewriter"  # Monospace


# Font configurations for each style
STYLE_FONTS = {
    CaptionStyle.CLEAN: {
        "fontfile": "",  # Use system default
        "fontname": "Arial",
        "fontsize": 10,
        "fontcolor": "white",
        "borderw": 2,
        "bordercolor": "black",
    },
    CaptionStyle.BOLD: {
        "fontfile": "",
        "fontname": "Impact",
        "fontsize": 18,
        "fontcolor": "yellow",
        "borderw": 3,
        "bordercolor": "black",
    },
    CaptionStyle.TYPEWRITER: {
        "fontfile": "",
        "fontname": "Courier New",
        "fontsize": 18,
        "fontcolor": "white",
        "borderw": 2,
        "bordercolor": "black",
    },
}


def transcribe_video(video_path: Path, model: str = "base") -> List[Dict]:
    """
    Transcribe video audio using Whisper.
    
    Args:
        video_path: Path to video file
        model: Whisper model size (tiny, base, small, medium, large)
    
    Returns:
        List of segments with start, end, and text
    """
    import whisper
    
    print(f"Transcribing with Whisper ({model} model)...")
    
    model_obj = whisper.load_model(model)
    result = model_obj.transcribe(str(video_path), word_timestamps=True)
    
    segments = []
    for segment in result["segments"]:
        segments.append({
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"].strip(),
        })
    
    print(f"  Found {len(segments)} segments")
    return segments


def segments_to_srt(segments: List[Dict], output_path: Path) -> Path:
    """Convert segments to SRT subtitle file."""
    
    def format_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
    
    return output_path


def burn_captions(
    video_path: Path,
    output_path: Path,
    segments: Optional[List[Dict]] = None,
    srt_path: Optional[Path] = None,
    style: CaptionStyle = CaptionStyle.CLEAN,
    position: str = "bottom",  # "top", "center", "bottom"
) -> Path:
    """
    Burn captions into video using FFmpeg.
    
    Args:
        video_path: Source video
        output_path: Output path
        segments: Caption segments (will be converted to SRT)
        srt_path: Pre-existing SRT file (alternative to segments)
        style: Caption style preset
        position: Vertical position of captions
    
    Returns:
        Path to captioned video
    """
    # Get or create SRT file
    if srt_path is None:
        if segments is None:
            raise ValueError("Must provide either segments or srt_path")
        srt_path = Path(tempfile.mktemp(suffix=".srt"))
        segments_to_srt(segments, srt_path)
    
    # Get style config
    font_config = STYLE_FONTS[style]
    
    # Calculate vertical position
    margin_v = {
        "top": 50,
        "center": -1,  # Special case: center
        "bottom": 50,
    }.get(position, 50)
    
    alignment = {
        "top": 6,     # Top center
        "center": 10, # Middle center  
        "bottom": 2,  # Bottom center
    }.get(position, 2)
    
    # Build subtitle filter
    # Escape path for FFmpeg (handle colons and backslashes)
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    
    subtitle_filter = (
        f"subtitles='{srt_escaped}':"
        f"force_style='FontName={font_config['fontname']},"
        f"FontSize={font_config['fontsize']},"
        f"PrimaryColour=&H00FFFFFF,"  # White (ABGR format)
        f"OutlineColour=&H00000000,"  # Black outline
        f"BorderStyle=1,"
        f"Outline={font_config['borderw']},"
        f"Shadow=0,"
        f"Alignment={alignment},"
        f"MarginV={margin_v if margin_v > 0 else 200}'"
    )
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:a", "copy",
        str(output_path)
    ]
    
    print(f"Burning captions ({style.value} style, {position})...")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg subtitle burn failed: {result.stderr}")
    
    return output_path


def edit_transcript(segments: List[Dict]) -> List[Dict]:
    """
    Interactive transcript editor (terminal-based).
    Returns edited segments.
    """
    print("\n--- Transcript Editor ---")
    print("Enter new text for each segment, or press Enter to keep original.")
    print("Type 'SKIP' to remove a segment.\n")
    
    edited = []
    for i, seg in enumerate(segments):
        print(f"[{seg['start']:.1f}s - {seg['end']:.1f}s]")
        print(f"  Current: {seg['text']}")
        new_text = input("  New: ").strip()
        
        if new_text.upper() == "SKIP":
            print("  (skipped)")
            continue
        elif new_text:
            seg["text"] = new_text
        
        edited.append(seg)
    
    return edited


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        video = Path(sys.argv[1])
        segments = transcribe_video(video)
        for seg in segments[:5]:
            print(f"[{seg['start']:.1f}s] {seg['text']}")
