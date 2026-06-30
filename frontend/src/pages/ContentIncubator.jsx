import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from 'antd';
import { ArrowLeftOutlined, FireOutlined, EditOutlined, LockOutlined } from '@ant-design/icons';
import LimitUpBoard from './LimitUpBoard';
import ContentOps from './ContentOps';

// 授权码 → 可访问的 tab
const AUTH_MAP = {
  '777': ['limitup'],
  '789': ['contentops'],
  'xu':  ['limitup', 'contentops'],
};

const ALL_TABS = [
  { key: 'limitup',    label: '涨停分布', icon: <FireOutlined /> },
  { key: 'contentops', label: '内容创作', icon: <EditOutlined /> },
];

export default function ContentIncubator() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [authCode, setAuthCode] = useState('');
  const [authInput, setAuthInput] = useState('');
  const [authError, setAuthError] = useState('');

  const allowedTabs = AUTH_MAP[authCode] || [];
  const tabs = ALL_TABS.filter(t => allowedTabs.includes(t.key));

  const activeTab = (() => {
    const tab = searchParams.get('tab') || '';
    if (allowedTabs.includes(tab)) return tab;
    return allowedTabs[0] || '';
  })();

  const switchTab = (key) => setSearchParams({ tab: key });

  const handleAuth = () => {
    const input = authInput.trim();
    if (AUTH_MAP[input]) {
      setAuthCode(input);
      setAuthError('');
      setAuthInput('');
      // 自动跳到该授权码第一个可用 tab
      setSearchParams({ tab: AUTH_MAP[input][0] });
    } else {
      setAuthError('授权码错误，请重试');
    }
  };

  // 未授权：显示授权浮层
  if (!authCode) {
    return (
      <div style={S.authOverlay}>
        <div style={S.authBox}>
          <div style={S.authIcon}><LockOutlined /></div>
          <div style={S.authTitle}>内容孵化器</div>
          <input
            type="password"
            value={authInput}
            onChange={e => { setAuthInput(e.target.value); setAuthError(''); }}
            onKeyDown={e => e.key === 'Enter' && handleAuth()}
            placeholder="请输入授权码"
            autoFocus
            style={S.authInput}
          />
          {authError && <div style={S.authError}>{authError}</div>}
          <button onClick={handleAuth} style={S.authBtn}>进入</button>
        </div>
      </div>
    );
  }

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

        {/* Tab 栏（只显示有权限的 tab） */}
        <div style={S.tabBar}>
          {tabs.map(tab => (
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

      {/* 内容区 */}
      <div style={S.content}>
        {allowedTabs.includes('limitup') && (
          <div style={{ display: activeTab === 'limitup' ? 'block' : 'none' }}>
            <LimitUpBoard embedded />
          </div>
        )}
        {allowedTabs.includes('contentops') && (
          <div style={{ display: activeTab === 'contentops' ? 'block' : 'none' }}>
            <ContentOps embedded />
          </div>
        )}
      </div>
    </div>
  );
}

const S = {
  // 授权浮层
  authOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(10,14,20,0.98)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 3000,
  },
  authBox: {
    background: '#0d1117',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 16,
    padding: '36px 32px 28px',
    minWidth: 300,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
  },
  authIcon: {
    fontSize: 28,
    color: '#4a8abf',
    marginBottom: 4,
  },
  authTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: '#c8d8e8',
    letterSpacing: '1px',
    marginBottom: 8,
  },
  authInput: {
    width: 200,
    padding: '10px 14px',
    borderRadius: 8,
    border: '1.5px solid #313a4d',
    background: '#181c24',
    color: '#fff',
    fontSize: 16,
    outline: 'none',
    textAlign: 'center',
    fontWeight: 600,
    letterSpacing: 3,
  },
  authError: {
    color: '#ff4d4f',
    fontSize: 12,
    fontWeight: 500,
    marginTop: -4,
  },
  authBtn: {
    width: 200,
    padding: '9px 0',
    borderRadius: 8,
    border: 'none',
    background: 'linear-gradient(90deg, #4a8abf, #7ab8e0)',
    color: '#fff',
    fontWeight: 700,
    fontSize: 15,
    cursor: 'pointer',
    marginTop: 4,
    letterSpacing: '1px',
  },
  // 主页面
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
