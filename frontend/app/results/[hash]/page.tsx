'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ShieldCheck,
  BarChart2,
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  Link as LinkIcon,
  CheckCircle2,
  FileText,
  Download,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────
interface NumericStats {
  column_name: string;
  original_mean: number;
  protected_mean: number;
  original_std: number;
  protected_std: number;
  epsilon_used: number;
}

interface CategoryDistribution {
  column_name: string;
  distribution: Record<string, number>;
}

interface PipelineSummary {
  total_rows_processed: number;
  columns_ignored: number;
  columns_laplace: number;
  columns_randomized: number;
  columns_reviewed: number;
}

interface ResultData {
  status: string;
  result_id: string;
  result_url: string;
  filename: string;
  summary: PipelineSummary;
  numeric_stats: NumericStats[];
  category_distributions: CategoryDistribution[];
  charts: Array<{ title: string; type: string; plotly_json: object }>;
}

// ── Plotly Chart Component ───────────────────────────────────────────────────
function PlotlyChart({ chart }: { chart: { title: string; plotly_json: object } }) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const renderChart = () => {
      if ((window as any).Plotly && containerRef.current) {
        const { data, layout } = chart.plotly_json as any;

        // Memaksa data trace agar monokrom (hitam, abu-abu, putus-putus)
        const monochromeData = data.map((trace: any) => {
          const newTrace = { ...trace };
          const isOriginal = newTrace.name?.toLowerCase().includes('asli') || newTrace.name?.toLowerCase().includes('original');
          const isMean = newTrace.name?.toLowerCase().includes('mean');

          if (newTrace.marker) {
            newTrace.marker = {
              ...newTrace.marker,
              color: isOriginal ? '#a1a1aa' : '#000000',
              line: { color: isOriginal ? '#a1a1aa' : '#000000' }
            };
          }
          if (newTrace.line) {
            newTrace.line = {
              ...newTrace.line,
              color: isOriginal ? '#a1a1aa' : '#000000',
              dash: isMean ? 'dash' : 'solid'
            };
          }
          return newTrace;
        });

        const mergedLayout = {
          ...layout,
          margin: { t: 50, r: 20, b: 70, l: 60 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: '#fafafa',
          font: { family: 'Courier New, monospace', size: 10, color: '#000000' },
          height: 320,
          title: { ...layout?.title, font: { family: 'Courier New, monospace', size: 12, color: '#000000', weight: 700 } },
        };
        (window as any).Plotly.react(containerRef.current, monochromeData, mergedLayout, {
          responsive: true,
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        });
        setLoaded(true);
      }
    };

    const existing = document.querySelector('script[src*="plotly"]');
    if ((window as any).Plotly) {
      renderChart();
    } else if (!existing) {
      const script = document.createElement('script');
      script.src = 'https://cdn.plot.ly/plotly-2.27.0.min.js';
      script.onload = renderChart;
      document.head.appendChild(script);
    } else {
      existing.addEventListener('load', renderChart);
    }
  }, [chart]);

  return (
    <div className="bg-white border border-zinc-300 p-5 font-mono">
      <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">
        {chart.title}
      </p>
      {!loaded && (
        <div className="h-48 flex items-center justify-center bg-zinc-50 border border-zinc-200">
          <RefreshCw className="w-4 h-4 text-zinc-400 animate-spin" />
        </div>
      )}
      <div ref={containerRef} className={`w-full overflow-hidden border border-zinc-200 ${!loaded ? 'hidden' : ''}`} />
    </div>
  );
}

// ── Main Page Component ──────────────────────────────────────────────────────
export default function ResultPage() {
  const params = useParams();
  const hash = params?.hash as string;

  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<ResultData | null>(null);
  const [error, setError] = useState<{ code: number; message: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!hash) return;

    const fetchResult = async () => {
      try {
        const res = await fetch(`http://localhost:8000/v1/results/${hash}/raw`);

        if (res.status === 401) {
          setError({ code: 401, message: 'Akses ditolak. URL tidak valid atau sudah kedaluwarsa.' });
          return;
        }
        if (res.status === 404) {
          setError({ code: 404, message: 'Hasil tidak ditemukan.' });
          return;
        }
        if (!res.ok) {
          setError({ code: res.status, message: `Server error (${res.status})` });
          return;
        }

        const json = await res.json();
        setResult(json.data);
      } catch (err) {
        setError({ code: 0, message: 'Tidak dapat terhubung ke server. Pastikan backend berjalan.' });
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [hash]);

  const copyUrl = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center font-mono text-black">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border border-black flex items-center justify-center mx-auto bg-white">
            <RefreshCw className="w-5 h-5 text-black animate-spin" />
          </div>
          <p className="text-xs font-bold uppercase tracking-wider">Memproses & Memvalidasi Akses...</p>
          <p className="text-zinc-500 text-[10px] font-mono">{hash}</p>
        </div>
      </div>
    );
  }

  // ── 401 / Error ────────────────────────────────────────────────────────────
  if (error) {
    const is401 = error.code === 401;
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center p-6 font-mono text-black">
        <div className="max-w-md w-full border border-zinc-300 bg-white p-8 space-y-6 shadow-sm">
          <div className="w-12 h-12 border border-black flex items-center justify-center mx-auto bg-zinc-50">
            <AlertTriangle className="w-6 h-6 text-black" />
          </div>

          <div className="text-center">
            <div className="inline-block text-[10px] font-bold uppercase tracking-widest px-3 py-1 border border-zinc-300 bg-zinc-100 mb-3">
              {is401 ? '401 Unauthorized' : `Error ${error.code}`}
            </div>
            <h1 className="text-base font-bold uppercase tracking-wider mb-3">
              {is401 ? 'AKSES DITOLAK' : 'TIDAK DITEMUKAN'}
            </h1>
            <p className="text-zinc-500 text-xs leading-relaxed">{error.message}</p>
          </div>

          {is401 && (
            <div className="bg-zinc-50 border border-zinc-200 p-4 space-y-2 text-xs">
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">Hash Dicoba:</p>
              <code className="text-[10px] font-mono text-black block break-all">{hash}</code>
              <p className="text-[10px] text-zinc-400 mt-2">
                Tautan mungkin sudah kedaluwarsa, tidak valid, atau server telah di-restart.
              </p>
            </div>
          )}

          <div className="text-center">
            <Link
              href="/"
              className="inline-flex items-center gap-2 bg-black text-white hover:bg-zinc-900 border border-black px-4 py-2 font-bold text-xs uppercase tracking-wider cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Kembali ke Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  // ── Success — Result Viewer ────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-zinc-50 font-mono text-zinc-900 selection:bg-black selection:text-white">
      {/* Header */}
      <header className="bg-white border-b border-zinc-300 sticky top-0 z-10 py-4 px-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-1.5 text-zinc-500 hover:text-black transition-colors text-xs font-bold uppercase">
              <ArrowLeft className="w-3.5 h-3.5" />
              [Dashboard]
            </Link>
            <span className="text-zinc-300">·</span>
            <div className="flex items-center gap-2">
              <span className="font-bold text-black text-xs uppercase tracking-wider">[Hasil Pemrosesan]</span>
              <span className="text-[9px] bg-zinc-100 text-zinc-800 px-2 py-0.5 border border-zinc-300 font-bold uppercase">
                TERVERIFIKASI
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <a
              href={`http://localhost:8000/v1/results/${hash}/download`}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-black text-white hover:bg-zinc-900 transition-colors border border-black font-bold uppercase tracking-wider cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              Unduh CSV
            </a>
            <button
              onClick={copyUrl}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 border font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                copied
                  ? 'bg-zinc-100 text-black border-zinc-400'
                  : 'bg-white text-zinc-600 hover:bg-zinc-50 border-zinc-300'
              }`}
            >
              {copied ? <CheckCircle2 className="w-3.5 h-3.5" /> : <LinkIcon className="w-3.5 h-3.5" />}
              {copied ? 'Tersalin!' : 'Salin URL'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6 bg-white border border-zinc-300 my-8 shadow-sm p-8">
        {/* File info + hash */}
        <div className="border-2 border-black bg-white p-6 text-black">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 border border-zinc-300 bg-zinc-50 flex items-center justify-center">
                <FileText className="w-5 h-5 text-black" />
              </div>
              <div>
                <h1 className="text-base font-bold uppercase tracking-wider mb-1">{result.filename}</h1>
                <p className="text-zinc-500 text-xs">
                  {result.summary.total_rows_processed} baris data · Parameter proteksi terpasang.
                </p>
              </div>
            </div>
            <div className="text-right hidden md:block font-mono">
              <p className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider mb-1">Hash Tautan</p>
              <code className="text-xs bg-zinc-100 border border-zinc-200 px-2.5 py-0.5">{hash}</code>
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono">
          {[
            { label: 'Baris Diproses', value: result.summary.total_rows_processed, color: 'text-black', bg: 'bg-white border-zinc-300' },
            { label: 'Kolom Dihapus', value: result.summary.columns_ignored, color: 'text-zinc-500', bg: 'bg-zinc-50 border-zinc-200' },
            { label: 'Laplace Noise', value: result.summary.columns_laplace, color: 'text-black font-bold', bg: 'bg-white border-zinc-300' },
            { label: 'Randomized', value: result.summary.columns_randomized, color: 'text-black', bg: 'bg-white border-zinc-300' },
          ].map((item) => (
            <div key={item.label} className={`border p-4 rounded-none ${item.bg}`}>
              <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
              <p className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider mt-1">{item.label}</p>
            </div>
          ))}
        </div>

        {/* Numeric Stats Table */}
        {result.numeric_stats.length > 0 && (
          <div className="bg-white border border-zinc-300 p-6">
            <div className="flex items-center gap-2 mb-5 font-mono">
              <BarChart2 className="w-4 h-4 text-black" />
              <h2 className="font-bold text-black text-xs uppercase tracking-wide">
                [Statistik Kolom Numerik — Asli vs Terlindung]
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-zinc-200 text-zinc-500">
                    {['Kolom', 'Mean Asli', 'Mean Terlindung', 'Std Asli', 'Std Terlindung', 'ε'].map(h => (
                      <th key={h} className="text-left py-2.5 px-3 text-[10px] font-bold uppercase tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {result.numeric_stats.map((stat) => (
                    <tr key={stat.column_name} className="hover:bg-zinc-50">
                      <td className="py-3 px-3 font-bold text-black">{stat.column_name}</td>
                      <td className="py-3 px-3 text-zinc-600">{stat.original_mean.toFixed(3)}</td>
                      <td className="py-3 px-3 text-black font-bold">{stat.protected_mean.toFixed(3)}</td>
                      <td className="py-3 px-3 text-zinc-500">{stat.original_std.toFixed(3)}</td>
                      <td className="py-3 px-3 text-zinc-500">{stat.protected_std.toFixed(3)}</td>
                      <td className="py-3 px-3">
                        <span className="text-[10px] bg-zinc-100 border border-zinc-300 px-2 py-0.5 font-bold">
                          ε={stat.epsilon_used}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Charts */}
        {result.charts.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 font-mono">
              <BarChart2 className="w-4 h-4 text-black" />
              <h2 className="font-bold text-black text-xs uppercase tracking-wide">
                [Visualisasi Kurva & Sebaran] ({result.charts.length} chart)
              </h2>
            </div>
            {result.charts.map((chart, idx) => (
              <PlotlyChart key={idx} chart={chart} />
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="bg-white/60 border border-slate-100 rounded-xl p-4 text-center backdrop-blur-sm">
          <p className="text-xs text-slate-400">
            Dihasilkan oleh{' '}
            <span className="font-bold text-indigo-600">BARASWARA Privacy Engine v0.3.0</span>
            {' '}· Differential Privacy (Laplace + Randomized Response)
          </p>
          <p className="text-[10px] text-slate-300 mt-1 font-mono">
            hash: {hash}
          </p>
        </div>
      </main>
    </div>
  );
}
