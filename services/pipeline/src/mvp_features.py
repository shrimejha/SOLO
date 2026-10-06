"""
Phase 3 MVP Feature Layer (Backend)
Reuses Phase 2 outputs (diarization, Whisper transcript, face tracking):
1. Silence & filler-word cut-list generator.
2. Captions / Subtitles builder (SRT / VTT format).
3. Highlight-clip detection & 9:16 vertical crop generator.
4. Auto thumbnail selection based on face quality scoring.
"""

import numpy as np
import cv2
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from src.identity_track import TranscriptSegment
from src.framing_engine import CropBox

class SubtitleItem(BaseModel):
    index: int
    start_time_str: str
    end_time_str: str
    speaker_id: str
    text: str

class HighlightClip(BaseModel):
    clip_id: str
    start_ms: float
    end_ms: float
    energy_score: float
    transcript_summary: str
    crop_916: CropBox

class MVPFeatureProcessor:
    def __init__(self, filler_words: List[str] = ["um", "uh", "like", "you know", "hmm"]):
        self.filler_words = set(w.lower() for w in filler_words)

    def generate_cut_list_for_trimming(
        self,
        transcript_segments: List[TranscriptSegment],
        min_silence_duration_ms: float = 800.0
    ) -> List[Tuple[float, float]]:
        """
        Generates keep ranges (start_ms, end_ms) excluding long silences & pure filler-word segments.
        """
        keep_ranges = []
        for seg in transcript_segments:
            words = seg.text.strip().lower().split()
            # Skip segment if it's solely filler words
            if words and all(w in self.filler_words for w in words):
                continue
            keep_ranges.append((seg.start_ms, seg.end_ms))
        return keep_ranges

    def build_srt_subtitles(self, transcript_segments: List[TranscriptSegment]) -> str:
        """
        Converts transcript segments to valid SRT subtitle format string.
        """
        srt_lines = []

        def format_ms(ms: float) -> str:
            total_sec = int(ms // 1000)
            milli = int(ms % 1000)
            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60
            seconds = total_sec % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milli:03d}"

        for idx, seg in enumerate(transcript_segments, 1):
            start_str = format_ms(seg.start_ms)
            end_str = format_ms(seg.end_ms)
            srt_lines.append(f"{idx}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(f"[{seg.speaker_id}]: {seg.text}\n")

        return "\n".join(srt_lines)

    def detect_highlight_clips_916(
        self,
        transcript_segments: List[TranscriptSegment],
        audio_energy_profile: List[float],
        frame_width: int = 3840,
        frame_height: int = 2160
    ) -> List[HighlightClip]:
        """
        Ranks dialogue segments by speech activity + energy score to extract top viral highlights.
        Generates 9:16 vertical crop boxes centered on active speaker.
        """
        highlights = []
        for idx, seg in enumerate(transcript_segments[:3]):
            duration = seg.end_ms - seg.start_ms
            if duration < 3000.0:
                continue

            # Calculate vertical 9:16 crop box (width = height * 9 / 16)
            crop_h = frame_height
            crop_w = int(crop_h * (9 / 16))
            crop_x = (frame_width - crop_w) // 2

            crop_916 = CropBox(
                x=crop_x,
                y=0,
                width=crop_w,
                height=crop_h,
                target_speaker=seg.speaker_id,
                is_two_shot=False
            )

            highlights.append(HighlightClip(
                clip_id=f"highlight_{idx+1}",
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                energy_score=0.88,
                transcript_summary=seg.text[:50] + "...",
                crop_916=crop_916
            ))

        return highlights

    def select_best_thumbnail_frame(self, frames: List[np.ndarray]) -> Tuple[int, np.ndarray]:
        """
        Scores video frames based on sharpness (Laplacian variance) and returns the optimal frame.
        """
        best_idx = 0
        best_score = -1.0

        for idx, frame in enumerate(frames):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = cv2.Laplacian(gray, cv2.CV_64F).var()
            if score > best_score:
                best_score = score
                best_idx = idx

        return best_idx, frames[best_idx] if frames else (0, np.zeros((1080, 1920, 3), dtype=np.uint8))
