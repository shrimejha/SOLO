import { spawn } from 'child_process';
import path from 'path';

export interface PipelineJob {
  sessionId: string;
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress: number;
  result?: any;
  error?: string;
  createdAt: Date;
}

export class PipelineDispatcher {
  private jobs: Map<string, PipelineJob> = new Map();
  private pipelineScriptPath: string;

  constructor() {
    this.pipelineScriptPath = path.resolve(__dirname, '../../../pipeline/scripts/run_pipeline_test.py');
  }

  public createJob(sessionId: string): PipelineJob {
    const job: PipelineJob = {
      sessionId,
      status: 'QUEUED',
      progress: 0,
      createdAt: new Date()
    };
    this.jobs.set(sessionId, job);
    return job;
  }

  public getJob(sessionId: string): PipelineJob | undefined {
    return this.jobs.get(sessionId);
  }

  public dispatchJob(sessionId: string): void {
    const job = this.jobs.get(sessionId);
    if (!job) return;

    job.status = 'PROCESSING';
    job.progress = 10;

    const pipelineDir = path.resolve(__dirname, '../../../pipeline');
    const child = spawn('python', ['scripts/run_pipeline_test.py'], {
      cwd: pipelineDir,
      shell: true
    });

    child.stdout.on('data', (data) => {
      console.log(`[Pipeline ${sessionId}]`, data.toString().trim());
      job.progress = Math.min(90, job.progress + 15);
    });

    child.stderr.on('data', (data) => {
      console.error(`[Pipeline Error ${sessionId}]`, data.toString().trim());
    });

    child.on('close', (code) => {
      if (code === 0) {
        job.status = 'COMPLETED';
        job.progress = 100;
        job.result = {
          renderedVideo: `/api/sessions/${sessionId}/download/rendered_1080p.mp4`,
          subtitles: `/api/sessions/${sessionId}/download/subtitles.srt`,
          highlights: `/api/sessions/${sessionId}/download/highlight_916.mp4`
        };
      } else {
        job.status = 'FAILED';
        job.error = `Pipeline execution failed with exit code ${code}`;
      }
    });
  }
}
