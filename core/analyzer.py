"""
AI-powered clip detection using Claude.
Analyzes transcripts to find the best standalone moments.
"""

import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import tempfile


@dataclass
class ClipCandidate:
    """A potential clip identified by AI analysis."""
    start_time: float  # seconds
    end_time: float    # seconds
    transcript: str
    summary: str
    score: float
    reasoning: str
    thumbnail_path: Optional[Path] = None


def transcribe_full_video(video_path: Path, model: str = "base") -> List[Dict]:
    """
    Transcribe entire video with word-level timestamps.
    Returns segments with start, end, and text.
    """
    import whisper
    
    print(f"Transcribing full video with Whisper ({model})...")
    model_obj = whisper.load_model(model)
    result = model_obj.transcribe(
        str(video_path),
        word_timestamps=True,
        verbose=False
    )
    
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        })
    
    print(f"  Transcribed {len(segments)} segments ({result['segments'][-1]['end']:.0f}s total)")
    return segments


def chunk_transcript(
    segments: List[Dict],
    chunk_duration: float = 60.0,
    overlap: float = 15.0
) -> List[Dict]:
    """
    Break transcript into overlapping chunks for analysis.
    Each chunk is ~60s with 15s overlap to catch clips at boundaries.
    """
    if not segments:
        return []
    
    total_duration = segments[-1]["end"]
    chunks = []
    
    start = 0.0
    while start < total_duration:
        end = min(start + chunk_duration, total_duration)
        
        # Get segments in this range
        chunk_segments = [
            s for s in segments
            if s["start"] < end and s["end"] > start
        ]
        
        if chunk_segments:
            chunk_text = " ".join(s["text"] for s in chunk_segments)
            chunks.append({
                "start": start,
                "end": end,
                "text": chunk_text,
                "segments": chunk_segments,
            })
        
        start += chunk_duration - overlap
    
    return chunks


def analyze_chunk_with_claude(
    chunk: Dict,
    video_context: str = "",
    api_key: Optional[str] = None
) -> Optional[ClipCandidate]:
    """
    Send a transcript chunk to Claude for analysis.
    Returns a ClipCandidate if a good clip is found.
    """
    import anthropic
    
    if api_key is None:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""You are analyzing a video transcript to find standalone clips suitable for social media (TikTok, Reels, Shorts).

VIDEO CONTEXT: {video_context or "Unknown"}

TRANSCRIPT CHUNK (timestamps in seconds):
Start: {chunk['start']:.1f}s
End: {chunk['end']:.1f}s

Text:
{chunk['text']}

TASK: Evaluate if this chunk contains a good standalone clip (30-120 seconds ideal).

A GREAT clip:
- Makes complete sense WITHOUT any prior context
- Contains a complete thought, story, or insight
- Is interesting, funny, insightful, or memorable
- Would make someone stop scrolling
- Has a clear beginning and end (not mid-sentence)

Score this chunk 1-10 and if score >= 7, identify the EXACT best start and end timestamps.

Respond in JSON format:
{{
  "score": <1-10>,
  "has_good_clip": <true/false>,
  "reasoning": "<why this is/isn't a good clip>",
  "clip": {{
    "start": <seconds>,
    "end": <seconds>,
    "summary": "<one line description>",
    "transcript": "<the exact text for the clip>"
  }}
}}

If no good clip exists in this chunk, set "has_good_clip": false and omit "clip".
"""

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON from response
        text = response.content[0].text
        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            return None
        
        data = json.loads(json_match.group())
        
        if data.get("has_good_clip") and data.get("clip"):
            clip = data["clip"]
            return ClipCandidate(
                start_time=float(clip["start"]),
                end_time=float(clip["end"]),
                transcript=clip.get("transcript", ""),
                summary=clip.get("summary", ""),
                score=float(data.get("score", 0)),
                reasoning=data.get("reasoning", ""),
            )
        
        return None
        
    except Exception as e:
        print(f"  Warning: Claude analysis failed: {e}")
        return None


def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> Path:
    """Extract a single frame from video at given timestamp."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path)
    ]
    
    subprocess.run(cmd, capture_output=True)
    return output_path


def validate_clip_boundaries(
    video_path: Path,
    clip: ClipCandidate,
    adjustment_window: float = 2.0
) -> ClipCandidate:
    """
    Validate and potentially adjust clip boundaries by checking frames.
    Looks for scene transitions and adjusts to avoid cutting mid-transition.
    """
    # For now, just extract thumbnail at midpoint
    # Future: implement scene detection
    midpoint = (clip.start_time + clip.end_time) / 2
    
    thumb_path = Path(tempfile.mktemp(suffix=".jpg"))
    extract_frame(video_path, midpoint, thumb_path)
    clip.thumbnail_path = thumb_path
    
    return clip


def find_clips(
    video_path: Path,
    count: int = 5,
    min_length: float = 30.0,
    max_length: float = 120.0,
    whisper_model: str = "base",
    video_context: str = "",
) -> List[ClipCandidate]:
    """
    Find the best clips in a video.
    
    Args:
        video_path: Path to video file
        count: Number of clips to return
        min_length: Minimum clip length in seconds
        max_length: Maximum clip length in seconds
        whisper_model: Whisper model size
        video_context: Optional context about the video (title, description)
    
    Returns:
        List of ClipCandidates sorted by score (highest first)
    """
    print(f"\n🔍 Finding {count} best clips in: {video_path.name}")
    
    # Step 1: Transcribe
    print("\n📝 Step 1: Transcribing...")
    segments = transcribe_full_video(video_path, model=whisper_model)
    
    # Step 2: Chunk for analysis
    print("\n📊 Step 2: Analyzing transcript...")
    chunks = chunk_transcript(segments, chunk_duration=90.0, overlap=30.0)
    print(f"  Created {len(chunks)} overlapping chunks")
    
    # Step 3: Analyze each chunk with Claude
    candidates = []
    for i, chunk in enumerate(chunks):
        print(f"  Analyzing chunk {i+1}/{len(chunks)}...", end=" ")
        clip = analyze_chunk_with_claude(chunk, video_context)
        
        if clip:
            # Filter by length
            duration = clip.end_time - clip.start_time
            if min_length <= duration <= max_length:
                candidates.append(clip)
                print(f"✓ Found clip (score: {clip.score})")
            else:
                print(f"✗ Clip too {'short' if duration < min_length else 'long'}")
        else:
            print("✗ No good clip")
    
    # Step 4: Deduplicate overlapping clips
    print("\n🔄 Step 3: Deduplicating...")
    candidates = deduplicate_clips(candidates)
    
    # Step 5: Sort by score and take top N
    candidates.sort(key=lambda c: c.score, reverse=True)
    top_clips = candidates[:count]
    
    # Step 6: Validate boundaries and generate thumbnails
    print(f"\n🖼️  Step 4: Generating previews...")
    for i, clip in enumerate(top_clips):
        print(f"  Clip {i+1}: {clip.start_time:.1f}s - {clip.end_time:.1f}s")
        validate_clip_boundaries(video_path, clip)
    
    return top_clips


def deduplicate_clips(clips: List[ClipCandidate], overlap_threshold: float = 0.5) -> List[ClipCandidate]:
    """
    Remove overlapping clips, keeping the higher-scored one.
    """
    if not clips:
        return []
    
    # Sort by score descending
    sorted_clips = sorted(clips, key=lambda c: c.score, reverse=True)
    
    kept = []
    for clip in sorted_clips:
        # Check if this clip overlaps significantly with any kept clip
        dominated = False
        for kept_clip in kept:
            overlap = calculate_overlap(clip, kept_clip)
            if overlap > overlap_threshold:
                dominated = True
                break
        
        if not dominated:
            kept.append(clip)
    
    return kept


def calculate_overlap(clip1: ClipCandidate, clip2: ClipCandidate) -> float:
    """Calculate overlap ratio between two clips."""
    start = max(clip1.start_time, clip2.start_time)
    end = min(clip1.end_time, clip2.end_time)
    
    if start >= end:
        return 0.0
    
    overlap_duration = end - start
    min_duration = min(
        clip1.end_time - clip1.start_time,
        clip2.end_time - clip2.start_time
    )
    
    return overlap_duration / min_duration if min_duration > 0 else 0.0


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def print_clips_table(clips: List[ClipCandidate]):
    """Print clips in a nice table format."""
    print("\n" + "=" * 70)
    print(f"{'#':^3} {'Start':^8} {'End':^8} {'Score':^6} {'Summary':<40}")
    print("-" * 70)
    
    for i, clip in enumerate(clips, 1):
        summary = clip.summary[:37] + "..." if len(clip.summary) > 40 else clip.summary
        print(f"{i:^3} {format_time(clip.start_time):^8} {format_time(clip.end_time):^8} {clip.score:^6.1f} {summary:<40}")
    
    print("=" * 70)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        video = Path(sys.argv[1])
        clips = find_clips(video, count=5)
        print_clips_table(clips)
