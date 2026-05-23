"""
Command-line interface for ytdlp-pro.

Usage examples
--------------
# Single video, best quality
ytdlp-pro https://youtu.be/dQw4w9WgXcQ

# 720p with Arabic + English subtitles
ytdlp-pro https://youtu.be/dQw4w9WgXcQ -q 720p --subtitles --sub-langs en ar

# Audio only (MP3 320k)
ytdlp-pro https://youtu.be/dQw4w9WgXcQ --audio-only

# Full playlist, throttled to 2 MB/s
ytdlp-pro https://www.youtube.com/playlist?list=PL... --playlist --rate-limit 2M

# Age-restricted video via cookies
ytdlp-pro https://youtu.be/xxx --cookies ~/cookies.txt
"""

from __future__ import annotations

import argparse
import logging
import sys

from ytdlp_pro.downloader import QUALITY_MAP, download_media


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytdlp-pro",
        description="Professional YouTube downloader powered by yt-dlp.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Positional ────────────────────────────────────────────────────────
    parser.add_argument("url", help="YouTube video or playlist URL")

    # ── Output ────────────────────────────────────────────────────────────
    parser.add_argument(
        "-o", "--output-dir",
        default="downloads",
        metavar="DIR",
        help="Destination directory (default: downloads/)",
    )
    parser.add_argument(
        "-f", "--filename",
        metavar="NAME",
        help="Custom output filename stem (single-video only, no extension)",
    )

    # ── Quality ───────────────────────────────────────────────────────────
    parser.add_argument(
        "-q", "--quality",
        choices=list(QUALITY_MAP.keys()),
        default="best",
        help="Video quality preset (default: best)",
    )

    # ── Mode ──────────────────────────────────────────────────────────────
    parser.add_argument(
        "-a", "--audio-only",
        action="store_true",
        help="Download audio only as MP3 320 kbps",
    )
    parser.add_argument(
        "-p", "--playlist",
        action="store_true",
        help="Treat URL as a playlist and download all items",
    )

    # ── Subtitles ─────────────────────────────────────────────────────────
    parser.add_argument(
        "--subtitles",
        action="store_true",
        help="Download subtitles alongside the video",
    )
    parser.add_argument(
        "--sub-langs",
        nargs="+",
        default=["en"],
        metavar="LANG",
        help="Subtitle language codes (default: en).  Example: --sub-langs en ar fr",
    )

    # ── Network ───────────────────────────────────────────────────────────
    parser.add_argument(
        "--rate-limit",
        metavar="RATE",
        help="Maximum download speed, e.g. 2M (2 MB/s) or 500K",
    )
    parser.add_argument(
        "--cookies",
        metavar="FILE",
        help="Path to Netscape cookies.txt for age-restricted or private content",
    )

    # ── Extras ────────────────────────────────────────────────────────────
    parser.add_argument(
        "--embed-thumbnail",
        action="store_true",
        help="Embed video thumbnail into the output file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    result = download_media(
        url=args.url,
        output_dir=args.output_dir,
        filename=args.filename,
        audio_only=args.audio_only,
        playlist=args.playlist,
        quality=args.quality,
        subtitles=args.subtitles,
        subtitle_langs=args.sub_langs,
        rate_limit=args.rate_limit,
        cookies=args.cookies,
        embed_thumbnail=args.embed_thumbnail,
    )

    if result.warnings:
        for w in result.warnings:
            logging.getLogger(__name__).warning("⚠  %s", w)

    if result.success:
        print(f"\n✔  Saved to: {result.output_path}")
        return 0
    else:
        print(f"\n✖  Failed: {result.error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
