import axios, { type AxiosInstance, type AxiosResponse } from 'axios';
import type { ProcessingResult, SeparationResult, TransposeRequest, TransposeResponse, AvailableKeysResponse, NoteData } from '../types';

const API_BASE_URL = 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/api`,
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
  async healthCheck(): Promise<{ message: string }> {
    const response: AxiosResponse<{ message: string }> = await axios.get(API_BASE_URL);
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

  // Get MusicXML content as text (for OSMD)
  async getMusicXML(url: string): Promise<string> {
    const response = await axios.get(`${API_BASE_URL}${url}`, {
      responseType: 'text',
    });
    return response.data;
  }

  // Download file (MIDI, MusicXML, stems)
  async downloadFile(url: string, filename?: string): Promise<Blob> {
    // URL already includes /api prefix, use base URL directly
    const response: AxiosResponse<Blob> = await axios.get(`${API_BASE_URL}${url}`, {
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

  // Get stem audio URL for streaming/playing
  getStemAudioUrl(stemPath: string): string {
    return `${API_BASE_URL}${stemPath}`;
  }

  // Transpose notes by semitones or to a target key
  async transposeNotes(
    notes: NoteData[],
    options: { semitones?: number; from_key?: string; to_key?: string }
  ): Promise<TransposeResponse> {
    const request: TransposeRequest = {
      notes,
      ...options,
    };
    const response: AxiosResponse<TransposeResponse> = await this.client.post('/transpose', request);
    return response.data;
  }

  // Get available keys for transposition
  async getAvailableKeys(): Promise<string[]> {
    const response: AxiosResponse<AvailableKeysResponse> = await this.client.get('/transpose/keys');
    return response.data.keys;
  }
}

export const apiClient = new ApiClient();
export default ApiClient;