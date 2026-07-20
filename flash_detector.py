"""
WCAG 2.3.1 Flash Detection Engine
Detects general flashes and red flashes that could trigger seizures.
"""

import cv2
import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class FlashViolation:
    timestamp: float
    delta: float
    flash_type: str  # "general" or "red"
    area_percent: float


class FlashDetector:
    """
    Detects flashing content per WCAG 2.3.1 Success Criterion.

    WCAG thresholds:
    - General flashes: no more than 3 per second
    - Red flashes: no more than 3 per second
    - Flash area: must not exceed 25% of screen
    """

    GENERAL_FLASH_THRESHOLD = 0.10  # 10% luminance change
    RED_FLASH_THRESHOLD_R = 0.80    # Red channel threshold
    RED_FLASH_THRESHOLD_GB = 0.20   # Green/Blue channel threshold
    MAX_FLASHES_PER_SECOND = 3
    MAX_FLASH_AREA_PERCENT = 25.0
    SAMPLE_FPS = 30

    def __init__(self, sample_fps: int = 30):
        self.sample_fps = sample_fps

    def _extract_luminance(self, frame: np.ndarray) -> np.ndarray:
        """Calculate relative luminance per pixel (WCAG formula)."""
        frame = frame.astype(np.float32) / 255.0
        r, g, b = frame[:, :, 2], frame[:, :, 1], frame[:, :, 0]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _is_red_flash(self, frame1: np.ndarray, frame2: np.ndarray) -> tuple:
        """
        Detect saturated red flashes.
        Returns: (is_red_flash, area_percent)
        """
        f1 = frame1.astype(np.float32) / 255.0
        f2 = frame2.astype(np.float32) / 255.0

        # Check for saturated red in either frame
        red_mask1 = (f1[:, :, 2] > self.RED_FLASH_THRESHOLD_R) & \
                    (f1[:, :, 1] < self.RED_FLASH_THRESHOLD_GB) & \
                    (f1[:, :, 0] < self.RED_FLASH_THRESHOLD_GB)
        red_mask2 = (f2[:, :, 2] > self.RED_FLASH_THRESHOLD_R) & \
                    (f2[:, :, 1] < self.RED_FLASH_THRESHOLD_GB) & \
                    (f2[:, :, 0] < self.RED_FLASH_THRESHOLD_GB)

        # Flash occurs if red appears/disappears between frames
        flash_mask = red_mask1 != red_mask2
        area_percent = (np.sum(flash_mask) / flash_mask.size) * 100

        return np.any(flash_mask), area_percent

    def analyze(self, video_path: str) -> Dict[str, Any]:
        """
        Analyze video for flashing content.

        Returns:
            {
                "status": "PASS" | "FAIL",
                "score": float (0.0 to 1.0),
                "max_flashes_per_second": int,
                "max_red_flashes_per_second": int,
                "violations": List[FlashViolation],
                "details": {...}
            }
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {
                "status": "ERROR",
                "score": 0.0,
                "error": "Could not open video file"
            }

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(fps / self.sample_fps))

        lum_values = []
        timestamps = []
        frames = []

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                lum = self._extract_luminance(frame)
                lum_values.append(np.mean(lum))
                timestamps.append(frame_idx / fps)
                frames.append(frame)
            frame_idx += 1

        cap.release()

        if len(lum_values) < 2:
            return {
                "status": "PASS",
                "score": 1.0,
                "max_flashes_per_second": 0,
                "violations": [],
                "details": {"message": "Video too short to analyze"}
            }

        # Detect general flashes
        general_violations = []
        for i in range(1, len(lum_values)):
            delta = abs(lum_values[i] - lum_values[i - 1])
            if delta > self.GENERAL_FLASH_THRESHOLD:
                general_violations.append(FlashViolation(
                    timestamp=timestamps[i],
                    delta=round(float(delta), 3),
                    flash_type="general",
                    area_percent=100.0  # Simplified: assume full frame
                ))

        # Detect red flashes
        red_violations = []
        for i in range(1, len(frames)):
            is_red, area = self._is_red_flash(frames[i - 1], frames[i])
            if is_red and area > 1.0:  # Ignore tiny areas
                red_violations.append(FlashViolation(
                    timestamp=timestamps[i],
                    delta=0.0,
                    flash_type="red",
                    area_percent=round(float(area), 2)
                ))

        # Count per-second windows
        from collections import defaultdict
        general_per_sec = defaultdict(int)
        red_per_sec = defaultdict(int)

        for v in general_violations:
            general_per_sec[int(v.timestamp)] += 1
        for v in red_violations:
            red_per_sec[int(v.timestamp)] += 1

        max_general = max(general_per_sec.values()) if general_per_sec else 0
        max_red = max(red_per_sec.values()) if red_per_sec else 0

        all_violations = general_violations + red_violations
        all_violations.sort(key=lambda x: x.timestamp)

        # Determine pass/fail
        failed = (
            max_general > self.MAX_FLASHES_PER_SECOND or
            max_red > self.MAX_FLASHES_PER_SECOND
        )

        score = 1.0 if not failed else max(0.0, 1.0 - (max_general / 10.0))

        return {
            "status": "FAIL" if failed else "PASS",
            "score": round(score, 2),
            "max_flashes_per_second": max_general,
            "max_red_flashes_per_second": max_red,
            "total_violations": len(all_violations),
            "violations": [
                {
                    "timestamp": round(v.timestamp, 2),
                    "type": v.flash_type,
                    "delta": v.delta if v.delta > 0 else None,
                    "area_percent": v.area_percent
                }
                for v in all_violations[:50]  # Cap at 50 for report size
            ],
            "details": {
                "frames_analyzed": len(lum_values),
                "video_fps": fps,
                "sample_fps": self.sample_fps,
                "threshold": self.GENERAL_FLASH_THRESHOLD
            }
        }


# CLI entry point for quick testing
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python flash_detector.py <video_path>")
        sys.exit(1)

    detector = FlashDetector()
    result = detector.analyze(sys.argv[1])
    print(json.dumps(result, indent=2))
