import express, { Request, Response } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import { MinioStorageService } from './storage/MinioService';
import { PipelineDispatcher } from './jobs/PipelineDispatcher';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());
app.use(express.raw({ type: 'application/octet-stream', limit: '500mb' }));

const storageService = new MinioStorageService();
const dispatcher = new PipelineDispatcher();

// 1. Session Setup Metadata Endpoint
app.post('/api/sessions', (req: Request, res: Response) => {
  const { sessionId, intrinsics, scaleFactorPpm, speakers } = req.body;
  
  if (!sessionId) {
    return res.status(400).json({ error: 'sessionId is required' });
  }

  const job = dispatcher.createJob(sessionId);
  return res.status(201).json({
    message: 'Session setup initialized successfully',
    sessionId,
    status: job.status
  });
});

// 2. Presigned Upload URL Endpoint
app.post('/api/sessions/:id/upload-url', (req: Request, res: Response) => {
  const sessionId = req.params.id;
  const { fileName } = req.body;

  if (!fileName) {
    return res.status(400).json({ error: 'fileName is required' });
  }

  const presigned = storageService.getPresignedUploadUrl(sessionId, fileName);
  return res.json(presigned);
});

// 3. Binary Upload Direct Endpoint
app.put('/api/sessions/:id/upload/:fileId', (req: Request, res: Response) => {
  const { id: sessionId, fileId } = req.params;
  const targetPath = path.resolve(process.cwd(), `./storage_data/${sessionId}/${fileId}`);

  if (!req.body || !Buffer.isBuffer(req.body)) {
    return res.status(400).json({ error: 'Invalid binary buffer' });
  }

  storageService.saveUploadedChunk(targetPath, req.body);
  return res.json({ message: 'Chunk uploaded successfully', fileId, size: req.body.length });
});

// 4. Start Pipeline Processing Endpoint
app.post('/api/sessions/:id/start-processing', (req: Request, res: Response) => {
  const sessionId = req.params.id;
  const job = dispatcher.getJob(sessionId) || dispatcher.createJob(sessionId);

  dispatcher.dispatchJob(sessionId);

  return res.json({
    message: 'Pipeline processing dispatched',
    sessionId,
    status: job.status
  });
});

// 5. Query Session Job Status Endpoint
app.get('/api/sessions/:id/status', (req: Request, res: Response) => {
  const sessionId = req.params.id;
  const job = dispatcher.getJob(sessionId);

  if (!job) {
    return res.status(404).json({ error: 'Session job not found' });
  }

  return res.json(job);
});

app.listen(PORT, () => {
  console.log(`[+] Private Podcast Backend API listening on http://localhost:${PORT}`);
});
