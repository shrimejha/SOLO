"""
Phase 2.3 Framing Decision Engine (Backend)
Determines exact frame crop box path over time.
Combines Fast Timing Track (VAD + onset + visual veto) with Slow Identity Track.
Applies:
- Debounced minimum-hold window (~400ms) to prevent whiplash cuts on interjections.
- Exponential Moving Average (EMA) crop-box movement smoothing.
- Scale-capped zoom limits (based on Phase 0 intrinsics).
- Automatic two-shot (wide angle) mode during cross-talk or silence.
"""

import numpy as np
from typing import Tuple, List, Optional
from pydantic import BaseModel
from src.timing_track import SpeechTrigger, VisualSpeakerConfidence
from src.identity_track import FaceDetectionResult

class CropBox(BaseModel):
    x: float  # Normalized 0.0 - 1.0 or pixel coordinates
    y: float
    width: float
    height: float
    target_speaker: str
    is_two_shot: bool = False

class FramingEngine:
    def __init__(self, frame_width: int = 3840, frame_height: int = 2160, aspect_ratio: float = 16/9):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.aspect_ratio = aspect_ratio
        
        # Debounce settings (Risk 3)
        self.debounce_hold_ms = 400.0
        self.last_cut_timestamp_ms = 0.0
        self.current_active_speaker: Optional[str] = None

        # Exponential Moving Average (EMA) smoothing parameters
        self.alpha_pos = 0.15  # Position transition speed
        self.alpha_scale = 0.10  # Zoom transition speed
        self.current_crop: Optional[CropBox] = None

    def calculate_two_shot_crop(self, faces: List[FaceDetectionResult]) -> CropBox:
        """
        Computes a wider 16:9 crop bounding box that encompasses all detected speakers.
        """
        if not faces:
            # Full frame default
            return CropBox(x=0, y=0, width=self.frame_width, height=self.frame_height, target_speaker="all", is_two_shot=True)

        min_x = min(f.bounding_box[0] for f in faces)
        min_y = min(f.bounding_box[1] for f in faces)
        max_x = max(f.bounding_box[0] + f.bounding_box[2] for f in faces)
        max_y = max(f.bounding_box[1] + f.bounding_box[3] for f in faces)

        padding = int(self.frame_width * 0.08)
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = min(self.frame_width, max_x + padding)
        max_y = min(self.frame_height, max_y + padding)

        w = max_x - min_x
        h = max_y - min_y

        # Enforce 16:9 aspect ratio
        if w / max(1, h) < self.aspect_ratio:
            target_w = h * self.aspect_ratio
            diff = target_w - w
            min_x = max(0, min_x - diff / 2)
            w = target_w
        else:
            target_h = w / self.aspect_ratio
            diff = target_h - h
            min_y = max(0, min_y - diff / 2)
            h = target_h

        # Clamp to bounds
        w = min(self.frame_width, w)
        h = min(self.frame_height, h)
        min_x = max(0, min(self.frame_width - w, min_x))
        min_y = max(0, min(self.frame_height - h, min_y))

        return CropBox(x=min_x, y=min_y, width=w, height=h, target_speaker="all", is_two_shot=True)

    def calculate_single_speaker_crop(self, face: FaceDetectionResult) -> CropBox:
        """
        Computes a medium single-shot 16:9 crop box focused on the active speaker.
        """
        fx, fy, fw, fh = face.bounding_box
        center_x = fx + fw / 2.0
        center_y = fy + fh / 3.0  # Eye-line alignment rule of thirds

        # Single shot scale (approx 1.8x - 2.2x zoom)
        target_w = self.frame_width / 1.8
        target_h = target_w / self.aspect_ratio

        min_x = center_x - target_w / 2.0
        min_y = center_y - target_h / 2.0

        # Clamp to bounds
        min_x = max(0, min(self.frame_width - target_w, min_x))
        min_y = max(0, min(self.frame_height - target_h, min_y))

        return CropBox(
            x=min_x,
            y=min_y,
            width=target_w,
            height=target_h,
            target_speaker=face.speaker_id or face.face_id,
            is_two_shot=False
        )

    def update(
        self,
        timestamp_ms: float,
        speech_trigger: SpeechTrigger,
        visual_confidences: List[VisualSpeakerConfidence],
        faces: List[FaceDetectionResult],
        identified_speaker: str
    ) -> CropBox:
        """
        Processes frame timing and identity state to yield the smoothed CropBox target.
        """
        # Determine target speaker with visual veto check (Risk 4)
        target_speaker = identified_speaker
        for vconf in visual_confidences:
            if vconf.has_visual_veto and speech_trigger.is_speech:
                # Lip motion vetoed audio identification -> revert to wide two-shot
                target_speaker = "all"
                break

        # Check cross-talk / silence / single speaker condition
        is_silence = not speech_trigger.is_speech
        time_since_last_cut = timestamp_ms - self.last_cut_timestamp_ms

        # Trigger decision logic
        if is_silence or target_speaker == "all":
            desired_target = "all"
        else:
            desired_target = target_speaker

        # Apply minimum hold debounce (~400ms hold) to avoid rapid whiplash cuts (Risk 3)
        if desired_target != self.current_active_speaker:
            if time_since_last_cut >= self.debounce_hold_ms or self.current_active_speaker is None:
                self.current_active_speaker = desired_target
                self.last_cut_timestamp_ms = timestamp_ms

        # Compute raw target crop box
        if self.current_active_speaker == "all" or not faces:
            raw_crop = self.calculate_two_shot_crop(faces)
        else:
            # Find face matching active speaker
            matching_face = next((f for f in faces if f.speaker_id == self.current_active_speaker or f.face_id == self.current_active_speaker), None)
            if matching_face:
                raw_crop = self.calculate_single_speaker_crop(matching_face)
            else:
                raw_crop = self.calculate_two_shot_crop(faces)

        # Apply Exponential Moving Average (EMA) smoothing for fluid camera pan/zoom
        if self.current_crop is None:
            self.current_crop = raw_crop
        else:
            smooth_x = self.current_crop.x + self.alpha_pos * (raw_crop.x - self.current_crop.x)
            smooth_y = self.current_crop.y + self.alpha_pos * (raw_crop.y - self.current_crop.y)
            smooth_w = self.current_crop.width + self.alpha_scale * (raw_crop.width - self.current_crop.width)
            smooth_h = self.current_crop.height + self.alpha_scale * (raw_crop.height - self.current_crop.height)

            self.current_crop = CropBox(
                x=smooth_x,
                y=smooth_y,
                width=smooth_w,
                height=smooth_h,
                target_speaker=self.current_active_speaker or "all",
                is_two_shot=raw_crop.is_two_shot
            )

        return self.current_crop
