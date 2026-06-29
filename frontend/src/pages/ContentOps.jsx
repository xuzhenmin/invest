import React, { useState, useEffect, useCallback } from 'react';
import { Button, Spin, message, Table, Popconfirm, Tag, Segmented, Input } from 'antd';
import {
  ThunderboltOutlined, DeleteOutlined,
  ArrowLeftOutlined, BookOutlined, VideoCameraOutlined, FileTextOutlined,
  UserAddOutlined, HeartOutlined, CommentOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
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

const ContentOps = ({ embedded = false }) => {
  const navigate = useNavigate();
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

  const fetchHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const res = await axios.get(`${API_BASE_URL}/api/content/list?limit=20`);
      if (res.data?.success) {
        setHistoryList(res.data.data || []);
      }
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
    if (!contentId) {
      message.warning('请先生成素材');
      return;
    }
    const pf = PLATFORMS[platform];
    try {
      setFormattingXhs(true);
      const res = await axios.post(`${API_BASE_URL}${pf.formatEndpoint}`, {
        content_id: contentId,
        platform: platform,
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
    if (!contentId) {
      message.warning('请先生成并转写内容');
      return;
    }
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
      if (contentId === id) {
        setMaterial(null);
        setXhsData(null);
        setContentId(null);
      }
      fetchHistory();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const historyColumns = [
    {
      title: '日期', dataIndex: 'content_date', key: 'date', width: 100,
      render: (v) => <span style={{ color: '#d0d0d0', fontSize: 12 }}>{v}</span>,
    },
    {
      title: '标题', dataIndex: 'xhs_title', key: 'title',
      render: (v) => (
        <span style={{ color: v ? '#d0d0d0' : '#555', fontSize: 12 }}>
          {v || '(未生成)'}
        </span>
      ),
    },
    {
      title: '阶段', dataIndex: 'stage', key: 'stage', width: 80,
      render: (v) => (
        <Tag color={v === 'formatted' ? 'green' : 'blue'} style={{ fontSize: 10 }}>
          {v === 'formatted' ? '已生成' : '素材'}
        </Tag>
      ),
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_, record) => (
        <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
          <Button type="text" size="small" icon={<DeleteOutlined />}
            style={{ color: '#ff4d4f' }} />
        </Popconfirm>
      ),
    },
  ];

  const expandedRowRender = (record) => {
    const rawMaterial = record.raw_material || null;
    const xhsDataRec = record.xhs_title ? {
      title: record.xhs_title,
      body: record.xhs_body,
      tags: record.xhs_tags || [],
      cover_text: record.xhs_cover_text,
    } : null;
    const hasVerification = !!record.verification_result;
    const pf = PLATFORMS[platform];

    return (
      <div style={{ display: 'flex', gap: 16, padding: '12px 0' }}>
        <div style={{
          flex: 1, padding: '12px 16px', borderRadius: 8,
          background: '#1a1e28', border: '1px solid #252a36',
          maxHeight: 400, overflowY: 'auto',
        }}>
          <div style={{ color: '#8c8c8c', fontSize: 11, marginBottom: 8,
            borderBottom: '1px solid #252a36', paddingBottom: 4 }}>
            素材内容
          </div>
          <MaterialPanel material={rawMaterial} />
        </div>
        <div style={{
          flex: 1, padding: '12px 16px', borderRadius: 8,
          background: '#1a1e28', border: '1px solid #252a36',
          maxHeight: 400, overflowY: 'auto',
        }}>
          <div style={{ color: '#8c8c8c', fontSize: 11, marginBottom: 8,
            borderBottom: '1px solid #252a36', paddingBottom: 4 }}>
            {pf.shortLabel}内容
          </div>
          <XhsPreview xhsData={xhsDataRec} loading={false} onFormat={null} platform={pf} />
        </div>
        {hasVerification && (
          <div style={{
            flex: 1, padding: '12px 16px', borderRadius: 8,
            background: '#1a1e28', border: '1px solid #252a36',
            maxHeight: 400, overflowY: 'auto',
          }}>
            <div style={{ color: '#8c8c8c', fontSize: 11, marginBottom: 8,
              borderBottom: '1px solid #252a36', paddingBottom: 4 }}>
              验证报告
            </div>
            <VerificationReport verificationResult={record.verification_result} />
          </div>
        )}
      </div>
    );
  };

  const pf = PLATFORMS[platform];

  return (
    <div className="content-ops-page" style={{
      ...(embedded ? {} : { minHeight: '100vh', background: '#0d1117' }),
      padding: '20px 24px', color: '#e0e0e0',
    }}>
      {/* 顶部栏（嵌入模式下隐藏） */}
      {!embedded && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button type="text" icon={<ArrowLeftOutlined />}
              style={{ color: '#8c8c8c' }}
              onClick={() => navigate('/')} />
            <span style={{ fontSize: 18, fontWeight: 600 }}>内容创作工坊</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Segmented
              value={platform}
              onChange={(val) => { setPlatform(val); setXhsData(null); setVerificationResult(null); }}
              options={Object.values(PLATFORMS).map(p => ({
                value: p.key,
                label: (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                    {platformIcons[p.key]} {p.label}
                  </span>
                ),
              }))}
              style={{ background: '#1a1e28', borderColor: '#313a4d' }}
            />
            <Button type="primary" icon={<ThunderboltOutlined />}
              loading={generatingMaterial}
              onClick={handleGenerateMaterial}>
              生成素材
            </Button>
          </div>
        </div>
      )}
      {/* 嵌入模式下的操作栏 */}
      {embedded && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <Segmented
            value={platform}
            onChange={(val) => { setPlatform(val); setXhsData(null); setVerificationResult(null); }}
            options={Object.values(PLATFORMS).map(p => ({
              value: p.key,
              label: (
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                  {platformIcons[p.key]} {p.label}
                </span>
              ),
            }))}
            style={{ background: '#1a1e28', borderColor: '#313a4d' }}
          />
          <Button type="primary" icon={<ThunderboltOutlined />}
            loading={generatingMaterial}
            onClick={handleGenerateMaterial}>
            生成素材
          </Button>
        </div>
      )}

      {/* 主体两栏布局 */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
        {/* 左侧：素材面板 */}
        <div style={{
          flex: 1, padding: '16px 20px', borderRadius: 10,
          background: '#141720', border: '1px solid #252a36',
          maxHeight: '65vh', overflowY: 'auto',
        }}>
          <div style={{
            color: '#8c8c8c', fontSize: 12, marginBottom: 12,
            borderBottom: '1px solid #252a36', paddingBottom: 6,
          }}>
            素材面板
          </div>
          {generatingMaterial ? (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <Spin tip="正在采集数据并生成素材..." />
            </div>
          ) : (
            <MaterialPanel material={material} />
          )}
        </div>

        {/* 右侧：内容预览 */}
        <div style={{
          flex: 1, padding: '16px 20px', borderRadius: 10,
          background: '#141720', border: '1px solid #252a36',
          maxHeight: '65vh', overflowY: 'auto',
        }}>
          <div style={{
            color: '#8c8c8c', fontSize: 12, marginBottom: 12,
            borderBottom: '1px solid #252a36', paddingBottom: 6,
          }}>
            {pf.previewTitle}
          </div>
          <div style={{ marginBottom: 10 }}>
            <div style={{ color: '#8c8c8c', fontSize: 11, marginBottom: 6 }}>运营目标（可选）</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[
                { key: 'follow', label: '涨粉关注', icon: <UserAddOutlined /> },
                { key: 'like_collect', label: '点赞收藏', icon: <HeartOutlined /> },
                { key: 'discuss', label: '评论讨论', icon: <CommentOutlined /> },
              ].map(g => (
                <Tag key={g.key}
                  style={{
                    cursor: 'pointer', fontSize: 11, padding: '2px 10px',
                    background: goal === g.key ? '#1890ff22' : '#1a1e28',
                    borderColor: goal === g.key ? '#1890ff' : '#313a4d',
                    color: goal === g.key ? '#1890ff' : '#8c8c8c',
                    transition: 'all 0.2s',
                  }}
                  onClick={() => setGoal(goal === g.key ? null : g.key)}>
                  {g.icon} {g.label}
                </Tag>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 10 }}>
            <div style={{ color: '#8c8c8c', fontSize: 11, marginBottom: 6 }}>内容模块（可取消勾选）</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                { key: 'market_overview', label: '市场总览' },
                { key: 'sector_review', label: '板块复盘' },
                { key: 'hot_sectors', label: '行业故事' },
                { key: 'hot_topics', label: '热点话题' },
                { key: 'knowledge_seed', label: '知识科普' },
              ].map(m => (
                <Tag key={m.key}
                  style={{
                    cursor: 'pointer', fontSize: 11, padding: '2px 8px',
                    background: modules.includes(m.key) ? '#52c41a22' : '#1a1e28',
                    borderColor: modules.includes(m.key) ? '#52c41a' : '#313a4d',
                    color: modules.includes(m.key) ? '#52c41a' : '#555',
                    transition: 'all 0.2s',
                  }}
                  onClick={() => {
                    if (modules.includes(m.key)) {
                      setModules(modules.filter(x => x !== m.key));
                    } else {
                      setModules([...modules, m.key]);
                    }
                  }}>
                  {modules.includes(m.key) ? '✓ ' : ''}{m.label}
                </Tag>
              ))}
            </div>
          </div>
          <Input.TextArea
            value={userInstructions}
            onChange={(e) => setUserInstructions(e.target.value)}
            placeholder="可选：输入自定义要求，如「重点聊消费板块」「语气更轻松」"
            autoSize={{ minRows: 1, maxRows: 3 }}
            style={{
              background: '#1a1e28', borderColor: '#313a4d', color: '#d0d0d0',
              fontSize: 12, marginBottom: 12, resize: 'none',
            }}
          />
          {formattingXhs ? (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <Spin tip={pf.spinTip} />
            </div>
          ) : (
            <XhsPreview
              xhsData={xhsData}
              loading={formattingXhs}
              onFormat={contentId ? handleFormatXhs : null}
              onVerify={xhsData ? handleVerify : null}
              verifyLoading={verifying}
              verificationResult={verificationResult}
              platform={pf}
            />
          )}
        </div>
      </div>

      {/* 底部：历史列表 */}
      <div style={{
        padding: '16px 20px', borderRadius: 10,
        background: '#141720', border: '1px solid #252a36',
      }}>
        <div style={{
          color: '#8c8c8c', fontSize: 12, marginBottom: 12,
          borderBottom: '1px solid #252a36', paddingBottom: 6,
        }}>
          历史内容
        </div>
        <Table
          dataSource={historyList}
          columns={historyColumns}
          rowKey="id"
          size="small"
          loading={loadingHistory}
          pagination={{ pageSize: 5, size: 'small' }}
          expandable={{ expandedRowRender }}
          style={{ background: 'transparent' }}
          locale={{ emptyText: <span style={{ color: '#555' }}>暂无历史内容</span> }}
        />
      </div>

      <style>{`
        .content-ops-page .ant-table {
          background: transparent !important;
        }
        .content-ops-page .ant-table-thead > tr > th {
          background: #1a1e28 !important;
          color: #b0bec5 !important;
          font-weight: 600;
          font-size: 12px;
          border-bottom: 1px solid #313a4d !important;
        }
        .content-ops-page .ant-table-thead > tr > th::before {
          display: none !important;
        }
        .content-ops-page .ant-table-tbody > tr > td {
          background: #141720 !important;
          color: #d0d0d0 !important;
          font-size: 12px;
          border-bottom: 1px solid #252a36 !important;
        }
        .content-ops-page .ant-table-tbody > tr:hover > td {
          background: #1a1e28 !important;
        }
        .content-ops-page .ant-table-cell {
          border-color: #252a36 !important;
        }
        .content-ops-page .ant-table-placeholder .ant-table-cell {
          background: #141720 !important;
        }
        .content-ops-page .ant-pagination .ant-pagination-item {
          background: #1a1e28 !important;
          border-color: #313a4d !important;
        }
        .content-ops-page .ant-pagination .ant-pagination-item a {
          color: #d0d0d0 !important;
        }
        .content-ops-page .ant-pagination .ant-pagination-item-active {
          background: #1890ff !important;
          border-color: #1890ff !important;
        }
        .content-ops-page .ant-pagination .ant-pagination-item-active a {
          color: #fff !important;
        }
        .content-ops-page .ant-spin-text {
          color: #8c8c8c !important;
        }
        .content-ops-page .ant-spin .ant-spin-dot-item {
          background-color: #1890ff !important;
        }
        .content-ops-page .ant-empty-description {
          color: #555 !important;
        }
        .content-ops-page .ant-table-expanded-row > td {
          background: #141720 !important;
          border-bottom: 1px solid #252a36 !important;
        }
        .content-ops-page .ant-segmented {
          background: #1a1e28 !important;
          padding: 2px !important;
        }
        .content-ops-page .ant-segmented-item {
          color: #8c8c8c !important;
        }
        .content-ops-page .ant-segmented-item-selected {
          background: #252a36 !important;
          color: #e0e0e0 !important;
        }
        .content-ops-page .ant-input,
        .content-ops-page .ant-input:focus,
        .content-ops-page .ant-input:hover {
          background: #1a1e28 !important;
          border-color: #313a4d !important;
          color: #d0d0d0 !important;
          box-shadow: none !important;
        }
        .content-ops-page .ant-input::placeholder {
          color: #555 !important;
        }
      `}</style>
    </div>
  );
};

export default ContentOps;
