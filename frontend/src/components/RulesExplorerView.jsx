import React, { useEffect, useState } from 'react';
import { Scale, BookOpen, AlertCircle } from 'lucide-react';

export default function RulesExplorerView() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/rules')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch rules');
        return res.json();
      })
      .then((data) => {
        setRules(data.rules || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="glass-card width-full">
      <div className="card-header">
        <h3><Scale size={20} /> Department of Consumer Affairs - Legal Metrology Rules Database</h3>
        <span className="badge-tag">Official Regulations</span>
      </div>
      <p className="section-intro">
        Comprehensive registry of deterministic legal rules derived from the Legal Metrology (Packaged Commodities) Rules, 2011 and official amendments (2017, 2020, 2021, 2022).
      </p>

      {loading && (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading Official Legal Metrology Rules...</p>
        </div>
      )}

      {error && (
        <div className="verdict-banner danger">
          <AlertCircle size={24} />
          <div>
            <h4>Error Loading Rules</h4>
            <p>{error}</p>
          </div>
        </div>
      )}

      {!loading && !error && (
        <div className="rules-grid">
          {rules.map((rule, idx) => (
            <div className="rule-card" key={rule.rule_id || idx}>
              <div className="rule-card-header">
                <span className="rule-clause-badge">{rule.rule_clause}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{rule.version}</span>
              </div>
              <h4>{rule.rule_name}</h4>
              <p>{rule.description}</p>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                <strong>Target Field:</strong> <code>{rule.target_field}</code><br />
                <strong>Mandatory:</strong>{' '}
                {rule.is_mandatory ? (
                  <span style={{ color: 'var(--status-fail)', fontWeight: 'bold' }}>YES</span>
                ) : (
                  'OPTIONAL'
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
