"""
Full-screen interactive wizard for `clipper batch`.

Visual style is modeled on a media-browser TUI reference: a big ASCII banner,
a boxed input for the "current question", an options list you navigate with
arrow keys, and a Footer showing the active hotkeys. Green/cyan to match the
clipper's existing terminal look.

This module only *collects* settings and clip ranges. Once the wizard exits,
cli.py takes the returned BatchConfig and runs the actual download/trim/crop/
caption pipeline the same way it always has, with plain console output --
that part is long-running and log-heavy, so it stays outside the TUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pyfiglet
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from core.timecode import format_ffmpeg_timestamp, is_full_video_marker, parse_clip_range

APP_VERSION = "v0.1.0"
BANNER_ART = pyfiglet.figlet_format("CLIPPER", font="ansi_shadow").rstrip("\n")

WIZARD_CSS = """
Screen {
    background: #000000;
    color: #baf7d7;
    align: center top;
}

#banner {
    width: 100%;
    height: auto;
    align: center middle;
    padding-top: 1;
}

.banner-art {
    width: auto;
    content-align: center middle;
    color: #33ff99;
    text-style: bold;
}

.banner-subtitle {
    width: 100%;
    content-align: center middle;
    color: #7fffd4;
    text-style: bold;
}

.banner-version {
    width: 100%;
    content-align: center middle;
    color: #3a6b56;
    margin-bottom: 1;
}

#stage {
    width: 100%;
    height: 1fr;
    align: center top;
}

.step-title {
    width: 90%;
    max-width: 90;
    content-align: center middle;
    color: #d8fff0;
    margin: 1 0;
}

.hint {
    width: 90%;
    max-width: 90;
    content-align: center middle;
    color: #5c9c81;
    margin-top: 1;
}

.error {
    width: 90%;
    max-width: 90;
    content-align: center middle;
    color: #ff6b6b;
}

.input-box {
    border: heavy #2ecc71;
    background: #061b12;
    width: 70%;
    max-width: 90;
    min-height: 4;
    padding: 1 1;
    margin: 1 0 0 0;
}

.input-box:focus-within {
    border: heavy #6bffc0;
    background: #0a231b;
}

Input {
    width: 100%;
    min-height: 3;
    color: #ffffff;
    background: #010b08;
    border: heavy #33ff99;
    padding: 0 1;
    text-style: none;
    content-align: left middle;
}

Input:focus {
    color: #ffffff;
    background: #041c14;
    border: heavy #8affd0;
}

#field {
    width: 100%;
    min-height: 3;
    padding: 0 1;
    color: #ffffff;
    background: #010b08;
}

#field:focus {
    background: #041c14;
    border: heavy #8affd0;
}

Input.-placeholder {
    color: #9dbdb1;
}

OptionList {
    border: heavy #2ecc71;
    background: #000000;
    width: 70%;
    max-width: 90;
    height: auto;
    max-height: 12;
}

.clip-log {
    border: heavy #1e5240;
    background: #000000;
    width: 70%;
    max-width: 90;
    height: 10;
    padding: 0 1;
    margin-top: 1;
    overflow-y: auto;
}

.summary-box {
    border: double #2ecc71;
    background: #000000;
    width: 70%;
    max-width: 90;
    height: auto;
    padding: 1 2;
}
"""


@dataclass
class BatchConfig:
    url: str
    aspect: str
    captions: bool
    caption_style: str
    caption_position: str
    download_once: bool
    padding_seconds: int
    ranges: List[Tuple[float, float]]


@dataclass
class WizardDefaults:
    """Values the CLI flags pre-fill the wizard with."""
    aspect: str = "mobile"
    captions: bool = True
    caption_style: str = "clean"
    caption_position: str = "bottom"
    padding_seconds: int = 10


class BannerMixin:
    """Gives every step screen the same banner + Footer chrome."""

    subtitle = "BATCH MODE"

    def compose_banner(self) -> ComposeResult:
        yield Static(Text(BANNER_ART, style="bold", justify="center"), classes="banner-art")
        yield Static(f"— {self.subtitle} —", classes="banner-subtitle")
        yield Static(APP_VERSION, classes="banner-version")


class WizardScreen(BannerMixin, Screen):
    """Base class for every step. Escape always cancels the whole wizard."""

    CSS = WIZARD_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextStepScreen(WizardScreen):
    """A single boxed text input, like the MovieBox search bar."""

    BINDINGS = [Binding("enter", "submit", "Confirm", show=False)]

    def __init__(self, title: str, placeholder: str, initial: str = "",
                 validator=None, hint: str = ""):
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._initial = initial
        self._validator = validator
        self._hint = hint

    def compose(self) -> ComposeResult:
        yield from self.compose_banner()
        with Vertical(id="stage"):
            yield Static(self._title, classes="step-title")
            with Vertical(classes="input-box"):
                yield Input(value=self._initial, placeholder=self._placeholder, id="field")
            yield Static(self._hint, classes="hint")
            yield Static("", classes="error", id="error")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#field", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._try_submit(event.value)

    def action_submit(self) -> None:
        self._try_submit(self.query_one("#field", Input).value)

    def _try_submit(self, value: str) -> None:
        value = value.strip()
        if self._validator:
            try:
                self._validator(value)
            except ValueError as exc:
                self.query_one("#error", Static).update(f"⚠ {exc}")
                return
        self.dismiss(value)


class ChoiceStepScreen(WizardScreen):
    """An arrow-key navigable list of options, like MovieBox's category list."""

    def __init__(self, title: str, options: List[Tuple[str, str]], initial: str = ""):
        """options: list of (id, label) pairs."""
        super().__init__()
        self._title = title
        self._options = options
        self._initial = initial

    def compose(self) -> ComposeResult:
        yield from self.compose_banner()
        with Vertical(id="stage"):
            yield Static(self._title, classes="step-title")
            yield OptionList(
                *[Option(label, id=opt_id) for opt_id, label in self._options]
            )
            yield Static("↑/↓ to move · Enter to select · Esc to cancel", classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        option_list = self.query_one(OptionList)
        option_list.focus()
        ids = [opt_id for opt_id, _ in self._options]
        if self._initial in ids:
            option_list.highlighted = ids.index(self._initial)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class ClipRangesScreen(WizardScreen):
    """Repeated boxed input for pasting clip ranges, with a live running log."""

    def __init__(self, padding_seconds: int):
        super().__init__()
        self._padding = padding_seconds
        self._ranges: List[Tuple[float, float]] = []

    def compose(self) -> ComposeResult:
        yield from self.compose_banner()
        with Vertical(id="stage"):
            yield Static(
                "Paste one range per line, e.g. 1:24 - 2:03", classes="step-title"
            )
            with Vertical(classes="input-box"):
                yield Input(placeholder=f"Clip {len(self._ranges) + 1}", id="field")
            yield Static(
                "Enter to add a clip · type DONE when finished · Esc to cancel",
                classes="hint",
            )
            yield Static("", classes="error", id="error")
            yield Static("", classes="clip-log", id="log")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#field", Input).focus()
        self._refresh_log()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        field = self.query_one("#field", Input)
        error = self.query_one("#error", Static)

        if line.upper() == "DONE":
            self.action_finish()
            return
        if not line:
            error.update("⚠ Enter a range, or type DONE to finish.")
            return

        if is_full_video_marker(line):
            self._ranges.append((-1.0, -1.0))
            error.update("")
            field.value = ""
            field.placeholder = f"Clip {len(self._ranges) + 1}"
            self._refresh_log()
            return

        try:
            start, end = parse_clip_range(line)
        except ValueError as exc:
            error.update(f"⚠ Invalid range: {exc}")
            return

        start = max(0.0, start - self._padding)
        end += self._padding
        self._ranges.append((start, end))
        error.update("")
        field.value = ""
        field.placeholder = f"Clip {len(self._ranges) + 1}"
        self._refresh_log()

    def _refresh_log(self) -> None:
        log = self.query_one("#log", Static)
        if not self._ranges:
            log.update("[dim]No clips added yet.[/dim]")
            return
        lines = []
        for i, item in enumerate(self._ranges, 1):
            if item == (-1.0, -1.0):
                lines.append(f"[bold]Clip {i}:[/bold] FULL VIDEO  [dim](download the complete video)[/dim]")
                continue
            start, end = item
            lines.append(
                f"[bold]Clip {i}:[/bold] {format_ffmpeg_timestamp(start)} – "
                f"{format_ffmpeg_timestamp(end)}  [dim](with {self._padding}s padding)[/dim]"
            )
        log.update("\n".join(lines))

    def action_finish(self) -> None:
        if not self._ranges:
            self.query_one("#error", Static).update(
                "⚠ Add at least one clip before finishing."
            )
            return
        self.dismiss(list(self._ranges))


class SummaryScreen(WizardScreen):
    """Final confirm-and-go screen."""

    BINDINGS = [Binding("enter", "confirm", "Start", show=False)]

    def __init__(self, config: BatchConfig):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        yield from self.compose_banner()
        c = self._config
        caption_line = (
            f"Captions: {c.caption_style} / {c.caption_position}"
            if c.captions else "Captions: off"
        )
        body = "\n".join([
            f"[bold]URL[/bold]        {c.url}",
            f"[bold]Format[/bold]     {c.aspect}",
            caption_line,
            f"Download     {'once, reused for all clips' if c.download_once else 'per clip'}",
            f"Padding      {c.padding_seconds}s",
            f"Clips        {len(c.ranges)}",
        ])
        with Vertical(id="stage"):
            yield Static("Ready to go", classes="step-title")
            yield Static(body, classes="summary-box")
            yield Static("Enter to start · Esc to cancel", classes="hint")
        yield Footer()

    def action_confirm(self) -> None:
        self.dismiss(True)


class BatchWizardApp(App):
    """Drives the linear sequence of steps and collects a BatchConfig."""

    CSS = WIZARD_CSS
    TITLE = "YouTube Clipper — Batch Mode"

    def __init__(self, defaults: WizardDefaults):
        super().__init__()
        self.defaults = defaults
        self.result: Optional[BatchConfig] = None

    def on_mount(self) -> None:
        self._run_wizard()

    @work
    async def _run_wizard(self) -> None:
        try:
            result = await self._collect()
        except Exception as exc:  # noqa: BLE001 - debug aid, tightened below
            import traceback
            traceback.print_exc()
            result = None
        self.result = result
        self.exit(result=result)

    async def _collect(self) -> Optional[BatchConfig]:
        d = self.defaults

        def _require_url(value: str) -> None:
            if not value:
                raise ValueError("a YouTube URL is required")

        url = await self.push_screen_wait(
            TextStepScreen(
                "YouTube URL",
                placeholder="https://www.youtube.com/watch?v=...",
                validator=_require_url,
            )
        )
        if url is None:
            return None

        aspect = await self.push_screen_wait(
            ChoiceStepScreen(
                "Video format",
                [("mobile", "Mobile (9:16)"), ("square", "Square (1:1)"),
                 ("desktop", "Desktop (16:9)")],
                initial=d.aspect,
            )
        )
        if aspect is None:
            return None

        captions_choice = await self.push_screen_wait(
            ChoiceStepScreen(
                "Add captions to every clip?",
                [("yes", "Yes"), ("no", "No")],
                initial="yes" if d.captions else "no",
            )
        )
        if captions_choice is None:
            return None
        captions = captions_choice == "yes"

        caption_style = d.caption_style
        caption_position = d.caption_position
        if captions:
            caption_style = await self.push_screen_wait(
                ChoiceStepScreen(
                    "Caption style",
                    [("clean", "Clean"), ("bold", "Bold"), ("typewriter", "Typewriter")],
                    initial=d.caption_style,
                )
            )
            if caption_style is None:
                return None

            caption_position = await self.push_screen_wait(
                ChoiceStepScreen(
                    "Caption position",
                    [("top", "Top"), ("center", "Center"), ("bottom", "Bottom")],
                    initial=d.caption_position,
                )
            )
            if caption_position is None:
                return None

        download_choice = await self.push_screen_wait(
            ChoiceStepScreen(
                "Download the full source once and reuse it for all clips?",
                [("once", "Yes — download once, reuse for every clip"),
                 ("separate", "No — download each clip separately")],
                initial="once",
            )
        )
        if download_choice is None:
            return None
        download_once = download_choice == "once"

        def _validate_padding(value: str) -> None:
            if not value.isdigit() or not (0 <= int(value) <= 3600):
                raise ValueError("enter a whole number of seconds, 0–3600")

        padding_str = await self.push_screen_wait(
            TextStepScreen(
                "Extra seconds before and after every clip",
                placeholder=str(d.padding_seconds),
                initial=str(d.padding_seconds),
                validator=_validate_padding,
            )
        )
        if padding_str is None:
            return None
        padding_seconds = int(padding_str) if padding_str else d.padding_seconds

        ranges = await self.push_screen_wait(ClipRangesScreen(padding_seconds))
        if ranges is None:
            return None

        config = BatchConfig(
            url=url,
            aspect=aspect,
            captions=captions,
            caption_style=caption_style,
            caption_position=caption_position,
            download_once=download_once,
            padding_seconds=padding_seconds,
            ranges=ranges,
        )

        confirmed = await self.push_screen_wait(SummaryScreen(config))
        if not confirmed:
            return None

        return config


def run_batch_wizard(defaults: WizardDefaults) -> Optional[BatchConfig]:
    """Entry point cli.py calls. Returns None if the user cancelled."""
    app = BatchWizardApp(defaults)
    return app.run()
