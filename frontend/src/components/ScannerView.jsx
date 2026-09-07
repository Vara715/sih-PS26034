import React, { useState, useRef } from 'react';
import { Camera, Tags, UploadCloud, FolderOpen, X, FlaskConical, CheckCircle2, XCircle, AlertTriangle, Type, Zap, Image as ImageIcon } from 'lucide-react';

const SAMPLES = {
  compliant: {
    text: "ABC Premium Wheat Biscuits\nNet Qty: 500 g\nMRP Rs. 120.00 (incl. of all taxes)\nMfd Date: 08/2026\nManufactured by ABC Foods Pvt Ltd, Industrial Area, New Delhi - 110020\nConsumer Care Helpline: 1800-111-2222 Email: care@abcfoods.in\nCountry of Origin: India\nUnit Sale Price: Rs 0.24 / g",
    category: "food"
  },
  nonCompliant: {
    text: "Golden Pure Cooking Oil\nNet Quantity: 1 L\nMfd Date: 12/2025\nManufactured by Sunrise Oils Ltd, Plot 45, Gujarat\nCustomer Care: care@sunriseoils.com",
    category: "packaged_goods"
  },
  notebookPaper: {
    text: "Notebook Page / Handwritten Study Notes\nMRP ₹120\nNet Qty 500 g\nManufacturer ABC Foods",
    category: "packaged_goods"
  },
  blurry: {
    text: "l0r3m ip5um 120... [illegible blurry text]",
    category: "packaged_goods"
  }
};

export default function ScannerView({
  selectedFile,
  setSelectedFile,
  previewUrl,
  setPreviewUrl,
  selectedFileBack,
  setSelectedFileBack,
  previewUrlBack,
  setPreviewUrlBack,
  category,
  setCategory,
  ocrText,
  setOcrText,
  onScan,
  isLoading
}) {
  const [activeSample, setActiveSample] = useState(null);
  const fileInputRefFront = useRef(null);
  const fileInputRefBack = useRef(null);

  const handleFrontFileChange = (file) => {
    if (!file) return;
    setActiveSample(null); // Reset demo sample state when user uploads real image
    setSelectedFile(file);
    setOcrText('');
    const reader = new FileReader();
    reader.onload = (e) => setPreviewUrl(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleBackFileChange = (file) => {
    if (!file) return;
    setActiveSample(null); // Reset demo sample state when user uploads real image
    setSelectedFileBack(file);
    setOcrText('');
    const reader = new FileReader();
    reader.onload = (e) => setPreviewUrlBack(e.target.result);
    reader.readAsDataURL(file);
  };

  const clearFrontImage = (e) => {
    e.stopPropagation();
    setSelectedFile(null);
    setPreviewUrl(null);
    if (fileInputRefFront.current) fileInputRefFront.current.value = '';
  };

  const clearBackImage = (e) => {
    e.stopPropagation();
    setSelectedFileBack(null);
    setPreviewUrlBack(null);
    if (fileInputRefBack.current) fileInputRefBack.current.value = '';
  };

  const applySample = (sampleKey) => {
    const sample = SAMPLES[sampleKey];
    if (sample) {
      // 1. Clear any existing front/back file selections completely
      setSelectedFile(null);
      setPreviewUrl(null);
      setSelectedFileBack(null);
      setPreviewUrlBack(null);

      // 2. Clear native input elements
      if (fileInputRefFront.current) fileInputRefFront.current.value = '';
      if (fileInputRefBack.current) fileInputRefBack.current.value = '';

      // 3. Set text, category, and visual active state
      setOcrText(sample.text);
      setCategory(sample.category);
      setActiveSample(sampleKey);
    }
  };

  return (
    <div className="glass-card upload-panel">
      <div className="card-header">
        <h3><Camera size={20} className="icon-blue" /> Package Label Dual Scan</h3>
        <span className="step-indicator">Step 1 of 3</span>
      </div>

      {/* Category Selection */}
      <div className="form-group">
        <label htmlFor="categorySelect">
          <Tags size={15} /> Product Category
        </label>
        <select
          id="categorySelect"
          className="form-select"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="packaged_goods">General Packaged Commodities</option>
          <option value="food">Packaged Food Products</option>
          <option value="imported">Imported Commodity Goods</option>
          <option value="electronics">Electronic Equipment Packaging</option>
          <option value="garments">Garments & Textiles</option>
        </select>
      </div>

      {/* Dual Image Upload Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', marginBottom: '1.2rem' }}>
        {/* Front Image Slot */}
        <div>
          <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <ImageIcon size={14} /> Front Package / Artwork
          </label>
          <div
            className="drop-zone"
            style={{ padding: '1rem', minHeight: '130px' }}
            onClick={() => !previewUrl && fileInputRefFront.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRefFront}
              accept="image/*"
              className="file-input"
              onChange={(e) => e.target.files?.[0] && handleFrontFileChange(e.target.files[0])}
            />

            {!previewUrl ? (
              <div className="drop-zone-content" style={{ padding: '0.5rem 0' }}>
                <UploadCloud className="drop-icon" size={28} />
                <h4 style={{ fontSize: '0.85rem' }}>Upload Front Image</h4>
                <button
                  type="button"
                  className="btn btn-outline"
                  style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem', marginTop: '0.3rem' }}
                  onClick={(e) => { e.stopPropagation(); fileInputRefFront.current?.click(); }}
                >
                  <FolderOpen size={12} /> Browse
                </button>
              </div>
            ) : (
              <div className="image-preview-container">
                <img src={previewUrl} alt="Front Package Preview" style={{ maxHeight: '110px' }} />
                <button type="button" className="btn-remove-img" onClick={clearFrontImage}>
                  <X size={12} /> Remove
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Back Image Slot */}
        <div>
          <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <ImageIcon size={14} /> Back Label / Declarations (Optional)
          </label>
          <div
            className="drop-zone"
            style={{ padding: '1rem', minHeight: '130px' }}
            onClick={() => !previewUrlBack && fileInputRefBack.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRefBack}
              accept="image/*"
              className="file-input"
              onChange={(e) => e.target.files?.[0] && handleBackFileChange(e.target.files[0])}
            />

            {!previewUrlBack ? (
              <div className="drop-zone-content" style={{ padding: '0.5rem 0' }}>
                <UploadCloud className="drop-icon" size={28} />
                <h4 style={{ fontSize: '0.85rem' }}>Upload Back Image</h4>
                <button
                  type="button"
                  className="btn btn-outline"
                  style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem', marginTop: '0.3rem' }}
                  onClick={(e) => { e.stopPropagation(); fileInputRefBack.current?.click(); }}
                >
                  <FolderOpen size={12} /> Browse
                </button>
              </div>
            ) : (
              <div className="image-preview-container">
                <img src={previewUrlBack} alt="Back Package Preview" style={{ maxHeight: '110px' }} />
                <button type="button" className="btn-remove-img" onClick={clearBackImage}>
                  <X size={12} /> Remove
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Test Samples */}
      <div className="sample-section">
        <label><FlaskConical size={15} /> Instant Demo Sample Test Case:</label>
        <div className="sample-buttons">
          <button
            type="button"
            className={`sample-btn compliant ${activeSample === 'compliant' ? 'active' : ''}`}
            onClick={() => applySample('compliant')}
            style={activeSample === 'compliant' ? { outline: '2px solid #4ade80', background: 'rgba(74, 222, 128, 0.15)' } : {}}
          >
            <CheckCircle2 size={14} /> Compliant Biscuit {activeSample === 'compliant' ? '✓' : ''}
          </button>
          <button
            type="button"
            className={`sample-btn non-compliant ${activeSample === 'notebookPaper' ? 'active' : ''}`}
            onClick={() => applySample('notebookPaper')}
            style={activeSample === 'notebookPaper' ? { outline: '2px solid #f87171', background: 'rgba(248, 113, 113, 0.15)' } : {}}
          >
            <XCircle size={14} /> Notebook "MRP ₹120" {activeSample === 'notebookPaper' ? '✓' : ''}
          </button>
          <button
            type="button"
            className={`sample-btn blurry ${activeSample === 'blurry' ? 'active' : ''}`}
            onClick={() => applySample('blurry')}
            style={activeSample === 'blurry' ? { outline: '2px solid #facc15', background: 'rgba(250, 204, 21, 0.15)' } : {}}
          >
            <AlertTriangle size={14} /> Blurry Image {activeSample === 'blurry' ? '✓' : ''}
          </button>
        </div>
      </div>

      {/* OCR Text Override */}
      <div className="form-group text-override-group">
        <label htmlFor="ocrTextOverride">
          <Type size={15} /> Label Text (OCR / Manual Correction)
        </label>
        <textarea
          id="ocrTextOverride"
          className="form-textarea"
          rows={3}
          placeholder="OCR detected text will appear here automatically, or type custom label text..."
          value={ocrText}
          onChange={(e) => {
            setOcrText(e.target.value);
            setActiveSample(null);
          }}
        />
      </div>

      {/* Scan Button */}
      <button
        type="button"
        className="btn btn-primary btn-block"
        onClick={onScan}
        disabled={isLoading}
      >
        <Zap size={18} /> {isLoading ? 'Running Product Validation & Audit Scan...' : 'Run Legal Metrology Audit Scan'}
      </button>
    </div>
  );
}
