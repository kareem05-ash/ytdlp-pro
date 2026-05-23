"""
Unit tests for ytdlp-pro.

Run with:  pytest
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ytdlp_pro.downloader import (
    QUALITY_MAP,
    DownloadResult,
    _build_output_template,
    _create_output_directory,
    download_media,
)


# ---------------------------------------------------------------------------
# _create_output_directory
# ---------------------------------------------------------------------------

class TestCreateOutputDirectory:
    def test_creates_directory(self, tmp_path):
        target = tmp_path / "new" / "nested"
        result = _create_output_directory(str(target))
        assert result.is_dir()

    def test_returns_path_object(self, tmp_path):
        result = _create_output_directory(str(tmp_path))
        assert isinstance(result, Path)

    def test_idempotent_on_existing_directory(self, tmp_path):
        _create_output_directory(str(tmp_path))
        _create_output_directory(str(tmp_path))  # should not raise
        assert tmp_path.is_dir()


# ---------------------------------------------------------------------------
# _build_output_template
# ---------------------------------------------------------------------------

class TestBuildOutputTemplate:
    def test_playlist_template(self, tmp_path):
        tmpl = _build_output_template(tmp_path, filename=None, is_playlist=True)
        assert "%(playlist_title)s" in tmpl
        assert "%(playlist_index)s" in tmpl

    def test_custom_filename(self, tmp_path):
        tmpl = _build_output_template(tmp_path, filename="my_video", is_playlist=False)
        assert "my_video.%(ext)s" in tmpl

    def test_default_filename(self, tmp_path):
        tmpl = _build_output_template(tmp_path, filename=None, is_playlist=False)
        assert "%(title)s.%(ext)s" in tmpl

    def test_playlist_ignores_filename(self, tmp_path):
        tmpl = _build_output_template(tmp_path, filename="ignored", is_playlist=True)
        assert "ignored" not in tmpl


# ---------------------------------------------------------------------------
# download_media
# ---------------------------------------------------------------------------

class TestDownloadMedia:
    """Tests for download_media() using a mocked YoutubeDL."""

    def _make_mock_ydl(self):
        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_returns_download_result(self, tmp_path):
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            MockYDL.return_value = self._make_mock_ydl()
            result = download_media("https://youtu.be/test", output_dir=str(tmp_path))
        assert isinstance(result, DownloadResult)

    def test_success_on_clean_run(self, tmp_path):
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            MockYDL.return_value = self._make_mock_ydl()
            result = download_media("https://youtu.be/test", output_dir=str(tmp_path))
        assert result.success is True

    def test_invalid_quality_returns_failure(self, tmp_path):
        result = download_media(
            "https://youtu.be/test",
            output_dir=str(tmp_path),
            quality="4k",  # not in QUALITY_MAP
        )
        assert result.success is False
        assert "Invalid quality" in (result.error or "")

    def test_missing_cookies_file_returns_failure(self, tmp_path):
        result = download_media(
            "https://youtu.be/test",
            output_dir=str(tmp_path),
            cookies="/nonexistent/cookies.txt",
        )
        assert result.success is False
        assert "Cookies file not found" in (result.error or "")

    def test_download_error_captured(self, tmp_path):
        import yt_dlp

        with patch("yt_dlp.YoutubeDL") as MockYDL:
            instance = self._make_mock_ydl()
            instance.download.side_effect = yt_dlp.utils.DownloadError("403 Forbidden")
            MockYDL.return_value = instance
            result = download_media("https://youtu.be/bad", output_dir=str(tmp_path))

        assert result.success is False
        assert result.error is not None

    def test_unexpected_error_captured(self, tmp_path):
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            instance = self._make_mock_ydl()
            instance.download.side_effect = RuntimeError("something broke")
            MockYDL.return_value = instance
            result = download_media("https://youtu.be/bad", output_dir=str(tmp_path))

        assert result.success is False
        assert "something broke" in (result.error or "")

    def test_audio_only_uses_postprocessor(self, tmp_path):
        captured: list[dict] = []

        def fake_ydl(opts):
            captured.append(opts)
            return self._make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            download_media("https://youtu.be/x", output_dir=str(tmp_path), audio_only=True)

        assert any("postprocessors" in o for o in captured)

    def test_rate_limit_passed_through(self, tmp_path):
        captured: list[dict] = []

        def fake_ydl(opts):
            captured.append(opts)
            return self._make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            download_media(
                "https://youtu.be/x",
                output_dir=str(tmp_path),
                rate_limit="2M",
            )

        assert any(o.get("ratelimit") == "2M" for o in captured)

    def test_subtitles_options_set(self, tmp_path):
        captured: list[dict] = []

        def fake_ydl(opts):
            captured.append(opts)
            return self._make_mock_ydl()

        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl):
            download_media(
                "https://youtu.be/x",
                output_dir=str(tmp_path),
                subtitles=True,
                subtitle_langs=["ar", "en"],
            )

        opts = captured[0]
        assert opts.get("writesubtitles") is True
        assert "ar" in opts.get("subtitleslangs", [])


# ---------------------------------------------------------------------------
# DownloadResult
# ---------------------------------------------------------------------------

class TestDownloadResult:
    def test_bool_true_on_success(self):
        assert bool(DownloadResult(success=True)) is True

    def test_bool_false_on_failure(self):
        assert bool(DownloadResult(success=False)) is False

    def test_warnings_default_empty(self):
        r = DownloadResult(success=True)
        assert r.warnings == []


# ---------------------------------------------------------------------------
# QUALITY_MAP completeness
# ---------------------------------------------------------------------------

class TestQualityMap:
    @pytest.mark.parametrize("key", ["best", "1080p", "720p", "480p", "360p"])
    def test_all_keys_present(self, key):
        assert key in QUALITY_MAP

    @pytest.mark.parametrize("key", ["best", "1080p", "720p", "480p", "360p"])
    def test_values_are_non_empty_strings(self, key):
        assert isinstance(QUALITY_MAP[key], str)
        assert len(QUALITY_MAP[key]) > 0
