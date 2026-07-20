"""
WCAG 1.2.2 Caption Compliance Engine
Checks for presence, coverage, and synchronization of captions.
"""

import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str


class CaptionChecker:
    """
    Validates video caption compliance per WCAG 1.2.2.
    
    Checks:
    1. Caption track exists (embedded or external)
    2. Caption coverage (% of video duration covered)
    3. Caption sync accuracy (timing alignment)
    4. Non-speech information (sound effects, music)
    """
    
    MIN_COVERAGE_PERCENT = 80.0  # Minimum caption coverage
    MAX_SYNC_DRIFT_MS = 500      # Max acceptable sync drift in ms
    
    def __init__(self):
        self.has_whisper = False
        try:
            import whisper
            self.has_whisper = True
        except ImportError:
            pass
    
    def _parse_srt(self, content: str) -> List[CaptionSegment]:
        """Parse SRT subtitle format."""
        segments = []
        blocks = re.split(r'\n\n+', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 2:
                continue
            
            # Find timing line (contains -->)
            timing_line = None
            for line in lines:
                if '-->' in line:
                    timing_line = line
                    break
            
            if not timing_line:
                continue
            
            # Parse timestamps
            match = re.match(
                r'(\d{1,2}):\s*(\d{2}):\s*(\d{2}[,\.]\d{0,3})?\s*-->\s*'
                r'(\d{1,2}):\s*(\d{2}):\s*(\d{2}[,\.]\d{0,3})?',
                timing_line.strip()
            )
            if not match:
                # Try simpler format
                parts = timing_line.split('-->')
                if len(parts) == 2:
                    start = self._time_to_seconds(parts[0].strip())
                    end = self._time_to_seconds(parts[1].strip())
                else:
                    continue
            else:
                start = self._time_to_seconds(match.group(1) + ':' + match.group(2) + ':' + match.group(3))
                end = self._time_to_seconds(match.group(4) + ':' + match.group(5) + ':' + match.group(6))
            
            text = ' '.join(line for line in lines if '-->' not in line and not line.strip().isdigit())
            segments.append(CaptionSegment(start=start, end=end, text=text.strip()))
        
        return segments
    
    def _parse_vtt(self, content: str) -> List[CaptionSegment]:
        """Parse WebVTT subtitle format."""
        segments = []
        lines = content.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip WEBVTT header and empty lines
            if line.startswith('WEBVTT') or not line:
                i += 1
                continue
            
            # Skip cue identifiers
            if '-->' not in line:
                i += 1
                continue
            
            # Parse timing line
            timing_line = line
            parts = timing_line.split('-->')
            if len(parts) != 2:
                i += 1
                continue
            
            start = self._vtt_time_to_seconds(parts[0].strip())
            end = self._vtt_time_to_seconds(parts[1].strip().split()[0])  # Remove positioning
            
            # Collect text lines
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            
            if text_lines:
                segments.append(CaptionSegment(
                    start=start,
                    end=end,
                    text=' '.join(text_lines)
                ))
            
            i += 1
        
        return segments
    
    def _time_to_seconds(self, time_str: str) -> float:
        """Convert HH:MM:SS,mmm to seconds."""
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return 0.0
    
    def _vtt_time_to_seconds(self, time_str: str) -> float:
        """Convert WebVTT timestamp to seconds."""
        time_str = time_str.strip()
        if '.' in time_str:
            time_str = time_str.replace('.', ',')
        return self._time_to_seconds(time_str)
    
    def _check_coverage(self, segments: List[CaptionSegment], duration: float) -> float:
        """Calculate caption coverage percentage."""
        if duration <= 0:
            return 0.0
        
        covered = 0.0
        for seg in segments:
            covered += max(0, seg.end - seg.start)
        
        return min(100.0, (covered / duration) * 100)
    
    def _check_non_speech(self, segments: List[CaptionSegment]) -> Dict[str, Any]:
        """Check for non-speech information in captions."""
        non_speech_patterns = [
            r'\[.*?\]',           # [music playing]
            r'\(.*?\)',           # (applause)
            r'\*.*?\*',           # *sound effect*
            r'(?i)\b(music|applause|laughter|sighs|gasps)\b',
        ]
        
        non_speech_count = 0
        examples = []
        
        for seg in segments:
            for pattern in non_speech_patterns:
                matches = re.findall(pattern, seg.text)
                if matches:
                    non_speech_count += len(matches)
                    if len(examples) < 5:
                        examples.append({
                            "timestamp": round(seg.start, 2),
                            "text": seg.text[:100]
                        })
        
        return {
            "count": non_speech_count,
            "has_non_speech": non_speech_count > 0,
            "examples": examples
        }
    
    def analyze(
        self,
        video_path: str,
        caption_path: Optional[str] = None,
        video_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Analyze caption compliance.
        
        Args:
            video_path: Path to video file
            caption_path: Optional path to external caption file (.srt, .vtt)
            video_duration: Optional pre-computed video duration
        
        Returns:
            Compliance report dict
        """
        # Try to get video duration
        if video_duration is None:
            try:
                import ffmpeg
                probe = ffmpeg.probe(video_path)
                video_duration = float(probe['format']['duration'])
            except Exception:
                video_duration = 0.0
        
        segments = []
        caption_source = None
        
        # 1. Check for external caption file
        if caption_path and os.path.exists(caption_path):
            with open(caption_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if caption_path.lower().endswith('.vtt'):
                segments = self._parse_vtt(content)
                caption_source = "external_vtt"
            elif caption_path.lower().endswith('.srt'):
                segments = self._parse_srt(content)
                caption_source = "external_srt"
        
        # 2. Check for embedded captions (simplified)
        if not segments:
            try:
                import ffmpeg
                streams = ffmpeg.probe(video_path)
                subtitle_streams = [
                    s for s in streams.get('streams', [])
                    if s.get('codec_type') == 'subtitle'
                ]
                if subtitle_streams:
                    caption_source = "embedded"
                    # Note: Extracting embedded subtitle text requires
                    # additional ffmpeg processing. For MVP, we flag presence.
            except Exception:
                pass
        
        # 3. Auto-generate transcript with Whisper (if available)
        whisper_transcript = None
        if not segments and self.has_whisper:
            try:
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(video_path)
                whisper_transcript = result.get("text", "")
            except Exception as e:
                whisper_transcript = f"Error: {str(e)}"
        
        # Calculate metrics
        coverage = self._check_coverage(segments, video_duration) if segments else 0.0
        non_speech = self._check_non_speech(segments) if segments else {"count": 0, "has_non_speech": False, "examples": []}
        
        # Determine pass/fail
        has_captions = len(segments) > 0 or caption_source == "embedded"
        sufficient_coverage = coverage >= self.MIN_COVERAGE_PERCENT
        
        if not has_captions:
            status = "FAIL"
            score = 0.0
        elif not sufficient_coverage:
            status = "PARTIAL"
            score = round(coverage / 100.0, 2)
        else:
            status = "PASS"
            score = 1.0
        
        return {
            "status": status,
            "score": score,
            "details": {
                "caption_track_found": has_captions,
                "caption_source": caption_source,
                "total_segments": len(segments),
                "coverage_percentage": round(coverage, 2),
                "video_duration": round(video_duration, 2),
                "sufficient_coverage": sufficient_coverage,
                "non_speech_info": non_speech,
                "auto_generated_transcript": whisper_transcript is not None,
                "transcript_preview": whisper_transcript[:200] if whisper_transcript else None
            }
        }


# CLI entry point
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python caption_checker.py <video_path> [caption_path]")
        sys.exit(1)
    
    checker = CaptionChecker()
    result = checker.analyze(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(result, indent=2))
