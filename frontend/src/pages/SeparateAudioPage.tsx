import React, { useState, useCallback, useRef } from 'react';
import { apiClient } from '../services/api';
import type { SeparationResult, StemInfo } from '../types';
import ProcessingStatus from '../components/ProcessingStatus';

const STEM_CONFIG: Record<string, Omit<StemInfo, 'url'>> = {
  vocals: {
    name: 'Vocals',
    key: 'vocals',
    color: 'text-purple-700',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-300',
    icon: '🎤',
  },
  no_vocals: {
    name: 'No Vocals (Instrumental)',
    key: 'no_vocals',
    color: 'text-orange-700',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-300',
    icon: '🎸',
  },
  drums: {
    name: 'Drums',
    key: 'drums',
    color: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-300',
    icon: '🥁',
  },
  bass: {
    name: 'Bass',
    key: 'bass',
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-300',
    icon: '🎸',
  },
  other: {
    name: 'Other',
    key: 'other',
    color: 'text-green-700',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-300',
    icon: '🎹',
  },
};

const SeparateAudioPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<SeparationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [playingStems, setPlayingStems] = useState<Record<string, boolean>>({});
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
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

  const handleSeparate = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError(null);

    try {
      const separationResult = await apiClient.separateAudio(file);
      setResult(separationResult);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || 'Failed to separate audio');
    } finally {
      setIsProcessing(false);
    }
  };

  const downloadStem = async (stemUrl: string, stemName: string) => {
    try {
      await apiClient.downloadFile(
        stemUrl,
        `${file?.name?.split('.')[0] || 'audio'}_${stemName}.wav`
      );
    } catch (err) {
      console.error('Failed to download stem:', err);
    }
  };

  const togglePlayStem = (stemKey: string) => {
    const audioEl = audioRefs.current[stemKey];

    if (audioEl) {
      if (playingStems[stemKey]) {
        audioEl.pause();
        setPlayingStems((prev) => ({ ...prev, [stemKey]: false }));
      } else {
        // Pause all other stems
        Object.keys(audioRefs.current).forEach((key) => {
          if (key !== stemKey && audioRefs.current[key]) {
            audioRefs.current[key]!.pause();
          }
        });
        setPlayingStems({ [stemKey]: true });
        audioEl.play();
      }
    }
  };

  const handleAudioEnded = (stemKey: string) => {
    setPlayingStems((prev) => ({ ...prev, [stemKey]: false }));
  };

  const resetState = () => {
    // Stop all audio
    Object.values(audioRefs.current).forEach((audio) => {
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
      }
    });
    setFile(null);
    setResult(null);
    setError(null);
    setPlayingStems({});
  };

  if (isProcessing) {
    return (
      <ProcessingStatus
        stage="separating"
        progress={50}
        message="Separating audio into stems using AI... This may take a few minutes."
      />
    );
  }

  if (result) {
    const stemOrder: (keyof SeparationResult['stems'])[] = [
      'vocals',
      'no_vocals',
      'drums',
      'bass',
      'other',
    ];

    return (
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">✅ Separation Complete!</h1>
          <p className="text-lg text-gray-600">
            Your audio has been separated into {stemOrder.length} stems
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {stemOrder.map((stemKey) => {
            const config = STEM_CONFIG[stemKey];
            const stemUrl = result.stems[stemKey];
            const audioUrl = apiClient.getStemAudioUrl(stemUrl);
            const isPlaying = playingStems[stemKey] || false;

            return (
              <div
                key={stemKey}
                className={`rounded-xl p-5 border-2 ${config.bgColor} ${config.borderColor} transition-all hover:shadow-lg`}
              >
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-3xl">{config.icon}</span>
                  <h3 className={`text-lg font-bold ${config.color}`}>{config.name}</h3>
                </div>

                {/* Audio Player */}
                <audio
                  ref={(el) => {
                    audioRefs.current[stemKey] = el;
                  }}
                  src={audioUrl}
                  onEnded={() => handleAudioEnded(stemKey)}
                  preload="none"
                />

                <div className="flex gap-3">
                  <button
                    onClick={() => togglePlayStem(stemKey)}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                      isPlaying
                        ? 'bg-gray-700 text-white hover:bg-gray-800'
                        : `${config.borderColor} border-2 ${config.color} hover:bg-white`
                    }`}
                  >
                    {isPlaying ? '⏸️ Pause' : '▶️ Play'}
                  </button>
                  <button
                    onClick={() => downloadStem(stemUrl, stemKey)}
                    className={`py-2 px-4 rounded-lg font-medium transition-colors border-2 ${config.borderColor} ${config.color} hover:bg-white`}
                  >
                    📥
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="text-center">
          <button onClick={resetState} className="btn-secondary text-lg px-8 py-3">
            🔄 Separate Another Audio
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">🎵 Audio Separation</h1>
        <p className="text-lg text-gray-600">
          Separate your audio into individual stems using AI
        </p>
        <p className="text-sm text-gray-500 mt-2">
          Extract vocals, drums, bass, and more from any song
        </p>
      </div>

      <div className="card p-6">
        <div
          className={`relative border-2 border-dashed rounded-lg p-8 text-center hover:border-gray-400 transition-colors ${
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
              <div className="text-green-600 text-lg">✅ {file.name}</div>
              <div className="text-sm text-gray-500">
                {(file.size / 1024 / 1024).toFixed(1)} MB
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="text-5xl">🎵</div>
              <div className="text-gray-600 font-medium">
                Drag and drop your audio file here
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
            onClick={handleSeparate}
            disabled={!file || isProcessing}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed text-lg py-3"
          >
            🔀 Separate Audio
          </button>
        </div>

        <div className="mt-6 grid grid-cols-5 gap-2">
          {Object.entries(STEM_CONFIG).map(([key, config]) => (
            <div
              key={key}
              className={`text-center p-2 rounded-lg ${config.bgColor} border ${config.borderColor}`}
            >
              <span className="text-xl">{config.icon}</span>
              <p className={`text-xs font-medium mt-1 ${config.color}`}>
                {config.name.split(' ')[0]}
              </p>
            </div>
          ))}
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

export default SeparateAudioPage;