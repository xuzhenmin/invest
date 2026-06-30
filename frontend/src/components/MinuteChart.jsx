import React, { useRef, useEffect } from 'react';

const W = 148, H = 62;
const PAD = { t: 6, b: 14, l: 2, r: 2 };
const iW = W - PAD.l - PAD.r;
const iH = H - PAD.t - PAD.b;

// 一字板：合成全天平线数据（09:30 ~ 15:00，每分钟一个点，共241个点）
function buildFlatPoints(price) {
  const points = [];
  for (let i = 0; i <= 240; i++) {
    const totalMin = 9 * 60 + 30 + (i <= 120 ? i : i + 90); // 跳过11:30-13:00午休
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    points.push({ price, _flat: true, _label: `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}` });
  }
  return points;
}

export default function MinuteChart({ stock, points, prevClose, limitPrice, index }) {
  const pathRef = useRef(null);

  const isFlat = !points?.length && limitPrice != null;
  const displayPoints = isFlat ? buildFlatPoints(limitPrice) : (points || []);

  const prices = displayPoints.map(p => p.price);
  const hasData = prices.length >= 2;

  const refPrice = prevClose ?? (!isFlat && prices[0]) ?? limitPrice ?? 0;

  const allPrices = refPrice ? [...prices, refPrice] : prices;
  const minP = hasData ? Math.min(...allPrices) : 0;
  const maxP = hasData ? Math.max(...allPrices) : 1;
  const range = maxP - minP || refPrice * 0.001 || 0.01;

  const toX = (i) => PAD.l + (i / (prices.length - 1)) * iW;
  const toY = (price) => PAD.t + iH - ((price - minP) / range) * iH;

  const refY = refPrice ? toY(refPrice) : PAD.t + iH / 2;
  const lastPrice = prices[prices.length - 1] ?? refPrice;
  const isUp = lastPrice >= (refPrice || 0);
  const changePct = refPrice ? ((lastPrice - refPrice) / refPrice * 100).toFixed(2) : '0.00';
  const color = isUp ? '#ff5566' : '#2ed573';
  const gradId = `g${stock.stock_code.replace(/[.]/g, '')}`;

  const dLine = hasData
    ? displayPoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.price).toFixed(1)}`).join(' ')
    : '';
  const dFill = hasData
    ? `${dLine} L${(PAD.l + iW).toFixed(1)},${(PAD.t + iH).toFixed(1)} L${PAD.l},${(PAD.t + iH).toFixed(1)} Z`
    : '';

  useEffect(() => {
    const path = pathRef.current;
    if (!path || !hasData || isFlat) return;

    const len = path.getTotalLength();
    path.style.strokeDasharray = len;
    path.style.strokeDashoffset = len;

    const delay = 80 + index * 60;
    const duration = 8000;
    let raf;

    const timer = setTimeout(() => {
      const t0 = performance.now();
      const tick = (now) => {
        const t = Math.min((now - t0) / duration, 1);
        if (path) path.style.strokeDashoffset = len * (1 - t);
        if (t < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, delay);

    return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
  }, []);

  return (
    <div style={{ ...S.card, ...(isFlat ? S.cardFlat : {}) }}>
      <div style={S.header}>
        <span style={S.name}>{stock.stock_name}</span>
        {isFlat
          ? <span style={S.flatBadge}>一字板</span>
          : <span style={{ ...S.change, color }}>
              {isUp && hasData ? '+' : ''}{hasData ? `${changePct}%` : '--'}
            </span>
        }
      </div>
      <svg width={W} height={H} style={{ display: 'block', overflow: 'visible' }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={isFlat ? 0.1 : 0.22} />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {hasData && (
          <>
            <line
              x1={PAD.l} y1={refY} x2={PAD.l + iW} y2={refY}
              stroke="rgba(255,255,255,0.14)" strokeWidth="0.5" strokeDasharray="3,2"
            />
            <path d={dFill} fill={`url(#${gradId})`} />
            <path
              ref={pathRef}
              d={dLine}
              fill="none"
              stroke={color}
              strokeWidth={isFlat ? 1 : 1.4}
              strokeLinejoin="round"
              strokeLinecap="round"
              strokeDasharray={isFlat ? '4,3' : undefined}
            />
          </>
        )}
        {!hasData && (
          <text x={W / 2} y={H / 2 + 4} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.2)">
            暂无数据
          </text>
        )}
        <text x={PAD.l} y={H - 1} fontSize="7" fill="rgba(255,255,255,0.2)" textAnchor="start">09:30</text>
        <text x={PAD.l + iW} y={H - 1} fontSize="7" fill="rgba(255,255,255,0.2)" textAnchor="end">15:00</text>
      </svg>
    </div>
  );
}

const S = {
  card: {
    background: '#0e141d',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 6,
    padding: '6px 6px 2px',
    display: 'flex',
    flexDirection: 'column',
  },
  cardFlat: {
    border: '1px solid rgba(255,85,102,0.2)',
    background: 'rgba(255,85,102,0.03)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 3,
  },
  name: {
    fontSize: 10,
    color: '#a0b4c4',
    fontWeight: 600,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    maxWidth: 80,
  },
  change: {
    fontSize: 10,
    fontWeight: 700,
    fontVariantNumeric: 'tabular-nums',
  },
  flatBadge: {
    fontSize: 8,
    color: '#ff5566',
    border: '1px solid rgba(255,85,102,0.4)',
    borderRadius: 3,
    padding: '1px 4px',
    letterSpacing: '0.5px',
    background: 'rgba(255,85,102,0.08)',
  },
};
