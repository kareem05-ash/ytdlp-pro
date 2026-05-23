# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] – 2026-05-23

### Added
- `download_media()` public API with typed `DownloadResult` return value
- Quality presets: `best`, `1080p`, `720p`, `480p`, `360p`
- Audio-only mode (MP3 320 kbps via FFmpeg)
- Subtitle download with multi-language support (`--subtitles`, `--sub-langs`)
- Rate limiting (`--rate-limit`)
- Cookie-based authentication for age-restricted content (`--cookies`)
- Thumbnail embedding (`--embed-thumbnail`)
- Structured logging via the standard `logging` module
- Proper exit codes for shell/CI scripting
- Full test suite with `pytest`
- GitHub Actions CI for linting, type-checking, and testing on Python 3.10–3.12
- `pyproject.toml` packaging (PEP 517/518 compliant)

### Fixed
- Removed deprecated `continuedl` yt-dlp option (now default behaviour)

### Changed
- Replaced bare `print()` calls with `logging` throughout

---

## [Unreleased]

_Nothing yet._
