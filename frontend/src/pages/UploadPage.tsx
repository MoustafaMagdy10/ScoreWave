import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import type { ProcessingResult } from '../types';
import ProcessingStatus from '../components/ProcessingStatus';

const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const navigate = useNavigate();

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
      const result = await apiClient.processAudio(file);
      setResult(result);
      
      // Save to localStorage for history
      const history = JSON.parse(localStorage.getItem('songify_history') || '[]');
      history.unshift({
        ...result,
        filename: file.name,
        uploadedAt: new Date().toISOString(),
      });
      localStorage.setItem('songify_history', JSON.stringify(history.slice(0, 20))); // Keep last 20
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to process audio file');
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

  if (isProcessing) {
    return <ProcessingStatus stage="processing" progress={50} message="Converting audio to sheet music..." />;
  }

  if (result) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="card p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">✅ Processing Complete!</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Results</h3>
              <div className="space-y-2">
                <p><span className="font-medium">Note Count:</span> {result.note_count} notes</p>
                <p><span className="font-medium">Duration:</span> {Math.round(result.duration_s)}s</p>
                <p><span className="font-medium">Tempo:</span> {result.tempo_bpm ? `${Math.round(result.tempo_bpm)} BPM` : 'Auto-detected'}</p>
                <p><span className="font-medium">Range:</span> G clef (treble clef) only</p>
              </div>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Statistics</h3>
              <div className="space-y-2">
                <p><span className="font-medium">Original Notes:</span> {result.stats.original_count}</p>
                <p><span className="font-medium">Final Notes:</span> {result.stats.final_count}</p>
                <p><span className="font-medium">Filtered:</span> {result.stats.reduction_pct.toFixed(1)}%</p>
                <p><span className="font-medium">Vocal Guided:</span> {result.stats.vocal_guided ? '✅ Yes' : '❌ No'}</p>
              </div>
            </div>
          </div>
          
          <div className="mt-6 flex space-x-4">
            <button
              onClick={downloadMIDI}
              className="btn-primary"
            >
              📥 Download MIDI
            </button>
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