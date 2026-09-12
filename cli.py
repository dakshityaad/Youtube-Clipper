#!/usr/bin/env python3
"""
YouTube Clipper CLI
Extract, crop, and caption YouTube video clips.
"""

import re
import shutil
from datetime import datetime

import click
from pathlib import Path
from typing import List, Optional, Tuple

from core.downloader import download_clip, get_video_info
from core.processor import crop_video, trim_video, AspectRatio
from core.captioner import transcribe_video, burn_captions, CaptionStyle, edit_transcript
from core.analyzer import find_clips, print_clips_table, format_time
from core.timecode import format_ffmpeg_timestamp
from core.tui import run_batch_wizard, WizardDefaults

BATCH_PADDING_SECONDS = 10


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """YouTube Clipper - Extract, crop, and caption video clips."""
    pass


def _remove_if_exists(path: Optional[Path]) -> None:
    """Remove a temporary file without hiding an earlier processing error."""
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


@cli.command()
@click.option(
    "--aspect", "-a",
    type=click.Choice(["mobile", "square", "desktop"]),
    default="mobile", show_default=True,
    help="Target aspect ratio",
)
@click.option("--crop-x", type=float, default=50.0, show_default=True,
              help="Crop horizontal position: 0=left, 50=center, 100=right")
@click.option("--captions/--no-captions", default=True, show_default=True,
              help="Add captions to every clip")
@click.option("--caption-style", type=click.Choice(["clean", "bold", "typewriter"]),
              default="clean", show_default=True, help="Caption style preset")
@click.option("--caption-position", type=click.Choice(["top", "center", "bottom"]),
              default="bottom", show_default=True, help="Caption vertical position")
@click.option("--edit-transcript", is_flag=True,
              help="Edit each clip transcript before captions are burned")
@click.option("--whisper-model", default="base", show_default=True,
              help="Whisper model size")
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path),
              default=Path("output"), show_default=True,
              help="Folder for generated clips")
def batch(
    aspect: str,
    crop_x: float,
    captions: bool,
    caption_style: str,
    caption_position: str,
    edit_transcript: bool,
    whisper_model: str,
    output_dir: Path,
):
    """Interactively create several clips from one YouTube video."""
    config = run_batch_wizard(
        WizardDefaults(
            aspect=aspect,
            captions=captions,
            caption_style=caption_style,
            caption_position=caption_position,
            padding_seconds=BATCH_PADDING_SECONDS,
        )
    )
    if config is None:
        click.echo("Cancelled.")
        return

    url = config.url
    aspect = config.aspect
    captions = config.captions
    caption_style = config.caption_style
    caption_position = config.caption_position
    download_once = config.download_once
    padding_seconds = config.padding_seconds
    ranges: List[Tuple[float, float]] = config.ranges

    if not ranges:
        click.echo("No clips entered; nothing to do.")
        return

    click.echo(f"\n🎬 Starting batch: {len(ranges)} clip(s) from {url}\n")


    batch_folder = datetime.now().strftime("batch_%Y-%m-%d_%H-%M-%S")
    output_dir = output_dir / batch_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    aspect_enum = {
        "mobile": AspectRatio.MOBILE,
        "square": AspectRatio.SQUARE,
        "desktop": AspectRatio.DESKTOP,
    }[aspect]
    style_enum = CaptionStyle[caption_style.upper()]

    source_video: Optional[Path] = None
    if download_once:
        click.echo("\n📥 Downloading source video once...")
        source_video = Path(download_clip(url))
        click.echo("✓ Source downloaded")
    else:
        click.echo("\n📥 Each requested clip will be downloaded separately.")

    completed = 0
    try:
        for index, range_value in enumerate(ranges, 1):
            output_path = output_dir / f"clip_{index:02d}.mp4"
            trimmed_path = output_dir / f".clip_{index:02d}.trimmed.mp4"
            cropped_path = output_dir / f".clip_{index:02d}.cropped.mp4"
            captioned_path = output_dir / f".clip_{index:02d}.captioned.mp4"
            downloaded_clip: Optional[Path] = None

            if range_value == (-1.0, -1.0):
                start = 0.0
                end = 0.0
                clip_label = "FULL VIDEO"
            else:
                start, end = range_value
                clip_label = f"{format_ffmpeg_timestamp(start)} - {format_ffmpeg_timestamp(end)}"

            click.echo(
                f"\n🎞️  Creating clip {index}/{len(ranges)} "
                f"({clip_label})..."
            )
            try:
                if range_value == (-1.0, -1.0):
                    if download_once:
                        clip_input = source_video
                    else:
                        downloaded_clip = Path(download_clip(url))
                        clip_input = downloaded_clip
                elif download_once:
                    trim_video(
                        source_video,
                        trimmed_path,
                        start_time=format_ffmpeg_timestamp(start),
                        end_time=format_ffmpeg_timestamp(end),
                    )
                    clip_input = trimmed_path
                else:
                    downloaded_clip = Path(
                        download_clip(url, format_ffmpeg_timestamp(start), format_ffmpeg_timestamp(end))
                    )
                    clip_input = downloaded_clip

                crop_video(clip_input, cropped_path, aspect_enum, crop_x)

                if captions:
                    segments = transcribe_video(cropped_path, model=whisper_model)
                    if edit_transcript:
                        segments = edit_transcript(segments)
                    burn_captions(
                        cropped_path,
                        captioned_path,
                        segments=segments,
                        style=style_enum,
                        position=caption_position,
                    )
                    shutil.move(str(captioned_path), str(output_path))
                else:
                    shutil.move(str(cropped_path), str(output_path))

                completed += 1
                click.echo(f"✓ Saved: {output_path}")
            except Exception as exc:
                click.echo(f"✗ Clip {index} failed: {exc}", err=True)
            finally:
                _remove_if_exists(trimmed_path)
                _remove_if_exists(cropped_path)
                _remove_if_exists(captioned_path)
                _remove_if_exists(downloaded_clip)
    finally:
        _remove_if_exists(source_video)

    click.echo(f"\n✅ Finished {completed}/{len(ranges)} clips.")
    click.echo(f"   Output: {output_dir.resolve()}")


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


@cli.command()
@click.argument("url")
@click.option("--count", "-n", default=5, help="Number of clips to find")
@click.option("--min-length", default=30.0, help="Minimum clip length in seconds")
@click.option("--max-length", default=120.0, help="Maximum clip length in seconds")
@click.option("--whisper-model", default="base", help="Whisper model size")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table")
@click.option("--export-all", is_flag=True, help="Export all found clips")
@click.option("--aspect", "-a", type=click.Choice(["mobile", "square", "desktop"]), default=None)
@click.option("--captions/--no-captions", default=True)
def find(
    url: str,
    count: int,
    min_length: float,
    max_length: float,
    whisper_model: str,
    output: str,
    export_all: bool,
    aspect: Optional[str],
    captions: bool,
):
    """
    Find the best clips in a YouTube video using AI.
    
    Examples:
    
        clipper find "https://youtube.com/..." --count 5
        
        clipper find "https://youtube.com/..." -n 10 --min-length 45 --max-length 90
        
        clipper find "https://youtube.com/..." --export-all --aspect mobile
    """
    import json as json_module
    
    # Get video info
    print(f"\n🎬 YouTube Clipper - Auto Clip Finder")
    info = get_video_info(url)
    print(f"   Video: {info['title']}")
    print(f"   Duration: {info['duration'] // 60}:{info['duration'] % 60:02d}")
    
    # Download full video
    print(f"\n📥 Downloading video...")
    video_path = download_clip(url)
    
    # Find clips
    video_context = f"Title: {info['title']}. Channel: {info.get('uploader', 'Unknown')}"
    clips = find_clips(
        video_path,
        count=count,
        min_length=min_length,
        max_length=max_length,
        whisper_model=whisper_model,
        video_context=video_context,
    )
    
    if not clips:
        print("\n❌ No good clips found.")
        return
    
    # Output results
    if output == "json":
        result = {
            "video": {
                "title": info["title"],
                "url": url,
                "duration": info["duration"],
            },
            "clips": [
                {
                    "index": i + 1,
                    "start": clip.start_time,
                    "end": clip.end_time,
                    "start_formatted": format_time(clip.start_time),
                    "end_formatted": format_time(clip.end_time),
                    "duration": clip.end_time - clip.start_time,
                    "score": clip.score,
                    "summary": clip.summary,
                    "transcript": clip.transcript,
                    "reasoning": clip.reasoning,
                }
                for i, clip in enumerate(clips)
            ]
        }
        print(json_module.dumps(result, indent=2))
    else:
        print_clips_table(clips)
        
        # Save clips metadata
        clips_file = Path("clips_found.json")
        with open(clips_file, "w") as f:
            json_module.dump({
                "video_path": str(video_path),
                "url": url,
                "clips": [
                    {
                        "index": i + 1,
                        "start": c.start_time,
                        "end": c.end_time,
                        "score": c.score,
                        "summary": c.summary,
                    }
                    for i, c in enumerate(clips)
                ]
            }, f, indent=2)
        print(f"\n💾 Clip data saved to: {clips_file}")
        print(f"   Run: clipper export 1,3,5 --aspect mobile")
    
    # Export if requested
    if export_all and aspect:
        print(f"\n📦 Exporting {len(clips)} clips...")
        aspect_enum = {
            "mobile": AspectRatio.MOBILE,
            "square": AspectRatio.SQUARE,
            "desktop": AspectRatio.DESKTOP,
        }[aspect]
        
        for i, clip in enumerate(clips, 1):
            safe_title = "".join(c for c in info["title"][:30] if c.isalnum() or c in " -_")
            output_path = Path(f"{safe_title}_clip{i}_{aspect}.mp4")
            
            print(f"\n  Clip {i}: {format_time(clip.start_time)} - {format_time(clip.end_time)}")
            
            # Download just this segment
            clip_video = download_clip(
                url,
                start_time=str(int(clip.start_time)),
                end_time=str(int(clip.end_time))
            )
            
            # Crop
            cropped = output_path.with_suffix(".cropped.mp4")
            crop_video(clip_video, cropped, aspect_enum)
            
            # Captions
            if captions:
                from core.captioner import transcribe_video, burn_captions, CaptionStyle
                segments = transcribe_video(cropped)
                burn_captions(cropped, output_path, segments=segments, style=CaptionStyle.CLEAN)
                cropped.unlink()
            else:
                import shutil
                shutil.move(str(cropped), str(output_path))
            
            clip_video.unlink()
            print(f"  ✓ Saved: {output_path}")
        
        print(f"\n✅ Exported {len(clips)} clips!")


@cli.command()
@click.argument("clip_ids")
@click.option("--aspect", "-a", type=click.Choice(["mobile", "square", "desktop"]), default="mobile")
@click.option("--captions/--no-captions", default=True)
@click.option("--caption-style", type=click.Choice(["clean", "bold", "typewriter"]), default="clean")
def export(clip_ids: str, aspect: str, captions: bool, caption_style: str):
    """
    Export previously found clips by index.
    
    Examples:
    
        clipper export 1,3,5 --aspect mobile
        
        clipper export 2 --aspect square --no-captions
    """
    import json as json_module
    
    # Load clips metadata
    clips_file = Path("clips_found.json")
    if not clips_file.exists():
        print("❌ No clips found. Run 'clipper find' first.")
        return
    
    with open(clips_file) as f:
        data = json_module.load(f)
    
    # Parse clip IDs
    ids = [int(x.strip()) for x in clip_ids.split(",")]
    
    video_path = Path(data["video_path"])
    url = data["url"]
    
    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        print("   Re-run 'clipper find' to download again.")
        return
    
    aspect_enum = {
        "mobile": AspectRatio.MOBILE,
        "square": AspectRatio.SQUARE,
        "desktop": AspectRatio.DESKTOP,
    }[aspect]
    
    style_enum = CaptionStyle[caption_style.upper()]
    
    for clip_id in ids:
        clip_data = next((c for c in data["clips"] if c["index"] == clip_id), None)
        if not clip_data:
            print(f"⚠️  Clip #{clip_id} not found, skipping.")
            continue
        
        print(f"\n📦 Exporting clip #{clip_id}...")
        
        output_path = Path(f"clip_{clip_id}_{aspect}.mp4")
        
        # Trim
        from core.processor import trim_video
        trimmed = output_path.with_suffix(".trimmed.mp4")
        trim_video(
            video_path,
            trimmed,
            start_time=format_time(clip_data["start"]),
            end_time=format_time(clip_data["end"])
        )
        
        # Crop
        cropped = output_path.with_suffix(".cropped.mp4")
        crop_video(trimmed, cropped, aspect_enum)
        trimmed.unlink()
        
        # Captions
        if captions:
            segments = transcribe_video(cropped)
            burn_captions(cropped, output_path, segments=segments, style=style_enum)
            cropped.unlink()
        else:
            import shutil
            shutil.move(str(cropped), str(output_path))
        
        print(f"✓ Saved: {output_path}")
    
    print(f"\n✅ Export complete!")


if __name__ == "__main__":
    cli()
