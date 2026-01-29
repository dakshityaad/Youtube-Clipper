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

## Coming Soon

- Auto clip finder (AI-powered best moment detection)
- GUI editor
- More caption animation styles
