import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Spin, message } from 'antd';
import { CameraOutlined, ReloadOutlined } from '@ant-design/icons';
import { toPng } from 'html-to-image';
import axios from 'axios';
import MinuteChartPanel from '../components/MinuteChartPanel';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

export default function LimitUpBoard({ embedded = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedSector, setSelectedSector] = useState(null);
  const [trend, setTrend] = useState([]);

  const handleSectorClick = useCallback((sector) => {
    setSelectedSector(prev => {
      const closing = prev?.industry === sector.industry;
      if (!closing) window.scrollTo({ top: 0, behavior: 'smooth' });
      return closing ? null : sector;
    });
  }, []);
  const ref1 = useRef(null);
  const ref2 = useRef(null);
  const ref3 = useRef(null);
  const industryTrend = useMemo(() => (data?.industry_trend || []).filter(t => t.today_count > 0).slice(0, 8), [data]);
  const industryExitTrend = useMemo(() => (data?.industry_exit_trend || []).slice(0, 5), [data]);

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/limit-up/today`);
      if (res.data?.success) setData(res.data.data);
    } catch (e) { /* ignore */ }
    try {
      const trendRes = await axios.get(`${API_BASE_URL}/api/limit-up/trend?days=15`);
      if (trendRes.data?.success) setTrend(trendRes.data.data || []);
    } catch (e) { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCollect = async () => {
    message.loading({ content: '正在采集...', key: 'c' });
    try {
      await axios.post(`${API_BASE_URL}/api/limit-up/collect`);
      await fetchData();
      message.success({ content: '采集完成', key: 'c' });
    } catch (e) { message.error({ content: '采集失败', key: 'c' }); }
  };

  const handleScreenshot = async () => {
    const date = data?.date || 'today';
    const opts = { backgroundColor: '#0a0e14', pixelRatio: 2 };
    const parts = [
      { ref: ref1, name: '①复盘总结' },
      { ref: ref2, name: '②板块热度' },
      { ref: ref3, name: '③连板梯队' },
    ];
    try {
      for (const { ref, name } of parts) {
        if (!ref.current) continue;
        const url = await toPng(ref.current, opts);
        const a = document.createElement('a');
        a.download = `涨停复盘_${date}_${name}.png`;
        a.href = url;
        a.click();
        await new Promise(r => setTimeout(r, 400));
      }
      message.success('已保存 3 张图片');
    } catch (e) { message.error('保存失败'); }
  };

  if (loading) return <div style={S.loadingPage}><Spin /></div>;
  if (!data || !data.by_consecutive) return (
    <div style={S.loadingPage}>
      <span style={{ color: '#6e7681', marginBottom: 12 }}>暂无数据</span>
      <button onClick={handleCollect} style={S.primaryBtn}>采集今日涨停</button>
    </div>
  );

  const levels = Object.keys(data.by_consecutive).map(Number).sort((a, b) => b - a);

  return (
    <div style={embedded ? S.pageEmbedded : S.page}>
      <div style={S.leftColFull}>
      {/* 操作栏 */}
      <div style={embedded ? S.toolbarEmbedded : S.toolbar}>
        <span onClick={handleCollect} style={S.toolBtn}><ReloadOutlined /> 刷新数据</span>
        <span onClick={handleScreenshot} style={S.toolBtn}><CameraOutlined /> 保存图片</span>
      </div>

      {/* 第一张：复盘总结（方形科技风） */}
      <div ref={ref1} style={S.summaryCard}>
        {/* 网格背景 */}
        <div style={S.summaryBgGrid} />
        {/* 中心辉光 */}
        <div style={S.summaryBgGlow} />
        {/* 顶部光线 */}
        <div style={S.summaryBgBeam} />
        {/* 四角装饰 */}
        {[['top','left'],['top','right'],['bottom','left'],['bottom','right']].map(([v,h]) => (
          <div key={v+h} style={{ position:'absolute', [v]: 16, [h]: 16, width: 18, height: 18,
            borderTop: v==='top' ? '1.5px solid rgba(80,160,240,0.5)' : 'none',
            borderBottom: v==='bottom' ? '1.5px solid rgba(80,160,240,0.5)' : 'none',
            borderLeft: h==='left' ? '1.5px solid rgba(80,160,240,0.5)' : 'none',
            borderRight: h==='right' ? '1.5px solid rgba(80,160,240,0.5)' : 'none',
          }} />
        ))}

        {/* 内容区 */}
        <div style={S.summaryContent}>
          {/* 日期标签 */}
          <div style={S.summaryDateChip}>{data.date}</div>

          {/* 主标题 */}
          <div style={S.summaryTitle}>涨停分布</div>

          {/* 标题下分割线 */}
          <div style={S.summaryDivider} />

          {/* 涨停数据行 */}
          <div style={S.summaryStatsRow}>
            {[
              { label: '涨停', value: data.total_count, color: '#ff6b7a' },
              { label: '新增', value: data.new_count,   color: '#2ed573' },
              { label: '退出', value: data.exit_count,  color: '#7a8a99' },
              ...(data.max_consecutive > 1 ? [{ label: '最高', value: `${data.max_consecutive}连板`, color: '#ffa502' }] : []),
            ].map((item, i, arr) => (
              <React.Fragment key={i}>
                <div style={S.summaryStat}>
                  <span style={{ ...S.summaryStatNum, color: item.color }}>{item.value}</span>
                  <span style={S.summaryStatLabel}>{item.label}</span>
                </div>
                {i < arr.length - 1 && <div style={S.summaryStatSep} />}
              </React.Fragment>
            ))}
          </div>

          {/* 市场涨跌行（次要信息，样式弱化） */}
          {data.advance_count ? (
            <div style={S.summaryBreadthRow}>
              <span style={S.summaryBreadthLabel}>今日A股</span>
              {[
                { label: '上涨', value: data.advance_count, color: '#c0454f' },
                { label: '下跌', value: data.decline_count, color: '#2a7a52' },
                { label: '平盘', value: data.flat_count,    color: '#3a4a55' },
              ].map((item, i, arr) => (
                <React.Fragment key={i}>
                  <span style={{ ...S.summaryBreadthNum, color: item.color }}>{item.value}</span>
                  <span style={S.summaryBreadthTag}>{item.label}</span>
                  {i < arr.length - 1 && <span style={S.summaryBreadthDot}>·</span>}
                </React.Fragment>
              ))}
            </div>
          ) : null}

          {/* 涨停数量趋势 */}
          {trend.length > 0 && (
            <div style={{ padding: '12px 8px 4px', borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: 4 }}>
              <div style={{ fontSize: 9, color: '#2e4a62', marginBottom: 6, letterSpacing: '0.5px' }}>
                近 {trend.length} 个交易日涨停数量
              </div>
              <TrendChart trend={trend} />
            </div>
          )}

          {/* 来源 */}
          <div style={S.summaryFooter}>数据来源：公开数据 · 仅供参考</div>
        </div>
      </div>

      {/* 第二张：板块热度 + 遇冷 */}
      <div ref={ref2} style={S.sectorCard}>
        {/* 背景：网格 */}
        <div style={S.sectorBgGrid} />
        {/* 背景：K线走势（装饰） */}
        <div style={S.sectorBgKline}>
          <svg width="460" height="90" xmlns="http://www.w3.org/2000/svg">
            {[
              [10,78,82,88,92,false],[30,74,78,84,88,true],[50,70,74,80,84,true],
              [70,72,76,80,84,false],[90,66,70,76,80,true],[110,62,66,72,76,true],
              [130,64,68,72,76,false],[150,58,62,68,72,true],[170,54,58,64,68,true],
              [190,56,60,64,68,false],[210,50,54,60,64,true],[230,46,50,56,60,true],
              [250,48,52,56,60,false],[270,42,46,52,56,true],[290,38,42,48,52,true],
              [310,40,44,48,52,false],[330,34,38,44,48,true],[350,30,34,40,44,true],
              [370,32,36,40,44,false],[390,26,30,36,40,true],[410,22,26,32,36,true],
              [430,24,28,32,36,false],[450,18,22,28,32,true],
            ].map(([cx,wt,bt,bb,wb,up],i) => (
              <g key={i}>
                <line x1={cx} y1={wt} x2={cx} y2={wb} stroke={up?'#26de81':'#ff4757'} strokeWidth="0.8"/>
                <rect x={cx-3} y={bt} width="6" height={bb-bt}
                  fill={up?'none':'#ff4757'} stroke={up?'#26de81':'#ff4757'} strokeWidth="0.8"/>
              </g>
            ))}
          </svg>
        </div>
        {/* 顶部光线 */}
        <div style={S.sectorTopBeam} />

        {/* 卡片头部 */}
        <div style={S.sectorCardHead}>
          <div style={S.sectorCardHeadLeft}>
            <span style={S.sectorCardHeadTitle}>板块热度分布</span>
            <span style={S.sectorCardHeadSub}>涨停板块 · 资金聚集方向</span>
          </div>
          <span style={S.sectorCardHeadDate}>{data.date}</span>
        </div>

        {/* 热板 区块 */}
        {industryTrend.length > 0 && (
          <div style={S.sectorSection}>
            <div style={S.sectorSectionHead}>
              <span style={S.sectorHotLabel}>热板</span>
              <span style={S.sectorSectionCount}>{industryTrend.length} 个板块</span>
            </div>
            <div style={{ ...S.tierGrid, padding: '0 14px 14px' }}>
              {industryTrend.map((t, i) => {
                const isHot = t.today_count >= 3;
                const isSelected = selectedSector?.industry === t.industry;
                return (
                  <div
                    key={i}
                    style={{
                      ...S.cell, width: 76,
                      background: isHot ? 'rgba(255,60,70,0.08)' : '#131920',
                      borderColor: isSelected
                        ? 'rgba(80,160,255,0.6)'
                        : isHot ? 'rgba(255,71,87,0.45)' : 'rgba(255,255,255,0.08)',
                      cursor: 'pointer',
                    }}
                    onClick={() => handleSectorClick(t)}
                  >
                    <span style={{ ...S.cellName, color: isHot ? '#ff8090' : '#c8d4de', fontSize: 12 }}>{t.industry}</span>
                    <span style={{ ...S.cellIndustry, color: isHot ? '#ff9a9a' : '#7a8e9e', fontSize: 11 }}>
                      {t.today_count}只
                      {t.change > 0 && <span style={{ color: '#ff5566' }}> +{t.change}</span>}
                      {t.change < 0 && <span style={{ color: '#2ed573' }}> {t.change}</span>}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 分隔线 */}
        <div style={S.sectorDivider} />

        {/* 遇冷 区块 */}
        {industryExitTrend.length > 0 && (
          <div style={{ ...S.sectorSection, paddingBottom: 16 }}>
            <div style={S.sectorSectionHead}>
              <span style={S.sectorColdLabel}>遇冷</span>
              <span style={S.sectorSectionCount}>{industryExitTrend.length} 个板块</span>
            </div>
            <div style={{ ...S.tierGrid, padding: '0 14px 0' }}>
              {industryExitTrend.map((t, i) => {
                const isSelected = selectedSector?.industry === t.industry;
                return (
                  <div
                    key={i}
                    style={{
                      ...S.cell, width: 76, background: 'rgba(30,50,70,0.4)',
                      borderColor: isSelected ? 'rgba(80,160,255,0.6)' : 'rgba(80,120,160,0.2)',
                      cursor: 'pointer',
                    }}
                    onClick={() => handleSectorClick(t)}
                  >
                    <span style={{ ...S.cellName, color: '#8aa0b4', fontSize: 12 }}>{t.industry}</span>
                    <span style={{ ...S.cellIndustry, fontSize: 10 }}>
                      <span style={{ color: t.today_count > 0 ? '#6a8aa4' : '#445566' }}>{t.today_count ?? 0}只 </span>
                      <span style={{ color: '#506070' }}>-{t.count}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 第三张：连板梯队 */}
      <div ref={ref3} style={{ ...S.board, marginTop: 8 }}>
        {levels.map(level => {
            const stocks = data.by_consecutive[level] || [];
            const activeCount = stocks.filter(s => !s.is_exit).length;
            const label = level === 1 ? '首板' : `${level}板`;
            const isHigh = level >= 3;
            return (
              <div key={level} style={{ ...S.tier, ...(level === levels[levels.length - 1] ? { borderBottom: 'none' } : {}) }}>
                <div style={S.tierLabel}>
                  <span style={{ ...S.tierBadge, background: isHigh ? '#2d1520' : level === 2 ? '#2d2010' : '#1e2d3d', color: isHigh ? '#ff7a7a' : level === 2 ? '#ffb84d' : '#b0bec8' }}>
                    {label}
                  </span>
                  <span style={S.tierCount}>({activeCount})</span>
                </div>
                <div style={S.tierGrid}>
                  {stocks.map((s, i) => {
                    const isExit = s.is_exit;
                    return (
                      <div key={i} style={{
                        ...S.cell,
                        borderColor: isExit ? 'rgba(255,255,255,0.06)' : isHigh ? 'rgba(255,71,87,0.5)' : level === 2 ? 'rgba(255,165,2,0.35)' : 'rgba(255,255,255,0.08)',
                        background: isExit
                          ? `linear-gradient(to bottom right, transparent calc(50% - 0.5px), rgba(120,140,160,0.4) 50%, transparent calc(50% + 0.5px)), linear-gradient(to bottom left, transparent calc(50% - 0.5px), rgba(120,140,160,0.4) 50%, transparent calc(50% + 0.5px)), #131920`
                          : '#131920',
                      }}>
                        <span style={{
                          ...S.cellName,
                          color: isExit ? '#8a9bab' : isHigh ? '#ff6b81' : level === 2 ? '#ffc048' : '#e2e8f0',
                        }}>{s.stock_name}</span>
                        {s.first_limit_time && !isExit && !s.is_yizi_ban ? <span style={S.cellTime}>{s.first_limit_time.slice(0, 5)}</span> : null}
                        {s.industry ? <span style={S.cellIndustry}>{s.industry}</span> : null}
                        {s.is_yizi_ban && !isExit ? <span style={S.cellYizi}>一字</span> : null}
                        {s.is_new && !isExit ? <span style={S.cellNew}>N</span> : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        <div style={S.footer}>数据来源：公开数据 | 仅供参考，不构成投资建议</div>
      </div>

      </div>{/* end leftColFull */}

      {/* 右侧：分时面板 */}
      {selectedSector && (
        <MinuteChartPanel
          sector={selectedSector}
          date={data.date}
          onClose={() => setSelectedSector(null)}
        />
      )}
    </div>
  );
}

// ── 涨停数量趋势图 ──
function TrendChart({ trend }) {
  const svgRef = React.useRef(null);
  const [w, setW] = React.useState(428);

  React.useEffect(() => {
    if (!svgRef.current) return;
    const obs = new ResizeObserver(entries => {
      setW(entries[0].contentRect.width);
    });
    obs.observe(svgRef.current.parentElement);
    setW(svgRef.current.parentElement.clientWidth);
    return () => obs.disconnect();
  }, []);

  const H = 96, PAD = { t: 16, b: 26, l: 32, r: 8 };
  const iW = w - PAD.l - PAD.r;
  const iH = H - PAD.t - PAD.b;
  const n = trend.length;
  const totals = trend.map(d => d.total);
  const maxV = Math.max(...totals);
  const minV = Math.min(...totals);
  const range = maxV - minV || 1;

  const toX = i => PAD.l + (i / Math.max(n - 1, 1)) * iW;
  const toY = v => PAD.t + iH - ((v - minV) / range) * iH;

  const pts = totals.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  const area = `M${toX(0)},${toY(totals[0])} ` +
    totals.slice(1).map((v, i) => `L${toX(i + 1)},${toY(v)}`).join(' ') +
    ` L${toX(n - 1)},${PAD.t + iH} L${PAD.l},${PAD.t + iH} Z`;

  const yTicks = [minV, Math.round((minV + maxV) / 2), maxV];

  return (
    <svg ref={svgRef} width="100%" height={H} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4a8fd9" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#4a8fd9" stopOpacity="0" />
        </linearGradient>
      </defs>

      {yTicks.map((v, i) => (
        <g key={i}>
          <line x1={PAD.l} y1={toY(v)} x2={PAD.l + iW} y2={toY(v)}
            stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" strokeDasharray="3,2" />
          <text x={PAD.l - 5} y={toY(v) + 3.5} fontSize="8" fill="#2e4a62" textAnchor="end">{v}</text>
        </g>
      ))}

      <path d={area} fill="url(#tg)" />
      <polyline points={pts} fill="none" stroke="#4a8fd9" strokeWidth="1.6"
        strokeLinejoin="round" strokeLinecap="round" />

      {trend.map((d, i) => {
        const x = toX(i), y = toY(d.total);
        const isLast = i === n - 1;
        const showLabel = i % 2 === 0 || isLast;
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={isLast ? 3.5 : 2.5}
              fill={isLast ? '#4a8fd9' : '#0f1923'}
              stroke="#4a8fd9" strokeWidth={isLast ? 0 : 1} />
            {isLast && (
              <text x={x} y={y - 7} fontSize="9" fill="#7ab8e0"
                textAnchor="middle" fontWeight="700">{d.total}</text>
            )}
            {showLabel && (
              <text x={x} y={H - 2} fontSize="7.5" fill="#2e4a62" textAnchor="middle">
                {d.trade_date.slice(5)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

const S = {
  page: {
    width: '100vw', minHeight: '100vh', background: '#0a0e14',
    display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 8px',
  },
  leftColFull: { display: 'contents' },
  pageEmbedded: {
    width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 8px',
    fontFamily: '-apple-system, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  loadingPage: {
    width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', background: '#0a0e14', gap: 12,
  },
  primaryBtn: {
    padding: '10px 20px', background: 'linear-gradient(135deg, #ff4757, #ff6348)',
    border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer',
    fontSize: 13, fontWeight: 600, letterSpacing: '0.5px',
  },
  summaryCard: {
    width: 460, height: 460, flexShrink: 0,
    position: 'relative', overflow: 'hidden', borderRadius: 16,
    background: 'linear-gradient(150deg, #060d1a 0%, #0c1828 50%, #07121e 100%)',
    border: '1px solid rgba(50,120,200,0.2)',
    boxShadow: '0 20px 60px rgba(0,0,0,0.7)',
  },
  summaryBgGrid: {
    position: 'absolute', inset: 0,
    backgroundImage: [
      'linear-gradient(rgba(40,100,180,0.06) 1px, transparent 1px)',
      'linear-gradient(90deg, rgba(40,100,180,0.06) 1px, transparent 1px)',
    ].join(','),
    backgroundSize: '36px 36px',
  },
  summaryBgGlow: {
    position: 'absolute', top: '35%', left: '50%', transform: 'translateX(-50%)',
    width: 340, height: 280,
    background: 'radial-gradient(ellipse, rgba(30,90,180,0.18) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  summaryBgBeam: {
    position: 'absolute', top: 0, left: '10%', right: '10%', height: 1,
    background: 'linear-gradient(90deg, transparent, rgba(80,160,255,0.5), transparent)',
  },
  summaryContent: {
    position: 'relative', zIndex: 1,
    height: '100%', display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    padding: '40px 44px', textAlign: 'center',
  },
  summaryDateChip: {
    fontSize: 16, color: '#a8d4f0', letterSpacing: '4px', fontWeight: 700,
    padding: '6px 22px', border: '1px solid rgba(80,160,240,0.5)',
    borderRadius: 24, marginBottom: 16,
    background: 'rgba(40,100,180,0.15)',
    textShadow: '0 0 20px rgba(80,160,255,0.6)',
    boxShadow: '0 0 16px rgba(40,120,220,0.15)',
  },
  summaryTitle: {
    fontSize: 40, fontWeight: 700, color: '#ddeeff',
    letterSpacing: '10px', marginBottom: 10,
    textShadow: '0 0 40px rgba(60,140,240,0.5)',
  },
  summaryDivider: {
    width: 60, height: 1, marginBottom: 20,
    background: 'linear-gradient(90deg, transparent, rgba(60,140,240,0.6), transparent)',
  },
  summaryStatsRow: {
    display: 'flex', alignItems: 'center',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 12, padding: '16px 8px', marginBottom: 28, width: '100%',
    justifyContent: 'center',
  },
  summaryStat: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0 16px',
  },
  summaryStatNum: { fontSize: 24, fontWeight: 700, lineHeight: 1.2 },
  summaryStatLabel: { fontSize: 10, color: '#6a8ea8', marginTop: 5, letterSpacing: '1px' },
  summaryStatSep: { width: 1, height: 28, background: 'rgba(255,255,255,0.07)' },
  summaryBreadthRow: {
    display: 'flex', alignItems: 'center', gap: 5,
    paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.05)',
    width: '100%', justifyContent: 'center',
  },
  summaryBreadthLabel: { fontSize: 10, color: '#5a7a90', letterSpacing: '1px', marginRight: 6 },
  summaryBreadthNum: { fontSize: 12, fontWeight: 600 },
  summaryBreadthTag: { fontSize: 10, color: '#5a7a90' },
  summaryBreadthDot: { fontSize: 10, color: '#3a5568', margin: '0 2px' },
  summaryFooter: {
    position: 'absolute', bottom: 20,
    fontSize: 10, color: '#2a4a62', letterSpacing: '1px',
  },
  toolbar: {
    width: '100%', maxWidth: 460, display: 'flex', gap: 8, marginBottom: 10,
  },
  toolbarEmbedded: {
    width: '100%', maxWidth: 460, display: 'flex', gap: 8, marginBottom: 10,
  },
  toolBtn: {
    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
    padding: '10px 0', fontSize: 12, color: '#a0adb9', background: '#131920',
    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, cursor: 'pointer',
    fontWeight: 500,
  },
  board: {
    width: '100%', maxWidth: 460, background: '#0f1419',
    borderRadius: 12, overflow: 'hidden',
    border: '1px solid rgba(255,255,255,0.06)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
  },
  sectorCard: {
    width: '100%', maxWidth: 460, marginTop: 8,
    position: 'relative', overflow: 'hidden', borderRadius: 12,
    background: 'linear-gradient(155deg, #070e1a 0%, #0b1622 55%, #060d18 100%)',
    border: '1px solid rgba(50,110,190,0.18)',
    boxShadow: '0 12px 40px rgba(0,0,0,0.6)',
  },
  sectorBgGrid: {
    position: 'absolute', inset: 0, pointerEvents: 'none',
    backgroundImage: [
      'linear-gradient(rgba(40,90,160,0.05) 1px, transparent 1px)',
      'linear-gradient(90deg, rgba(40,90,160,0.05) 1px, transparent 1px)',
    ].join(','),
    backgroundSize: '32px 32px',
  },
  sectorBgKline: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    opacity: 0.09, pointerEvents: 'none',
  },
  sectorTopBeam: {
    position: 'absolute', top: 0, left: '15%', right: '15%', height: 1,
    background: 'linear-gradient(90deg, transparent, rgba(80,150,255,0.5), transparent)',
  },
  sectorCardHead: {
    position: 'relative', zIndex: 1,
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 16px 12px',
    borderBottom: '1px solid rgba(255,255,255,0.05)',
    background: 'rgba(255,255,255,0.015)',
  },
  sectorCardHeadLeft: { display: 'flex', flexDirection: 'column', gap: 3 },
  sectorCardHeadTitle: { fontSize: 14, fontWeight: 700, color: '#c8ddf0', letterSpacing: '1px' },
  sectorCardHeadSub: { fontSize: 10, color: '#3d5a74', letterSpacing: '0.5px' },
  sectorCardHeadDate: {
    fontSize: 11, color: '#3d6080', letterSpacing: '1px',
    padding: '3px 10px', borderRadius: 10,
    border: '1px solid rgba(60,120,180,0.2)',
    background: 'rgba(40,90,160,0.06)',
  },
  sectorSection: { position: 'relative', zIndex: 1 },
  sectorSectionHead: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px 8px',
  },
  sectorHotLabel: {
    fontSize: 11, fontWeight: 700, color: '#ff7070',
    padding: '3px 10px', borderRadius: 4,
    background: 'rgba(255,60,60,0.1)',
    border: '1px solid rgba(255,60,60,0.25)',
    borderLeft: '3px solid #ff4757', letterSpacing: '1px',
  },
  sectorColdLabel: {
    fontSize: 11, fontWeight: 700, color: '#7aa8c8',
    padding: '3px 10px', borderRadius: 4,
    background: 'rgba(50,100,160,0.1)',
    border: '1px solid rgba(60,110,170,0.25)',
    borderLeft: '3px solid #4a80b4', letterSpacing: '1px',
  },
  sectorSectionCount: { fontSize: 10, color: '#3a5570' },
  sectorDivider: {
    margin: '0 14px', height: 1,
    background: 'linear-gradient(90deg, transparent, rgba(60,110,170,0.2), transparent)',
  },
  tier: {
    display: 'flex', alignItems: 'flex-start', padding: '14px 16px',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
  },
  tierLabel: {
    width: 46, flexShrink: 0, display: 'flex', flexDirection: 'column',
    alignItems: 'center', paddingTop: 4, gap: 4,
  },
  tierBadge: {
    fontSize: 11, fontWeight: 700, padding: '4px 7px',
    borderRadius: 4, lineHeight: 1, whiteSpace: 'nowrap',
  },
  tierCount: { fontSize: 10, color: '#9aaab8' },
  tierGrid: { flex: 1, display: 'flex', flexWrap: 'wrap', gap: 5 },
  cell: {
    width: 72, height: 52, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 5, position: 'relative',
    background: '#131920', overflow: 'hidden', padding: '3px 2px',
  },
  cellName: {
    fontSize: 11, fontWeight: 600, lineHeight: 1.3,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
    maxWidth: 66, textAlign: 'center',
  },
  cellIndustry: {
    fontSize: 9, color: '#8a97a6', lineHeight: 1.2, marginTop: 1,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
    maxWidth: 66, textAlign: 'center',
  },
  cellTime: {
    fontSize: 9, color: '#7a8e9e', lineHeight: 1.2,
    textAlign: 'center', fontVariantNumeric: 'tabular-nums',
  },
  cellNew: {
    position: 'absolute', top: 1, right: 1,
    fontSize: 7, color: '#0a0e14', background: '#2ed573',
    borderRadius: 2, width: 10, height: 10, lineHeight: '10px',
    textAlign: 'center', fontWeight: 700,
  },
  cellYizi: {
    position: 'absolute', top: 1, left: 1,
    fontSize: 7, color: '#0a0e14', background: '#a29bfe',
    borderRadius: 2, padding: '1px 2px', lineHeight: '9px',
    textAlign: 'center', fontWeight: 700, letterSpacing: '0.5px',
  },
  footer: {
    padding: '10px 16px', fontSize: 9, color: '#6b7a8a',
    borderTop: '1px solid rgba(255,255,255,0.04)', textAlign: 'center',
  },
};
