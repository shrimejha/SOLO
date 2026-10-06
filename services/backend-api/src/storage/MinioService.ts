import fs from 'fs';
import path from 'path';

export interface PresignedUploadUrlResponse {
  fileId: string;
  uploadUrl: string;
  targetPath: string;
}

export class MinioStorageService {
  private storageDir: string;

  constructor() {
    this.storageDir = path.resolve(process.cwd(), './storage_data');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
  }

  public getPresignedUploadUrl(sessionId: string, fileName: string): PresignedUploadUrlResponse {
    const sessionDir = path.join(this.storageDir, sessionId);
    if (!fs.existsSync(sessionDir)) {
      fs.mkdirSync(sessionDir, { recursive: true });
    }

    const fileId = `${Date.now()}_${fileName}`;
    const targetPath = path.join(sessionDir, fileId);

    return {
      fileId,
      uploadUrl: `/api/sessions/${sessionId}/upload/${fileId}`,
      targetPath
    };
  }

  public saveUploadedChunk(targetPath: string, buffer: Buffer): void {
    fs.writeFileSync(targetPath, buffer);
  }

  public getDownloadUrl(sessionId: string, fileName: string): string {
    return `/api/sessions/${sessionId}/download/${fileName}`;
  }
}
