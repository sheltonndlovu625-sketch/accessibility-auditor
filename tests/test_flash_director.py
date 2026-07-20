"""
Tests for FlashDetector
"""

import pytest
import numpy as np
from src.flash_detector import FlashDetector


class TestFlashDetector:

    def test_init(self):
        detector = FlashDetector(sample_fps=15)
        assert detector.sample_fps == 15

    def test_extract_luminance(self):
        detector = FlashDetector()
        # Create a simple RGB frame (white)
        frame = np.full((100, 100, 3), 255, dtype=np.uint8)
        lum = detector._extract_luminance(frame)

        # White should have luminance ~1.0
        assert np.isclose(np.mean(lum), 1.0, atol=0.01)

    def test_black_frame_luminance(self):
        detector = FlashDetector()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        lum = detector._extract_luminance(frame)
        assert np.isclose(np.mean(lum), 0.0, atol=0.01)

    def test_red_flash_detection(self):
        detector = FlashDetector()

        # Frame 1: saturated red
        frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
        frame1[:, :, 2] = 255  # Red channel (OpenCV is BGR)

        # Frame 2: black
        frame2 = np.zeros((100, 100, 3), dtype=np.uint8)

        is_red, area = detector._is_red_flash(frame1, frame2)
        assert is_red is True
        assert area > 50.0  # Should detect large area

    def test_no_red_flash(self):
        detector = FlashDetector()

        # Two identical frames
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        is_red, area = detector._is_red_flash(frame, frame)

        assert is_red is False

    def test_analyze_nonexistent_file(self):
        detector = FlashDetector()
        result = detector.analyze("/nonexistent/video.mp4")

        assert result["status"] == "ERROR"
        assert "error" in result