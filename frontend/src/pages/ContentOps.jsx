import React, { useState, useEffect, useCallback } from 'react';
import { Button, Spin, message, Popconfirm, Tag, Segmented, Input } from 'antd';
import {
  ThunderboltOutlined, DeleteOutlined,
  BookOutlined, VideoCameraOutlined, FileTextOutlined,
  UserAddOutlined, HeartOutlined, CommentOutlined,
  CopyOutlined, SafetyCertificateOutlined, EditOutlined,
  AppstoreOutlined, HistoryOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import MaterialPanel from '../components/ContentOps/MaterialPanel';
import XhsPreview from '../components/ContentOps/XhsPreview';
import VerificationReport from '../components/ContentOps/VerificationReport';
import PLATFORMS, { DEFAULT_PLATFORM } from '../components/ContentOps/platformConfig';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const platformIcons = {
  note: <BookOutlined />,
  shortVideo: <VideoCameraOutlined />,
  article: <FileTextOutlined />,
};

// ── History Card ──────────────────────────────────────────────────────────────
const HistoryCard = ({ record, platform, onDelete }) => {
  const [expanded, setExpanded] = useState(false);
  const pf = platform || {};

  return (
    <div style={{
      marginBottom: 10, borderRadius: 12,
      background: '#141720', border: '1px solid #252a36',
      overflow: 'hidden',
    }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', cursor: 'pointer',
        }}
        onClick={() => setExpanded(o => !o)}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ color: '#666', fontSize: 11 }}>{record.content_date}</span>
            <Tag
              color={record.stage === 'formatted' ? 'success' : 'processing'}
              style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 5px' }}
            >
              {record.stage === 'formatted' ? '已生成' : '素材'}
            </Tag>
          </div>
          <div style={{
            color: record.xhs_title ? '#d0d0d0' : '#555',
            fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {record.xhs_title || '(未生成内容)'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 10 }}>
          <Popconfirm
            title="确认删除？"
            onConfirm={() => onDelete(record.id)}
          >
            <Button
              type="text" size="small" icon={<DeleteOutlined />}
              style={{ color: '#ff4d4f' }}
              onClick={e => e.stopPropagation()}
            />
          </Popconfirm>
          <span style={{ color: '#444', fontSize: 13 }}>{expanded ? '∧' : '∨'}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid #252a36' }}>
          {record.raw_material && (
            <div style={{ padding: '12px 14px', borderBottom: '1px solid #1a1e28' }}>
              <div style={{ color: '#666', fontSize: 10, marginBottom: 8, letterSpacing: 1 }}>素材内容</div>
              <MaterialPanel material={record.raw_material} compact />
            </div>
          )}
          {record.xhs_title && (
            <div style={{ padding: '12px 14px', borderBottom: record.verification_result ? '1px solid #1a1e28' : 'none' }}>
              <div style={{ color: '#666', fontSize: 10, marginBottom: 8, letterSpacing: 1 }}>
                {pf.shortLabel}内容
              </div>
              <XhsPreview
                xhsData={{
                  title: record.xhs_title,
                  body: record.xhs_body,
                  tags: record.xhs_tags || [],
                  cover_text: record.xhs_cover_text,
                }}
                loading={false}
                onFormat={null}
                onVerify={null}
                platform={pf}
                showActions={false}
              />
            </div>
          )}
          {record.verification_result && (
            <div style={{ padding: '12px 14px' }}>
              <div style={{ color: '#666', fontSize: 10, marginBottom: 8, letterSpacing: 1 }}>验证报告</div>
              <VerificationReport verificationResult={record.verification_result} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
const ContentOps = ({ embedded = false }) => {
  const [activeView, setActiveView] = useState('material');
  const [platform, setPlatform] = useState(DEFAULT_PLATFORM);
  const [material, setMaterial] = useState(null);
  const [xhsData, setXhsData] = useState(null);
  const [contentId, setContentId] = useState(null);
  const [generatingMaterial, setGeneratingMaterial] = useState(false);
  const [formattingXhs, setFormattingXhs] = useState(false);
  const [historyList, setHistoryList] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [userInstructions, setUserInstructions] = useState('');
  const [goal, setGoal] = useState(null);
  const [modules, setModules] = useState(['market_overview', 'sector_review', 'hot_sectors', 'hot_topics', 'knowledge_seed']);
  const [configOpen, setConfigOpen] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const res = await axios.get(`${API_BASE_URL}/api/content/list?limit=20`);
      if (res.data?.success) setHistoryList(res.data.data || []);
    } catch (e) {
      console.error('获取历史列表失败:', e);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleGenerateMaterial = async () => {
    try {
      setGeneratingMaterial(true);
      setMaterial(null);
      setXhsData(null);
      setContentId(null);
      setVerificationResult(null);
      const res = await axios.post(`${API_BASE_URL}/api/content/generate-material`);
      if (res.data?.success) {
        const data = res.data.data;
        setMaterial(data);
        setContentId(data.id);
        message.success('素材生成完成');
        fetchHistory();
        setActiveView('create');
      } else {
        message.error(res.data?.message || '生成失败');
      }
    } catch (e) {
      message.error('素材生成失败: ' + (e.response?.data?.message || e.message));
    } finally {
      setGeneratingMaterial(false);
    }
  };

  const handleFormatXhs = async () => {
    if (!contentId) { message.warning('请先生成素材'); return; }
    const pf = PLATFORMS[platform];
    try {
      setFormattingXhs(true);
      const res = await axios.post(`${API_BASE_URL}${pf.formatEndpoint}`, {
        content_id: contentId,
        platform,
        user_instructions: userInstructions || undefined,
        goal: goal || undefined,
        modules: modules.length < 5 ? modules : undefined,
      });
      if (res.data?.success) {
        setXhsData(res.data.data);
        message.success(pf.successMsg);
        fetchHistory();
      } else {
        message.error(res.data?.message || '生成失败');
      }
    } catch (e) {
      message.error('生成失败: ' + (e.response?.data?.message || e.message));
    } finally {
      setFormattingXhs(false);
    }
  };

  const handleVerify = async () => {
    if (!contentId) { message.warning('请先生成并转写内容'); return; }
    try {
      setVerifying(true);
      const res = await axios.post(`${API_BASE_URL}/api/content/verify`, { content_id: contentId });
      if (res.data?.success) {
        setVerificationResult(res.data.data.verification_result);
        message.success('内容验证完成');
        fetchHistory();
      } else {
        message.error(res.data?.message || '验证失败');
      }
    } catch (e) {
      message.error('验证失败: ' + (e.response?.data?.message || e.message));
    } finally {
      setVerifying(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API_BASE_URL}/api/content/${id}`);
      message.success('已删除');
      if (contentId === id) { setMaterial(null); setXhsData(null); setContentId(null); }
      fetchHistory();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleCopyAll = () => {
    if (!xhsData) return;
    const { title, body, tags } = xhsData;
    const tagStr = (tags || []).join(' ');
    const fullText = `${title}\n\n${body}\n\n${tagStr}`;
    navigator.clipboard.writeText(fullText)
      .then(() => message.success('已复制到剪贴板'))
      .catch(() => {
        const ta = document.createElement('textarea');
        ta.value = fullText;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        message.success('已复制到剪贴板');
      });
  };

  const pf = PLATFORMS[platform];
  const hasActionBar = activeView !== 'history';
  const contentPaddingBottom = hasActionBar ? 120 : 64;

  // ── Tab views ──────────────────────────────────────────────────────────────

  const MaterialView = (
    <div style={{ padding: '12px 14px' }}>
      {generatingMaterial ? (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin tip="正在采集数据并生成素材..." />
        </div>
      ) : (
        <MaterialPanel material={material} />
      )}
    </div>
  );

  const CreateView = (
    <div style={{ padding: '12px 14px' }}>
      {/* Config collapsible */}
      <div style={{
        marginBottom: 12, borderRadius: 12,
        background: '#141720', border: '1px solid #252a36',
        overflow: 'hidden',
      }}>
        <div
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '11px 14px', cursor: 'pointer',
          }}
          onClick={() => setConfigOpen(o => !o)}
        >
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>生成配置</span>
          <span style={{ color: '#444', fontSize: 12 }}>{configOpen ? '收起 ∧' : '展开 ∨'}</span>
        </div>
        {configOpen && (
          <div style={{ padding: '0 14px 14px', borderTop: '1px solid #252a36' }}>
            <div style={{ color: '#8c8c8c', fontSize: 11, margin: '10px 0 6px' }}>运营目标（可选）</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
              {[
                { key: 'follow', label: '涨粉关注', icon: <UserAddOutlined /> },
                { key: 'like_collect', label: '点赞收藏', icon: <HeartOutlined /> },
                { key: 'discuss', label: '评论讨论', icon: <CommentOutlined /> },
              ].map(g => (
                <Tag key={g.key}
                  style={{
                    cursor: 'pointer', fontSize: 11, padding: '4px 10px',
                    background: goal === g.key ? '#1890ff22' : '#1a1e28',
                    borderColor: goal === g.key ? '#1890ff' : '#313a4d',
                    color: goal === g.key ? '#1890ff' : '#8c8c8c',
                  }}
                  onClick={() => setGoal(goal === g.key ? null : g.key)}>
                  {g.icon} {g.label}
                </Tag>
              ))}
            </div>
            <div style={{ color: '#8c8c8c', fontSize: 11, marginBottom: 6 }}>内容模块</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
              {[
                { key: 'market_overview', label: '市场总览' },
                { key: 'sector_review', label: '板块复盘' },
                { key: 'hot_sectors', label: '行业故事' },
                { key: 'hot_topics', label: '热点话题' },
                { key: 'knowledge_seed', label: '知识科普' },
              ].map(m => (
                <Tag key={m.key}
                  style={{
                    cursor: 'pointer', fontSize: 11, padding: '3px 8px',
                    background: modules.includes(m.key) ? '#52c41a22' : '#1a1e28',
                    borderColor: modules.includes(m.key) ? '#52c41a' : '#313a4d',
                    color: modules.includes(m.key) ? '#52c41a' : '#555',
                  }}
                  onClick={() => {
                    if (modules.includes(m.key)) setModules(modules.filter(x => x !== m.key));
                    else setModules([...modules, m.key]);
                  }}>
                  {modules.includes(m.key) ? '✓ ' : ''}{m.label}
                </Tag>
              ))}
            </div>
            <Input.TextArea
              value={userInstructions}
              onChange={e => setUserInstructions(e.target.value)}
              placeholder="自定义要求，如「重点聊消费板块」「语气更轻松」"
              autoSize={{ minRows: 1, maxRows: 3 }}
              style={{
                background: '#1a1e28', borderColor: '#313a4d', color: '#d0d0d0',
                fontSize: 12, resize: 'none',
              }}
            />
          </div>
        )}
      </div>

      {/* Content preview */}
      {formattingXhs ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin tip={pf.spinTip} />
        </div>
      ) : (
        <XhsPreview
          xhsData={xhsData}
          loading={formattingXhs}
          onFormat={null}
          onVerify={null}
          verifyLoading={verifying}
          verificationResult={verificationResult}
          platform={pf}
          showActions={false}
        />
      )}

      {/* Verification result */}
      {(verificationResult || verifying) && (
        <div style={{
          marginTop: 12, padding: '12px 14px', borderRadius: 12,
          background: '#141720', border: '1px solid #252a36',
        }}>
          <div style={{ color: '#666', fontSize: 10, marginBottom: 8, letterSpacing: 1 }}>验证报告</div>
          <VerificationReport verificationResult={verificationResult} loading={verifying} />
        </div>
      )}
    </div>
  );

  const HistoryView = (
    <div style={{ padding: '12px 14px' }}>
      {loadingHistory ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin tip="加载历史..." />
        </div>
      ) : historyList.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#555', fontSize: 13 }}>
          暂无历史内容
        </div>
      ) : (
        historyList.map(record => (
          <HistoryCard
            key={record.id}
            record={record}
            platform={pf}
            onDelete={handleDelete}
          />
        ))
      )}
    </div>
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="co-mobile" style={{ background: '#0d1117', color: '#e0e0e0', paddingBottom: contentPaddingBottom }}>
      <style>{`
        .co-mobile .ant-segmented { background: #141720 !important; }
        .co-mobile .ant-segmented-item { color: #8c8c8c !important; }
        .co-mobile .ant-segmented-item:hover { color: #b0bec5 !important; }
        .co-mobile .ant-segmented-item-selected { background: #252a36 !important; color: #e0e0e0 !important; }
        .co-mobile .ant-segmented-item-label { display: flex; align-items: center; justify-content: center; }
      `}</style>

      {/* Sticky platform switcher — full width bar, inner content capped at 460 */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: '#0d1117',
        borderBottom: '1px solid #1a1e28',
        padding: '8px 14px',
      }}>
        <div style={{ maxWidth: 460, margin: '0 auto' }}>
          <Segmented
            value={platform}
            onChange={val => { setPlatform(val); setXhsData(null); setVerificationResult(null); }}
            options={Object.values(PLATFORMS).map(p => ({
              value: p.key,
              label: (
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                  {platformIcons[p.key]} {p.label}
                </span>
              ),
            }))}
            block
            style={{ background: '#141720' }}
          />
        </div>
      </div>

      {/* Tab content — centered at 460 */}
      <div style={{ maxWidth: 460, margin: '0 auto', width: '100%' }}>
        {activeView === 'material' && MaterialView}
        {activeView === 'create' && CreateView}
        {activeView === 'history' && HistoryView}
      </div>

      {/* Fixed action bar — full width rail, buttons capped at 460 */}
      {hasActionBar && (
        <div style={{
          position: 'fixed', bottom: 56, left: 0, right: 0, zIndex: 150,
          background: 'linear-gradient(to top, #0d1117 65%, rgba(13,17,23,0))',
        }}>
          <div style={{ maxWidth: 460, margin: '0 auto', padding: '10px 14px 6px' }}>
            {activeView === 'material' && (
              <Button
                type="primary" icon={<ThunderboltOutlined />}
                loading={generatingMaterial}
                onClick={handleGenerateMaterial}
                block size="large"
                style={{ borderRadius: 12, height: 48, fontWeight: 700, fontSize: 15 }}
              >
                {material ? '重新生成素材' : '生成素材'}
              </Button>
            )}
            {activeView === 'create' && !xhsData && (
              <Button
                type="primary" icon={<EditOutlined />}
                loading={formattingXhs}
                onClick={handleFormatXhs}
                disabled={!contentId}
                block size="large"
                style={{ borderRadius: 12, height: 48, fontWeight: 700, fontSize: 15 }}
              >
                {!contentId ? '请先生成素材' : pf.generateBtnText}
              </Button>
            )}
            {activeView === 'create' && xhsData && (
              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  type="primary" icon={<CopyOutlined />}
                  onClick={handleCopyAll}
                  style={{ flex: 1, height: 46, borderRadius: 12, fontWeight: 600 }}
                >
                  复制全文
                </Button>
                <Button
                  icon={<SafetyCertificateOutlined />}
                  loading={verifying}
                  onClick={handleVerify}
                  style={{ flex: 1, height: 46, borderRadius: 12, borderColor: '#52c41a', color: '#52c41a' }}
                >
                  验证
                </Button>
                <Button
                  ghost icon={<EditOutlined />}
                  loading={formattingXhs}
                  onClick={handleFormatXhs}
                  style={{ flex: 1, height: 46, borderRadius: 12, borderColor: '#313a4d', color: '#d0d0d0' }}
                >
                  重新生成
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fixed bottom tab nav — full width rail, tabs capped at 460 */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, height: 56,
        zIndex: 200,
        background: '#0d1117',
        borderTop: '1px solid #1a1e28',
        display: 'flex',
        justifyContent: 'center',
      }}>
        <div style={{ width: '100%', maxWidth: 460, display: 'flex' }}>
        {[
          { key: 'material', label: '素材', icon: <AppstoreOutlined /> },
          { key: 'create', label: '创作', icon: <EditOutlined /> },
          { key: 'history', label: '历史', icon: <HistoryOutlined /> },
        ].map(tab => (
          <div
            key={tab.key}
            style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              gap: 3, cursor: 'pointer',
              color: activeView === tab.key ? '#5aa3d0' : '#555',
              fontSize: 10, fontWeight: activeView === tab.key ? 600 : 400,
              position: 'relative',
              transition: 'color 0.2s',
              paddingBottom: 4,
            }}
            onClick={() => setActiveView(tab.key)}
          >
            {activeView === tab.key && (
              <div style={{
                position: 'absolute', top: 0, left: '50%',
                transform: 'translateX(-50%)',
                width: 28, height: 2, borderRadius: 1,
                background: '#5aa3d0',
              }} />
            )}
            <span style={{ fontSize: 20 }}>{tab.icon}</span>
            <span>{tab.label}</span>
          </div>
        ))}
        </div>
      </div>
    </div>
  );
};

export default ContentOps;
