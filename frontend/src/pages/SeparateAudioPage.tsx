import React, { useState } from 'react';
import { apiClient } from '../services/api';

const SeparateAudioPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSeparate = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError(null);
    
    try {
      const result = await apiClient.separateAudio(file);
      setResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to separate audio');
    } finally {
      setIsProcessing(false);
    }
  };

  const downloadStem = async (stemUrl: string, stemName: string) => {
    try {
      await apiClient.downloadFile(stemUrl, `${file?.name?.split('.')[0] || 'audio'}_${stemName}.wav`);
    } catch (err) {
      console.error('Failed to download stem:', err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">🎵 Audio Separation</h1>
        <p className="text-lg text-gray-600">
          Separate your audio into individual stems (vocals, drums, bass, other)
        </p>
      </div>

      {!result && (
        <div className="card p-6">
          <div className="space-y-4">
            <div>
              <label htmlFor="audio-file" className="block text-sm font-medium text-gray-700">
                Audio File
              </label>
              <input
                type="file"
                id="audio-file"
                accept="audio/*"
                onChange={handleFileChange}
                className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
              />
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-600">❌ {error}</p>
              </div>
            )}

            <button
              onClick={handleSeparate}
              disabled={!file || isProcessing}
              className="w-full btn-primary disabled:opacity-50"
            >
              {isProcessing ? '⏳ Separating...' : '🔀 Separate Audio'}
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="card p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">✅ Separation Complete!</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(result.stems).map(([stemName, stemUrl]) => (
              <div key={stemName} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900 capitalize">{stemName.replace('_', ' ')}</h3>
                    <p className="text-sm text-gray-500">Audio stem</p>
                  </div>
                  <button
                    onClick={() => downloadStem(stemUrl as string, stemName)}
                    className="btn-secondary text-sm"
                  >
                    📥 Download
                  </button>
                </div>
              </div>
            ))}
          </div>
          
          <div className="mt-6">
            <button
              onClick={() => {
                setFile(null);
                setResult(null);
                setError(null);
              }}
              className="btn-secondary"
            >
              🔄 Separate Another
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SeparateAudioPage;