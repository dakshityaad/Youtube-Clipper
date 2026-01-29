# YouTube Clipper - Project Plan

## Vision
A local-first tool to extract, transform, and caption YouTube clips for social media. Two modes:
1. **Manual** — You specify the timestamps, crop, and captions
2. **Auto** — AI finds the best standalone moments from a full video

Built for content creators who need quick, high-quality clips without complex video editing software.

---

## User Stories

### Story 1: Quick Manual Clip
> "I found a great 45-second moment in a podcast. I want to crop it for TikTok (9:16), add captions, and export."

```bash
clipper extract "https://youtube.com/..." \
  --start 14:22 --end 15:07 \
  --aspect mobile \
  --captions
```

### Story 2: Batch from Transcript
> "I have a 2-hour interview. Find me the 5 best standalone clips, let me pick which ones to export."

```bash
clipper find "https://youtube.com/..." --count 5
# Outputs a list with previews
clipper export --clips 1,3,5 --aspect mobile --captions
```

### Story 3: Fine-Tune in GUI
> "I want to scrub through the video, adjust crop position to keep the speaker's face centered, and tweak the auto-generated captions before exporting."

```bash
clipper gui video.mp4
# Opens visual editor
```

---

## Phase 1: Manual Clip Extraction (CLI)

### Workflow
```
YouTube URL → Download → Trim → Crop → Transcribe → Burn Captions → Export
     │           │         │      │         │              │           │
     └───────────┴─────────┴──────┴─────────┴──────────────┴───────────┘
                              (each step optional)
```

### Commands

```bash
# Basic extraction (just download + trim)
clipper extract URL --start 1:30 --end 3:45

# With crop
clipper extract URL -s 1:30 -e 3:45 --aspect mobile --crop-x 50

# With captions
clipper extract URL -s 1:30 -e 3:45 --captions --style bold

# Full pipeline
clipper extract URL \
  --start 1:30 \
  --end 3:45 \
  --aspect mobile \
  --crop-x 60 \
  --captions \
  --style clean \
  --position bottom \
  --edit \
  --output "my_clip.mp4"

# From local file (skip download)
clipper extract video.mp4 --start 1:30 --end 3:45 --captions
```

### Aspect Ratios & Cropping

| Preset | Ratio | Resolution | Platform |
|--------|-------|------------|----------|
| `mobile` | 9:16 | 1080×1920 | TikTok, Reels, Shorts |
| `square` | 1:1 | 1080×1080 | Instagram feed |
| `desktop` | 16:9 | 1920×1080 | YouTube, Twitter |

**Crop Focus (`--crop-x`)**
- When converting 16:9 → 9:16, you lose ~60% of the frame
- `--crop-x 0` = take from left edge
- `--crop-x 50` = center (default)
- `--crop-x 100` = take from right edge
- Use case: speaker is on the right side of frame → `--crop-x 70`

**Smart Crop (future)**
- Face detection to auto-track subject
- Ken Burns effect (subtle pan across frame)

### Caption System

**Styles (presets)**

| Style | Font | Size | Color | Use Case |
|-------|------|------|-------|----------|
| `clean` | Inter/Arial | 48px | White + black outline | Professional |
| `bold` | Impact | 56px | Yellow + black outline | High energy |
| `typewriter` | Courier | 44px | White + black outline | Documentary feel |
| `minimal` | System | 36px | White, no outline | Subtle |

**Animations**

| Animation | How It Works | Implementation |
|-----------|--------------|----------------|
| `static` | All text appears at once | Standard SRT → FFmpeg subtitles |
| `word` | Words appear one by one | Whisper word timestamps → multiple subtitle entries |
| `highlight` | Current word highlighted | ASS subtitles with `\k` karaoke tags |
| `pop` | Words scale in | ASS subtitles with `\t` transform |

**Transcript Editing**
- `--edit` flag opens interactive editor before burning
- Shows each segment, allows text correction
- Can merge/split segments
- Can delete unwanted sections

### Output

**Naming Convention**
```
{video_title}_{start}-{end}_{aspect}.mp4

Examples:
- "Joe Rogan #2103_14m22s-15m07s_mobile.mp4"
- "TED Talk on AI_3m00s-5m30s_square.mp4"
```

**Metadata**
- Preserves original video metadata where possible
- Adds custom tags: `clipper_version`, `source_url`, `clip_range`

---

## Phase 2: Auto Clip Finder

### Workflow
```
YouTube URL → Download Full Video → Transcribe (Whisper)
                                         │
                                         ▼
                              AI Analysis (Claude)
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                       Clip Candidates        Frame Validation
                              │                     │
                              └──────────┬──────────┘
                                         ▼
                              Ranked Clip List + Previews
```

### AI Clip Detection Algorithm

**Step 1: Segment the Transcript**
- Break into ~30 second chunks with overlap
- Preserve sentence boundaries

**Step 2: Score Each Segment**

Send to Claude with this prompt structure:
```
You are analyzing a video transcript to find the best standalone clips.

TRANSCRIPT CHUNK:
[text with timestamps]

Score this segment (1-10) on:
- Standalone: Does it make sense without context?
- Complete: Is it a complete thought/story?
- Engaging: Is it interesting, funny, insightful, or memorable?
- Quotable: Would someone share this clip?

Also identify:
- Best start point (exact timestamp)
- Best end point (exact timestamp)
- One-line summary
- Why this would make a good clip
```

**Step 3: Rank and Deduplicate**
- Sort by combined score
- Remove overlapping clips (keep higher scored)
- Return top N candidates

**Step 4: Frame Validation**
- Extract frame at proposed start/end times
- Check for:
  - Scene transitions (avoid cutting mid-transition)
  - Text on screen (don't cut mid-title)
  - Speaker visibility (prefer when speaker is visible)
- Adjust timestamps ±2 seconds if needed

### Commands

```bash
# Find clips
clipper find URL --count 5

# Find with constraints
clipper find URL --count 10 --min-length 30 --max-length 120

# Output formats
clipper find URL --output json    # Machine-readable
clipper find URL --output table   # Human-readable (default)

# Export found clips
clipper find URL --count 5 --export-all --aspect mobile
```

### Output Format

```
┌─────────────────────────────────────────────────────────────┐
│ 🎬 Found 5 clips in "Joe Rogan #2103 - Guest Name"          │
├─────┬──────────┬──────────┬───────┬─────────────────────────┤
│  #  │  Start   │   End    │ Score │ Summary                 │
├─────┼──────────┼──────────┼───────┼─────────────────────────┤
│  1  │  14:22   │  15:07   │  9.2  │ "The AI will..."        │
│  2  │  45:11   │  46:45   │  8.8  │ "When I realized..."    │
│  3  │  1:02:33 │  1:04:01 │  8.5  │ "The trick to..."       │
│  4  │  23:45   │  24:30   │  8.1  │ "Nobody talks about..." │
│  5  │  1:45:22 │  1:46:50 │  7.9  │ "Here's what changed.." │
└─────┴──────────┴──────────┴───────┴─────────────────────────┘

Preview thumbnails saved to: ./clips_preview/
Run `clipper export 1,3 --aspect mobile` to export clips #1 and #3
```

---

## Phase 3: GUI Editor

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  YouTube Clipper                                    [─] [□] [×] │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────┐  ┌───────────────────────┐ │
│  │                                 │  │ SETTINGS              │ │
│  │                                 │  │                       │ │
│  │         VIDEO PREVIEW           │  │ Aspect: [Mobile ▼]    │ │
│  │         (with crop overlay)     │  │                       │ │
│  │                                 │  │ Crop X: [====●====]   │ │
│  │                                 │  │         50%           │ │
│  │                                 │  │                       │ │
│  │    [  ◄◄  ] [ ▶ ] [  ►►  ]     │  │ ─────────────────     │ │
│  │                                 │  │ CAPTIONS              │ │
│  └─────────────────────────────────┘  │ [✓] Enable            │ │
│                                       │ Style: [Clean ▼]      │ │
│  ┌─────────────────────────────────┐  │ Position: [Bottom ▼]  │ │
│  │ TIMELINE                        │  │                       │ │
│  │ [▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░] │  │ ─────────────────     │ │
│  │  ▲                          ▲   │  │ TRANSCRIPT            │ │
│  │  start                    end   │  │ ┌───────────────────┐ │ │
│  │  1:30                    3:45   │  │ │ [0:00] Hello...   │ │ │
│  └─────────────────────────────────┘  │ │ [0:05] Today we...│ │ │
│                                       │ │ [0:12] The key... │ │ │
│  ┌─────────────────────────────────┐  │ └───────────────────┘ │ │
│  │  [  Import  ]    [  Export  ]   │  │                       │ │
│  └─────────────────────────────────┘  └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Key Interactions
- **Drag timeline handles** to adjust start/end
- **Click crop preview** to adjust crop region visually
- **Click transcript line** to jump to that timestamp
- **Edit transcript text** inline before export
- **Live preview** updates as you change settings
- **Keyboard shortcuts**: Space=play/pause, J/L=skip, I/O=set in/out points

### Tech: PyQt6
- Cross-platform (Mac, Windows, Linux)
- Native look and feel
- Good video playback with `QMediaPlayer`
- Stays in Python ecosystem

---

## Configuration

### Config File (`~/.clipper/config.yaml`)

```yaml
defaults:
  aspect: mobile
  crop_x: 50
  captions: true
  caption_style: clean
  whisper_model: base

output:
  directory: ~/Videos/Clips
  naming: "{title}_{start}-{end}_{aspect}"
  
presets:
  tiktok:
    aspect: mobile
    captions: true
    caption_style: bold
    caption_position: center
    
  podcast:
    aspect: mobile
    crop_x: 50
    captions: true
    caption_style: clean
    
  youtube_short:
    aspect: mobile
    captions: true
    caption_style: minimal

ai:
  model: claude-3-haiku  # or claude-3-sonnet for better accuracy
  max_clips: 10
```

### Using Presets

```bash
clipper extract URL --preset tiktok --start 1:30 --end 2:15
```

---

## Technical Details

### Dependencies

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Runtime |
| FFmpeg | 5.0+ | Video processing |
| yt-dlp | latest | YouTube download |
| Whisper | base model | Transcription |
| Claude API | - | AI clip finding (Phase 2 only) |
| PyQt6 | 6.x | GUI (Phase 3 only) |

### Performance Considerations

| Operation | Time (1 min clip) | Time (10 min video) |
|-----------|-------------------|---------------------|
| Download | ~5s | ~30s |
| Transcode/crop | ~10s | ~2 min |
| Whisper (base) | ~15s | ~2 min |
| Caption burn | ~10s | ~2 min |
| **Total** | **~40s** | **~6 min** |

**Optimizations**:
- Download only the needed segment (yt-dlp `--download-sections`)
- Use hardware acceleration (`-hwaccel auto`) where available
- Cache Whisper model in memory between runs
- Parallel processing for batch exports

### Error Handling

| Error | Handling |
|-------|----------|
| Video unavailable | Clear error message, suggest alternatives |
| Invalid timestamps | Clamp to video duration, warn user |
| FFmpeg failure | Show FFmpeg error, suggest common fixes |
| Whisper OOM | Suggest smaller model or chunked processing |
| Network timeout | Retry with exponential backoff |

---

## Project Structure

```
youtube-clipper/
├── cli.py                 # CLI entry point
├── core/
│   ├── __init__.py
│   ├── downloader.py      # yt-dlp wrapper
│   ├── processor.py       # FFmpeg crop/trim
│   ├── captioner.py       # Whisper + caption rendering
│   └── analyzer.py        # AI clip detection (Phase 2)
├── gui/
│   ├── __init__.py
│   ├── app.py             # PyQt main window
│   ├── video_player.py    # Video preview widget
│   ├── timeline.py        # Timeline widget
│   └── transcript.py      # Transcript editor widget
├── config/
│   ├── defaults.yaml
│   └── caption_styles.yaml
├── tests/
│   ├── test_downloader.py
│   ├── test_processor.py
│   └── test_captioner.py
├── requirements.txt
├── setup.py
└── README.md
```

---

## Milestones

### ✅ M1: Core CLI (Phase 1)
- [x] Project structure
- [x] Download with yt-dlp
- [x] Trim with FFmpeg
- [x] Crop to aspect ratios
- [x] Whisper transcription
- [x] Basic caption burning
- [ ] Caption animations (word-by-word)
- [ ] Interactive transcript editor
- [ ] Config file support
- [ ] Presets

### ✅ M2: Auto Finder (Phase 2)
- [x] Full video transcription
- [x] Claude API integration
- [x] Clip scoring algorithm
- [x] Frame validation (basic - thumbnail extraction)
- [x] Batch export

### 🔲 M3: GUI (Phase 3)
- [ ] Video player widget
- [ ] Timeline with drag handles
- [ ] Crop preview overlay
- [ ] Transcript editor
- [ ] Settings panel
- [ ] Export workflow

---

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime | Local only | Privacy, no API costs for basic use |
| Transcription | Whisper | More accurate than YouTube captions |
| Captions | FFmpeg burn-in | Simple, portable output |
| GUI framework | PyQt6 | Unified Python stack, native feel |
| AI for clips | Claude API | Best reasoning for content analysis |

---

*Created: Jan 29, 2026*
*Last updated: Jan 29, 2026*
