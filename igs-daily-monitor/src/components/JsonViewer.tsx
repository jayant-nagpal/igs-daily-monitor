import { useState } from 'react';
import { ChevronRight, ChevronDown, Copy, Check } from 'lucide-react';

export default function JsonViewer({ value, label = 'Raw JSON payload' }: { value: unknown; label?: string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(value, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked in sandbox; ignore */
    }
  };

  return (
    <div className="json-viewer">
      <div className="jv-head">
        <button className="jv-toggle" onClick={() => setOpen((o) => !o)} data-testid="button-toggle-json">
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          {label}
        </button>
        {open && (
          <button className="jv-copy" onClick={copy} data-testid="button-copy-json">
            {copied ? <Check size={13} /> : <Copy size={13} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
      {open && (
        <pre className="jv-body mono" data-testid="text-json-payload">
          {text}
        </pre>
      )}
    </div>
  );
}
