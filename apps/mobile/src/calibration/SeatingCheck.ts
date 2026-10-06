/**
 * Phase 1.3 Guided Seating Check (Mobile Preview Overlay)
 * Performs real-time face detection on preview frames.
 * Uses calibration scale factor to ENFORCE a strict distance/spacing boundary
 * between podcaster subjects before enabling the recording button.
 */

export interface DetectedPersonFrame {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  distanceMeter: number;
}

export interface SeatingCheckValidationResult {
  isValid: boolean;
  message: string;
  detectedPeopleCount: number;
  separationDistanceMeter: number;
}

export class SeatingCheckEngine {
  private minAllowedDistanceMeter: number = 0.8;
  private maxAllowedDistanceMeter: number = 3.5;
  private scaleFactorPpm: number;

  constructor(scaleFactorPpm: number = 1200.0) {
    this.scaleFactorPpm = scaleFactorPpm;
  }

  public validateSeatingLayout(people: DetectedPersonFrame[]): SeatingCheckValidationResult {
    if (people.length < 2) {
      return {
        isValid: false,
        message: 'Please seat at least 2 speakers in view of the camera preview.',
        detectedPeopleCount: people.length,
        separationDistanceMeter: 0
      };
    }

    // Sort left to right
    const sorted = [...people].sort((a, b) => a.x - b.x);
    const p1 = sorted[0];
    const p2 = sorted[sorted.length - 1];

    // Compute pixel distance between centers
    const p1CenterX = p1.x + p1.width / 2;
    const p2CenterX = p2.x + p2.width / 2;
    const pixelDistance = Math.abs(p2CenterX - p1CenterX);

    // Convert pixel distance to metric distance using Phase 0 scale factor
    const metricDistance = pixelDistance / this.scaleFactorPpm;

    if (metricDistance < this.minAllowedDistanceMeter) {
      return {
        isValid: false,
        message: `Speakers are sitting too close (${metricDistance.toFixed(2)}m). Please separate to at least ${this.minAllowedDistanceMeter}m.`,
        detectedPeopleCount: people.length,
        separationDistanceMeter: metricDistance
      };
    }

    if (metricDistance > this.maxAllowedDistanceMeter) {
      return {
        isValid: false,
        message: `Speakers are sitting too far apart (${metricDistance.toFixed(2)}m) for locked main lens pan headroom. Please move closer.`,
        detectedPeopleCount: people.length,
        separationDistanceMeter: metricDistance
      };
    }

    return {
      isValid: true,
      message: `Seating geometry valid (${metricDistance.toFixed(2)}m spacing). Recording UNLOCKED.`,
      detectedPeopleCount: people.length,
      separationDistanceMeter: metricDistance
    };
  }
}
