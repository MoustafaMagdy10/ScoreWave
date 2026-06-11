import React, { useEffect, useRef, useState } from 'react';
import { OpenSheetMusicDisplay as OSMD } from 'opensheetmusicdisplay';

interface SheetMusicViewerProps {
  musicXmlUrl: string;
  title?: string;
  keySignature?: string;
  onError?: (error: Error) => void;
}

const SheetMusicViewer: React.FC<SheetMusicViewerProps> = ({
  musicXmlUrl,
  title,
  keySignature,
  onError,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<OSMD | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1.0);

  useEffect(() => {
    if (!containerRef.current) return;

    const initOSMD = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Clear previous content
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
        }

        // Initialize OSMD
        const osmd = new OSMD(containerRef.current!, {
          autoResize: true,
          drawTitle: true,
          drawSubtitle: false,
          drawComposer: true,
          drawCredits: false,
          drawPartNames: false,
          drawPartAbbreviations: false,
          drawingParameters: 'default',
        });

        osmdRef.current = osmd;

        // Fetch MusicXML content
        const response = await fetch(`http://localhost:8000${musicXmlUrl}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch MusicXML: ${response.statusText}`);
        }
        
        const xmlContent = await response.text();

        // Load and render
        await osmd.load(xmlContent);
        osmd.zoom = zoom;
        await osmd.render();

        setIsLoading(false);
      } catch (err) {
        console.error('OSMD Error:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to load sheet music';
        setError(errorMessage);
        setIsLoading(false);
        if (onError && err instanceof Error) {
          onError(err);
        }
      }
    };

    initOSMD();

    return () => {
      osmdRef.current = null;
    };
  }, [musicXmlUrl, onError]);

  // Handle zoom changes
  useEffect(() => {
    if (osmdRef.current && !isLoading) {
      osmdRef.current.zoom = zoom;
      osmdRef.current.render();
    }
  }, [zoom, isLoading]);

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.1, 2.0));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.1, 0.5));
  const handleZoomReset = () => setZoom(1.0);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-600 mb-2">❌ {error}</p>
        <p className="text-sm text-gray-500">
          The sheet music could not be displayed. You can still download the MusicXML file.
        </p>
      </div>
    );
  }

  return (
    <div className="sheet-music-viewer">
      {/* Header with controls */}
      <div className="flex items-center justify-between mb-4 p-3 bg-gray-50 rounded-lg">
        <div>
          {title && <h3 className="font-semibold text-gray-800">{title}</h3>}
          {keySignature && (
            <p className="text-sm text-gray-600">Key: {keySignature}</p>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={handleZoomOut}
            className="p-2 text-gray-600 hover:bg-gray-200 rounded"
            title="Zoom out"
          >
            ➖
          </button>
          <span className="text-sm text-gray-600 min-w-[50px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            className="p-2 text-gray-600 hover:bg-gray-200 rounded"
            title="Zoom in"
          >
            ➕
          </button>
          <button
            onClick={handleZoomReset}
            className="p-2 text-gray-600 hover:bg-gray-200 rounded text-sm"
            title="Reset zoom"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500"></div>
          <span className="ml-3 text-gray-600">Loading sheet music...</span>
        </div>
      )}

      {/* Sheet music container */}
      <div
        ref={containerRef}
        className={`sheet-music-container bg-white rounded-lg border border-gray-200 overflow-auto min-h-[400px] ${
          isLoading ? 'hidden' : ''
        }`}
        style={{ maxHeight: '70vh' }}
      />
    </div>
  );
};

export default SheetMusicViewer;
