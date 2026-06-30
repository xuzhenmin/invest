import React from 'react';
import { Button, Empty, message, Tag } from 'antd';
import { CopyOutlined, EditOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import VerificationReport from './VerificationReport';

const XhsPreview = ({ xhsData, loading, onFormat, onVerify, verifyLoading, verificationResult, platform, showActions = true }) => {
  const pf = platform || {};
  if (!xhsData) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Empty
          description={<span style={{ color: '#666' }}>{pf.emptyTip || '生成素材后点击下方按钮'}</span>}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ opacity: 0.6 }}
        />
        <Button type="primary" ghost size="small" icon={<EditOutlined />}
          loading={loading} onClick={onFormat}
          style={{ marginTop: 12 }} disabled={!onFormat}>
          {pf.generateBtnText || '生成内容'}
        </Button>
      </div>
    );
  }

  const { title, body, tags, cover_text } = xhsData;

  const handleCopyAll = () => {
    const tagStr = (tags || []).join(' ');
    const fullText = `${title}\n\n${body}\n\n${tagStr}`;
    navigator.clipboard.writeText(fullText).then(() => {
      message.success('已复制到剪贴板');
    }).catch(() => {
      const textarea = document.createElement('textarea');
      textarea.value = fullText;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      message.success('已复制到剪贴板');
    });
  };

  const handleCopyTitle = () => {
    navigator.clipboard.writeText(title || '').then(() => message.success('标题已复制'));
  };

  return (
    <div>
      <div style={{
        padding: '16px 20px', marginBottom: 12, borderRadius: 8,
        background: 'linear-gradient(135deg, #1a1e28, #252a36)',
        border: '1px solid #313a4d',
      }}>
        <div style={{ color: '#666', fontSize: 10, marginBottom: 6 }}>标题</div>
        <div style={{
          color: '#fff', fontSize: 18, fontWeight: 600, lineHeight: 1.4,
          cursor: 'pointer',
        }} onClick={handleCopyTitle}>
          {title}
        </div>
      </div>

      {cover_text && (
        <div style={{
          padding: '10px 14px', marginBottom: 12, borderRadius: 6,
          background: '#1a1e28', border: '1px dashed #faad14',
        }}>
          <div style={{ color: '#faad14', fontSize: 10, marginBottom: 4 }}>封面文案</div>
          <div style={{ color: '#e0e0e0', fontSize: 13 }}>{cover_text}</div>
        </div>
      )}

      <div style={{
        padding: '16px 20px', marginBottom: 12, borderRadius: 8,
        background: '#1a1e28', border: '1px solid #313a4d',
        maxHeight: 400, overflowY: 'auto',
      }}>
        <div style={{ color: '#666', fontSize: 10, marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
          <span>正文</span>
          <span style={{ color: '#8c8c8c' }}>{body ? body.length : 0} 字</span>
        </div>
        <div style={{
          color: '#d0d0d0', fontSize: 13, lineHeight: 1.8,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {body}
        </div>
      </div>

      {tags && tags.length > 0 && (
        <div style={{
          padding: '10px 14px', marginBottom: 16, borderRadius: 6,
          background: '#1a1e28', border: '1px solid #313a4d',
        }}>
          <div style={{ color: '#666', fontSize: 10, marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
            <span>话题标签</span>
            <span style={{ color: '#8c8c8c' }}>{tags.join('').length} 字 / {tags.length} 个</span>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {tags.map((tag, i) => (
              <Tag key={i} color="blue" style={{ margin: 0, fontSize: 11 }}>{tag}</Tag>
            ))}
          </div>
        </div>
      )}

      {showActions && (
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginBottom: 12 }}>
          <Button type="primary" icon={<CopyOutlined />} onClick={handleCopyAll}>
            复制全文
          </Button>
          {onVerify && (
            <Button icon={<SafetyCertificateOutlined />}
              loading={verifyLoading} onClick={onVerify}
              style={{ borderColor: '#52c41a', color: '#52c41a' }}>
              验证
            </Button>
          )}
          <Button ghost icon={<EditOutlined />} loading={loading} onClick={onFormat}
            style={{ borderColor: '#313a4d', color: '#d0d0d0' }}>
            {pf.regenerateBtnText || '重新生成'}
          </Button>
        </div>
      )}

      {(verificationResult || verifyLoading) && (
        <div style={{
          padding: '12px 16px', borderRadius: 8,
          background: '#141720', border: '1px solid #252a36',
        }}>
          <div style={{ color: '#8c8c8c', fontSize: 10, marginBottom: 8,
            borderBottom: '1px solid #252a36', paddingBottom: 4 }}>
            验证报告
          </div>
          <VerificationReport verificationResult={verificationResult} loading={verifyLoading} />
        </div>
      )}
    </div>
  );
};

export default XhsPreview;
