"""
Core download engine for ytdlp-pro.

Handles video, audio, and playlist downloads with full
quality control, subtitle support, rate limiting, and
structured result reporting.

YouTube changes its anti-bot protections frequently.  This module therefore:

* logs the yt-dlp version and warns if no JavaScript runtime is available
  (YouTube now needs one to solve its "n" challenge - without it you get 403s),
* uses flexible format selection (``format_sort``) instead of hard-coded
  container filters that make downloads fail when a format disappears,
* automatically retries a 403 with alternative YouTube player clients,
* can borrow login cookies straight from your browser.
"""

from __future__ import annotations

import copy
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yt_dlp
import yt_dlp.version

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DownloadResult:
    """Structured result returned by every download call."""

    success: bool
    output_path: Path | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # allows `if result:` idiom
        return self.success


# ---------------------------------------------------------------------------
# Quality maps
# ---------------------------------------------------------------------------

# Format selectors are deliberately free of ``[ext=...]`` filters: those break
# as soon as YouTube stops offering that exact container.  Container preference
# is expressed through QUALITY_SORT instead (a preference, not a hard filter).
QUALITY_MAP: dict[str, str] = {
    "best":  "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]/b",
    "720p":  "bv*[height<=720]+ba/b[height<=720]/b",
    "480p":  "bv*[height<=480]+ba/b[height<=480]/b",
    "360p":  "bv*[height<=360]+ba/b[height<=360]/b",
}

# yt-dlp ``format_sort``: highest resolution first, then prefer mp4/m4a so the
# merged file plays everywhere, but fall back to anything else if needed.
QUALITY_SORT: dict[str, list[str]] = {
    "best":  ["res", "ext:mp4:m4a"],
    "1080p": ["res:1080", "ext:mp4:m4a"],
    "720p":  ["res:720", "ext:mp4:m4a"],
    "480p":  ["res:480", "ext:mp4:m4a"],
    "360p":  ["res:360", "ext:mp4:m4a"],
}

AUDIO_FORMAT = "bestaudio/best"

# ---------------------------------------------------------------------------
# 403 fallback strategies
# ---------------------------------------------------------------------------
# Each entry: (label, extra yt-dlp options).  The first is the normal run; the
# rest are only tried if the previous attempt ended in "HTTP Error 403".
# Client names are YouTube-specific and change over time - this list is
# best-effort, and updating yt-dlp matters far more than anything here.
_CHUNK = 10 * 1024 * 1024

_ATTEMPTS: list[tuple[str, dict[str, Any]]] = [
    ("default clients", {}),
    (
        "tv + web_safari clients",
        {
            "extractor_args": {"youtube": {"player_client": ["tv", "web_safari"]}},
            "http_chunk_size": _CHUNK,
        },
    ),
    (
        "mweb client",
        {
            "extractor_args": {"youtube": {"player_client": ["mweb"]}},
            "http_chunk_size": _CHUNK,
        },
    ),
]

_JS_RUNTIME_NAMES: dict[str, tuple[str, ...]] = {
    "deno": ("deno",),
    "node": ("node", "nodejs"),
    "bun": ("bun",),
    "quickjs": ("qjs", "quickjs"),
}

_JS_HINT = (
    "No JavaScript runtime found. YouTube needs one to solve its challenge, "
    "and without it downloads often fail with 403. Install Deno "
    "(Windows: winget install DenoLand.Deno) and restart your terminal."
)

_FAILURE_HINT = (
    "\n\nHow to fix a persistent 403:\n"
    "  1. Update yt-dlp:        ytdlp-pro --update   (or --update --nightly)\n"
    "  2. Install a JS runtime: winget install DenoLand.Deno\n"
    "  3. Use browser cookies:  --cookies-from-browser chrome  (or firefox/edge)\n"
    "  4. Run  ytdlp-pro --doctor  to check your setup."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_output_directory(path: str) -> Path:
    """Create *path* (and any parents) if it does not already exist."""
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _build_output_template(
    output_dir: Path,
    filename: str | None,
    is_playlist: bool,
) -> str:
    """Return a yt-dlp ``outtmpl`` string for the given configuration."""
    if is_playlist:
        return str(
            output_dir
            / "%(playlist_title)s"
            / "%(playlist_index)s - %(title)s.%(ext)s"
        )
    if filename:
        return str(output_dir / f"{filename}.%(ext)s")
    return str(output_dir / "%(title)s.%(ext)s")


def find_js_runtimes() -> dict[str, dict[str, str]]:
    """Return ``{runtime: {"path": ...}}`` for every JS runtime found on PATH."""
    found: dict[str, dict[str, str]] = {}
    for runtime, executables in _JS_RUNTIME_NAMES.items():
        for exe in executables:
            path = shutil.which(exe)
            if path:
                found[runtime] = {"path": path}
                break
    return found


def _is_403(message: str) -> bool:
    low = message.lower()
    return "403" in low or "forbidden" in low


class _YtdlpLogger:
    """Forward yt-dlp's own messages to the standard logger."""

    def __init__(self, warnings: list[str]) -> None:
        self._warnings = warnings

    def debug(self, msg: str) -> None:
        logger.debug("%s", msg)

    def info(self, msg: str) -> None:
        logger.debug("%s", msg)

    def warning(self, msg: str) -> None:
        self._warnings.append(msg)
        logger.warning("%s", msg)

    def error(self, msg: str) -> None:
        logger.debug("yt-dlp: %s", msg)


def _make_progress_hook(errors: list[str]):
    """Return a yt-dlp progress hook that prints progress and logs events."""

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            percent = d.get("_percent_str", "").strip()
            speed   = d.get("_speed_str",   "N/A")
            eta     = d.get("_eta_str",     "N/A")
            # \r rewrites the same line; end="" suppresses the newline
            print(
                f"\r  Downloading: {percent:<6} | Speed: {speed:<12} | ETA: {eta:<8}",
                end="",
                flush=True,
            )
        elif status == "finished":
            print()  # newline after the progress line
            logger.info("Post-processing: %s", d.get("filename", ""))
        elif status == "error":
            print()  # newline after the progress line
            msg = d.get("error", "Unknown error during download")
            errors.append(str(msg))
            logger.warning("Download error: %s", msg)

    return hook


def _build_postprocessors(
    *,
    audio_only: bool,
    cover: bool,
    subtitles: bool,
    embed_thumbnail: bool,
) -> list[dict[str, Any]]:
    """Assemble the post-processor chain (subtitles no longer clobbered by audio)."""
    pps: list[dict[str, Any]] = []

    if audio_only:
        pps.append(
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}
        )
        if embed_thumbnail and not cover:
            pps.append({"key": "EmbedThumbnail"})
    elif subtitles:
        pps.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})
        pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    if cover:
        pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
        pps.append({"key": "FFmpegVideoConvertor", "preferedformat": "mp4"})

    return pps


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_media(
    url: str,
    output_dir: str = "downloads",
    filename: str | None = None,
    audio_only: bool = False,
    playlist: bool = False,
    quality: str = "best",
    subtitles: bool = False,
    subtitle_langs: list[str] | None = None,
    rate_limit: str | None = None,
    cookies: str | None = None,
    embed_thumbnail: bool = False,
    cover: bool = False,
    cookies_from_browser: str | None = None,
) -> DownloadResult:
    """
    Download video or audio from YouTube (and other yt-dlp supported sites).

    Parameters
    ----------
    url:
        Video or playlist URL.
    output_dir:
        Directory where files will be saved.  Created automatically.
    filename:
        Override the output filename stem (single-video mode only).
    audio_only:
        Extract audio as 320 kbps MP3 instead of downloading video.
    playlist:
        Treat the URL as a playlist and download every item.
    quality:
        One of ``"best"``, ``"1080p"``, ``"720p"``, ``"480p"``, ``"360p"``.
    subtitles:
        Embed subtitle tracks into the output MP4 (soft subtitles).
    subtitle_langs:
        List of language codes, e.g. ``["en", "ar"]``.
        Defaults to ``["en"]`` when *subtitles* is ``True``.
    rate_limit:
        yt-dlp rate-limit string, e.g. ``"2M"`` (2 MB/s).  ``None`` = unlimited.
    cookies:
        Path to a Netscape-format ``cookies.txt`` file.
    embed_thumbnail:
        Embed the video thumbnail into the output file.
    cover:
        Mux the thumbnail + audio into an MP4 with a static image background.
        Implies ``audio_only=True``.  Requires FFmpeg.
    cookies_from_browser:
        Browser name (``"chrome"``, ``"firefox"``, ``"edge"``, ...) to read
        login cookies from.  Often fixes 403 / "sign in to confirm" errors.

    Returns
    -------
    DownloadResult
        ``success=True`` on completion, ``success=False`` with ``error`` set
        on failure.
    """
    errors: list[str] = []     # errors reported by the progress hook
    warnings: list[str] = []   # yt-dlp warnings (informational only)

    # --cover implies audio-only
    if cover:
        audio_only = True

    # Validate quality choice
    if quality not in QUALITY_MAP:
        return DownloadResult(
            success=False,
            error=f"Invalid quality '{quality}'. Choose from: {', '.join(QUALITY_MAP)}",
        )

    output_path = _create_output_directory(output_dir)
    outtmpl = _build_output_template(output_path, filename, playlist)

    ydl_opts: dict[str, Any] = {
        # ── Quality ──────────────────────────────────────────────────────────
        "format": AUDIO_FORMAT if audio_only else QUALITY_MAP[quality],
        "merge_output_format": "mp4",

        # ── Output ───────────────────────────────────────────────────────────
        "outtmpl": outtmpl,

        # ── Playlist ─────────────────────────────────────────────────────────
        "noplaylist": not playlist,

        # ── Resilience ───────────────────────────────────────────────────────
        # ignoreerrors=True skips broken *playlist* items without aborting,
        # but also swallows single-video errors - only enable for playlists.
        "ignoreerrors": playlist,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,

        # ── Metadata ─────────────────────────────────────────────────────────
        "addmetadata": True,
        "writethumbnail": embed_thumbnail or cover,

        # ── Network ──────────────────────────────────────────────────────────
        "geo_bypass": True,

        # ── Logging ──────────────────────────────────────────────────────────
        "progress_hooks": [_make_progress_hook(errors)],
        "logger": _YtdlpLogger(warnings),
        "quiet": True,
        "no_warnings": False,
    }

    if not audio_only:
        ydl_opts["format_sort"] = QUALITY_SORT[quality]

    # JavaScript runtime (needed by YouTube's challenge solver)
    js_runtimes = find_js_runtimes()
    if js_runtimes:
        ydl_opts["js_runtimes"] = js_runtimes
    else:
        logger.warning(_JS_HINT)

    # Optional: subtitles
    if subtitles and not audio_only:
        ydl_opts.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": subtitle_langs or ["en"],
            }
        )

    postprocessors = _build_postprocessors(
        audio_only=audio_only,
        cover=cover,
        subtitles=subtitles,
        embed_thumbnail=embed_thumbnail,
    )
    if postprocessors:
        ydl_opts["postprocessors"] = postprocessors

    # Optional: rate limiting
    if rate_limit:
        ydl_opts["ratelimit"] = rate_limit

    # Optional: cookies
    if cookies:
        cookies_path = Path(cookies)
        if not cookies_path.is_file():
            return DownloadResult(
                success=False,
                error=f"Cookies file not found: {cookies}",
            )
        ydl_opts["cookiefile"] = str(cookies_path)
    elif cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser.lower(),)

    # ── Run ──────────────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("URL        : %s", url)
    logger.info("Output     : %s", output_path.resolve())
    logger.info("Quality    : %s", "audio-only (MP3 320k)" if audio_only else quality)
    logger.info("Playlist   : %s", playlist)
    logger.info("yt-dlp     : %s", getattr(yt_dlp.version, "__version__", "unknown"))
    logger.info("JS runtime : %s", ", ".join(js_runtimes) if js_runtimes else "NONE FOUND")
    if cover:
        logger.info("Cover      : yes (static thumbnail + audio -> MP4)")
    if subtitles:
        logger.info("Subtitles  : %s", subtitle_langs or ["en"])
    if rate_limit:
        logger.info("Rate limit : %s", rate_limit)
    if cookies_from_browser and not cookies:
        logger.info("Cookies    : from %s", cookies_from_browser)
    logger.info("=" * 70)

    last_error = "Unknown error"

    for index, (label, extra) in enumerate(_ATTEMPTS):
        is_last = index == len(_ATTEMPTS) - 1
        attempt_opts = copy.copy(ydl_opts)
        attempt_opts.update(copy.deepcopy(extra))
        errors.clear()

        if index > 0:
            logger.info("Retrying with %s (attempt %d/%d)...", label, index + 1, len(_ATTEMPTS))

        try:
            with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                retcode = ydl.download([url])

            # For single videos, any hook-reported error or non-zero exit code
            # means nothing was saved.
            if not playlist and errors:
                last_error = errors[-1]
            elif not playlist and isinstance(retcode, int) and retcode != 0:
                last_error = "yt-dlp reported a failure (see messages above)"
            else:
                logger.info("Download completed successfully.")
                return DownloadResult(success=True, output_path=output_path, warnings=warnings)

        except yt_dlp.utils.DownloadError as exc:
            last_error = str(exc)
            logger.error("Download failed: %s", exc)

        except Exception as exc:
            logger.exception("Unexpected error during download.")
            return DownloadResult(success=False, error=str(exc), warnings=warnings)

        # Only a 403 is worth retrying with different clients.
        if is_last or not _is_403(last_error):
            break

    if _is_403(last_error):
        last_error += _FAILURE_HINT
    return DownloadResult(success=False, error=last_error, warnings=warnings)
