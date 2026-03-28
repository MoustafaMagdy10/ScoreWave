import React from 'react';

interface ProcessingStatusProps {
  stage: 'uploading' | 'separating' | 'transcribing' | 'analyzing' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ stage, progress, message }) => {
  const getStageIcon = (currentStage: string) => {
    switch (currentStage) {
      case 'uploading': return '📤';
      case 'separating': return '🎵';
      case 'transcribing': return '🎼';
      case 'analyzing': return '🧠';
      case 'processing': return '⚙️';
      case 'completed': return '✅';
      case 'failed': return '❌';
      default: return '⏳';
    }
  };

  const stages = [
    { key: 'uploading', label: 'Uploading' },
    { key: 'separating', label: 'Separating Audio' },
    { key: 'transcribing', label: 'Transcribing Notes' },
    { key: 'analyzing', label: 'Analyzing Melody' },
    { key: 'completed', label: 'Complete' },
  ];

  const getCurrentStageIndex = () => {
    return stages.findIndex(s => s.key === stage);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="card p-6">
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">
            {getStageIcon(stage)}
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Processing Your Audio</h2>
          <p className="text-gray-600">{message}</p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Stage Indicators */}
        <div className="space-y-4">
          {stages.map((stageInfo, index) => {
            const currentIndex = getCurrentStageIndex();
            const isActive = index === currentIndex;
            const isCompleted = index < currentIndex;

            return (
              <div
                key={stageInfo.key}
                className={`flex items-center space-x-3 p-3 rounded-lg ${
                  isActive 
                    ? 'bg-primary-50 border border-primary-200' 
                    : isCompleted 
                      ? 'bg-green-50 border border-green-200'
                      : 'bg-gray-50 border border-gray-200'
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  isActive
                    ? 'bg-primary-600 text-white'
                    : isCompleted
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-300 text-gray-600'
                }`}>
                  {isCompleted ? '✓' : isActive ? '⏳' : index + 1}
                </div>
                <span className={`font-medium ${
                  isActive 
                    ? 'text-primary-900'
                    : isCompleted 
                      ? 'text-green-900'
                      : 'text-gray-500'
                }`}>
                  {stageInfo.label}
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-6 text-center text-sm text-gray-500">
          <p>This may take 1-3 minutes depending on file size...</p>
          <p className="mt-1">Please do not close this window</p>
        </div>
      </div>
    </div>
  );
};

export default ProcessingStatus;