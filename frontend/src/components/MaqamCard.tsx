import React, { useEffect, useRef } from 'react';

export interface MaqamInfo {
  maqam: string;
  confidence: number;
  tonic_note: string;
  tonic_hz?: number;
  tonic_cents?: number;
  peak_cents?: number[];
  essentia_used?: boolean;
  method?: string;
  db_info?: {
    name_arabic: string;
    name_latin: string;
    root_note: string;
    scale_cents: number[];
    mood_english?: string;
    mood_arabic?: string;
    famous_songs?: string[];
    jins_structure?: string;
    has_quarter_tones: boolean;
  } | null;
  // From note-analysis path
  maqam_confidence?: number;
  quarter_tone_count?: number;
  is_eastern?: boolean;
}

interface MaqamCardProps {
  info: MaqamInfo;
  className?: string;
}

/** Confidence colour: red→yellow→green */
function confidenceColor(c: number): string {
  if (c >= 0.7) return '#22c55e';   // green-500
  if (c >= 0.45) return '#eab308';  // yellow-500
  return '#ef4444';                  // red-500
}

/** Draw the 24-TET cents ruler onto a canvas */
function drawScaleRuler(
  canvas: HTMLCanvasElement,
  scaleCents: number[],
  tonicCents?: number,
  peakCents?: number[],
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  // Background
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, W, H);

  const toPercent = (cents: number) => (cents / 1200) * W;

  // Quarter-tone grid lines (every 50 cents = 1 quarter tone)
  for (let qt = 0; qt <= 24; qt++) {
    const x = toPercent(qt * 50);
    ctx.strokeStyle = qt % 2 === 0 ? '#334155' : '#1e293b';
    ctx.lineWidth = qt % 2 === 0 ? 1 : 0.5;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }

  // Pitch histogram peaks (faint glow)
  if (peakCents && peakCents.length > 0) {
    peakCents.forEach((c) => {
      const x = toPercent(c % 1200);
      const grad = ctx.createLinearGradient(x - 6, 0, x + 6, 0);
      grad.addColorStop(0, 'rgba(251,191,36,0)');
      grad.addColorStop(0.5, 'rgba(251,191,36,0.25)');
      grad.addColorStop(1, 'rgba(251,191,36,0)');
      ctx.fillStyle = grad;
      ctx.fillRect(x - 6, 0, 12, H);
    });
  }

  // Scale degree bars
  scaleCents.forEach((cents, i) => {
    if (cents === 0 || cents === 1200) return; // tonic drawn separately
    const x = toPercent(cents);
    const isQuarterTone = cents % 100 !== 0;

    ctx.fillStyle = isQuarterTone ? '#a78bfa' : '#38bdf8'; // purple=QT, blue=semitone
    ctx.fillRect(x - 2, H * 0.15, 4, H * 0.7);

    // Note index label
    ctx.fillStyle = '#94a3b8';
    ctx.font = `${Math.max(8, H * 0.22)}px monospace`;
    ctx.textAlign = 'center';
    ctx.fillText(String(i + 1), x, H * 0.12);
  });

  // Tonic marker (always at position derived from scale root)
  const tonicX = tonicCents !== undefined ? toPercent(tonicCents % 1200) : toPercent(0);
  ctx.fillStyle = '#f97316'; // orange
  ctx.fillRect(tonicX - 3, H * 0.1, 6, H * 0.8);

  // Tonic label
  ctx.fillStyle = '#f97316';
  ctx.font = `bold ${Math.max(9, H * 0.24)}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.fillText('T', tonicX, H - 2);

  // Octave labels
  ['C', 'D', 'E', 'F', 'G', 'A', 'B'].forEach((note, i) => {
    const semitones = [0, 2, 4, 5, 7, 9, 11];
    const x = toPercent(semitones[i] * 100);
    ctx.fillStyle = '#475569';
    ctx.font = `${Math.max(8, H * 0.2)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(note, x, H - 2);
  });
}

const MaqamCard: React.FC<MaqamCardProps> = ({ info, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const confidence = info.confidence ?? info.maqam_confidence ?? 0;
  const confPct = Math.round(confidence * 100);
  const confColor = confidenceColor(confidence);

  const db = info.db_info;
  const scaleCents: number[] = db?.scale_cents ?? [];
  const maqamName = info.maqam !== 'Unknown' ? info.maqam : (db?.name_latin ?? '—');
  const arabicName = db?.name_arabic ?? '';
  const tonicNote = info.tonic_note || db?.root_note || '?';
  const mood = db?.mood_english;
  const famousSongs = db?.famous_songs ?? [];
  const jins = db?.jins_structure;
  const hasQT = db?.has_quarter_tones ?? (info.quarter_tone_count ? info.quarter_tone_count > 0 : false);

  // Draw ruler whenever scale changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || scaleCents.length === 0) return;
    drawScaleRuler(canvas, scaleCents, info.tonic_cents, info.peak_cents);
  }, [scaleCents, info.tonic_cents, info.peak_cents]);

  return (
    <div
      id="maqam-card"
      className={`rounded-2xl border border-amber-500/30 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden shadow-xl ${className}`}
    >
      {/* ── Header ── */}
      <div className="px-6 pt-5 pb-3 border-b border-slate-700/60">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-baseline gap-3">
              <h3 className="text-2xl font-bold tracking-tight text-amber-400">
                {maqamName}
              </h3>
              {arabicName && (
                <span
                  className="text-xl text-amber-300/80"
                  dir="rtl"
                  style={{ fontFamily: 'serif' }}
                >
                  {arabicName}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-400 mt-0.5">
              Tonic: <span className="text-sky-300 font-semibold">{tonicNote}</span>
              {info.tonic_hz && info.tonic_hz > 0 && (
                <span className="ml-2 text-slate-500">
                  ({info.tonic_hz.toFixed(1)} Hz)
                </span>
              )}
              {hasQT && (
                <span className="ml-3 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50">
                  ¼-tone
                </span>
              )}
            </p>
          </div>

          {/* Confidence gauge */}
          <div className="flex flex-col items-center min-w-[56px]">
            <svg width="52" height="52" viewBox="0 0 52 52" className="-rotate-90">
              <circle cx="26" cy="26" r="20" fill="none" stroke="#1e293b" strokeWidth="6" />
              <circle
                cx="26" cy="26" r="20" fill="none"
                stroke={confColor} strokeWidth="6"
                strokeDasharray={`${(confidence * 125.6).toFixed(1)} 125.6`}
                strokeLinecap="round"
                style={{ transition: 'stroke-dasharray 0.8s ease' }}
              />
            </svg>
            <span className="text-xs font-bold -mt-1" style={{ color: confColor }}>
              {confPct}%
            </span>
          </div>
        </div>
      </div>

      {/* ── Scale Ruler ── */}
      {scaleCents.length > 0 && (
        <div className="px-6 py-3">
          <p className="text-xs text-slate-500 mb-1 uppercase tracking-widest">
            Scale ruler · 1200¢ octave · <span className="text-sky-400">━</span> semitone
            &nbsp;·&nbsp; <span className="text-violet-400">━</span> quarter-tone
            &nbsp;·&nbsp; <span className="text-orange-400">━</span> tonic
          </p>
          <canvas
            ref={canvasRef}
            width={560}
            height={40}
            className="w-full rounded-md"
            style={{ imageRendering: 'crisp-edges' }}
          />
          {/* Cent values */}
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
            {scaleCents.map((c, i) => (
              <span key={i} className="text-[10px] text-slate-500 font-mono">
                {i === 0 ? 'T' : i}:{c}¢
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Metadata grid ── */}
      <div className="px-6 pb-5 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3 mt-1">
        {mood && (
          <div className="sm:col-span-2">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-0.5">Mood</p>
            <p className="text-sm text-slate-200 italic">"{mood}"</p>
          </div>
        )}

        {jins && (
          <div>
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-0.5">Jins Structure</p>
            <p className="text-sm text-slate-300">{jins}</p>
          </div>
        )}

        {info.essentia_used !== undefined && (
          <div>
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-0.5">Detection Engine</p>
            <p className="text-sm text-slate-300">
              {info.essentia_used ? '🔬 Essentia PitchMelodia' : '📊 librosa pyin'}
            </p>
          </div>
        )}

        {info.quarter_tone_count !== undefined && info.quarter_tone_count > 0 && (
          <div>
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-0.5">Quarter Tones</p>
            <p className="text-sm text-violet-300 font-semibold">{info.quarter_tone_count} notes</p>
          </div>
        )}

        {famousSongs.length > 0 && (
          <div className="sm:col-span-2">
            <p className="text-xs uppercase tracking-widest text-slate-500 mb-1">Famous songs</p>
            <div className="flex flex-wrap gap-2">
              {famousSongs.map((song, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-900/40 text-amber-300 border border-amber-700/40"
                >
                  🎶 {song}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MaqamCard;
