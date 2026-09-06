import React, { useState } from 'react';
import { Scale, User, ClipboardCheck, Factory, KeyRound, Mail, Lock, UserPlus, LogIn, ArrowRight, ShieldCheck, CheckCircle2 } from 'lucide-react';

export default function AuthPage({ onAuthSuccess }) {
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [role, setRole] = useState('inspector'); // 'inspector', 'public', 'manufacturer'

  // Form State
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [badgeOrLicense, setBadgeOrLicense] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const fillQuickDemo = (demoRole) => {
    setErrorMsg('');
    setSuccessMsg('');
    setAuthMode('login');
    setRole(demoRole);
    if (demoRole === 'inspector') {
      setEmail('officer@metrology.gov.in');
      setPassword('officer123');
    } else if (demoRole === 'public') {
      setEmail('consumer@metrology.gov.in');
      setPassword('consumer123');
    } else if (demoRole === 'manufacturer') {
      setEmail('manufacturer@abcfoods.in');
      setPassword('mfg123');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      if (authMode === 'register') {
        if (!username.trim() || !email.trim() || !password.trim()) {
          throw new Error('Please fill in all required registration fields.');
        }

        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: username.trim(),
            email: email.trim(),
            password: password.trim(),
            role: role,
            badge_or_license: badgeOrLicense.trim() || (role === 'inspector' ? 'INS-GOI-DEFAULT' : 'PUBLIC-USER')
          })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Registration failed.');

        setSuccessMsg('Account registered successfully! Logging you in...');
        setTimeout(() => {
          onAuthSuccess(data.user);
        }, 1000);
      } else {
        if (!email.trim() || !password.trim()) {
          throw new Error('Please enter your email address and password.');
        }

        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: email.trim(),
            password: password.trim()
          })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Invalid login credentials.');

        onAuthSuccess(data.user);
      }
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message || 'Authentication error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-portal-container">
      <div className="auth-portal-card">
        {/* Brand Header */}
        <div className="auth-brand-header">
          <div className="auth-logo-emblem">
            <Scale size={32} />
          </div>
          <h2>LEGAL METROLOGY <span>INTELLIGENCE</span></h2>
          <p>Packaged Commodities Compliance & Field Inspection Portal (SIH26034)</p>
          <span className="auth-security-badge">
            <ShieldCheck size={14} /> Official Department Authentication Required
          </span>
        </div>

        {/* Auth Mode Toggle (Login vs Sign Up) */}
        <div className="auth-mode-toggle">
          <button
            type="button"
            className={`auth-toggle-btn ${authMode === 'login' ? 'active' : ''}`}
            onClick={() => { setAuthMode('login'); setErrorMsg(''); setSuccessMsg(''); }}
          >
            <LogIn size={16} /> Sign In
          </button>
          <button
            type="button"
            className={`auth-toggle-btn ${authMode === 'register' ? 'active' : ''}`}
            onClick={() => { setAuthMode('register'); setErrorMsg(''); setSuccessMsg(''); }}
          >
            <UserPlus size={16} /> Create Account (Sign Up)
          </button>
        </div>

        {/* Role Cards Selector */}
        <div className="auth-role-grid">
          <div
            className={`auth-role-card ${role === 'inspector' ? 'selected' : ''}`}
            onClick={() => setRole('inspector')}
          >
            <ClipboardCheck size={20} className="role-icon" />
            <div className="role-title">Official Officer</div>
            <div className="role-desc">Field Inspections & Ledger</div>
          </div>

          <div
            className={`auth-role-card ${role === 'public' ? 'selected' : ''}`}
            onClick={() => setRole('public')}
          >
            <User size={20} className="role-icon" />
            <div className="role-title">Public Citizen</div>
            <div className="role-desc">Product Declarations Scanner</div>
          </div>

          <div
            className={`auth-role-card ${role === 'manufacturer' ? 'selected' : ''}`}
            onClick={() => setRole('manufacturer')}
          >
            <Factory size={20} className="role-icon" />
            <div className="role-title">Manufacturer</div>
            <div className="role-desc">Pre-Release Artwork Studio</div>
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && <div className="auth-alert error">{errorMsg}</div>}
        {successMsg && <div className="auth-alert success"><CheckCircle2 size={16} /> {successMsg}</div>}

        {/* Form Inputs */}
        <form onSubmit={handleSubmit} className="auth-form">
          {authMode === 'register' && (
            <div className="form-group">
              <label><User size={15} /> Full Name / Organization Name</label>
              <input
                type="text"
                className="form-select"
                placeholder="e.g. Inspector Sharma or ABC Foods India"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
          )}

          <div className="form-group">
            <label><Mail size={15} /> Email Address</label>
            <input
              type="email"
              className="form-select"
              placeholder="e.g. officer@metrology.gov.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label><Lock size={15} /> Password</label>
            <input
              type="password"
              className="form-select"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {authMode === 'register' && (
            <div className="form-group">
              <label>
                <KeyRound size={15} /> {role === 'inspector' ? 'Inspector Badge ID' : (role === 'manufacturer' ? 'LMO License Number' : 'Citizen ID')}
              </label>
              <input
                type="text"
                className="form-select"
                placeholder={role === 'inspector' ? 'e.g. INS-8021-GOI' : (role === 'manufacturer' ? 'e.g. LMO-2026-DEL-049' : 'Optional')}
                value={badgeOrLicense}
                onChange={(e) => setBadgeOrLicense(e.target.value)}
              />
            </div>
          )}

          <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={isLoading}>
            {isLoading ? (
              'Authenticating...'
            ) : (
              <>
                {authMode === 'register' ? 'Register Account & Access Dashboard' : 'Sign In to Dashboard'} <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        {/* Quick Demo Test Buttons */}
        <div className="quick-demo-container">
          <span className="demo-label">Instant Demo One-Click Sign In:</span>
          <div className="demo-buttons">
            <button
              type="button"
              className="demo-btn officer"
              onClick={() => fillQuickDemo('inspector')}
            >
              <ClipboardCheck size={14} /> Officer Account
            </button>
            <button
              type="button"
              className="demo-btn consumer"
              onClick={() => fillQuickDemo('public')}
            >
              <User size={14} /> Citizen Consumer
            </button>
            <button
              type="button"
              className="demo-btn mfg"
              onClick={() => fillQuickDemo('manufacturer')}
            >
              <Factory size={14} /> Manufacturer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
