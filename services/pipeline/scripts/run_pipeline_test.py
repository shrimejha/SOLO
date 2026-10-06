"""
Synthetic Session Test Generator & Execution Runner
Generates synthetic podcaster video frames & audio signals to test the complete AI camera pipeline.
"""

import sys
import os
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import PipelineOrchestrator
from src.calibration import CalibrationData, CameraIntrinsics
from src.identity_track import SpeakerVoiceprint

def generate_synthetic_podcast_session():
    width, height = 3840, 2160
    num_frames = 60  # 2 seconds @ 30fps

    frames = []

    for i in range(num_frames):
        # Studio background (dark aesthetic)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (25, 20, 30)  # Dark purple-grey tone

        # Studio lights / decor background lines
        cv2.rectangle(frame, (100, 100), (3740, 2060), (45, 35, 55), 4)

        # Speaker 1 (Left Side - Host)
        spk1_x, spk1_y = 900, 900
        cv2.circle(frame, (spk1_x, spk1_y), 180, (200, 150, 100), -1)  # Face
        # Mouth movement simulation (moving up/down when speaking)
        mouth_offset = int(np.sin(i * 0.8) * 15) if i < 30 else 0
        cv2.ellipse(frame, (spk1_x, spk1_y + 80), (50, 20 + abs(mouth_offset)), 0, 0, 180, (50, 40, 100), -1)

        # Speaker 2 (Right Side - Guest)
        spk2_x, spk2_y = 2900, 900
        cv2.circle(frame, (spk2_x, spk2_y), 180, (100, 150, 200), -1)  # Face
        mouth_offset2 = int(np.sin(i * 0.8) * 15) if i >= 30 else 0
        cv2.ellipse(frame, (spk2_x, spk2_y + 80), (50, 20 + abs(mouth_offset2)), 0, 0, 180, (50, 100, 40), -1)

        # Text overlay labels
        cv2.putText(frame, "HOST (Speaker 1)", (spk1_x - 150, spk1_y - 220), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 4)
        cv2.putText(frame, "GUEST (Speaker 2)", (spk2_x - 150, spk2_y - 220), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 4)

        frames.append(frame)

    # Generate synthetic 16kHz audio sample array
    duration_sec = num_frames / 30.0
    num_samples = int(16000 * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)

    # First half Speaker 1 (440Hz tone + noise), Second half Speaker 2 (880Hz tone + noise)
    audio = np.zeros(num_samples, dtype=np.float32)
    half = num_samples // 2
    audio[:half] = 0.3 * np.sin(2 * np.pi * 440 * t[:half]) + 0.01 * np.random.randn(half)
    audio[half:] = 0.3 * np.sin(2 * np.pi * 880 * t[half:]) + 0.01 * np.random.randn(num_samples - half)

    # Calibration data
    calib = CalibrationData(
        intrinsics=CameraIntrinsics(fx=3000.0, fy=3000.0, cx=1920.0, cy=1080.0),
        scale_factor_ppm=1200.0,
        reference_plate_paths=["plate1.png"]
    )

    # Voiceprints
    vp1 = SpeakerVoiceprint(speaker_id="Speaker_1", name="Host", embedding=[0.1] * 128)
    vp2 = SpeakerVoiceprint(speaker_id="Speaker_2", name="Guest", embedding=[0.9] * 128)

    return frames, audio, calib, [vp1, vp2]

if __name__ == "__main__":
    print("[*] Generating synthetic 4K podcaster session...")
    frames, audio, calib, voiceprints = generate_synthetic_podcast_session()

    orchestrator = PipelineOrchestrator(output_dir="./test_output")
    res = orchestrator.process_session(
        session_id="synth_session_001",
        video_frames=frames,
        audio_samples=audio,
        calibration_data=calib,
        voiceprints=voiceprints
    )

    print("\n[=== Test Execution Complete ===]")
    print(res)
