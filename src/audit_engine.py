"""
Main Audit Engine — Orchestrates all WCAG compliance checks.
"""

import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from .flash_detector import FlashDetector
from .caption_checker import CaptionChecker


@dataclass
class AuditReport:
    video_id: str
    duration_seconds: float
    wcag_version: str = "2.2"
    overall_compliance: str = "UNKNOWN"
    checks: Dict[str, Any] = None
    summary: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class AuditEngine:
    """
    Orchestrates all accessibility checks and produces a unified report.
    """
    
    AVAILABLE_CHECKS = {
        "captions": "1.2.2_captions",
        "flashing": "2.3.1_flashing",
        "audio_description": "1.2.5_audio_description",
        "contrast": "1.4.3_contrast",
        "sign_language": "1.2.6_sign_language"
    }
    
    def __init__(self):
        self.flash_detector = FlashDetector()
        self.caption_checker = CaptionChecker()
    
    def audit(
        self,
        video_path: str,
        checks: Optional[List[str]] = None,
        caption_path: Optional[str] = None
    ) -> AuditReport:
        """
        Run accessibility audit on a video.
        
        Args:
            video_path: Path to video file
            checks: List of check names to run (default: all)
            caption_path: Optional external caption file
        
        Returns:
            AuditReport with full compliance results
        """
        if not os.path.exists(video_path):
            return AuditReport(
                video_id="unknown",
                duration_seconds=0.0,
                overall_compliance="ERROR",
                checks={},
                summary={"error": "Video file not found"}
            )
        
        # Get video duration
        duration = 0.0
        try:
            import ffmpeg
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
        except Exception:
            pass
        
        checks_to_run = checks or list(self.AVAILABLE_CHECKS.keys())
        results = {}
        
        # Run each requested check
        if "flashing" in checks_to_run:
            results["2.3.1_flashing"] = {
                "level": "A",
                **self.flash_detector.analyze(video_path)
            }
        
        if "captions" in checks_to_run:
            results["1.2.2_captions"] = {
                "level": "A",
                **self.caption_checker.analyze(video_path, caption_path, duration)
            }
        
        # Placeholder checks (not yet implemented)
        if "audio_description" in checks_to_run:
            results["1.2.5_audio_description"] = {
                "level": "AA",
                "status": "NOT_IMPLEMENTED",
                "score": None,
                "details": {"message": "Audio description detection coming in v0.2"}
            }
        
        if "contrast" in checks_to_run:
            results["1.4.3_contrast"] = {
                "level": "AA",
                "status": "NOT_IMPLEMENTED",
                "score": None,
                "details": {"message": "Text contrast analysis coming in v0.2"}
            }
        
        if "sign_language" in checks_to_run:
            results["1.2.6_sign_language"] = {
                "level": "AAA",
                "status": "NOT_IMPLEMENTED",
                "score": None,
                "details": {"message": "Sign language detection coming in v0.2"}
            }
        
        # Calculate summary
        total = len(results)
        passed = sum(1 for r in results.values() if r.get("status") == "PASS")
        failed = sum(1 for r in results.values() if r.get("status") == "FAIL")
        partial = sum(1 for r in results.values() if r.get("status") == "PARTIAL")
        
        # Overall compliance
        if failed > 0:
            overall = "FAIL"
        elif partial > 0:
            overall = "PARTIAL"
        elif passed == total:
            overall = "PASS"
        else:
            overall = "UNKNOWN"
        
        # Level-specific compliance
        level_a_checks = [r for r in results.values() if r.get("level") == "A"]
        level_aa_checks = [r for r in results.values() if r.get("level") == "AA"]
        level_aaa_checks = [r for r in results.values() if r.get("level") == "AAA"]
        
        def level_status(checks_list):
            if any(r.get("status") == "FAIL" for r in checks_list):
                return "FAIL"
            if any(r.get("status") in ("PARTIAL", "NOT_IMPLEMENTED") for r in checks_list):
                return "PARTIAL"
            return "PASS"
        
        summary = {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "level_a_compliance": level_status(level_a_checks),
            "level_aa_compliance": level_status(level_aa_checks),
            "level_aaa_compliance": level_status(level_aaa_checks)
        }
        
        return AuditReport(
            video_id=os.path.basename(video_path),
            duration_seconds=round(duration, 2),
            overall_compliance=overall,
            checks=results,
            summary=summary
        )


# CLI entry point
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python audit_engine.py <video_path> [check1,check2,...]")
        print("Available checks: captions, flashing, audio_description, contrast, sign_language")
        sys.exit(1)
    
    engine = AuditEngine()
    video = sys.argv[1]
    check_list = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    
    report = engine.audit(video, check_list)
    print(report.to_json())
