import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { ProcessingResult } from '../types';

const EditorPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const result = location.state?.result as ProcessingResult;
  
  // Editor settings (placeholder for future implementation)
  const [settings, setSettings] = useState({
    simplify: false,
    targetKey: 'C Major',
    targetTempo: result?.tempo_bpm || 120,
    removeOrnaments: false,
    quantize: false,
  });

  if (!result) {
    return (
      <div className="max-w-4xl mx-auto text-center py-12">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">No Data Found</h1>
        <p className="text-gray-600 mb-6">Please upload and process an audio file first.</p>
        <button onClick={() => navigate('/')} className="btn-primary">
          🚀 Upload Audio
        </button>
      </div>
    );
  }

  const handleApplyChanges = () => {
    // TODO: Implement when backend simplification/transposition is ready
    alert('Simplification and key changes will be implemented in a future version.');
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">✏️ Sheet Music Editor</h1>
        <button onClick={() => navigate('/')} className="btn-secondary">
          ← Back to Upload
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Settings Panel */}
        <div className="lg:col-span-1">
          <div className="card p-6 space-y-6">
            <h2 className="text-xl font-semibold text-gray-900">Edit Settings</h2>
            
            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.simplify}
                  onChange={(e) => setSettings({...settings, simplify: e.target.checked})}
                  className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="ml-2 text-sm text-gray-700">Simplify melody</span>
              </label>
              <p className="text-xs text-gray-500 ml-6">Remove ornamental notes and simplify rhythms</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Key
              </label>
              <select
                value={settings.targetKey}
                onChange={(e) => setSettings({...settings, targetKey: e.target.value})}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              >
                <option>C Major</option>
                <option>G Major</option>
                <option>D Major</option>
                <option>A Major</option>
                <option>E Major</option>
                <option>F Major</option>
                <option>Bb Major</option>
                <option>Eb Major</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Tempo (BPM)
              </label>
              <input
                type="number"
                min="60"
                max="180"
                value={settings.targetTempo}
                onChange={(e) => setSettings({...settings, targetTempo: parseInt(e.target.value)})}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.removeOrnaments}
                  onChange={(e) => setSettings({...settings, removeOrnaments: e.target.checked})}
                  className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="ml-2 text-sm text-gray-700">Remove ornaments</span>
              </label>
            </div>

            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.quantize}
                  onChange={(e) => setSettings({...settings, quantize: e.target.checked})}
                  className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="ml-2 text-sm text-gray-700">Quantize timing</span>
              </label>
            </div>

            <button
              onClick={handleApplyChanges}
              className="w-full btn-primary"
            >
              🎯 Apply Changes
            </button>
          </div>
        </div>

        {/* Preview Panel */}
        <div className="lg:col-span-2">
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Sheet Music Preview</h2>
            
            {/* Current Stats */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900">Current</h3>
                <div className="text-sm text-gray-600 space-y-1">
                  <p>Notes: {result.note_count}</p>
                  <p>Tempo: {result.tempo_bpm ? Math.round(result.tempo_bpm) : 'Auto'} BPM</p>
                  <p>Key: Auto-detected</p>
                  <p>Range: G clef (G3-E6)</p>
                </div>
              </div>
              
              <div className="bg-primary-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900">After Changes</h3>
                <div className="text-sm text-gray-600 space-y-1">
                  <p>Notes: {settings.simplify ? Math.round(result.note_count * 0.7) : result.note_count}</p>
                  <p>Tempo: {settings.targetTempo} BPM</p>
                  <p>Key: {settings.targetKey}</p>
                  <p>Range: G clef (treble)</p>
                </div>
              </div>
            </div>

            {/* Placeholder for sheet music display */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center">
              <div className="text-4xl mb-4">🎼</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Sheet Music Preview</h3>
              <p className="text-gray-600 mb-4">
                Visual sheet music display will be available in a future version
              </p>
              <div className="space-x-4">
                <button className="btn-primary">📥 Download MIDI</button>
                <button className="btn-secondary">📄 Generate PDF</button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-md">
        <p className="text-sm text-amber-800">
          <strong>Coming Soon:</strong> Sheet music editing, key changes, simplification, and PDF generation are planned features.
        </p>
      </div>
    </div>
  );
};

export default EditorPage;