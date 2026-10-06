/**
 * Phase 1.2 Voice Enrollment Module (Mobile App)
 * Prompts each podcast speaker to read an on-screen prompt snippet.
 * Captures clean audio audio samples and generates reference voiceprint embeddings.
 */

export interface EnrolledVoiceprint {
  speakerId: string;
  name: string;
  audioSamplePath: string;
  embeddingVector: number[];
}

export class VoiceEnrollmentModule {
  private enrolledSpeakers: Map<string, EnrolledVoiceprint> = new Map();

  public async recordSpeakerEnrollmentPrompt(
    speakerId: string,
    name: string,
    onProgress?: (percent: number) => void
  ): Promise<EnrolledVoiceprint> {
    console.log(`[Voice Enrollment] Recording prompt sample for ${name} (${speakerId})...`);

    // Simulate 3-second voice enrollment recording sample
    for (let p = 20; p <= 100; p += 20) {
      if (onProgress) onProgress(p);
    }

    // Mock 128-dimensional embedding vector (SpeechBrain ECAPA-TDNN format)
    const mockEmbedding = Array.from({ length: 128 }, (_, idx) => 
      Math.sin((idx + 1) * (speakerId === 'Speaker_1' ? 1.0 : 2.5))
    );

    const result: EnrolledVoiceprint = {
      speakerId,
      name,
      audioSamplePath: `/storage/voiceprints/${speakerId}_prompt.wav`,
      embeddingVector: mockEmbedding
    };

    this.enrolledSpeakers.set(speakerId, result);
    console.log(`[Voice Enrollment] Enrollment complete for ${name}. Voiceprint vector created.`);
    return result;
  }

  public getEnrolledSpeakers(): EnrolledVoiceprint[] {
    return Array.from(this.enrolledSpeakers.values());
  }
}
