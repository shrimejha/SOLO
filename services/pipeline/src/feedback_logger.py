"""
Phase 4 Learning & Feedback Loop Logger (Backend)
Records user crop correction nudges from the mobile review UI.
Formats training samples (audio features + face positions -> ground truth crop box).
"""

import os
import json
import time
from typing import Dict, Any, List
from pydantic import BaseModel

class CropCorrectionRecord(BaseModel):
    session_id: str
    timestamp_ms: float
    original_crop: Dict[str, float]
    corrected_crop: Dict[str, float]
    speaker_id: str
    user_id: str

class FeedbackLogger:
    def __init__(self, log_directory: str = "./logs/corrections"):
        self.log_directory = log_directory
        os.makedirs(self.log_directory, exist_ok=True)

    def log_correction(self, record: CropCorrectionRecord) -> str:
        """
        Saves user crop adjustment record as labeled JSON sample for ML model training.
        """
        filename = f"correction_{record.session_id}_{int(time.time() * 1000)}.json"
        filepath = os.path.join(self.log_directory, filename)

        with open(filepath, "w") as f:
            json.dump(record.model_dump(), f, indent=2)

        return filepath
