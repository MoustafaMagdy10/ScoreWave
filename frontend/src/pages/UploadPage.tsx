import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { ProcessingResult, NoteData } from '../types';
import ProcessingStatus from '../components/ProcessingStatus';
import SheetMusicViewer from '../components/SheetMusicViewer';
import MaqamCard, { type MaqamInfo } from '../components/MaqamCard';

const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showSheetMusic, setShowSheetMusic] = useState(true);
  const [availableKeys, setAvailableKeys] = useState<string[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>('');
  const [isTransposing, setIsTransposing] = useState(false);
  const [currentNotes, setCurrentNotes] = useState<NoteData[]>([]);
  const [transposedMusicXmlUrl, setTransposedMusicXmlUrl] = useState<string | null>(null);
  const [maqamInfo, setMaqamInfo] = useState<MaqamInfo | null>(null);
  const navigate = useNavigate();

  // Fetch available keys on mount
  useEffect(() => {
    apiClient.getAvailableKeys()
      .then(setAvailableKeys)
      .catch(err => console.error('Failed to fetch available keys:', err));
  }, []);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError(null);
    
    try {
      const processingResult = await apiClient.processAudio(file);
      setResult(processingResult);
      
      // Set initial selected key from result
      if (processingResult.key_signature) {
        setSelectedKey(processingResult.key_signature);
      }
      
      // Fetch notes for transpose functionality
      if (processingResult.melody_json_url) {
        try {
          const response = await fetch(`http://localhost:8000${processingResult.melody_json_url}`);
          const notesData = await response.json();
          setCurrentNotes(notesData.notes || notesData || []);
        } catch (noteErr) {
          console.error('Failed to fetch notes:', noteErr);
        }
      }
      
      // Extract maqam info if available
      if (processingResult.eastern_music) {
        setMaqamInfo(processingResult.eastern_music as MaqamInfo);
      }

      // Save to localStorage for history
      const history = JSON.parse(localStorage.getItem('songify_history') || '[]');
      history.unshift({
        ...processingResult,
        filename: file.name,
        uploadedAt: new Date().toISOString(),
      });
      localStorage.setItem('songify_history', JSON.stringify(history.slice(0, 20))); // Keep last 20
      
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process audio file';
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const downloadMIDI = async () => {
    if (!result) return;
    try {
      await apiClient.downloadFile(result.melody_midi_url, `${file?.name?.split('.')[0] || 'melody'}.mid`);
    } catch (err) {
      console.error('Failed to download MIDI:', err);
    }
  };

  const downloadMusicXML = async () => {
    if (!result?.musicxml_url) return;
    try {
      await apiClient.downloadFile(result.musicxml_url, `${file?.name?.split('.')[0] || 'melody'}.musicxml`);
    } catch (err) {
      console.error('Failed to download MusicXML:', err);
    }
  };

  const handleTranspose = async (targetKey: string) => {
    if (!result || !currentNotes.length || !result.key_signature) return;
    
    setIsTransposing(true);
    setError(null);
    
    try {
      const transposed = await apiClient.transposeNotes(currentNotes, {
        from_key: result.key_signature,
        to_key: targetKey,
      });
      
      setCurrentNotes(transposed.notes);
      setSelectedKey(targetKey);
      
      // Re-generate sheet music with transposed notes
      const response = await fetch('http://localhost:8000/api/sheet-music/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notes: transposed.notes,
          key_signature: targetKey,
          tempo_bpm: result.tempo_bpm || 120,
        }),
      });
      
      if (response.ok) {
        const sheetData = await response.json();
        if (sheetData.musicxml_url) {
          setTransposedMusicXmlUrl(sheetData.musicxml_url);
        }
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to transpose notes';
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || errorMessage);
    } finally {
      setIsTransposing(false);
    }
  };

  if (isProcessing) {
    return <ProcessingStatus stage="processing" progress={50} message="Converting audio to sheet music..." />;
  }

  if (result) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="card p-6 mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">✅ Processing Complete!</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Results</h3>
              <div className="space-y-2 text-sm">
                <p><span className="font-medium">Notes:</span> {result.note_count}</p>
                <p><span className="font-medium">Duration:</span> {Math.round(result.duration_s)}s</p>
                <p><span className="font-medium">Tempo:</span> {result.tempo_bpm ? `${Math.round(result.tempo_bpm)} BPM` : 'Auto'}</p>
                {result.key_signature && (
                  <p><span className="font-medium">Original Key:</span> {result.key_signature}</p>
                )}
                {selectedKey && selectedKey !== result.key_signature && (
                  <p><span className="font-medium">Current Key:</span> {selectedKey}</p>
                )}
              </div>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Statistics</h3>
              <div className="space-y-2 text-sm">
                <p><span className="font-medium">Original:</span> {result.stats.original_count} notes</p>
                <p><span className="font-medium">Final:</span> {result.stats.final_count} notes</p>
                <p><span className="font-medium">Filtered:</span> {result.stats.reduction_pct.toFixed(1)}%</p>
                <p><span className="font-medium">Vocal Guided:</span> {result.stats.vocal_guided ? '✅' : '❌'}</p>
              </div>
            </div>

          {/* Maqam Result Card */}
          {maqamInfo && (maqamInfo.is_eastern || (maqamInfo.confidence ?? maqamInfo.maqam_confidence ?? 0) > 0.3) && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">🎵 Eastern Music Analysis</h3>
              <MaqamCard info={maqamInfo} />
            </div>
          )}

            {result.sheet_music && (
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Sheet Music</h3>
                <div className="space-y-2 text-sm">
                  <p><span className="font-medium">Key:</span> {result.sheet_music.key_signature}</p>
                  <p><span className="font-medium">Confidence:</span> {(result.sheet_music.key_confidence * 100).toFixed(0)}%</p>
                  <p><span className="font-medium">Dynamics:</span> {result.sheet_music.dynamics_added}</p>
                  <p><span className="font-medium">Rests:</span> {result.sheet_music.rest_count}</p>
                </div>
              </div>
            )}

            {result.eastern_music?.is_eastern && (
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">🎵 Eastern Music</h3>
                <div className="space-y-2 text-sm">
                  <p>
                    <span className="font-medium">Maqam:</span>{' '}
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                      {result.eastern_music.maqam}
                    </span>
                  </p>
                  <p><span className="font-medium">Confidence:</span> {(result.eastern_music.maqam_confidence * 100).toFixed(0)}%</p>
                  {result.eastern_music.quarter_tone_count > 0 && (
                    <p>
                      <span className="font-medium">Quarter Tones:</span>{' '}
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                        {result.eastern_music.quarter_tone_count} notes
                      </span>
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
          
          {/* Transpose Section */}
          {result.key_signature && availableKeys.length > 0 && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">🎹 Transpose</h3>
              <div className="flex items-center gap-4">
                <label htmlFor="transpose-key" className="text-sm font-medium text-gray-700">
                  Transpose to:
                </label>
                <select
                  id="transpose-key"
                  value={selectedKey}
                  onChange={(e) => handleTranspose(e.target.value)}
                  disabled={isTransposing}
                  className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50"
                >
                  {availableKeys.map((key) => (
                    <option key={key} value={key}>
                      {key} {key === result.key_signature ? '(original)' : ''}
                    </option>
                  ))}
                </select>
                {isTransposing && (
                  <span className="text-sm text-gray-500">⏳ Transposing...</span>
                )}
              </div>
            </div>
          )}
          
          <div className="mt-6 flex flex-wrap gap-3">
            <button onClick={downloadMIDI} className="btn-primary">
              📥 Download MIDI
            </button>
            {result.musicxml_url && (
              <button onClick={downloadMusicXML} className="btn-primary">
                📄 Download MusicXML
              </button>
            )}
            <button
              onClick={() => navigate('/editor', { state: { result } })}
              className="btn-secondary"
            >
              ✏️ Edit & Simplify
            </button>
            <button
              onClick={() => {
                setFile(null);
                setResult(null);
                setError(null);
              }}
              className="btn-secondary"
            >
              🔄 Process Another
            </button>
          </div>
        </div>

        {/* Sheet Music Viewer */}
        {result.musicxml_url && (
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">🎼 Sheet Music Preview</h3>
              <button
                onClick={() => setShowSheetMusic(!showSheetMusic)}
                className="text-sm text-primary-600 hover:text-primary-800"
              >
                {showSheetMusic ? 'Hide' : 'Show'} Preview
              </button>
            </div>
            
            {showSheetMusic && (
              <SheetMusicViewer
                musicXmlUrl={transposedMusicXmlUrl || result.musicxml_url}
                title={file?.name?.replace(/\.[^/.]+$/, '') || 'Transcribed Melody'}
                keySignature={selectedKey || result.key_signature || undefined}
              />
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">🎵 Audio to Sheet Music</h1>
        <p className="text-lg text-gray-600">
          Upload your audio file and get beautiful sheet music in G clef (treble clef)
        </p>
        <p className="text-sm text-gray-500 mt-2">
          Perfect for violin and guitar • Automatic melody extraction • No configuration needed
        </p>
      </div>

      <div className="card p-6">
        <div
          className={`relative border-2 border-dashed rounded-lg p-6 text-center hover:border-gray-400 transition-colors ${
            dragActive 
              ? 'border-primary-500 bg-primary-50' 
              : file 
                ? 'border-green-500 bg-green-50' 
                : 'border-gray-300'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          
          {file ? (
            <div className="space-y-2">
              <div className="text-green-600">
                ✅ {file.name}
              </div>
              <div className="text-sm text-gray-500">
                {(file.size / 1024 / 1024).toFixed(1)} MB
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-gray-400">
                📁 Drag and drop your audio file here
              </div>
              <div className="text-sm text-gray-500">
                or click to select • MP3, WAV, FLAC, M4A supported
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-600">❌ {error}</p>
          </div>
        )}

        <div className="mt-6">
          <button
            onClick={handleUpload}
            disabled={!file || isProcessing}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isProcessing ? '⏳ Processing...' : '🚀 Convert to Sheet Music'}
          </button>
        </div>
        
        <div className="mt-4 text-center">
          <p className="text-xs text-gray-500">
            Processing typically takes 1-3 minutes depending on file size
          </p>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;