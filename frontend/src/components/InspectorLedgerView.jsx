import React, { useEffect, useState } from 'react';
import { Database, RotateCw, Trash2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

export default function InspectorLedgerView({ scanResult }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = () => {
    setLoading(true);
    fetch('/api/inspections')
      .then((res) => res.json())
      .then((data) => {
        setHistory(data.inspections || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Are you sure you want to reset/clear all past inspection audit records from the database?')) {
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/inspections', { method: 'DELETE' });
      if (res.ok) {
        setHistory([]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [scanResult]);

  return (
    <div className="glass-card width-full">
      <div className="card-header">
        <h3><Database size={20} /> Inspector Audit Ledger & Inspection History</h3>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="button" className="btn btn-outline btn-sm" onClick={fetchHistory} disabled={loading}>
            <RotateCw size={14} className={loading ? 'spin' : ''} /> Refresh Ledger
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleClearHistory} disabled={loading || history.length === 0} title="Reset inspection history database">
            <Trash2 size={14} /> Clear Ledger
          </button>
        </div>
      </div>

      <div className="history-table-wrapper">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Inspection ID</th>
              <th>Timestamp</th>
              <th>Category</th>
              <th>Overall Verdict</th>
              <th>Blur Score</th>
              <th>Cryptographic SHA-256 Ledger Hash</th>
            </tr>
          </thead>
          <tbody>
            {history.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                  {loading ? 'Fetching audit records...' : 'No inspection records found in ledger yet.'}
                </td>
              </tr>
            ) : (
              history.map((item) => {
                let pillClass = 'pass';
                if (item.overall_status === 'POTENTIAL NON-COMPLIANCE') pillClass = 'fail';
                if (item.overall_status === 'INCONCLUSIVE') pillClass = 'inconclusive';

                return (
                  <tr key={item.id}>
                    <td><strong>{item.id}</strong></td>
                    <td>{new Date(item.timestamp).toLocaleString()}</td>
                    <td><span style={{ textTransform: 'capitalize' }}>{item.product_category}</span></td>
                    <td>
                      <span className={`status-pill ${pillClass}`}>
                        {item.overall_status}
                      </span>
                    </td>
                    <td>{item.blur_score ?? '150.0'}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--accent-primary)' }}>
                      {item.evidence_hash}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
