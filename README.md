# ytdlp-pro

> **A professional, batteries-included YouTube downloader built on [yt-dlp](https://github.com/yt-dlp/yt-dlp).**

[![CI](https://github.com/YOUR_USERNAME/ytdlp-pro/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/ytdlp-pro/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Table of contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Python API](#python-api)
- [Project structure](#project-structure)
- [Running tests](#running-tests)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Capability | Details |
|---|---|
| 🎬 **Video download** | Best available quality or a named preset (`best`, `1080p`, `720p`, `480p`, `360p`) |
| 🎵 **Audio-only** | Extracts MP3 at 320 kbps via FFmpeg |
| 📋 **Playlist support** | Downloads every item and organises them into a named sub-folder |
| 📝 **Subtitles** | Writes subtitle files in any language, including auto-generated captions |
| 🖼️ **Thumbnail embedding** | Embeds the video thumbnail directly into the output file |
| 🐢 **Rate limiting** | Prevents throttling and IP bans on bulk downloads |
| 🔑 **Cookie auth** | Supports age-restricted and private videos via a `cookies.txt` file |
| ♻️ **Resume support** | Interrupted downloads restart from where they left off |
| 📊 **Structured results** | Every call returns a typed `DownloadResult` — safe to use as a library |
| 📋 **Structured logging** | All output goes through Python's `logging` module — no bare `print()` calls |
| ✅ **Typed & linted** | Full type annotations, `mypy --strict`, and `ruff` checks |
| 🧪 **Tested** | Comprehensive `pytest` suite with mocks for all external calls |
| 🤖 **CI/CD ready** | GitHub Actions workflow for lint, type-check, and tests on Python 3.10–3.12 |

---

## Requirements

| Dependency | Minimum version | Notes |
|---|---|---|
| Python | 3.10 | Uses `X \| Y` union syntax and `match` |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 2024.1.0 | Installed automatically |
| [FFmpeg](https://ffmpeg.org/) | Any recent build | Required for merging formats and audio extraction |

### Installing FFmpeg

<details>
<summary><strong>macOS</strong></summary>

```bash
brew install ffmpeg
```
</details>

<details>
<summary><strong>Ubuntu / Debian</strong></summary>

```bash
sudo apt update && sudo apt install ffmpeg
```
</details>

<details>
<summary><strong>Windows</strong></summary>

Download a build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add it to your `PATH`.
</details>

---

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/YOUR_USERNAME/ytdlp-pro.git
cd ytdlp-pro
pip install -e ".[dev]"
```

### From PyPI *(once published)*

```bash
pip install ytdlp-pro
```

---

## Quick start

```bash
# Download a single video at best quality
ytdlp-pro https://youtu.be/dQw4w9WgXcQ

# Download at 720p into a custom folder
ytdlp-pro https://youtu.be/dQw4w9WgXcQ -q 720p -o ~/Videos

# Extract audio as MP3 320k
ytdlp-pro https://youtu.be/dQw4w9WgXcQ --audio-only

# Download a full playlist
ytdlp-pro "https://www.youtube.com/playlist?list=PL..." --playlist

# Download with English + Arabic subtitles
ytdlp-pro https://youtu.be/dQw4w9WgXcQ --subtitles --sub-langs en ar

# Throttle to 2 MB/s (useful for bulk downloads)
ytdlp-pro https://youtu.be/dQw4w9WgXcQ --rate-limit 2M

# Age-restricted video using a cookies file
ytdlp-pro https://youtu.be/xxx --cookies ~/cookies.txt
```

---

## CLI reference

```
usage: ytdlp-pro [-h] [-o DIR] [-f NAME] [-q QUALITY] [-a] [-p]
                 [--subtitles] [--sub-langs LANG [LANG ...]]
                 [--rate-limit RATE] [--cookies FILE]
                 [--embed-thumbnail] [-v]
                 url
```

| Flag | Short | Default | Description |
|---|---|---|---|
| `url` | — | *(required)* | YouTube video or playlist URL |
| `--output-dir` | `-o` | `downloads/` | Destination directory (created automatically) |
| `--filename` | `-f` | video title | Custom output filename stem (single-video only) |
| `--quality` | `-q` | `best` | Quality preset: `best` `1080p` `720p` `480p` `360p` |
| `--audio-only` | `-a` | off | Extract audio as MP3 320 kbps |
| `--playlist` | `-p` | off | Download all items in a playlist |
| `--subtitles` | — | off | Write subtitle files alongside the video |
| `--sub-langs` | — | `en` | Space-separated BCP-47 language codes |
| `--rate-limit` | — | unlimited | Max download speed, e.g. `2M`, `500K` |
| `--cookies` | — | none | Path to Netscape `cookies.txt` |
| `--embed-thumbnail` | — | off | Embed thumbnail into the output file |
| `--verbose` | `-v` | off | Enable debug-level logging |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Download completed successfully |
| `1` | Download failed (details logged to stderr) |

---

## Python API

`ytdlp-pro` is designed to be used both as a CLI tool **and** as a library.

```python
from ytdlp_pro import download_media

result = download_media(
    url="https://youtu.be/dQw4w9WgXcQ",
    output_dir="my_videos",
    quality="720p",
    subtitles=True,
    subtitle_langs=["en", "ar"],
)

if result:
    print(f"Saved to: {result.output_path}")
else:
    print(f"Failed:   {result.error}")
    for warning in result.warnings:
        print(f"  ⚠  {warning}")
```

### `download_media()` signature

```python
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
) -> DownloadResult: ...
```

### `DownloadResult`

```python
@dataclass
class DownloadResult:
    success: bool
    output_path: Path | None    # None on failure
    error: str | None           # None on success
    warnings: list[str]         # Non-fatal issues

    def __bool__(self) -> bool: ...   # True iff success
```

---

## Project structure

```
ytdlp-pro/
├── ytdlp_pro/
│   ├── __init__.py          # Public API surface
│   ├── downloader.py        # Core download engine + DownloadResult
│   └── cli.py               # Argument parser + entry point
│
├── tests/
│   └── test_downloader.py   # pytest suite (mocked yt-dlp)
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml           # Lint + type-check + tests on Python 3.10–3.12
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                  # MIT
├── pyproject.toml           # PEP 517/518 packaging + tool config
└── README.md
```

---

## Running tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=ytdlp_pro --cov-report=term-missing

# Single test file
pytest tests/test_downloader.py -v
```

---

## Contributing

Contributions are welcome!  Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## License

Distributed under the **MIT License**.  See [LICENSE](LICENSE) for full terms.

---

## Disclaimer

This tool is intended for **personal, offline, and educational use only**.  Always respect the terms of service of the platforms you download from and honour content creators' copyright.
