import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ModeBanner from './components/ModeBanner';
import ScannerView from './components/ScannerView';
import ResultsPanel from './components/ResultsPanel';
import RulesExplorerView from './components/RulesExplorerView';
import InspectorLedgerView from './components/InspectorLedgerView';
import AuthPage from './components/AuthPage';

export default function App() {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('lm_user');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const [currentMode, setCurrentMode] = useState(() => {
    return user ? user.role : 'public';
  });

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [selectedFileBack, setSelectedFileBack] = useState(null);
  const [previewUrlBack, setPreviewUrlBack] = useState(null);

  const [category, setCategory] = useState('packaged_goods');
  const [ocrText, setOcrText] = useState('');

  const [scanResult, setScanResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (user) {
      localStorage.setItem('lm_user', JSON.stringify(user));
      const roleDefault = user.role === 'inspector' ? 'inspector' : (user.role === 'manufacturer' ? 'manufacturer' : 'public');
      const allowedModes = {
        inspector: ['inspector', 'rules'],
        public: ['public', 'rules'],
        manufacturer: ['manufacturer', 'rules']
      }[user.role || 'public'] || ['public', 'rules'];

      if (!allowedModes.includes(currentMode)) {
        setCurrentMode(roleDefault);
      }
    } else {
      localStorage.removeItem('lm_user');
    }
  }, [user, currentMode]);

  const handleAuthSuccess = (userData) => {
    const userObj = {
      ...userData,
      authenticated: true
    };
    setUser(userObj);
    const initialMode = userData.role === 'inspector' ? 'inspector' : (userData.role === 'manufacturer' ? 'manufacturer' : 'public');
    setCurrentMode(initialMode);
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('lm_user');
  };

  const handleRoleSwitch = (mode) => {
    const userRole = user?.role || 'public';
    const allowedModes = {
      inspector: ['inspector', 'rules'],
      public: ['public', 'rules'],
      manufacturer: ['manufacturer', 'rules']
    }[userRole] || ['public', 'rules'];

    if (!allowedModes.includes(mode)) {
      alert('Access Denied: Requested view is not permitted for your user role.');
      return;
    }
    setCurrentMode(mode);
  };

  const handleScan = async () => {
    if (!selectedFile && !selectedFileBack && !ocrText.trim()) {
      alert('Please upload at least one package image (front/back) or enter label text.');
      return;
    }

    setIsLoading(true);
    const formData = new FormData();
    if (selectedFile) formData.append('file', selectedFile);
    if (selectedFileBack) formData.append('file_back', selectedFileBack);
    if (!selectedFile && !selectedFileBack && ocrText.trim()) {
      formData.append('raw_text_input', ocrText.trim());
    }
    formData.append('user_mode', currentMode);
    formData.append('product_category', category);

    try {
      const response = await fetch('/api/scan', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
      }

      const data = await response.json();
      setScanResult(data);
      const textToSet = data.ocr_text ?? data.ocr_result?.full_text;
      if (textToSet !== undefined && textToSet !== null) {
        setOcrText(textToSet);
      }
    } catch (err) {
      console.error('Scan Error:', err);
      alert('Error communicating with Legal Metrology API backend. Make sure FastAPI server is running.');
    } finally {
      setIsLoading(false);
    }
  };

  // Mandatory Authentication Gate: If user is not logged in, show AuthPage
  if (!user || !user.authenticated) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  return (
    <div className="app-container">
      <Header
        currentMode={currentMode}
        setMode={handleRoleSwitch}
        user={user}
        onLogout={handleLogout}
      />

      <main className="app-main">
        <ModeBanner currentMode={currentMode} />

        {currentMode === 'rules' ? (
          <RulesExplorerView />
        ) : (
          <>
            <div className="scanner-grid">
              <ScannerView
                selectedFile={selectedFile}
                setSelectedFile={setSelectedFile}
                previewUrl={previewUrl}
                setPreviewUrl={setPreviewUrl}
                selectedFileBack={selectedFileBack}
                setSelectedFileBack={setSelectedFileBack}
                previewUrlBack={previewUrlBack}
                setPreviewUrlBack={setPreviewUrlBack}
                category={category}
                setCategory={setCategory}
                ocrText={ocrText}
                setOcrText={setOcrText}
                onScan={handleScan}
                isLoading={isLoading}
              />

              <ResultsPanel scanData={scanResult} isLoading={isLoading} />
            </div>

            {currentMode === 'inspector' && user?.role === 'inspector' && scanResult && (
              <div style={{ marginTop: '2.5rem' }}>
                <InspectorLedgerView userRole={user.role} scanResult={scanResult} />
              </div>
            )}
          </>
        )}
      </main>

      <footer className="app-footer">
        <div className="footer-container">
          <p>Legal Metrology Packaged Commodities Compliance System (SIH26034) • Powered by React, Vite, FastAPI & OpenCV</p>
          <p className="disclaimer">
            Note: Public scan results provide automated preliminary assessments. Legal enforcement decisions are governed by official inspectors under the Legal Metrology Act, 2009.
          </p>
        </div>
      </footer>
    </div>
  );
}
