"""
Tests for CaptionChecker
"""

import pytest
from src.caption_checker import CaptionChecker


class TestCaptionChecker:

    def test_init(self):
        checker = CaptionChecker()
        assert checker is not None

    def test_parse_srt_simple(self):
        checker = CaptionChecker()
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:07,000
Second line
"""
        segments = checker._parse_srt(srt_content)
        assert len(segments) == 2
        assert segments[0].text == "Hello world"
        assert segments[0].start == 1.0
        assert segments[0].end == 4.0

    def test_parse_vtt_simple(self):
        checker = CaptionChecker()
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello world

00:00:05.000 --> 00:00:07.000
Second line
"""
        segments = checker._parse_vtt(vtt_content)
        assert len(segments) == 2
        assert segments[0].text == "Hello world"

    def test_time_to_seconds(self):
        checker = CaptionChecker()
        assert checker._time_to_seconds("00:01:30,500") == 90.5
        assert checker._time_to_seconds("01:00:00,000") == 3600.0

    def test_check_coverage(self):
        checker = CaptionChecker()
        from src.caption_checker import CaptionSegment

        segments = [
            CaptionSegment(start=0, end=10, text="Hello"),
            CaptionSegment(start=15, end=25, text="World")
        ]
        coverage = checker._check_coverage(segments, 30.0)
        assert coverage == (20.0 / 30.0) * 100

    def test_check_non_speech(self):
        checker = CaptionChecker()
        from src.caption_checker import CaptionSegment

        segments = [
            CaptionSegment(start=0, end=5, text="[music playing]"),
            CaptionSegment(start=5, end=10, text="Hello world")
        ]
        result = checker._check_non_speech(segments)

        assert result["has_non_speech"] is True
        assert result["count"] >= 1

    def test_analyze_no_video(self):
        checker = CaptionChecker()
        result = checker.analyze("/nonexistent/video.mp4")

        assert result["status"] == "FAIL"
        assert result["score"] == 0.0