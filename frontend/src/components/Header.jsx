import React from 'react';
import { Scale, UserShield, Factory, ClipboardCheck, BookOpen, LogOut } from 'lucide-react';

export default function Header({ currentMode, setMode, user, onLogout }) {
  const userRole = user?.role || 'public';

  // Strict Role-Based Access Navigation Mapping
  const roleModeMap = {
    inspector: [
      { id: 'inspector', label: 'Officer Field Hub & Ledger', icon: ClipboardCheck },
      { id: 'rules', label: 'Official Rules Registry', icon: BookOpen }
    ],
    public: [
      { id: 'public', label: 'Citizen Package Scanner', icon: UserShield },
      { id: 'rules', label: 'Consumer Rules & Rights', icon: BookOpen }
    ],
    manufacturer: [
      { id: 'manufacturer', label: 'Pre-Release Artwork Studio', icon: Factory },
      { id: 'rules', label: 'Manufacturer Compliance Rules', icon: BookOpen }
    ]
  };

  const availableModes = roleModeMap[userRole] || roleModeMap.public;

  const roleLabelMap = {
    inspector: 'OFFICER',
    public: 'CITIZEN',
    manufacturer: 'MANUFACTURER'
  };

  return (
    <header className="app-header">
      <div className="header-container">
        <div className="brand">
          <div className="brand-emblem">
            <Scale size={26} />
          </div>
          <div className="brand-text">
            <h1>LEGAL METROLOGY <span>INTELLIGENCE</span></h1>
            <p>Packaged Commodities Compliance System (SIH26034) • Dept of Consumer Affairs Rules 2011</p>
          </div>
        </div>

        <nav className="role-nav">
          {availableModes.map((mode) => {
            const Icon = mode.icon;
            const isActive = currentMode === mode.id;
            return (
              <button
                key={mode.id}
                className={`nav-btn ${isActive ? 'active' : ''}`}
                onClick={() => setMode(mode.id)}
              >
                <Icon size={16} />
                {mode.label}
              </button>
            );
          })}
        </nav>

        {/* User Auth Profile Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {user && (
            <div className="user-profile-badge">
              <div className="profile-avatar">
                {user.username ? user.username.charAt(0).toUpperCase() : (user.name ? user.name.charAt(0).toUpperCase() : 'U')}
              </div>
              <div className="profile-info">
                <span className="profile-name">
                  [{roleLabelMap[userRole] || 'USER'}] {user.username || user.name || 'Authenticated User'}
                </span>
                <span className="profile-badge-id">
                  {user.badge_or_license || user.badgeId || user.email}
                </span>
              </div>
              <button type="button" className="btn-logout" onClick={onLogout} title="Sign Out & Exit Dashboard">
                <LogOut size={14} /> Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
