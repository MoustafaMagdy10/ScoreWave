import React, { useState } from 'react';

const ProfilePage: React.FC = () => {
  const [isEditing, setIsEditing] = useState(false);
  const [profile, setProfile] = useState({
    name: 'John Doe',
    email: 'john.doe@example.com',
    preferences: {
      defaultKey: 'C Major',
      defaultTempo: 120,
    },
  });

  const handleSave = () => {
    // TODO: Implement save logic when backend is ready
    setIsEditing(false);
    alert('Profile saved! (This will be implemented when backend auth is ready)');
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Profile Settings</h1>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="btn-secondary"
            >
              {isEditing ? 'Cancel' : 'Edit'}
            </button>
          </div>
          
          <div className="mt-6 grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Name
              </label>
              <div className="mt-1">
                {isEditing ? (
                  <input
                    type="text"
                    id="name"
                    value={profile.name}
                    onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                    className="shadow-sm focus:ring-primary-500 focus:border-primary-500 block w-full sm:text-sm border-gray-300 rounded-md"
                  />
                ) : (
                  <p className="text-sm text-gray-900">{profile.name}</p>
                )}
              </div>
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <div className="mt-1">
                {isEditing ? (
                  <input
                    type="email"
                    id="email"
                    value={profile.email}
                    onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                    className="shadow-sm focus:ring-primary-500 focus:border-primary-500 block w-full sm:text-sm border-gray-300 rounded-md"
                  />
                ) : (
                  <p className="text-sm text-gray-900">{profile.email}</p>
                )}
              </div>
            </div>

            <div>
              <label htmlFor="defaultKey" className="block text-sm font-medium text-gray-700">
                Default Key
              </label>
              <div className="mt-1">
                {isEditing ? (
                  <select
                    id="defaultKey"
                    value={profile.preferences.defaultKey}
                    onChange={(e) => setProfile({ 
                      ...profile, 
                      preferences: { ...profile.preferences, defaultKey: e.target.value }
                    })}
                    className="shadow-sm focus:ring-primary-500 focus:border-primary-500 block w-full sm:text-sm border-gray-300 rounded-md"
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
                ) : (
                  <p className="text-sm text-gray-900">{profile.preferences.defaultKey}</p>
                )}
              </div>
            </div>

            <div>
              <label htmlFor="defaultTempo" className="block text-sm font-medium text-gray-700">
                Default Tempo (BPM)
              </label>
              <div className="mt-1">
                {isEditing ? (
                  <input
                    type="number"
                    id="defaultTempo"
                    value={profile.preferences.defaultTempo}
                    onChange={(e) => setProfile({ 
                      ...profile, 
                      preferences: { ...profile.preferences, defaultTempo: parseInt(e.target.value) }
                    })}
                    className="shadow-sm focus:ring-primary-500 focus:border-primary-500 block w-full sm:text-sm border-gray-300 rounded-md"
                  />
                ) : (
                  <p className="text-sm text-gray-900">{profile.preferences.defaultTempo}</p>
                )}
              </div>
            </div>
          </div>

          {isEditing && (
            <div className="mt-6">
              <button
                onClick={handleSave}
                className="btn-primary"
              >
                Save Changes
              </button>
            </div>
          )}
        </div>
      </div>
      
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <p className="text-sm text-blue-800">
          <strong>Note:</strong> This is a placeholder profile page. User management will be implemented in a future version.
        </p>
      </div>
    </div>
  );
};

export default ProfilePage;