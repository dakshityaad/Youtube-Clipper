# YouTube Clipper — Project Plan

## Purpose

YouTube Clipper is a local-first CLI for creating short social-ready video clips from YouTube content. The current codebase focuses on a practical workflow:

1. download a source video or segment
2. choose a crop ratio
3. trim the clip to exact timestamps
4. transcribe and burn subtitles when needed
5. export finished MP4s
6. optionally find strong clip candidates automatically

This plan matches the repository as it exists today, not a future product fantasy.

---

## Current status

The project already has a working CLI and a batch wizard. The main implemented flows are:

- `clipper batch` for multi-clip conversion from one video
- `clipper extract` for one-off clip creation
- `clipper info` for metadata lookup
- `clipper transcribe` for local transcript export
- `clipper find` for AI-style candidate detection
- `clipper export` for exporting clips found by a previous search

The app is organized around a few core modules:

- `core/downloader.py` — YouTube downloads and time-range downloads
- `core/processor.py` — cropping and trimming via FFmpeg
- `core/captioner.py` — Whisper transcription and FFmpeg subtitle burn-in
- `core/analyzer.py` — transcript chunking and clip recommendation logic
- `core/tui.py` — interactive batch wizard built with Textual

---

## User goals

### Goal 1: Make a precise short clip

A creator has a YouTube video, knows the interesting moment, and wants a social-friendly version.

Example:

```bash
clipper extract "https://www.youtube.com/watch?v=VIDEO_ID" \
  --start 1:30 \
  --end 3:45 \
  --aspect mobile \
  --captions
```

### Goal 2: Create many clips from one video

A creator has a long video and wants several clips with consistent settings.

Example:

```bash
clipper batch
```

The batch flow asks for the URL, aspect ratio, captions, timing padding, and the clip ranges.

### Goal 3: Find strong moments automatically

A creator wants the app to suggest clip candidates from a full transcript.

Example:

```bash
clipper find "https://www.youtube.com/watch?v=VIDEO_ID" --count 5
```

This is not a full AI editor yet, but it does perform transcript-based chunk analysis and returns ranked clip suggestions.

---

## Current workflow

```text
YouTube URL
   ↓
Download source or selected range
   ↓
Trim to exact range
   ↓
Crop to mobile / square / desktop
   ↓
Optionally transcribe and burn captions
   ↓
Save final MP4
```

For batch workflows, the project reuses the same pipeline for every range and stores each run in its own dated folder under `output/`.

---

## Actual feature map

### Manual clip creation

Implemented and ready to use:

- precise start/end range selection
- three aspect presets: `mobile`, `square`, `desktop`
- optional burned-in captions
- custom caption style and vertical position
- output file naming and folder management

### Batch mode

Implemented and ready to use:

- guided wizard with direct terminal prompts
- one-time source download option or per-clip download option
- automatic padding before and after each range
- multiple timestamps in one run
- results stored in a dated batch folder

### Transcript and captioning

Implemented:

- Whisper-based transcription for videos
- SRT export from transcript segments
- language model-based subtitle burn-in with FFmpeg
- optional transcript editing in interactive terminal mode

### Auto clip suggestions

Partially implemented:

- transcript chunking
- Whisper transcription of the full video
- candidate extraction using AI prompt analysis
- ranking and export support from prior results

This depends on Anthropic access via `ANTHROPIC_API_KEY` and is best thought of as an assisted clip-suggestion tool, not a full editorial suite.

---

## Near-term roadmap

### Phase 1: polish the current CLI

Focus on reliability and usability:

- validate better error messages for missing FFmpeg / invalid URLs
- improve output naming and destination handling
- clean up export and retry behavior
- improve documentation and command examples

### Phase 2: stronger clip-finding logic

- better transcript segmentation and scoring
- deduplication of overlapping suggestions
- more robust candidate export workflow
- saved clip metadata and summaries

### Phase 3: advanced editing improvements

- tune crop and caption quality settings
- add more configurable caption presets
- expand transcript editing workflows
- improve support for local video files and Windows-friendly paths

---

## Out of scope for now

The repository does not currently include a real GUI editor or a full video timeline interface. The project is still CLI-first and intentionally lightweight.

That means the current trajectory is:

- practical CLI tooling
- solid batch workflow
- simple automatic suggestions
- better reliability over a polished desktop UI

---

## Success definition

The project is successful when a user can do all of the following without needing a full video editor:

- take a YouTube link
- choose a segment
- crop it for a social platform
- add captions if needed
- export the final MP4 quickly
- run a batch of multiple clips from the same video

That is the real product focus of this codebase right now.

