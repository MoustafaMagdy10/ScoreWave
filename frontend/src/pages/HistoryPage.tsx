import React, { useState, useEffect } from 'react';
import { apiClient } from '../services/api';

interface HistoryItem {
  job_id: string;
  filename: string;
  uploadedAt: string;
  note_count: number;
  duration_s: number;
  tempo_bpm: number | null;
  melody_midi_url: string;
}

const HistoryPage: React.FC = () => {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load history from localStorage
    const loadHistory = () => {
      try {
        const savedHistory = localStorage.getItem('songify_history');
        if (savedHistory) {
          setHistory(JSON.parse(savedHistory));
        }
      } catch (err) {
        console.error('Failed to load history:', err);
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, []);

  const downloadMIDI = async (item: HistoryItem) => {
    try {
      await apiClient.downloadFile(item.melody_midi_url, `${item.filename.split('.')[0]}.mid`);
    } catch (err) {
      console.error('Failed to download MIDI:', err);
    }
  };

  const clearHistory = () => {
    if (window.confirm('Are you sure you want to clear your upload history?')) {
      localStorage.removeItem('songify_history');
      setHistory([]);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">📚 Upload History</h1>
        {history.length > 0 && (
          <button
            onClick={clearHistory}
            className="btn-secondary text-red-600 hover:bg-red-50"
          >
            🗑️ Clear History
          </button>
        )}
      </div>

      {history.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">📝</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">No uploads yet</h2>
          <p className="text-gray-600 mb-6">
            Your processed audio files will appear here
          </p>
          <a href="/" className="btn-primary">
            🚀 Upload Your First File
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {history.map((item, index) => (
            <div key={item.job_id || index} className="card p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">
                    🎵 {item.filename}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-sm text-gray-600">
                    <div>
                      <span className="font-medium">Uploaded:</span> {formatDate(item.uploadedAt)}
                    </div>
                    <div>
                      <span className="font-medium">Notes:</span> {item.note_count}
                    </div>
                    <div>
                      <span className="font-medium">Duration:</span> {Math.round(item.duration_s)}s
                    </div>
                    <div>
                      <span className="font-medium">Tempo:</span> {item.tempo_bpm ? `${Math.round(item.tempo_bpm)} BPM` : 'Auto'}
                    </div>
                  </div>
                </div>
                
                <div className="ml-4">
                  <button
                    onClick={() => downloadMIDI(item)}
                    className="btn-primary"
                  >
                    📥 Download MIDI
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <p className="text-sm text-blue-800">
          <strong>Note:</strong> History is stored locally in your browser. Clear your browser data or use incognito mode to reset.
        </p>
      </div>
    </div>
  );
};

export default HistoryPage;