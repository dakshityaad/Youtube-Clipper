#!/usr/bin/env python3
"""
YouTube Clipper CLI
Extract, crop, and caption YouTube video clips.
"""

import click
from pathlib import Path
from typing import Optional

from core.downloader import download_clip, get_video_info
from core.processor import crop_video, AspectRatio
from core.captioner import transcribe_video, burn_captions, CaptionStyle, edit_transcript


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """YouTube Clipper - Extract, crop, and caption video clips."""
    pass


@cli.command()
@click.argument("url")
@click.option("--start", "-s", help="Start time (e.g., 1:30 or 90)")
@click.option("--end", "-e", help="End time (e.g., 3:45 or 225)")
@click.option(
    "--aspect",
    "-a",
    type=click.Choice(["mobile", "square", "desktop"]),
    default=None,
    help="Target aspect ratio",
)
@click.option(
    "--crop-x",
    type=float,
    default=50.0,
    help="Crop horizontal position: 0=left, 50=center, 100=right",
)
@click.option("--captions/--no-captions", default=False, help="Add captions")
@click.option(
    "--caption-style",
    type=click.Choice(["clean", "bold", "typewriter"]),
    default="clean",
    help="Caption style preset",
)
@click.option(
    "--caption-position",
    type=click.Choice(["top", "center", "bottom"]),
    default="bottom",
    help="Caption vertical position",
)
@click.option("--edit-transcript", is_flag=True, help="Edit transcript before burning")
@click.option("--whisper-model", default="base", help="Whisper model size")
@click.option("-o", "--output", type=click.Path(), help="Output file path")
def extract(
    url: str,
    start: Optional[str],
    end: Optional[str],
    aspect: Optional[str],
    crop_x: float,
    captions: bool,
    caption_style: str,
    caption_position: str,
    edit_transcript: bool,
    whisper_model: str,
    output: Optional[str],
):
    """
    Extract a clip from a YouTube video.
    
    Examples:
    
        clipper extract "https://youtube.com/..." --start 1:30 --end 3:45
        
        clipper extract "https://youtube.com/..." -s 90 -e 225 --aspect mobile
        
        clipper extract "https://youtube.com/..." --captions --caption-style bold
    """
    # Determine output path
    if output:
        output_path = Path(output)
    else:
        # Generate from video title
        info = get_video_info(url)
        safe_title = "".join(c for c in info["title"][:50] if c.isalnum() or c in " -_")
        output_path = Path(f"{safe_title.strip()}_clip.mp4")
    
    print(f"\n🎬 YouTube Clipper")
    print(f"   URL: {url}")
    print(f"   Output: {output_path}\n")
    
    # Step 1: Download
    print("📥 Step 1: Downloading...")
    raw_video = download_clip(url, start, end)
    current_video = raw_video
    
    # Step 2: Crop (if aspect ratio specified)
    if aspect:
        print(f"\n✂️  Step 2: Cropping to {aspect}...")
        aspect_enum = {
            "mobile": AspectRatio.MOBILE,
            "square": AspectRatio.SQUARE,
            "desktop": AspectRatio.DESKTOP,
        }[aspect]
        
        cropped_path = output_path.with_suffix(".cropped.mp4")
        crop_video(current_video, cropped_path, aspect_enum, crop_x)
        current_video = cropped_path
    else:
        print("\n✂️  Step 2: Skipping crop (no aspect ratio specified)")
    
    # Step 3: Captions
    if captions:
        print(f"\n💬 Step 3: Adding captions...")
        
        # Transcribe
        segments = transcribe_video(current_video, model=whisper_model)
        
        # Edit if requested
        if edit_transcript:
            segments = edit_transcript(segments)
        
        # Burn captions
        style_enum = CaptionStyle[caption_style.upper()]
        captioned_path = output_path.with_suffix(".captioned.mp4")
        burn_captions(
            current_video,
            captioned_path,
            segments=segments,
            style=style_enum,
            position=caption_position,
        )
        current_video = captioned_path
    else:
        print("\n💬 Step 3: Skipping captions")
    
    # Step 4: Final output
    print(f"\n📦 Step 4: Finalizing...")
    if current_video != output_path:
        import shutil
        shutil.move(str(current_video), str(output_path))
    
    # Cleanup temp files
    for temp_file in [raw_video, output_path.with_suffix(".cropped.mp4")]:
        if temp_file != output_path and temp_file.exists():
            temp_file.unlink()
    
    print(f"\n✅ Done! Saved to: {output_path}")
    print(f"   Size: {output_path.stat().st_size / (1024*1024):.1f} MB")


@cli.command()
@click.argument("url")
def info(url: str):
    """Show video information without downloading."""
    info = get_video_info(url)
    
    duration_min = info["duration"] // 60
    duration_sec = info["duration"] % 60
    
    print(f"\n📺 Video Info")
    print(f"   Title: {info['title']}")
    print(f"   Channel: {info.get('uploader', 'Unknown')}")
    print(f"   Duration: {duration_min}:{duration_sec:02d}")
    print(f"   Views: {info.get('view_count', 'N/A'):,}")
    print(f"   Upload: {info.get('upload_date', 'Unknown')}")


@cli.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--model", default="base", help="Whisper model size")
@click.option("-o", "--output", type=click.Path(), help="Output SRT file")
def transcribe(video: str, model: str, output: Optional[str]):
    """Transcribe a local video file."""
    from core.captioner import segments_to_srt
    
    video_path = Path(video)
    segments = transcribe_video(video_path, model=model)
    
    if output:
        srt_path = Path(output)
    else:
        srt_path = video_path.with_suffix(".srt")
    
    segments_to_srt(segments, srt_path)
    print(f"\n✅ Transcript saved to: {srt_path}")


if __name__ == "__main__":
    cli()
