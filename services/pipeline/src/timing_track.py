"""
Phase 2.1 Fast Timing Track (Runs on backend)
Provides sub-frame speech activity & acoustic onset timing.
Fuses audio triggers with visual active-speaker confidence (lip motion).
Applies VISUAL VETO POWER to prevent mic bleed cross-talk misattribution (Risk 4).
"""

import numpy as np
import cv2
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel

class SpeechTrigger(BaseModel):
    timestamp_ms: float
    duration_ms: float
    is_speech: bool
    acoustic_energy: float

class VisualSpeakerConfidence(BaseModel):
    face_id: str
    bounding_box: Tuple[int, int, int, int]  # x, y, w, h
    lip_activity_score: float  # 0.0 to 1.0
    has_visual_veto: bool = False

class FastTimingTrack:
    def __init__(self, sample_rate: int = 16000, frame_rate: float = 30.0):
        self.sample_rate = sample_rate
        self.frame_rate = frame_rate
        self.energy_threshold = 0.02

    def detect_vad_and_onset(self, audio_chunk: np.ndarray, current_timestamp_ms: float) -> SpeechTrigger:
        """
        Calculates short-term energy and sub-frame voice activity / acoustic onset.
        Avoids ASR latency lag (Risk 3).
        """
        if len(audio_chunk) == 0:
            return SpeechTrigger(
                timestamp_ms=current_timestamp_ms,
                duration_ms=0,
                is_speech=False,
                acoustic_energy=0.0
            )

        energy = float(np.mean(np.square(audio_chunk)))
        is_speech = energy > self.energy_threshold
        duration = (len(audio_chunk) / self.sample_rate) * 1000.0

        return SpeechTrigger(
            timestamp_ms=current_timestamp_ms,
            duration_ms=duration,
            is_speech=is_speech,
            acoustic_energy=energy
        )

    def compute_visual_active_speaker_confidence(
        self,
        frame: np.ndarray,
        previous_frame: np.ndarray,
        faces: List[Tuple[str, Tuple[int, int, int, int]]]
    ) -> List[VisualSpeakerConfidence]:
        """
        Measures lip-motion activity by optical flow / frame difference within lower face regions.
        If lip activity is low while audio energy is high (e.g. mic bleed), triggers VISUAL VETO (Risk 4).
        """
        confidences = []
        if previous_frame is None or frame is None:
            for face_id, bbox in faces:
                confidences.append(VisualSpeakerConfidence(
                    face_id=face_id,
                    bounding_box=bbox,
                    lip_activity_score=0.5,
                    has_visual_veto=False
                ))
            return confidences

        gray1 = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for face_id, (x, y, w, h) in faces:
            # Crop lower half of face (mouth area)
            mouth_y = y + int(h * 0.55)
            mouth_h = int(h * 0.4)
            mouth_x = x + int(w * 0.2)
            mouth_w = int(w * 0.6)

            # Clamp coordinates
            h_img, w_img = frame.shape[:2]
            mouth_x = max(0, min(mouth_x, w_img - 1))
            mouth_y = max(0, min(mouth_y, h_img - 1))
            mouth_w = max(1, min(mouth_w, w_img - mouth_x))
            mouth_h = max(1, min(mouth_h, h_img - mouth_y))

            crop1 = gray1[mouth_y:mouth_y+mouth_h, mouth_x:mouth_x+mouth_w]
            crop2 = gray2[mouth_y:mouth_y+mouth_h, mouth_x:mouth_x+mouth_w]

            if crop1.size == 0 or crop2.size == 0 or crop1.shape != crop2.shape:
                score = 0.0
            else:
                diff = cv2.absdiff(crop1, crop2)
                score = float(np.mean(diff)) / 255.0 * 10.0  # Normalized lip motion metric
                score = min(1.0, max(0.0, score))

            # Visual veto triggers if lip motion is below 0.1 threshold despite high audio
            has_veto = score < 0.1

            confidences.append(VisualSpeakerConfidence(
                face_id=face_id,
                bounding_box=(x, y, w, h),
                lip_activity_score=score,
                has_visual_veto=has_veto
            ))

        return confidences
