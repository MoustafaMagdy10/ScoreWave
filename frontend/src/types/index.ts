// API Types
export interface AudioFile {
  id: string;
  filename: string;
  uploadedAt: string;
  status: 'processing' | 'completed' | 'failed';
  size: number;
}

export interface ProcessingResult {
  job_id: string;
  melody_midi_url: string;
  melody_json_url: string;
  note_count: number;
  duration_s: number;
  tempo_bpm: number | null;
  stats: {
    original_count: number;
    after_range_filter: number;
    after_melodic_filter: number;
    after_pattern_filter: number;
    final_count: number;
    reduction_pct: number;
    vocal_guided: boolean;
    vocal_note_count: number;
  };
  stems: {
    vocals: string;
    no_vocals: string;
    drums: string;
    bass: string;
    other: string;
  };
}

export interface SeparationResult {
  job_id: string;
  stems: {
    vocals: string;
    no_vocals: string;
    drums: string;
    bass: string;
    other: string;
  };
}

// User Types (for future implementation)
export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  createdAt: string;
}

export interface UserProfile extends User {
  preferences: {
    defaultKey: string;
    defaultTempo: number;
  };
}

// Processing Status
export interface ProcessingStatus {
  stage: 'uploading' | 'separating' | 'transcribing' | 'analyzing' | 'completed' | 'failed';
  progress: number;
  message: string;
}