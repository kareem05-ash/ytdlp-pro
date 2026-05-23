"""
Core download engine for ytdlp-pro.

Handles video, audio, and playlist downloads with full
quality control, subtitle support, rate limiting, and
structured result reporting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

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
# Quality map
# ---------------------------------------------------------------------------

QUALITY_MAP: dict[str, str] = {
    "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
    "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
    "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
    "360p":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
}

AUDIO_FORMAT = "bestaudio/best"


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


def _make_progress_hook(warnings: list[str]):
    """Return a yt-dlp progress hook that logs to the standard logger."""

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            percent = d.get("_percent_str", "").strip()
            speed   = d.get("_speed_str",   "N/A")
            eta     = d.get("_eta_str",     "N/A")
            logger.info("Downloading: %s | Speed: %s | ETA: %s", percent, speed, eta)
        elif status == "finished":
            logger.info("Post-processing: %s", d.get("filename", ""))
        elif status == "error":
            msg = d.get("error", "Unknown error during download")
            warnings.append(str(msg))
            logger.warning("Hook reported error: %s", msg)

    return hook


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
        Embed subtitle tracks into the output MP4 (soft subtitles —
        selectable in any player, no re-encoding required).
    subtitle_langs:
        List of BCP-47 language codes, e.g. ``["en", "ar"]``.
        Defaults to ``["en"]`` when *subtitles* is ``True``.
    rate_limit:
        yt-dlp rate-limit string, e.g. ``"2M"`` (2 MB/s).  ``None`` = unlimited.
    cookies:
        Path to a Netscape-format ``cookies.txt`` file (age-restricted content).
    embed_thumbnail:
        Embed the video thumbnail into the output file.

    Returns
    -------
    DownloadResult
        ``success=True`` on completion, ``success=False`` with ``error`` set
        on failure.
    """
    warnings: list[str] = []

    # Validate quality choice
    if quality not in QUALITY_MAP:
        return DownloadResult(
            success=False,
            error=f"Invalid quality '{quality}'. Choose from: {', '.join(QUALITY_MAP)}",
        )

    output_path = _create_output_directory(output_dir)
    outtmpl = _build_output_template(output_path, filename, playlist)
    selected_format = AUDIO_FORMAT if audio_only else QUALITY_MAP[quality]

    ydl_opts: dict = {
        # ── Quality ──────────────────────────────────────────────────────────
        "format": selected_format,
        "merge_output_format": "mp4",

        # ── Output ───────────────────────────────────────────────────────────
        "outtmpl": outtmpl,

        # ── Playlist ─────────────────────────────────────────────────────────
        "noplaylist": not playlist,

        # ── Resilience ───────────────────────────────────────────────────────
        # ignoreerrors=True skips broken *playlist* items without aborting,
        # but also swallows single-video errors — only enable for playlists.
        "ignoreerrors": playlist,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,

        # ── Metadata ─────────────────────────────────────────────────────────
        "addmetadata": True,
        "writethumbnail": embed_thumbnail,

        # ── Network ──────────────────────────────────────────────────────────
        "geo_bypass": True,

        # ── Logging ──────────────────────────────────────────────────────────
        "progress_hooks": [_make_progress_hook(warnings)],
        "quiet": True,          # suppress yt-dlp's own stdout chatter
        "no_warnings": False,   # keep yt-dlp warnings flowing to the hook
    }

    # Optional: subtitles
    if subtitles:
        langs = subtitle_langs or ["en"]
        ydl_opts.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": langs,
                # Convert vtt → srt so FFmpeg can embed them
                "postprocessors": [
                    {"key": "FFmpegSubtitlesConvertor", "format": "srt"},
                    {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False},
                ],
            }
        )

    # Optional: rate limiting
    if rate_limit:
        ydl_opts["ratelimit"] = rate_limit

    # Optional: cookies (for age-restricted / private videos)
    if cookies:
        cookies_path = Path(cookies)
        if not cookies_path.is_file():
            return DownloadResult(
                success=False,
                error=f"Cookies file not found: {cookies}",
            )
        ydl_opts["cookiefile"] = str(cookies_path)

    # Audio post-processing
    if audio_only:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ]
        if embed_thumbnail:
            ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})

    # ── Run ──────────────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("URL        : %s", url)
    logger.info("Output     : %s", output_path.resolve())
    logger.info("Quality    : %s", "audio-only (MP3 320k)" if audio_only else quality)
    logger.info("Playlist   : %s", playlist)
    if subtitles:
        logger.info("Subtitles  : %s", subtitle_langs or ["en"])
    if rate_limit:
        logger.info("Rate limit : %s", rate_limit)
    logger.info("=" * 70)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # For single videos, any hook-reported error means nothing was saved.
        if not playlist and warnings:
            error_msg = warnings[-1]
            logger.error("Download failed: %s", error_msg)
            return DownloadResult(success=False, error=error_msg, warnings=warnings)

        logger.info("Download completed successfully.")
        return DownloadResult(success=True, output_path=output_path, warnings=warnings)

    except yt_dlp.utils.DownloadError as exc:
        logger.error("Download failed: %s", exc)
        return DownloadResult(success=False, error=str(exc), warnings=warnings)

    except Exception as exc:
        logger.exception("Unexpected error during download.")
        return DownloadResult(success=False, error=str(exc), warnings=warnings)
