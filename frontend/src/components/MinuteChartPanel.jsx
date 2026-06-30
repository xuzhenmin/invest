import React, { useState, useEffect, useCallback } from 'react';
import { Spin } from 'antd';
import { CloseOutlined, StockOutlined, DownloadOutlined } from '@ant-design/icons';
import MinuteChart from './MinuteChart';
import axios from 'axios';
import { generateSectorGif } from '../utils/generateGif';

if (typeof document !== 'undefined' && !document.getElementById('mcp-style')) {
  const style = document.createElement('style');
  style.id = 'mcp-style';
  style.textContent = `
    @keyframes slideInPanel {
      from { opacity: 0; transform: translateX(24px); }
      to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes slideUpDrawer {
      from { opacity: 0; transform: translateY(100%); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInOverlay {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 640);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

export default function MinuteChartPanel({ sector, date, onClose }) {
  const [stockData, setStockData] = useState({});
  const [loading, setLoading] = useState(false);
  const [animKey, setAnimKey] = useState(0);
  const [gifProgress, setGifProgress] = useState(null);
  const isMobile = useIsMobile();

  const fetchData = useCallback(async (stocks, date) => {
    setLoading(true);
    setStockData({});
    try {
      const codes = (stocks || []).map(s => s.stock_code);
      const res = await axios.post(`${API_BASE_URL}/api/stock/minute/batch`, { codes });
      const batch = res.data || {};
      const results = {};
      (stocks || []).forEach(s => {
        const all = Array.isArray(batch[s.stock_code]) ? batch[s.stock_code] : [];
        const pts = all.filter(p => p.time?.startsWith(date));
        const prevClose = pts.length && pts[0].last_close ? pts[0].last_close : null;
        results[s.stock_code] = { points: pts, prevClose };
      });
      setStockData(results);
    } catch {
      setStockData({});
    } finally {
      setAnimKey(k => k + 1);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!sector) return;
    fetchData(sector.stocks, date);
  }, [sector, date, fetchData]);

  const panelStyle = isMobile ? S.panelMobile : S.panelDesktop;

  return (
    <>
      {isMobile && <div style={S.overlay} onClick={onClose} />}
      <div style={panelStyle}>
      {isMobile
        ? <div style={S.dragHandle} />
        : <div style={S.topBeam} />
      }

      <div style={S.head}>
        <div style={S.headIcon}><StockOutlined /></div>
        <div style={S.headInfo}>
          <span style={S.headTitle}>{sector?.industry ?? '—'}</span>
          <span style={S.headSub}>
            {sector ? `${(sector.stocks || []).length} 只涨停 · 分时走势` : '点击板块查看分时走势'}
          </span>
        </div>
        <span style={S.closeBtn} onClick={onClose}><CloseOutlined /></span>
      </div>

      <div style={S.body}>
        {!sector && (
          <div style={S.empty}>
            <StockOutlined style={{ fontSize: 28, color: 'rgba(255,255,255,0.08)', marginBottom: 10 }} />
            <span style={S.emptyText}>点击左侧板块<br />查看个股分时走势</span>
          </div>
        )}

        {sector && loading && (
          <div style={S.loadingBox}>
            <Spin size="small" />
            <span style={S.loadingText}>加载分时数据...</span>
          </div>
        )}

        {sector && !loading && (
          <div style={S.grid}>
            {(sector.stocks || []).map((s, i) => (
              <MinuteChart
                key={`${s.stock_code}_${animKey}`}
                stock={s}
                points={stockData[s.stock_code]?.points || []}
                prevClose={stockData[s.stock_code]?.prevClose ?? null}
                index={i}
              />
            ))}
          </div>
        )}
      </div>

      {sector && !loading && (
        <div style={S.foot}>
          <span style={S.footNote}>基准线为昨收 · {date}</span>
          <span
            style={{ ...S.saveBtn, opacity: gifProgress !== null ? 0.5 : 1, cursor: gifProgress !== null ? 'default' : 'pointer' }}
            onClick={async () => {
              if (gifProgress !== null) return;
              setGifProgress(0);
              try {
                await generateSectorGif(sector, stockData, date, setGifProgress);
              } finally {
                setTimeout(() => setGifProgress(null), 600);
              }
            }}
          >
            {gifProgress !== null
              ? <><Spin size="small" style={{ marginRight: 4 }} />{gifProgress}%</>
              : <><DownloadOutlined style={{ marginRight: 3 }} />保存 GIF</>
            }
          </span>
        </div>
      )}
    </div>
    </>
  );
}

const panelBase = {
  background: 'linear-gradient(160deg, #080f1c 0%, #0b1520 100%)',
  border: '1px solid rgba(50,110,190,0.2)',
  overflow: 'hidden',
  boxShadow: '0 16px 48px rgba(0,0,0,0.8)',
  display: 'flex',
  flexDirection: 'column',
  zIndex: 200,
};

const S = {
  panelDesktop: {
    ...panelBase,
    position: 'fixed',
    left: 'calc(50% + 274px)',
    top: '18vh',
    width: 332,
    maxHeight: '68vh',
    borderRadius: 12,
    animation: 'slideInPanel 0.22s ease-out',
  },
  panelMobile: {
    ...panelBase,
    position: 'fixed',
    left: 0,
    right: 0,
    bottom: 0,
    width: '100%',
    maxHeight: '72vh',
    borderRadius: '14px 14px 0 0',
    borderBottom: 'none',
    animation: 'slideUpDrawer 0.28s ease-out',
  },
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.55)',
    zIndex: 199,
    animation: 'fadeInOverlay 0.2s ease-out',
  },
  dragHandle: {
    width: 36, height: 4,
    background: 'rgba(255,255,255,0.15)',
    borderRadius: 2,
    margin: '10px auto 6px',
    flexShrink: 0,
  },
  topBeam: {
    height: 1,
    background: 'linear-gradient(90deg, transparent, rgba(80,150,255,0.4), transparent)',
  },
  head: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '12px 14px',
    borderBottom: '1px solid rgba(255,255,255,0.05)',
    background: 'rgba(255,255,255,0.015)',
  },
  headIcon: {
    width: 28, height: 28,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'rgba(60,120,220,0.15)',
    border: '1px solid rgba(60,120,220,0.25)',
    borderRadius: 6, color: '#6aa8d0', fontSize: 13, flexShrink: 0,
  },
  headInfo: { flex: 1, display: 'flex', flexDirection: 'column', gap: 2 },
  headTitle: { fontSize: 13, fontWeight: 700, color: '#c0d4e8', letterSpacing: '0.5px' },
  headSub: { fontSize: 10, color: '#3a5570', letterSpacing: '0.3px' },
  closeBtn: {
    color: '#3a5570', cursor: 'pointer', fontSize: 12,
    padding: 4, borderRadius: 4, transition: 'color 0.2s',
  },
  body: { flex: 1, padding: '10px 10px 6px', overflowY: 'auto' },
  empty: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: '40px 0',
  },
  emptyText: {
    fontSize: 11, color: 'rgba(255,255,255,0.15)',
    textAlign: 'center', lineHeight: 1.8, letterSpacing: '0.5px',
  },
  loadingBox: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', gap: 10, padding: '40px 0',
  },
  loadingText: { fontSize: 11, color: 'rgba(255,255,255,0.2)' },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 },
  foot: {
    padding: '7px 12px 10px', fontSize: 9,
    borderTop: '1px solid rgba(255,255,255,0.04)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  footNote: { color: 'rgba(255,255,255,0.1)', letterSpacing: '0.5px' },
  saveBtn: {
    display: 'flex', alignItems: 'center', fontSize: 10, color: '#5a9abf',
    border: '1px solid rgba(60,120,180,0.25)', borderRadius: 4,
    padding: '3px 8px', background: 'rgba(30,70,120,0.15)',
    cursor: 'pointer', userSelect: 'none', transition: 'color 0.2s',
    minWidth: 68, justifyContent: 'center',
  },
};
