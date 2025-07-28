import React, { useState, useEffect, useRef } from 'react';

const RealTimePanel = ({ updates, isConnected, onToggle }) => {
  const [isMinimized, setIsMinimized] = useState(false);
  const [selectedUpdate, setSelectedUpdate] = useState(null);
  const [copySuccess, setCopySuccess] = useState('');
  const updatesRef = useRef(null);

  useEffect(() => {
    // Auto-scroll to top when new updates arrive
    if (updatesRef.current && updates.length > 0) {
      updatesRef.current.scrollTop = 0;
    }
  }, [updates]);

  const formatDateTime = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopySuccess('Copied!');
      setTimeout(() => setCopySuccess(''), 2000);
    }).catch(() => {
      setCopySuccess('Failed to copy');
      setTimeout(() => setCopySuccess(''), 2000);
    });
  };

  const copyAllUpdates = () => {
    const allUpdatesText = updates.map(update => {
      return `[${formatDateTime(update.timestamp)}] ${update.message}${update.details ? '\nDetails: ' + JSON.stringify(update.details, null, 2) : ''}`;
    }).join('\n\n');
    copyToClipboard(allUpdatesText);
  };

  const getUpdateIcon = (type) => {
    switch (type) {
      case 'success': return '✅';
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return '🔄';
    }
  };

  const getUpdateColor = (type) => {
    switch (type) {
      case 'success': return 'border-green-200 bg-green-50';
      case 'error': return 'border-red-200 bg-red-50';
      case 'warning': return 'border-yellow-200 bg-yellow-50';
      case 'info': return 'border-blue-200 bg-blue-50';
      default: return 'border-gray-200 bg-gray-50';
    }
  };

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white border border-gray-300 rounded-lg shadow-lg z-50">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <h3 className="text-sm font-semibold text-gray-800">Real-time Updates</h3>
          <span className="text-xs text-gray-500">({updates.length})</span>
        </div>
        <div className="flex items-center space-x-2">
          {copySuccess && (
            <span className="text-xs text-green-600 font-medium">{copySuccess}</span>
          )}
          <button
            onClick={copyAllUpdates}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            title="Copy all updates"
          >
            Copy All
          </button>
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="text-gray-500 hover:text-gray-700"
          >
            {isMinimized ? '▲' : '▼'}
          </button>
          <button
            onClick={onToggle}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Content */}
      {!isMinimized && (
        <div className="h-64 overflow-y-auto" ref={updatesRef}>
          {updates.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <div className="text-2xl mb-2">📡</div>
              <p className="text-sm">No real-time updates yet</p>
              <p className="text-xs text-gray-400">Updates will appear here as they happen</p>
            </div>
          ) : (
            <div className="p-2 space-y-2">
              {updates.map((update, index) => (
                <div
                  key={index}
                  className={`p-2 rounded border ${getUpdateColor(update.level)} cursor-pointer hover:shadow-sm transition-shadow`}
                  onClick={() => setSelectedUpdate(selectedUpdate === index ? null : index)}
                >
                  <div className="flex items-start space-x-2">
                    <span className="text-sm">{getUpdateIcon(update.level)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-gray-900 font-medium truncate">
                          {update.message || 'Real-time update'}
                        </p>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(update.message || 'Real-time update');
                          }}
                          className="text-xs text-blue-600 hover:text-blue-700 ml-2"
                          title="Copy message"
                        >
                          📋
                        </button>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {formatDateTime(update.timestamp || new Date())}
                      </p>
                      
                      {/* Expanded details */}
                      {selectedUpdate === index && (
                        <div className="mt-2 p-2 bg-white rounded border">
                          <div className="text-xs">
                            <p className="font-medium text-gray-700 mb-1">Full Message:</p>
                            <p className="text-gray-600 mb-2">{update.message || 'Real-time update'}</p>
                            
                            {update.details && (
                              <>
                                <p className="font-medium text-gray-700 mb-1">Details:</p>
                                <pre className="text-xs text-gray-600 bg-gray-50 p-2 rounded overflow-x-auto">
                                  {JSON.stringify(update.details, null, 2)}
                                </pre>
                              </>
                            )}
                            
                            {update.step && (
                              <p className="text-xs text-gray-500 mt-1">
                                <span className="font-medium">Step:</span> {update.step}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RealTimePanel;