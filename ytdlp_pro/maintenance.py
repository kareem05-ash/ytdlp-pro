"""
Maintenance helpers: update yt-dlp and diagnose the local setup.

YouTube breaks downloaders every few weeks; keeping yt-dlp current is the
single most effective fix for 403 errors.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import yt_dlp

from ytdlp_pro.downloader import find_js_runtimes


def _installed_version() -> str:
    import importlib

    import yt_dlp.version as v

    importlib.reload(v)
    return str(getattr(v, "__version__", "unknown"))


def update_ytdlp(nightly: bool = False) -> int:
    """Upgrade yt-dlp (with the ``default`` extra, which bundles yt-dlp-ejs)."""
    if getattr(sys, "frozen", False):
        print(
            "This is a frozen (PyInstaller) build - yt-dlp is baked in.\n"
            "Rebuild the executable after upgrading yt-dlp in your build environment."
        )
        return 1

    before = _installed_version()
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if nightly:
        cmd.append("--pre")  # yt-dlp publishes nightlies to PyPI as pre-releases
    cmd.append("yt-dlp[default]")

    print(f"Current yt-dlp: {before}")
    print("Running:", " ".join(cmd))
    code = subprocess.call(cmd)
    if code == 0:
        print("Done. Restart ytdlp-pro to use the new version.")
    return code


def doctor() -> int:
    """Print a short health report. Returns 0 if nothing critical is missing."""
    problems = 0
    print(f"Python      : {sys.version.split()[0]}")
    print(f"yt-dlp      : {_installed_version()}")

    try:
        import yt_dlp_ejs  # type: ignore[import-not-found]

        print(f"yt-dlp-ejs  : {getattr(yt_dlp_ejs, '__version__', 'installed')}")
    except ImportError:
        problems += 1
        print("yt-dlp-ejs  : MISSING  -> pip install -U \"yt-dlp[default]\"")

    runtimes = find_js_runtimes()
    if runtimes:
        print(f"JS runtime  : {', '.join(runtimes)}")
    else:
        problems += 1
        print("JS runtime  : MISSING  -> winget install DenoLand.Deno")

    if shutil.which("ffmpeg"):
        print("FFmpeg      : found")
    else:
        problems += 1
        print("FFmpeg      : MISSING (needed to merge video+audio and extract MP3)")

    print("\nAll good." if not problems else f"\n{problems} problem(s) found.")
    return 0 if not problems else 1


__all__ = ["doctor", "update_ytdlp", "yt_dlp"]
