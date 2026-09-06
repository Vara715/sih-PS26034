import React, { useState } from 'react';
import { ShieldCheck, User, ClipboardCheck, Factory, KeyRound, ArrowRight, Lock, CheckCircle } from 'lucide-react';

export default function LoginModal({ isOpen, onClose, onLogin, initialRole = 'public' }) {
  const [activeTab, setActiveTab] = useState(initialRole);
  const [consumerInput, setConsumerInput] = useState('');
  const [inspectorId, setInspectorId] = useState('');
  const [inspectorPin, setInspectorPin] = useState('');
  const [manufacturerName, setManufacturerName] = useState('');
  const [licenseNo, setLicenseNo] = useState('');
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (activeTab === 'public') {
      onLogin({
        role: 'public',
        name: consumerInput.trim() || 'Citizen User',
        badgeId: 'PUBLIC-GUEST',
        authenticated: true
      });
      onClose();
    } else if (activeTab === 'inspector') {
      if (!inspectorId.trim() || !inspectorPin.trim()) {
        setError('Please enter your Inspector ID and Security PIN.');
        return;
      }
      onLogin({
        role: 'inspector',
        name: `Inspector ${inspectorId.toUpperCase()}`,
        badgeId: inspectorId.toUpperCase(),
        authenticated: true
      });
      onClose();
    } else if (activeTab === 'manufacturer') {
      if (!manufacturerName.trim() || !licenseNo.trim()) {
        setError('Please enter your Company Name and Packaging License Number.');
        return;
      }
      onLogin({
        role: 'manufacturer',
        name: manufacturerName.trim(),
        badgeId: licenseNo.toUpperCase(),
        authenticated: true
      });
      onClose();
    }
  };

  return (
    <div className="login-modal-overlay">
      <div className="login-modal-card">
        <div className="login-modal-header">
          <div className="login-icon-badge">
            <Lock size={24} />
          </div>
          <h3>System Authentication</h3>
          <p>Select your authorized role to log into the Legal Metrology Platform</p>
        </div>

        {/* Role Tabs */}
        <div className="login-role-tabs">
          <button
            type="button"
            className={`login-tab ${activeTab === 'public' ? 'active' : ''}`}
            onClick={() => { setActiveTab('public'); setError(''); }}
          >
            <User size={16} /> Consumer
          </button>
          <button
            type="button"
            className={`login-tab ${activeTab === 'inspector' ? 'active' : ''}`}
            onClick={() => { setActiveTab('inspector'); setError(''); }}
          >
            <ClipboardCheck size={16} /> Inspector
          </button>
          <button
            type="button"
            className={`login-tab ${activeTab === 'manufacturer' ? 'active' : ''}`}
            onClick={() => { setActiveTab('manufacturer'); setError(''); }}
          >
            <Factory size={16} /> Manufacturer
          </button>
        </div>

        {error && <div className="login-error-msg">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          {activeTab === 'public' && (
            <div className="form-group">
              <label><User size={15} /> Mobile Number or Name (Optional)</label>
              <input
                type="text"
                className="form-select"
                placeholder="e.g. +91 9876543210 or Guest Consumer"
                value={consumerInput}
                onChange={(e) => setConsumerInput(e.target.value)}
              />
              <span className="form-help-text">Public citizen scanner access requires no password.</span>
            </div>
          )}

          {activeTab === 'inspector' && (
            <>
              <div className="form-group">
                <label><ClipboardCheck size={15} /> Official Inspector ID</label>
                <input
                  type="text"
                  className="form-select"
                  placeholder="e.g. INS-8021-DEL"
                  value={inspectorId}
                  onChange={(e) => setInspectorId(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label><KeyRound size={15} /> Security Passcode PIN</label>
                <input
                  type="password"
                  className="form-select"
                  placeholder="••••••••"
                  value={inspectorPin}
                  onChange={(e) => setInspectorPin(e.target.value)}
                  required
                />
                <span className="form-help-text">Demo Passcode: Any 4+ digit PIN</span>
              </div>
            </>
          )}

          {activeTab === 'manufacturer' && (
            <>
              <div className="form-group">
                <label><Factory size={15} /> Company / Manufacturer Name</label>
                <input
                  type="text"
                  className="form-select"
                  placeholder="e.g. ABC Foods India Pvt Ltd"
                  value={manufacturerName}
                  onChange={(e) => setManufacturerName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label><ShieldCheck size={15} /> Legal Metrology / FSSAI License No</label>
                <input
                  type="text"
                  className="form-select"
                  placeholder="e.g. LMO/2026/DEL/049"
                  value={licenseNo}
                  onChange={(e) => setLicenseNo(e.target.value)}
                  required
                />
              </div>
            </>
          )}

          <div className="login-actions">
            <button type="submit" className="btn btn-primary btn-block">
              Authenticate & Proceed <ArrowRight size={16} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
