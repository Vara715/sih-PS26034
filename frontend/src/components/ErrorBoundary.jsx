import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Uncaught React UI Error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0f172a',
          color: '#f8fafc',
          padding: '2rem',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{
            maxWidth: '520px',
            width: '100%',
            background: 'rgba(30, 41, 59, 0.95)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '12px',
            padding: '2rem',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            textAlign: 'center'
          }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'rgba(239, 68, 68, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.2rem auto',
              color: '#f87171'
            }}>
              <AlertTriangle size={32} />
            </div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.4rem' }}>Application UI Recovered</h3>
            <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '1.5rem', lineHeight: '1.5' }}>
              An unexpected display issue occurred in the interface. The system prevented a total blank screen crash.
            </p>
            {this.state.error && (
              <pre style={{
                textAlign: 'left',
                background: '#020617',
                padding: '0.8rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                color: '#f87171',
                overflowX: 'auto',
                marginBottom: '1.5rem'
              }}>
                {this.state.error.toString()}
              </pre>
            )}
            <button
              onClick={this.handleReset}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: '#2563eb',
                color: '#ffffff',
                border: 'none',
                padding: '0.65rem 1.4rem',
                borderRadius: '8px',
                fontWeight: '600',
                cursor: 'pointer',
                fontSize: '0.9rem'
              }}
            >
              <RotateCcw size={16} /> Reload Legal Metrology Dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
