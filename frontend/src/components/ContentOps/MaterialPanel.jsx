import React from 'react';
import { Tag, Empty } from 'antd';
import {
  DashboardOutlined, AppstoreOutlined, BulbOutlined,
  FireOutlined, FundOutlined, SyncOutlined,
} from '@ant-design/icons';

const moodConfig = {
  '热闹': { color: '#ff4d4f' },
  '躁动': { color: '#fa8c16' },
  '分化': { color: '#faad14' },
  '纠结': { color: '#1890ff' },
  '冷清': { color: '#8c8c8c' },
};

const MaterialPanel = ({ material }) => {
  if (!material) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Empty description={<span style={{ color: '#666' }}>点击「生成素材」开始</span>}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ opacity: 0.6 }}
        />
      </div>
    );
  }

  const overview = material.market_overview;
  const sectors = material.hot_sectors || [];
  const reviews = material.sector_review || [];
  const topics = material.hot_topics || [];
  const nugget = material.knowledge_seed;

  const sectionStyle = { marginBottom: 20 };
  const headerStyle = {
    color: '#b0bec5', fontSize: 13, fontWeight: 500, marginBottom: 10,
    display: 'flex', alignItems: 'center', gap: 6,
    borderBottom: '1px solid #252a36', paddingBottom: 6,
  };
  const cardStyle = {
    padding: '10px 14px', marginBottom: 8, borderRadius: 6,
    background: '#1a1e28', border: '1px solid #313a4d',
  };

  const pctColor = (v) => {
    const s = String(v || '');
    return s.includes('-') ? '#52c41a' : '#ff4d4f';
  };

  const safeText = (v) => {
    if (v === null || v === undefined) return null;
    if (typeof v === 'string') return v;
    if (typeof v === 'object') {
      if (v.main_net_inflow !== undefined) {
        const val = v.main_net_inflow;
        const unit = v.unit || '亿';
        return val >= 0 ? `主力净流入${val}${unit}` : `主力净流出${Math.abs(val)}${unit}`;
      }
      if (v.direction) return `${v.direction}${v.confidence ? `(${v.confidence})` : ''}: ${v.summary || ''}`;
      if (v.summary) return v.summary;
      return JSON.stringify(v);
    }
    return String(v);
  };

  return (
    <div>
      {/* 市场总览 */}
      {overview && (
        <div style={sectionStyle}>
          <div style={headerStyle}>
            <DashboardOutlined style={{ color: '#1890ff' }} /> 市场总览
          </div>
          <div style={{
            ...cardStyle,
            background: 'linear-gradient(135deg, #1a1e28, #252a36)',
            border: '1px solid #1890ff',
          }}>
            <div style={{ color: '#e0e0e0', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
              {overview.summary}
            </div>
            {overview.key_indices && (
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
                {Object.entries(overview.key_indices).map(([name, val]) => (
                  <span key={name} style={{ fontSize: 11 }}>
                    <span style={{ color: '#8c8c8c' }}>{name} </span>
                    <span style={{ color: pctColor(val), fontWeight: 600 }}>{val}</span>
                  </span>
                ))}
              </div>
            )}
            {overview.mood && (
              <Tag style={{
                margin: 0, fontSize: 10,
                color: (moodConfig[overview.mood] || moodConfig['纠结']).color,
                background: 'transparent',
                border: `1px solid ${(moodConfig[overview.mood] || moodConfig['纠结']).color}`,
              }}>
                {overview.mood}
              </Tag>
            )}
          </div>
        </div>
      )}

      {/* 热门行业 */}
      <div style={sectionStyle}>
        <div style={headerStyle}>
          <AppstoreOutlined style={{ color: '#722ed1' }} /> 热门行业
          {sectors.length > 0 && <span style={{ color: '#666', fontSize: 11 }}>({sectors.length})</span>}
        </div>
        {sectors.length === 0 ? (
          <div style={{ color: '#555', fontSize: 12, textAlign: 'center', padding: 16 }}>暂无数据</div>
        ) : sectors.map((s, i) => (
          <div key={i} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ color: '#e0e0e0', fontSize: 13, fontWeight: 500 }}>{s.sector_name}</span>
              {s.change_pct && s.change_pct !== 'N/A' && (
                <span style={{ color: pctColor(s.change_pct), fontSize: 12, fontWeight: 600 }}>
                  {s.change_pct}
                </span>
              )}
              {s.turnover && (
                <span style={{ color: '#666', fontSize: 10 }}>{s.turnover}</span>
              )}
            </div>
            <div style={{ color: '#8c8c8c', fontSize: 11, lineHeight: 1.6 }}>
              <div style={{ color: '#d0d0d0' }}>{s.driver}</div>
              {s.capital_flow && safeText(s.capital_flow) && (
                <div style={{ marginTop: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <FundOutlined style={{ color: '#1890ff', fontSize: 10 }} />
                  <span style={{ color: '#1890ff' }}>{safeText(s.capital_flow)}</span>
                </div>
              )}
              {s.rotation_context && (
                <div style={{ color: '#faad14', marginTop: 2, fontSize: 10 }}>{s.rotation_context}</div>
              )}
              {s.life_connection && (
                <div style={{ color: '#8c8c8c', marginTop: 2 }}>{s.life_connection}</div>
              )}
              {s.pool_analysis && safeText(s.pool_analysis) && (
                <div style={{ color: '#52c41a', marginTop: 2, fontSize: 10 }}>深度分析: {safeText(s.pool_analysis)}</div>
              )}
              {s.related_stocks?.length > 0 && (
                <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {s.related_stocks.map((st, j) => (
                    <Tag key={j} style={{ margin: 0, fontSize: 10, background: '#252a36', border: '1px solid #313a4d', color: '#aaa' }}>{st}</Tag>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 板块复盘 */}
      {reviews.length > 0 && (
        <div style={sectionStyle}>
          <div style={headerStyle}>
            <SyncOutlined style={{ color: '#eb2f96' }} /> 板块复盘（昨日提及）
            <span style={{ color: '#666', fontSize: 11 }}>({reviews.length})</span>
          </div>
          {reviews.map((r, i) => (
            <div key={i} style={cardStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{ color: '#e0e0e0', fontSize: 13, fontWeight: 500 }}>{r.sector_name}</span>
                {r.prev_change_pct && (
                  <span style={{ fontSize: 11, color: '#8c8c8c' }}>{r.prev_change_pct}</span>
                )}
                <span style={{ fontSize: 11, color: '#555' }}>→</span>
                <span style={{ fontSize: 11, color: pctColor(r.today_change_pct) }}>
                  {r.today_change_pct || '无数据'}
                </span>
                {r.continuation && (
                  <Tag style={{
                    margin: 0, fontSize: 10,
                    color: r.continuation === '延续' ? '#52c41a' : r.continuation === '反转' ? '#ff4d4f' : '#faad14',
                    background: 'transparent',
                    borderColor: r.continuation === '延续' ? '#52c41a' : r.continuation === '反转' ? '#ff4d4f' : '#faad14',
                  }}>
                    {r.continuation}
                  </Tag>
                )}
              </div>
              <div style={{ color: '#d0d0d0', fontSize: 11, lineHeight: 1.6 }}>
                {r.analysis}
              </div>
              {r.outlook && (
                <div style={{ color: '#8c8c8c', fontSize: 10, marginTop: 4 }}>{r.outlook}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 热点话题 */}
      <div style={sectionStyle}>
        <div style={headerStyle}>
          <FireOutlined style={{ color: '#fa8c16' }} /> 热点话题
          {topics.length > 0 && <span style={{ color: '#666', fontSize: 11 }}>({topics.length})</span>}
        </div>
        {topics.length === 0 ? (
          <div style={{ color: '#555', fontSize: 12, textAlign: 'center', padding: 16 }}>暂无话题</div>
        ) : topics.map((t, i) => (
          <div key={i} style={cardStyle}>
            <div style={{ color: '#e0e0e0', fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
              {t.title}
            </div>
            <div style={{ color: '#8c8c8c', fontSize: 11, lineHeight: 1.6 }}>
              <div>{t.summary}</div>
              {t.market_impact && <div style={{ color: '#d0d0d0', marginTop: 2 }}>影响: {t.market_impact}</div>}
              {t.life_angle && <div style={{ color: '#faad14', marginTop: 2 }}>{t.life_angle}</div>}
              {t.source && <div style={{ color: '#555', marginTop: 2, fontSize: 10 }}>来源: {t.source}</div>}
            </div>
          </div>
        ))}
      </div>

      {/* 小知识科普 */}
      {nugget && (
        <div style={sectionStyle}>
          <div style={headerStyle}>
            <BulbOutlined style={{ color: '#13c2c2' }} /> 小知识科普
          </div>
          <div style={{
            ...cardStyle,
            border: '1px solid #13c2c2',
            background: 'rgba(19,194,194,0.04)',
          }}>
            <div style={{ color: '#13c2c2', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              {nugget.concept}
            </div>
            {nugget.definition && (
              <div style={{ color: '#d0d0d0', fontSize: 12, lineHeight: 1.6, marginBottom: 4 }}>
                {nugget.definition}
              </div>
            )}
            {nugget.plain_explanation && (
              <div style={{ color: '#8c8c8c', fontSize: 12, lineHeight: 1.6, marginBottom: 4 }}>
                {nugget.plain_explanation}
              </div>
            )}
            {nugget.today_example && (
              <div style={{ color: '#8c8c8c', fontSize: 11, lineHeight: 1.5, fontStyle: 'italic' }}>
                {nugget.today_example}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MaterialPanel;
