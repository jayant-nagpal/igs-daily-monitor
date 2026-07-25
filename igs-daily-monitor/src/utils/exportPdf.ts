/* ============================================================
   PDF export — renders the current page's content region to a
   single-page-fit PDF. Never throws to the caller; on failure it
   logs and returns false so the UI can show a toast without crashing.
   ============================================================ */
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

const BG = '#0d0f12';

export async function exportElementToPdf(
  el: HTMLElement | null,
  fileName: string,
): Promise<boolean> {
  if (!el) return false;
  try {
    const canvas = await html2canvas(el, {
      backgroundColor: BG,
      scale: Math.min(2, window.devicePixelRatio || 1.5),
      useCORS: true,
      logging: false,
      windowWidth: el.scrollWidth,
      windowHeight: el.scrollHeight,
    });

    const imgData = canvas.toDataURL('image/png');
    const orientation = canvas.width >= canvas.height ? 'landscape' : 'portrait';
    const pdf = new jsPDF({ orientation, unit: 'pt', format: 'a4' });

    const pageW = pdf.internal.pageSize.getWidth();
    const pageH = pdf.internal.pageSize.getHeight();
    const margin = 24;
    const maxW = pageW - margin * 2;
    const maxH = pageH - margin * 2;

    const ratio = Math.min(maxW / canvas.width, maxH / canvas.height);
    const w = canvas.width * ratio;
    const h = canvas.height * ratio;
    const x = (pageW - w) / 2;
    const y = margin;

    pdf.setFillColor(BG);
    pdf.rect(0, 0, pageW, pageH, 'F');
    pdf.addImage(imgData, 'PNG', x, y, w, h);
    pdf.save(fileName);
    return true;
  } catch (e) {
    console.error('exportElementToPdf failed:', e);
    return false;
  }
}
