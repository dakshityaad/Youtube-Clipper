"""
Video processing with FFmpeg.
Handles cropping, aspect ratio changes, and basic transformations.
"""

import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum


class AspectRatio(Enum):
    ORIGINAL = "original"
    MOBILE = "9:16"      # TikTok, Reels, Shorts
    SQUARE = "1:1"       # Instagram feed
    DESKTOP = "16:9"     # YouTube, standard


def get_video_dimensions(video_path: Path) -> Tuple[int, int]:
    """Get video width and height."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "v:0",
        str(video_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return stream["width"], stream["height"]


def crop_video(
    input_path: Path,
    output_path: Path,
    aspect_ratio: AspectRatio = AspectRatio.MOBILE,
    crop_x_percent: float = 50.0,
) -> Path:
    """
    Crop video to target aspect ratio.
    
    Args:
        input_path: Source video file
        output_path: Destination path
        aspect_ratio: Target aspect ratio
        crop_x_percent: Horizontal crop position (0=left, 50=center, 100=right)
    
    Returns:
        Path to cropped video
    """
    width, height = get_video_dimensions(input_path)

    if aspect_ratio is AspectRatio.ORIGINAL:
        shutil.copy2(input_path, output_path)
        print(f"Keeping original format ({width}x{height})")
        return output_path
    
    # Parse target ratio
    ratio_parts = aspect_ratio.value.split(":")
    target_w_ratio = int(ratio_parts[0])
    target_h_ratio = int(ratio_parts[1])
    
    # Calculate crop dimensions
    # Try to maximize the crop area while maintaining aspect ratio
    target_ratio = target_w_ratio / target_h_ratio
    current_ratio = width / height
    
    if current_ratio > target_ratio:
        # Video is wider than target - crop width
        new_height = height
        new_width = int(height * target_ratio)
    else:
        # Video is taller than target - crop height
        new_width = width
        new_height = int(width / target_ratio)
    
    # Calculate crop position
    # crop_x_percent: 0 = left edge, 50 = center, 100 = right edge
    max_x_offset = width - new_width
    max_y_offset = height - new_height
    
    x_offset = int(max_x_offset * (crop_x_percent / 100.0))
    y_offset = max_y_offset // 2  # Always center vertically
    
    # Build FFmpeg filter
    crop_filter = f"crop={new_width}:{new_height}:{x_offset}:{y_offset}"
    
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", str(input_path),
        "-vf", crop_filter,
        "-c:a", "copy",  # Keep audio as-is
        str(output_path)
    ]
    
    print(f"Cropping to {aspect_ratio.value} (x={crop_x_percent}%)")
    print(f"  {width}x{height} → {new_width}x{new_height}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg crop failed: {result.stderr}")
    
    return output_path


def trim_video(
    input_path: Path,
    output_path: Path,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Path:
    """
    Trim video to specific time range.
    More precise than yt-dlp's download sections for local files.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
    ]
    
    if start_time:
        cmd.extend(["-ss", start_time])
    if end_time:
        cmd.extend(["-to", end_time])
    
    cmd.extend([
        "-c", "copy",  # Fast copy without re-encoding
        str(output_path)
    ])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg trim failed: {result.stderr}")
    
    return output_path


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        video = Path(sys.argv[1])
        w, h = get_video_dimensions(video)
        print(f"Dimensions: {w}x{h}")
