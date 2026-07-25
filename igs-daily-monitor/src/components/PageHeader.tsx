import { FileDown } from 'lucide-react';

type Props = {
  eyebrow: string;
  title: string;
  answer: string;
  onExport?: () => void;
  exporting?: boolean;
};

export default function PageHeader({ eyebrow, title, answer, onExport, exporting }: Props) {
  return (
    <header className="page-header" data-export-ignore="false">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        <p className="answer">{answer}</p>
      </div>
      {onExport && (
        <button
          className="export-btn"
          onClick={onExport}
          disabled={exporting}
          data-html2canvas-ignore="true"
        >
          <FileDown size={15} />
          {exporting ? 'Exporting…' : 'Export PDF'}
        </button>
      )}
    </header>
  );
}
