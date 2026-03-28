import axios, { type AxiosInstance, type AxiosResponse } from 'axios';
import type { ProcessingResult, SeparationResult } from '../types';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: 'http://localhost:8000/api',
      timeout: 300000, // 5 minutes for long processing tasks
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error);
        throw error;
      }
    );
  }

  // Health check
  async healthCheck(): Promise<{ Hello: string }> {
    const response: AxiosResponse<{ Hello: string }> = await this.client.get('/');
    return response.data;
  }

  // Upload and process audio (main pipeline)
  async processAudio(file: File): Promise<ProcessingResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response: AxiosResponse<ProcessingResult> = await this.client.post('/pipeline', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  }

  // Separate audio into stems
  async separateAudio(file: File): Promise<SeparationResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response: AxiosResponse<SeparationResult> = await this.client.post('/separate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  }

  // Download file (MIDI, PDF, stems)
  async downloadFile(url: string, filename?: string): Promise<Blob> {
    const response: AxiosResponse<Blob> = await this.client.get(url, {
      responseType: 'blob',
    });

    // Create download link
    const blob = new Blob([response.data]);
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(downloadUrl);

    return blob;
  }

  // Get processing status (for future polling implementation)
  async getProcessingStatus(jobId: string): Promise<{ status: string; progress: number }> {
    const response = await this.client.get(`/status/${jobId}`);
    return response.data;
  }
}

export const apiClient = new ApiClient();
export default ApiClient;