import React from 'react';
import { Progress, Empty, Tag } from 'antd';
import {
  CheckCircleOutlined, WarningOutlined, CloseCircleOutlined,
  QuestionCircleOutlined, ClockCircleOutlined, DatabaseOutlined,
} from '@ant-design/icons';

const verdictConfig = {
  pass: { color: '#52c41a', icon: <CheckCircleOutlined />, label: '通过' },
  warning: { color: '#faad14', icon: <WarningOutlined />, label: '存疑' },
  fail: { color: '#ff4d4f', icon: <CloseCircleOutlined />, label: '错误' },
  unverifiable: { color: '#8c8c8c', icon: <QuestionCircleOutlined />, label: '无法验证' },
};

const VerificationReport = ({ verificationResult, loading }) => {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c', fontSize: 12 }}>
        正在核验内容数据...
      </div>
    );
  }

  if (!verificationResult) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Empty
          description={<span style={{ color: '#555', fontSize: 12 }}>转写完成后可验证内容数据</span>}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ opacity: 0.5 }}
        />
      </div>
    );
  }

  const {
    overall_score,
    overall_assessment,
    summary,
    verified_at,
    verdicts = [],
    claim_verdicts = [],
    data_fetch_failures = [],
  } = verificationResult;

  const allVerdicts = verdicts.length > 0 ? verdicts : claim_verdicts;

  const scoreColor = overall_score == null ? '#8c8c8c'
    : overall_score >= 80 ? '#52c41a'
    : overall_score >= 60 ? '#faad14'
    : '#ff4d4f';

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '12px 16px', marginBottom: 12, borderRadius: 8,
        background: 'linear-gradient(135deg, #1a1e28, #252a36)',
        border: '1px solid #313a4d',
      }}>
        <Progress
          type="circle"
          percent={overall_score ?? 0}
          size={64}
          strokeColor={scoreColor}
          trailColor="#252a36"
          format={() => (
            <span style={{ color: scoreColor, fontSize: 18, fontWeight: 700 }}>
              {overall_score ?? '—'}
            </span>
          )}
        />
        <div style={{ flex: 1 }}>
          <div style={{ color: '#e0e0e0', fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
            可信度评分
          </div>
          <div style={{ color: '#8c8c8c', fontSize: 11, lineHeight: 1.5 }}>
            {overall_assessment || summary || '暂无评估'}
          </div>
          {verified_at && (
            <div style={{ color: '#555', fontSize: 10, marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
              <ClockCircleOutlined /> 验证时间: {verified_at}
            </div>
          )}
        </div>
      </div>

      {allVerdicts.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ color: '#8c8c8c', fontSize: 10, marginBottom: 8 }}>
            声明核验（{allVerdicts.length} 条）
          </div>
          {allVerdicts.map((v, i) => {
            const cfg = verdictConfig[v.verdict] || verdictConfig.unverifiable;
            return (
              <div key={i} style={{
                display: 'flex', gap: 0, marginBottom: 8, borderRadius: 6,
                overflow: 'hidden', border: '1px solid #252a36',
              }}>
                <div style={{ width: 4, background: cfg.color, flexShrink: 0 }} />
                <div style={{ flex: 1, padding: '10px 12px', background: '#1a1e28' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginBottom: 6,
                  }}>
                    <span style={{ color: '#d0d0d0', fontSize: 12, flex: 1 }}>
                      {v.claim || v.original_text || `声明 #${i + 1}`}
                    </span>
                    <Tag color={cfg.color} style={{
                      margin: 0, fontSize: 10, color: cfg.color,
                      background: 'transparent', border: `1px solid ${cfg.color}`,
                    }}>
                      {cfg.icon} {cfg.label}
                    </Tag>
                  </div>

                  {(v.real_value || v.actual_value) && (
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>
                      真实数据: <span style={{ color: cfg.color }}>{v.real_value || v.actual_value}</span>
                    </div>
                  )}

                  {v.deviation && (
                    <div style={{ fontSize: 11, color: cfg.color, marginBottom: 4 }}>
                      偏差: {v.deviation}
                    </div>
                  )}

                  {v.comment && (
                    <div style={{ color: '#666', fontSize: 11, lineHeight: 1.4 }}>
                      {v.comment}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {data_fetch_failures.length > 0 && (
        <div style={{
          padding: '8px 12px', borderRadius: 6,
          background: '#1a1e28', border: '1px solid #252a36',
          fontSize: 11, color: '#666', lineHeight: 1.5,
        }}>
          <span style={{ color: '#8c8c8c' }}>数据源异常：</span>
          {data_fetch_failures.join('；')}
        </div>
      )}
    </div>
  );
};

export default VerificationReport;
