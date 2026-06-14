'use client';

import React, { useState, useCallback, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Settings,
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Play,
  Link,
  BarChart2,
  Eye,
  EyeOff,
  Info,
  Download,
} from 'lucide-react';

// ── Type Definitions ──────────────────────────────────────────────────────────

interface FileMetadata {
  filename: string;
  total_rows: number;
  total_columns: number;
}

interface ColumnRecommendation {
  column_name: string;
  semantic_type: string;
  missing_values: number;
  recommended_action: 'IGNORE' | 'LAPLACE' | 'RANDOMIZED_RESPONSE' | 'REVIEW';
}

interface APIResponse {
  status: 'success';
  file_metadata: FileMetadata;
  schema_recommendation: ColumnRecommendation[];
}

interface ColumnConfig {
  column_name: string;
  semantic_type: string;
  action: 'IGNORE' | 'LAPLACE' | 'RANDOMIZED_RESPONSE' | 'REVIEW';
  epsilon: number;
}

interface ConfirmResponse {
  status: string;
  config_id: string;
  filename: string;
  total_columns: number;
  message: string;
}

interface ExecuteResponse {
  status: string;
  secure_hash: string;
  filename: string;
  viewer_url: string;
  download_url?: string;
  statistics?: Record<string, any>;
}

type AppState =
  | 'idle'
  | 'analyzing'
  | 'reviewed'
  | 'confirming'
  | 'confirmed'
  | 'executing'
  | 'done'
  | 'error';

// ── Step Indicator ────────────────────────────────────────────────────────────

const STEPS = ['Unggah', 'Tinjau', 'Konfirmasi', 'Eksekusi', 'Selesai'];

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-0 w-full">
      {STEPS.map((label, idx) => {
        const done = idx < current;
        const active = idx === current;
        return (
          <React.Fragment key={idx}>
            <div className="flex flex-col items-center flex-1 min-w-0">
              <div
                className={`w-7 h-7 border-2 flex items-center justify-center text-xs font-bold font-mono
                  ${done ? 'border-black bg-black text-white' : active ? 'border-black bg-white text-black' : 'border-zinc-300 bg-white text-zinc-400'}`}
              >
                {done ? '✓' : idx + 1}
              </div>
              <span
                className={`text-[9px] uppercase tracking-widest mt-1 font-mono truncate w-full text-center
                  ${done || active ? 'text-black font-bold' : 'text-zinc-400'}`}
              >
                {label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`h-px flex-1 mx-1 mb-4 ${done ? 'bg-black' : 'bg-zinc-200'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function BaraswaraDashboard() {
  const [appState, setAppState] = useState<AppState>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<APIResponse | null>(null);
  const [columnConfigs, setColumnConfigs] = useState<ColumnConfig[]>([]);
  const [confirmResponse, setConfirmResponse] = useState<ConfirmResponse | null>(null);
  const [executeResponse, setExecuteResponse] = useState<ExecuteResponse | null>(null);
  const [epsilonVisible, setEpsilonVisible] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentStep = {
    idle: 0,
    analyzing: 0,
    reviewed: 1,
    confirming: 2,
    confirmed: 2,
    executing: 3,
    done: 4,
    error: 0,
  }[appState];

  // ── Drag & Drop ─────────────────────────────────────────────────────────────
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.name.endsWith('.csv')) {
      processFile(dropped);
    } else {
      setErrorMsg('Hanya file .csv yang diterima.');
    }
  }, []);

  // ── Upload & Analisis ───────────────────────────────────────────────────────
  const processFile = async (selectedFile: File) => {
    setFile(selectedFile);
    setAppState('analyzing');
    setErrorMsg(null);
    setAnalysisResult(null);
    setConfirmResponse(null);
    setExecuteResponse(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch('http://localhost:8000/v1/privacy-engine/pre-check', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData?.detail?.message || `Analisis gagal (${response.status})`);
      }

      const data: APIResponse = await response.json();
      setAnalysisResult(data);

      setColumnConfigs(
        data.schema_recommendation.map((col) => ({
          column_name: col.column_name,
          semantic_type: col.semantic_type,
          action: col.recommended_action,
          epsilon: 1.0,
        }))
      );
      setAppState('reviewed');
    } catch (err: any) {
      setErrorMsg(err.message || 'Koneksi ke backend gagal. Pastikan server berjalan di port 8000.');
      setAppState('idle');
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) processFile(e.target.files[0]);
  };

  // ── Update Config Per Kolom ──────────────────────────────────────────────────
  const updateColumnAction = (colName: string, action: ColumnConfig['action']) => {
    setColumnConfigs((prev) =>
      prev.map((c) => (c.column_name === colName ? { ...c, action } : c))
    );
  };

  const updateColumnEpsilon = (colName: string, epsilon: number) => {
    setColumnConfigs((prev) =>
      prev.map((c) => (c.column_name === colName ? { ...c, epsilon } : c))
    );
  };

  // ── Konfirmasi HITL ──────────────────────────────────────────────────────────
  const handleConfirm = async () => {
    if (!analysisResult || !file) return;
    setAppState('confirming');
    setErrorMsg(null);

    const payload = {
      filename: file.name,
      total_rows: analysisResult.file_metadata.total_rows,
      columns: columnConfigs,
    };

    try {
      const response = await fetch('http://localhost:8000/v1/privacy-engine/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData?.detail?.message || `Konfirmasi gagal (${response.status})`);
      }

      const data: ConfirmResponse = await response.json();
      setConfirmResponse(data);
      setAppState('confirmed');
    } catch (err: any) {
      setErrorMsg(err.message || 'Gagal mengirim konfigurasi ke server.');
      setAppState('reviewed');
    }
  };

  // ── Eksekusi Pipeline ────────────────────────────────────────────────────────
  const handleExecute = async () => {
    if (!confirmResponse || !file) return;
    setAppState('executing');
    setErrorMsg(null);

    const formData = new FormData();
    formData.append('config_id', confirmResponse.config_id);
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/v1/pipeline/execute', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData?.detail?.message || `Eksekusi gagal (${response.status})`);
      }

      const data: ExecuteResponse = await response.json();
      setExecuteResponse(data);
      setAppState('done');
    } catch (err: any) {
      setErrorMsg(err.message || 'Pipeline gagal dieksekusi.');
      setAppState('confirmed');
    }
  };

  // ── Reset ────────────────────────────────────────────────────────────────────
  const handleReset = () => {
    setFile(null);
    setAppState('idle');
    setErrorMsg(null);
    setAnalysisResult(null);
    setColumnConfigs([]);
    setConfirmResponse(null);
    setExecuteResponse(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="min-h-screen bg-zinc-50 p-6 md:p-10 font-mono text-zinc-900 selection:bg-black selection:text-white">
      <div className="max-w-4xl mx-auto space-y-8 bg-white border border-zinc-300 p-8 shadow-sm">

        {/* ── HEADER ─────────────────────────────────────────────────────── */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-zinc-200">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold tracking-tight text-black">
                [BARASWARA]
              </h1>
              <span className="text-[10px] bg-zinc-100 text-zinc-800 px-2 py-0.5 border border-zinc-300 font-bold uppercase">
                PROTOTYPE v0.3.0
              </span>
            </div>
            <p className="text-zinc-500 text-xs mt-1">
              Modul Anonimisasi &amp; Proteksi Berkas Data (CSV)
            </p>
          </div>
          {file && (
            <button
              onClick={handleReset}
              className="text-xs font-bold text-zinc-500 border border-zinc-300 bg-white hover:bg-zinc-100 px-3 py-1.5 transition-colors uppercase tracking-wide cursor-pointer"
            >
              [Mulai Ulang]
            </button>
          )}
        </header>

        {/* ── STEP INDICATOR ─────────────────────────────────────────────── */}
        <StepIndicator current={currentStep} />

        {/* ── ERROR ALERT ────────────────────────────────────────────────── */}
        {errorMsg && (
          <div className="bg-white border-2 border-black text-black p-4 flex gap-3 text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 text-black mt-0.5" />
            <div>
              <p className="font-bold mb-0.5">KESALAHAN SISTEM</p>
              <p className="font-mono">{errorMsg}</p>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            STATE: IDLE — Upload Dropzone
            ═══════════════════════════════════════════════════════════════════ */}
        {(appState === 'idle' || appState === 'error') && (
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed p-14 text-center transition-all duration-200 cursor-pointer rounded-none
              ${isDragging
                ? 'border-black bg-zinc-100'
                : 'border-zinc-300 bg-white hover:border-black hover:bg-zinc-50'
              }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="w-12 h-12 border border-black flex items-center justify-center mx-auto mb-5">
              <UploadCloud className="h-6 w-6 text-black" />
            </div>
            <h3 className="text-sm font-bold text-black uppercase tracking-wider mb-2">
              [Unggah Berkas CSV]
            </h3>
            <p className="text-xs text-zinc-500 mb-6 max-w-sm mx-auto leading-relaxed">
              Seret &amp; lepas berkas CSV ke sini, atau klik untuk memilih. Sistem akan memetakan kolom data secara terstruktur.
            </p>
            <div className="inline-flex items-center gap-2 bg-black hover:bg-zinc-900 text-white px-5 py-2 border border-black font-bold text-xs uppercase tracking-wider transition-colors cursor-pointer">
              Pilih Berkas CSV
            </div>
            <p className="text-[10px] text-zinc-400 mt-4 font-mono">BATAS MAKSIMAL: 10 MB · EKSTENSI: .csv</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            STATE: ANALYZING — Loading
            ═══════════════════════════════════════════════════════════════════ */}
        {appState === 'analyzing' && (
          <div className="bg-white p-12 text-center border border-zinc-200">
            <div className="w-12 h-12 border border-black flex items-center justify-center mx-auto mb-5">
              <RefreshCw className="h-5 w-5 text-black animate-spin" />
            </div>
            <h3 className="font-bold text-black text-sm uppercase tracking-wider mb-2">Memindai Struktur Berkas...</h3>
            <p className="text-xs text-zinc-500">Mendeteksi jenis kolom &amp; metrik statistik baris</p>
            {file && (
              <div className="mt-4 inline-flex items-center gap-2 bg-zinc-50 border border-zinc-200 px-3 py-1.5 text-[10px] text-zinc-600 font-mono">
                <FileText className="w-3 h-3" /> {file.name}
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            STATE: REVIEWED / CONFIRMING — HITL Editor
            ═══════════════════════════════════════════════════════════════════ */}
        {(appState === 'reviewed' || appState === 'confirming') && analysisResult && (
          <div className="space-y-6">
            {/* File Info Bar */}
            <div className="flex items-center justify-between bg-zinc-50 border border-zinc-200 px-4 py-3">
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4 text-zinc-500" />
                <span className="text-xs font-bold text-black">{analysisResult.file_metadata.filename}</span>
                <span className="text-[10px] text-zinc-500 font-mono">
                  {analysisResult.file_metadata.total_rows} baris · {analysisResult.file_metadata.total_columns} kolom
                </span>
              </div>
              <button
                onClick={() => setEpsilonVisible((v) => !v)}
                className="flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-black border border-zinc-200 px-2 py-1 transition-colors"
              >
                {epsilonVisible ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                EPSILON
              </button>
            </div>

            {/* Info HITL */}
            <div className="flex items-start gap-2 text-[10px] text-zinc-500 border border-zinc-200 p-3 bg-zinc-50">
              <Info className="w-3 h-3 shrink-0 mt-0.5" />
              <span>
                Tinjau dan sesuaikan rekomendasi mekanisme privasi per kolom. Nilai epsilon (ε) lebih kecil = privasi lebih kuat = akurasi lebih rendah.
              </span>
            </div>

            {/* Column Config Table */}
            <div className="border border-zinc-200">
              <div className="grid grid-cols-12 bg-zinc-900 text-white text-[10px] font-bold uppercase tracking-widest px-4 py-2">
                <span className="col-span-3">Kolom</span>
                <span className="col-span-3">Tipe Semantik</span>
                <span className="col-span-3">Mekanisme</span>
                {epsilonVisible && <span className="col-span-3">Epsilon (ε)</span>}
              </div>
              {columnConfigs.map((col, idx) => (
                <div
                  key={col.column_name}
                  className={`grid grid-cols-12 items-center px-4 py-3 text-xs border-b border-zinc-100 last:border-0
                    ${idx % 2 === 0 ? 'bg-white' : 'bg-zinc-50'}`}
                >
                  <div className="col-span-3 font-bold font-mono text-black truncate pr-2">
                    {col.column_name}
                  </div>
                  <div className="col-span-3 text-zinc-500 text-[10px] pr-2 truncate">
                    {col.semantic_type}
                  </div>
                  <div className="col-span-3 pr-2">
                    <select
                      value={col.action}
                      onChange={(e) => updateColumnAction(col.column_name, e.target.value as ColumnConfig['action'])}
                      disabled={appState === 'confirming'}
                      className="w-full text-[10px] font-bold font-mono border border-zinc-300 bg-white px-2 py-1 uppercase focus:outline-none focus:border-black disabled:opacity-50"
                    >
                      <option value="IGNORE">IGNORE</option>
                      <option value="LAPLACE">LAPLACE</option>
                      <option value="RANDOMIZED_RESPONSE">RAND.RESP</option>
                      <option value="REVIEW">REVIEW</option>
                    </select>
                  </div>
                  {epsilonVisible && (
                    <div className="col-span-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0.1}
                          max={5}
                          step={0.1}
                          value={col.epsilon}
                          onChange={(e) => updateColumnEpsilon(col.column_name, parseFloat(e.target.value))}
                          disabled={col.action === 'IGNORE' || appState === 'confirming'}
                          className="flex-1 accent-black disabled:opacity-30"
                        />
                        <span className="text-[10px] font-mono w-6 text-right">{col.epsilon.toFixed(1)}</span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Confirm Button */}
            <button
              onClick={handleConfirm}
              disabled={appState === 'confirming'}
              className="w-full flex items-center justify-center gap-2 bg-black text-white py-3 text-xs font-bold uppercase tracking-widest hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {appState === 'confirming' ? (
                <><RefreshCw className="w-4 h-4 animate-spin" /> Menyimpan Konfigurasi...</>
              ) : (
                <><Settings className="w-4 h-4" /> Konfirmasi &amp; Simpan Konfigurasi</>
              )}
            </button>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            STATE: CONFIRMED — Preview & Execute
            ═══════════════════════════════════════════════════════════════════ */}
        {(appState === 'confirmed' || appState === 'executing') && confirmResponse && (
          <div className="space-y-6">
            {/* Confirmed banner */}
            <div className="flex items-center gap-3 bg-zinc-50 border border-zinc-200 px-4 py-3">
              <CheckCircle2 className="w-4 h-4 text-black shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-black">KONFIGURASI TERSIMPAN</p>
                <p className="text-[10px] text-zinc-500 font-mono truncate">
                  config_id: {confirmResponse.config_id}
                </p>
              </div>
            </div>

            {/* Summary config */}
            <div className="border border-zinc-200">
              <div className="bg-zinc-900 text-white text-[10px] font-bold uppercase tracking-widest px-4 py-2">
                Ringkasan Konfigurasi
              </div>
              <div className="divide-y divide-zinc-100">
                {columnConfigs.map((col) => (
                  <div key={col.column_name} className="flex items-center justify-between px-4 py-2 text-[10px] font-mono">
                    <span className="text-zinc-700 font-bold">{col.column_name}</span>
                    <span className={`font-bold uppercase ${col.action === 'IGNORE' ? 'text-zinc-400' : 'text-black'}`}>
                      {col.action}{col.action !== 'IGNORE' ? ` · ε=${col.epsilon.toFixed(1)}` : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Execute Button */}
            <button
              onClick={handleExecute}
              disabled={appState === 'executing'}
              className="w-full flex items-center justify-center gap-2 bg-black text-white py-3.5 text-xs font-bold uppercase tracking-widest hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {appState === 'executing' ? (
                <><RefreshCw className="w-4 h-4 animate-spin" /> Mengeksekusi Pipeline...</>
              ) : (
                <><Play className="w-4 h-4" /> Eksekusi Pipeline Differential Privacy</>
              )}
            </button>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            STATE: DONE — Results & Share
            ═══════════════════════════════════════════════════════════════════ */}
        {appState === 'done' && executeResponse && (
          <div className="space-y-6">
            {/* Success banner */}
            <div className="flex items-center gap-3 bg-black text-white px-4 py-4">
              <ShieldCheck className="w-5 h-5 shrink-0" />
              <div>
                <p className="text-xs font-bold uppercase tracking-widest">PIPELINE SELESAI</p>
                <p className="text-[10px] text-zinc-400 mt-0.5">
                  Data berhasil diproteksi dengan mekanisme Differential Privacy
                </p>
              </div>
            </div>

            {/* Viewer URL */}
            <div className="border border-zinc-200 p-4 space-y-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                Tautan Hasil (Secure URL)
              </p>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-zinc-50 border border-zinc-200 px-3 py-2 text-[10px] font-mono text-zinc-700 truncate">
                  {executeResponse.viewer_url}
                </div>
                <button
                  onClick={() => navigator.clipboard.writeText(executeResponse.viewer_url)}
                  className="flex items-center gap-1.5 bg-black text-white px-3 py-2 text-[10px] font-bold uppercase hover:bg-zinc-800 transition-colors shrink-0"
                >
                  <Link className="w-3 h-3" /> Salin
                </button>
              </div>
              <a
                href={executeResponse.viewer_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-black border border-zinc-200 px-3 py-1.5 transition-colors"
              >
                <BarChart2 className="w-3 h-3" /> Buka Visualisasi Grafik
              </a>
            </div>

            {/* Download */}
            {executeResponse.download_url && (
              <a
                href={`http://localhost:8000${executeResponse.download_url}`}
                download
                className="flex items-center justify-center gap-2 w-full border-2 border-black text-black py-3 text-xs font-bold uppercase tracking-widest hover:bg-black hover:text-white transition-colors"
              >
                <Download className="w-4 h-4" /> Unduh Berkas CSV Terproteksi
              </a>
            )}

            {/* Secure hash info */}
            <div className="text-[10px] text-zinc-400 font-mono text-center">
              secure_hash: {executeResponse.secure_hash}
            </div>

            {/* Mulai ulang */}
            <button
              onClick={handleReset}
              className="w-full flex items-center justify-center gap-2 border border-zinc-300 text-zinc-600 py-2.5 text-xs font-bold uppercase tracking-widest hover:bg-zinc-50 transition-colors"
            >
              <ChevronRight className="w-4 h-4" /> Proses Berkas Lain
            </button>
          </div>
        )}

      </div>
    </div>
  );
}