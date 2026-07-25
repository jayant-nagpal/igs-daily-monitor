import { useRef, useState } from 'react';
import { DataProvider, useData } from './DataContext';
import Sidebar, { type PageKey } from './components/Sidebar';
import RightPanel from './components/RightPanel';
import Overview from './pages/Overview';
import Slippage from './pages/Slippage';
import AlertsRisk from './pages/AlertsRisk';
import PriceCostDrift from './pages/PriceCostDrift';
import Exposure from './pages/Exposure';
import DataHealth from './pages/DataHealth';
import { exportElementToPdf } from './utils/exportPdf';

const PAGE_TITLES: Record<PageKey, string> = {
  overview: 'Overview',
  slippage: 'Slippage',
  alerts: 'Alerts_Risk',
  drift: 'Price_Cost_Drift',
  exposure: 'Exposure',
  health: 'Data_Health',
};

function Shell() {
  const { data } = useData();
  const [page, setPage] = useState<PageKey>('overview');
  const [exporting, setExporting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const exportPdf = async () => {
    if (!contentRef.current || exporting) return;
    setExporting(true);
    try {
      await new Promise((r) => setTimeout(r, 60));
      await exportElementToPdf(
        contentRef.current,
        `IGS_${PAGE_TITLES[page]}_${data.businessDate}.pdf`,
      );
    } finally {
      setExporting(false);
    }
  };

  const pageProps = { onExport: exportPdf, exporting };

  return (
    <div className="app-shell">
      <Sidebar active={page} onNavigate={setPage} />

      <main className="content">
        <div className="content-inner" ref={contentRef}>
          {page === 'overview' && <Overview {...pageProps} />}
          {page === 'slippage' && <Slippage {...pageProps} />}
          {page === 'alerts' && <AlertsRisk {...pageProps} />}
          {page === 'drift' && <PriceCostDrift {...pageProps} />}
          {page === 'exposure' && <Exposure {...pageProps} />}
          {page === 'health' && <DataHealth {...pageProps} />}
        </div>
      </main>

      <RightPanel onExport={exportPdf} exporting={exporting} />
    </div>
  );
}

export default function App() {
  return (
    <DataProvider>
      <Shell />
    </DataProvider>
  );
}
