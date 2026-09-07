import React, { useState } from 'react';
import {
  PieChart, Shield, CheckCircle2, AlertTriangle, HelpCircle,
  Eye, ListCheck, Lock, Gavel, Check, X, Download, Code, Layers, Info, ShieldAlert, Type,
  FileText, QrCode
} from 'lucide-react';

export default function ResultsPanel({ scanData, isLoading }) {
  const [showJson, setShowJson] = useState(false);

  if (isLoading) {
    return (
      <div className="glass-card results-panel">
        <div className="loading-state">
          <div className="spinner"></div>
          <h4>Running 3-Gate Sequential Pipeline...</h4>
          <p>Evaluating Gate 1 (Product Packaging Evidence), Gate 2 (Image Quality & Blur), Gate 3 (OCR & Deterministic Rule Engine)...</p>
        </div>
      </div>
    );
  }

  if (!scanData) {
    return (
      <div className="glass-card results-panel">
        <div className="card-header">
          <h3><PieChart size={20} /> Compliance Assessment</h3>
          <span className="step-indicator">INS-PENDING</span>
        </div>
        <div className="placeholder-state">
          <Shield className="placeholder-icon" size={56} />
          <h4>Ready for Compliance Evaluation</h4>
          <p>Upload a product package image (front/back) or select a demo sample to run the multi-stage product validation pipeline.</p>
        </div>
      </div>
    );
  }

  const { inspection_id = 'INS-UNKNOWN', input_validation, quality_assessment, compliance_report, evidence_ledger } = scanData || {};
  const {
    overall_status = 'PENDING',
    verdict_title = 'Compliance Assessment',
    reason = 'Evaluation details pending.',
    verdict_color = 'warning',
    rule_results = [],
    passed_rules_count = 0,
    rules_applied_count = 0,
    disclaimer = 'Automated preliminary assessment. System does not claim 100% accuracy or guaranteed legal compliance.'
  } = compliance_report || {};

  const downloadReport = () => {
    const blob = new Blob([JSON.stringify(scanData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `LegalMetrology_Report_${inspection_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadPdf = () => {
    window.open(`/api/inspections/${inspection_id}/pdf`, '_blank');
  };

  const getVerdictIcon = () => {
    if (verdict_color === 'success') return <CheckCircle2 size={32} />;
    if (verdict_color === 'danger') return <AlertTriangle size={32} />;
    return <HelpCircle size={32} />;
  };

  const getGate1StatusBadge = (status) => {
    if (status === 'VALID_PRODUCT') {
      return <span style={{ padding: '0.2rem 0.6rem', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', fontWeight: 'bold', fontSize: '0.8rem', border: '1px solid rgba(34, 197, 94, 0.4)' }}>PRODUCT DETECTED ✓</span>;
    }
    if (status === 'INCONCLUSIVE_INPUT') {
      return <span style={{ padding: '0.2rem 0.6rem', borderRadius: '4px', background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', fontWeight: 'bold', fontSize: '0.8rem', border: '1px solid rgba(234, 179, 8, 0.4)' }}>IMAGE REQUIRES VERIFICATION</span>;
    }
    return <span style={{ padding: '0.2rem 0.6rem', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', fontWeight: 'bold', fontSize: '0.8rem', border: '1px solid rgba(239, 68, 68, 0.4)' }}>INVALID PRODUCT IMAGE / REJECTED</span>;
  };

  return (
    <div className="glass-card results-panel">
      <div className="card-header">
        <h3><PieChart size={20} /> Compliance Assessment</h3>
        <span className="step-indicator">{inspection_id}</span>
      </div>

      {/* Verdict Banner */}
      <div className={`verdict-banner ${verdict_color || 'warning'}`}>
        <div className="verdict-icon">
          {getVerdictIcon()}
        </div>
        <div className="verdict-details">
          <span className="verdict-badge">{overall_status}</span>
          <h3>{verdict_title}</h3>
          <p>{reason}</p>
        </div>
      </div>

      {/* Gate 1 Diagnostic Evidence Card */}
      {input_validation && (
        <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', padding: '1rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
            <h4 style={{ margin: 0, fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-primary)' }}>
              <Layers size={16} className="icon-blue" /> Gate 1: Product Packaging Evidence Analysis
            </h4>
            {getGate1StatusBadge(input_validation.status)}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 0.6rem 0' }}>
            {input_validation.reason}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.6rem', fontSize: '0.78rem', background: 'rgba(0,0,0,0.2)', padding: '0.6rem', borderRadius: '6px' }}>
            <div>
              <span style={{ color: 'var(--text-secondary)' }}>Evidence Score:</span>{' '}
              <strong style={{ color: input_validation.confidence >= 0.6 ? '#4ade80' : '#f87171' }}>
                {(input_validation.confidence * 100).toFixed(0)}%
              </strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-secondary)' }}>OCR Execution:</span>{' '}
              <strong style={{ color: input_validation.should_proceed_to_ocr ? '#4ade80' : '#f87171' }}>
                {input_validation.should_proceed_to_ocr ? 'EXECUTED' : 'BLOCKED'}
              </strong>
            </div>
            {input_validation.breakdown && (
              <>
                {input_validation.breakdown.ruled_paper_detected !== undefined && (
                  <div>
                    <span style={{ color: 'var(--text-secondary)' }}>Notebook Lines:</span>{' '}
                    <strong style={{ color: input_validation.breakdown.ruled_paper_detected ? '#f87171' : '#4ade80' }}>
                      {input_validation.breakdown.ruled_paper_detected ? 'DETECTED' : 'None'}
                    </strong>
                  </div>
                )}
                {input_validation.breakdown.saturation_std_dev !== undefined && (
                  <div>
                    <span style={{ color: 'var(--text-secondary)' }}>Color Variance:</span>{' '}
                    <strong>{input_validation.breakdown.saturation_std_dev}</strong>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}


      {/* Quality & Rule Stats Bar */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-title"><Eye size={14} /> Image Blur Score</div>
          <div className="stat-val">{quality_assessment?.blur_score ?? 150.0}</div>
          <div className="stat-sub">Rating: {quality_assessment?.quality_rating || 'N/A'}</div>
        </div>

        <div className="stat-card">
          <div className="stat-title"><ListCheck size={14} /> Mandatory Rules</div>
          <div className="stat-val">{passed_rules_count || 0} / {rules_applied_count || 0} Passed</div>
          <div className="stat-sub">Legal Rules 2011 / 2022</div>
        </div>

        <div className="stat-card">
          <div className="stat-title"><Lock size={14} /> Evidence Hash</div>
          <div className="stat-val stat-hash">
            {evidence_ledger?.evidence_hash ? `${evidence_ledger.evidence_hash.substring(0, 12)}...` : 'SHA-256'}
          </div>
          <div className="stat-sub">SHA-256 Ledger Record</div>
        </div>
      </div>

      {/* Audit Checklist Table */}
      {rules_applied_count > 0 && (
        <div className="rules-audit-section">
          <h4><Gavel size={16} /> Declaration Checklist Audit (Rule 6)</h4>
          <div className="rules-table-wrapper">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Rule Clause</th>
                  <th>Declaration Field</th>
                  <th>Status</th>
                  <th>Extracted Evidence</th>
                  <th>Explanation</th>
                </tr>
              </thead>
              <tbody>
                {rule_results?.map((rule, idx) => {
                  let pillClass = 'pass';
                  let IconComp = Check;
                  if (rule.status === 'FAIL') {
                    pillClass = 'fail';
                    IconComp = X;
                  } else if (rule.status === 'INCONCLUSIVE') {
                    pillClass = 'inconclusive';
                    IconComp = HelpCircle;
                  }

                  return (
                    <tr key={idx}>
                      <td><strong style={{ color: 'var(--accent-primary)' }}>{rule.rule_clause}</strong></td>
                      <td>{rule.rule_name}</td>
                      <td>
                        <span className={`status-pill ${pillClass}`}>
                          <IconComp size={12} /> {rule.status}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.82rem', color: '#0f172a', fontWeight: '600' }}>
                        {rule.evidence_text || <em style={{ color: '#94a3b8', fontStyle: 'italic', fontWeight: '400' }}>Not detected</em>}
                      </td>
                      <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{rule.explanation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Legal Disclaimer Box */}
      <div style={{ background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.3)', padding: '0.6rem 0.8rem', borderRadius: '6px', fontSize: '0.78rem', color: '#fef08a', margin: '0.8rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Info size={16} style={{ flexShrink: 0 }} />
        <span>{disclaimer || "Automated preliminary assessment. System does not claim 100% accuracy or guaranteed legal compliance."}</span>
      </div>

      {/* Barcode & Readability Intelligence Card */}
      {(scanData?.barcode_data?.detected || scanData?.readability_analysis?.evaluated) && (
        <div style={{ background: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '8px', padding: '0.8rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.8rem' }}>
            {scanData.barcode_data?.detected && (
              <div>
                <strong style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#38bdf8' }}>
                  <QrCode size={14} /> Optical Codes Detected:
                </strong>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {scanData.barcode_data.raw_codes.join(', ')}
                </span>
              </div>
            )}
            {scanData.readability_analysis?.evaluated && (
              <div>
                <strong style={{ display: 'flex', alignItems: 'center', gap: '4px', color: scanData.readability_analysis.rule_9_compliant ? '#4ade80' : '#facc15' }}>
                  <Type size={14} /> Rule 9 Numeral Typography:
                </strong>
                <span style={{ color: 'var(--text-secondary)' }}>
                  Avg {scanData.readability_analysis.avg_token_height_px}px | {scanData.readability_analysis.recommendation}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Action Bar */}
      <div className="action-bar" style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-primary" onClick={downloadPdf}>
          <FileText size={16} /> Download Official PDF Certificate
        </button>
        <button type="button" className="btn btn-outline" onClick={downloadReport}>
          <Download size={16} /> Download JSON Report
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => setShowJson(!showJson)}>
          <Code size={16} /> {showJson ? 'Hide Raw JSON' : 'View Raw Structured JSON'}
        </button>
      </div>

      {showJson && (
        <pre className="json-display">
          {JSON.stringify(scanData, null, 2)}
        </pre>
      )}
    </div>
  );
}
