# YouTube Clipper

YouTube Clipper is a Python CLI for turning a YouTube video into clean short clips for social media. It can:

- download a YouTube video or a selected time range
- crop the video to a target aspect ratio
- add burned-in captions with Whisper + FFmpeg
- process several clips in a single guided batch run
- suggest standout moments from a full video transcript

This project is designed to be simple and local-first: you point it at a YouTube URL, choose your crop and timing, and export a finished clip.

## What the app does today

The repository already includes a working CLI with these commands:

- `clipper batch` — guided multi-clip workflow for one YouTube video
- `clipper extract` — export a single clip from a URL
- `clipper info` — show metadata about a video
- `clipper transcribe` — transcribe a local file into an SRT subtitle file
- `clipper find` — search a video for likely clip candidates using transcript analysis
- `clipper export` — export a selected set of clips from a previous `find` run

## Features

### Manual clip creation

Use `extract` to pull a time slice from YouTube and turn it into a final MP4 with optional cropping and captions.

```bash
clipper extract "https://www.youtube.com/watch?v=VIDEO_ID" \
  --start 1:30 \
  --end 3:45 \
  --aspect mobile \
  --captions
```

### Batch processing

Use `batch` when you already know the times you want to create. The app walks through:

1. YouTube URL
2. output aspect ratio (`mobile`, `square`, or `desktop`)
3. whether to caption every clip
4. caption style and position
5. whether to reuse one downloaded source for all clips or download each clip separately
6. padding around each range
7. the ranges to make

Example ranges:

```text
(03:43 - 04:32)
(08:08 - 10:45)
(13:30 - 14:00)
DONE
```

The app writes each batch into a unique output folder like:

```text
output/batch_2026-09-12_18-40-12/
```

Each clip is saved as `clip_01.mp4`, `clip_02.mp4`, and so on.

### Auto clip finding

`clipper find` downloads the video, transcribes it, chunks the transcript, and searches for strong standalone moments. It can output either a table or JSON result.

```bash
clipper find "https://www.youtube.com/watch?v=VIDEO_ID" --count 5 --aspect mobile
```

This feature uses Whisper and Anthropic. If you use the AI-assisted chunk analysis, make sure the environment variable `ANTHROPIC_API_KEY` is set.

## Installation

### 1) Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2) Install the CLI in editable mode

```bash
pip install -e .
```

This installs the `clipper` command.

### 3) Install FFmpeg

FFmpeg and ffprobe must be available on your system PATH.

On Windows, install FFmpeg and make sure the binary folder is added to PATH.

## Requirements

- Python 3.8+
- FFmpeg + ffprobe in PATH
- Internet access for downloading YouTube videos
- `clipper` command installed after `pip install -e .`

Optional:

- `ANTHROPIC_API_KEY` for the transcript-based clip finder

## Typical commands

```bash
# Show video metadata
clipper info "https://www.youtube.com/watch?v=VIDEO_ID"

# Create one clip with captions
clipper extract "https://www.youtube.com/watch?v=VIDEO_ID" \
  --start 1:30 \
  --end 3:45 \
  --aspect mobile \
  --captions

# Run the batch wizard
clipper batch

# Transcribe a local video file to SRT
clipper transcribe video.mp4 -o transcript.srt

# Find suggested clips in a video
clipper find "https://www.youtube.com/watch?v=VIDEO_ID" --count 5

# Export chosen clips from earlier results
clipper export 1,3,5 --aspect mobile
```

## Project structure

```text
youtube-clipper/
├── cli.py                  # entry point and CLI commands
├── core/
│   ├── downloader.py       # downloads YouTube videos and ranges
│   ├── processor.py        # trim/crop logic with FFmpeg
│   ├── captioner.py        # Whisper transcription and caption burning
│   ├── analyzer.py         # clip recommendation logic
│   ├── timecode.py         # timestamp parsing/formatting helpers
│   └── tui.py              # batch wizard UI
├── output/                 # generated clip output folders
├── requirements.txt        # Python dependencies
├── setup.py                # package metadata and console entry point
├── PLAN.md                 # project plan/status
├── README.md               # user-facing overview
├── clips_found.json        # created by `clipper find`
└── .gitignore              # project ignore rules
```

## Notes

- The batch mode is the main workflow for creating multiple clips quickly.
- Captions are burned into the final output video using FFmpeg subtitle rendering.
- The app is designed for real-world editing workflows, not a polished desktop editor.
- This project is still evolving, but the core CLI workflows above are already implemented.

## License

This project is licensed under the MIT License.

Copyright (c) 2026 Dakshit Yadav.

## Getting help

Use the built-in CLI help:

```bash
clipper --help
clipper batch --help
clipper extract --help
```

If a command fails, the most common causes are missing FFmpeg, missing dependencies, or an invalid YouTube URL.
