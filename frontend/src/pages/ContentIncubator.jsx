import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from 'antd';
import { ArrowLeftOutlined, FireOutlined, EditOutlined } from '@ant-design/icons';
import LimitUpBoard from './LimitUpBoard';
import ContentOps from './ContentOps';

const TABS = [
  { key: 'limitup',     label: '涨停分布', icon: <FireOutlined /> },
  { key: 'contentops',  label: '内容创作', icon: <EditOutlined /> },
];

export default function ContentIncubator() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'limitup';

  const switchTab = (key) => setSearchParams({ tab: key });

  return (
    <div style={S.page}>
      {/* 顶部导航 */}
      <div style={S.topBar}>
        <div style={S.topLeft}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            style={{ color: '#8c8c8c' }}
            onClick={() => navigate('/')}
          />
          <span style={S.topTitle}>内容孵化器</span>
        </div>

        {/* Tab 栏（放在顶部右侧） */}
        <div style={S.tabBar}>
          {TABS.map(tab => (
            <div
              key={tab.key}
              style={{ ...S.tabItem, ...(activeTab === tab.key ? S.tabItemActive : {}) }}
              onClick={() => switchTab(tab.key)}
            >
              <span style={S.tabIcon}>{tab.icon}</span>
              <span style={S.tabLabel}>{tab.label}</span>
              {activeTab === tab.key && <div style={S.tabUnderline} />}
            </div>
          ))}
        </div>
      </div>

      {/* 内容区：各子页面自行管理操作和状态 */}
      <div style={S.content}>
        {/* 保持两个组件都挂载，避免切换时重新请求数据 */}
        <div style={{ display: activeTab === 'limitup' ? 'block' : 'none' }}>
          <LimitUpBoard embedded />
        </div>
        <div style={{ display: activeTab === 'contentops' ? 'block' : 'none' }}>
          <ContentOps embedded />
        </div>
      </div>
    </div>
  );
}

const S = {
  page: {
    minHeight: '100vh',
    background: '#0a0e14',
    display: 'flex',
    flexDirection: 'column',
    color: '#e0e0e0',
  },
  topBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 20px',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    background: '#0d1117',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  topLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  topTitle: {
    fontSize: 17,
    fontWeight: 700,
    color: '#c8d8e8',
    letterSpacing: '1px',
  },
  topRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  actionBtn: {
    color: '#8c9cb0',
    fontSize: 13,
  },
  tabBar: {
    display: 'flex',
    gap: 0,
    padding: '0 20px',
    background: '#0d1117',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
  },
  tabItem: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 20px',
    cursor: 'pointer',
    color: '#5a6a7a',
    fontSize: 13,
    fontWeight: 500,
    transition: 'color 0.2s',
    userSelect: 'none',
  },
  tabItemActive: {
    color: '#7ab8e0',
  },
  tabIcon: {
    fontSize: 14,
  },
  tabLabel: {
    letterSpacing: '0.5px',
  },
  tabUnderline: {
    position: 'absolute',
    bottom: 0,
    left: 20,
    right: 20,
    height: 2,
    borderRadius: 1,
    background: 'linear-gradient(90deg, #4a8abf, #7ab8e0)',
  },
  content: {
    flex: 1,
    overflow: 'auto',
  },
};
