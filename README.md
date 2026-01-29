# YouTube Clipper

Extract, crop, and caption YouTube video clips from the command line.

## Requirements

- Python 3.8+
- FFmpeg (must be in PATH)
- yt-dlp
- openai-whisper

## Installation

```bash
cd youtube-clipper

# Install dependencies
pip install -r requirements.txt

# Install the CLI
pip install -e .
```

## Usage

### Extract a clip

```bash
# Basic clip extraction
clipper extract "https://youtube.com/watch?v=..." --start 1:30 --end 3:45

# With mobile aspect ratio (9:16)
clipper extract "https://youtube.com/..." -s 1:30 -e 3:45 --aspect mobile

# With captions
clipper extract "https://youtube.com/..." --captions --caption-style bold

# Full options
clipper extract "https://youtube.com/..." \
  --start 1:30 \
  --end 3:45 \
  --aspect mobile \
  --crop-x 60 \
  --captions \
  --caption-style clean \
  --caption-position bottom \
  --output my_clip.mp4
```

### Get video info

```bash
clipper info "https://youtube.com/watch?v=..."
```

### Transcribe a local video

```bash
clipper transcribe video.mp4 --output subtitles.srt
```

## Aspect Ratios

| Option | Ratio | Use Case |
|--------|-------|----------|
| `mobile` | 9:16 | TikTok, Reels, Shorts |
| `square` | 1:1 | Instagram feed |
| `desktop` | 16:9 | YouTube, standard |

## Caption Styles

- `clean` - Modern sans-serif, white text
- `bold` - Impact-style, yellow text
- `typewriter` - Monospace, white text

## Crop Position

Use `--crop-x` to control horizontal crop position:
- `0` = left edge
- `50` = center (default)
- `100` = right edge

## Auto Clip Finder (Phase 2)

Let AI find the best standalone clips in a video:

```bash
# Find 5 best clips
clipper find "https://youtube.com/watch?v=..." --count 5

# Find with constraints
clipper find "https://youtube.com/..." -n 10 --min-length 45 --max-length 90

# Find and export all at once
clipper find "https://youtube.com/..." --export-all --aspect mobile --captions

# Export specific clips from a previous find
clipper export 1,3,5 --aspect mobile
```

**How it works:**
1. Downloads and transcribes the full video (Whisper)
2. Breaks transcript into overlapping chunks
3. Sends each chunk to Claude to identify standalone moments
4. Deduplicates overlapping clips
5. Returns ranked list with scores and summaries

**Requires:** `ANTHROPIC_API_KEY` environment variable for Claude API.

## Coming Soon

- GUI editor with live preview
- More caption animation styles (word-by-word, karaoke)
- Smart crop with face detection
