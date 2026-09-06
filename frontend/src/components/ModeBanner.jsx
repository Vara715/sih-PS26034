import React from 'react';
import { ShieldCheck, Factory, ClipboardCheck, BookOpen } from 'lucide-react';

export default function ModeBanner({ currentMode }) {
  const bannerConfigs = {
    public: {
      badge: 'CITIZEN SCANNER MODE',
      icon: ShieldCheck,
      title: 'Verify Packaged Product Declarations',
      desc: 'Upload or capture product label photos to run automated Legal Metrology Rule checks for MRP, Net Quantity, Mfg Date, and Manufacturer details.'
    },
    manufacturer: {
      badge: 'MANUFACTURER PRE-COMPLIANCE STUDIO',
      icon: Factory,
      title: 'Pre-Release Artwork Compliance Validation',
      desc: 'Test new package designs before printing to detect missing mandatory declarations and prevent costly regulatory penalties.'
    },
    inspector: {
      badge: 'OFFICIAL INSPECTOR HUB',
      icon: ClipboardCheck,
      title: 'Field Inspection Intelligence & Audit Ledger',
      desc: 'Perform tamper-evident legal metrology field inspections backed by SHA-256 evidence hashing and immutable database audit records.'
    },
    rules: {
      badge: 'LEGAL RULES REGISTRY',
      icon: BookOpen,
      title: 'Official Legal Metrology (Packaged Commodities) Rules',
      desc: 'Browse deterministic regulatory rules derived from Legal Metrology Rules 2011 and official Department amendments.'
    }
  };

  const config = bannerConfigs[currentMode] || bannerConfigs.public;
  const Icon = config.icon;

  return (
    <section className="mode-banner">
      <div className="banner-badge">
        <Icon size={14} /> {config.badge}
      </div>
      <h2>{config.title}</h2>
      <p>{config.desc}</p>
    </section>
  );
}
