"""
ytdlp-pro
=========
A professional YouTube downloader built on top of yt-dlp.

Quick start
-----------
>>> from ytdlp_pro import download_media
>>> result = download_media("https://youtu.be/dQw4w9WgXcQ", output_dir="my_videos")
>>> print(result.success, result.output_path)
"""

from ytdlp_pro.downloader import DownloadResult, download_media

__all__ = ["DownloadResult", "download_media"]
__version__ = "1.0.0"
