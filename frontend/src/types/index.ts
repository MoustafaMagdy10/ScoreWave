// API Types
export interface AudioFile {
  id: string;
  filename: string;
  uploadedAt: string;
  status: 'processing' | 'completed' | 'failed';
  size: number;
}

export interface SheetMusicInfo {
  musicxml_url: string;
  sheet_midi_url: string;
  key_signature: string;
  key_confidence: number;
  dynamics_added: number;
  rest_count: number;
}

export interface EasternMusicInfo {
  maqam: string;
  maqam_confidence: number;
  quarter_tone_count: number;
  is_eastern: boolean;
}

export interface ProcessingResult {
  job_id: string;
  melody_midi_url: string;
  melody_json_url: string;
  musicxml_url: string | null;
  note_count: number;
  duration_s: number;
  tempo_bpm: number | null;
  key_signature: string | null;
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
  sheet_music: SheetMusicInfo | null;
  eastern_music: EasternMusicInfo | null;
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

export interface StemInfo {
  name: string;
  key: keyof SeparationResult['stems'];
  url: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: string;
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

// Transpose Types
export interface NoteData {
  pitch: number;
  start_time?: number;
  end_time?: number;
  duration?: number;
  velocity?: number;
  [key: string]: unknown;
}

export interface TransposeRequest {
  notes: NoteData[];
  semitones?: number;
  from_key?: string;
  to_key?: string;
}

export interface TransposeResponse {
  notes: NoteData[];
  semitones_applied: number;
  note_count: number;
}

export interface AvailableKeysResponse {
  keys: string[];
}