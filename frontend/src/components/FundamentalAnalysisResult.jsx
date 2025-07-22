import React from 'react';
import { Card, Row, Col, Typography, Tag, Tooltip, Divider, Space } from 'antd';
import { StockOutlined, ThunderboltOutlined, CheckCircleTwoTone, BellOutlined, FundOutlined, PieChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';

const { Title, Text } = Typography;

// 通用安全文本渲染函数
function safeText(val, preferKeys = []) {
  if (val == null) return '';
  if (typeof val === 'string' || typeof val === 'number') return val;
  if (Array.isArray(val)) return val.map(v => safeText(v, preferKeys)).join('；');
  if (typeof val === 'object') {
    for (const key of preferKeys) {
      if (typeof val[key] === 'string' || typeof val[key] === 'number') return val[key];
    }
    for (const k in val) {
      if (typeof val[k] === 'string' || typeof val[k] === 'number') return val[k];
    }
    return JSON.stringify(val);
  }
  return String(val);
}

function getValuationColor(judgment) {
  if (!judgment) return 'default';
  if (judgment.includes('严重高估')) return 'red';
  if (judgment.includes('高估')) return 'orange';
  if (judgment.includes('正常')) return 'blue';
  if (judgment.includes('低估')) return 'green';
  if (judgment.includes('严重低估')) return 'cyan';
  return 'default';
}

const FundamentalAnalysisResult = ({ data }) => {
  if (!data) return null;
  // 兼容不同结构
  const summary = safeText(data.summary);
  // 解析观点
  const viewpoints = Array.isArray(data.viewpoints)
    ? data.viewpoints.map(vp => safeText(vp, ['viewpoint', 'title']))
    : (data.viewpoints != null ? [safeText(data.viewpoints, ['viewpoint', 'title'])] : []);
  // 解析理由
  const reasons = Array.isArray(data.reasons)
    ? data.reasons.map(r => safeText(r, ['analysis', 'reason', 'detail']))
    : (data.reasons != null ? [safeText(data.reasons, ['analysis', 'reason', 'detail'])] : []);
  const advice = data.advice;
  // 兼容 advice 字段为对象（如 {操作建议, 理由}）或字符串
  const adviceText = safeText(advice, ['recommendation', '操作建议', 'advice']);
  const adviceReason = safeText(advice, ['reason', '理由']);
  const forecast = data.forecast;
  // 兼容 forecast 字段为对象或字符串
  const forecastText = safeText(forecast, ['1-2_year_outlook', 'outlook', 'performance', 'price_target', 'factors']);
  const forecastBasis = safeText(forecast, ['basis']);
  const valuation = data.valuation;

  // 估值条形图数据
  // let valuationChart = null;
  // if (valuation && typeof valuation === 'object') {
  //   const items = [];
  //   if (valuation.pe_analysis) items.push({ name: 'PE', value: parseFloat((valuation.pe_analysis.match(/([\d.]+)/) || [])[1] || 0), desc: valuation.pe_analysis });
  //   if (valuation.pb_analysis) items.push({ name: 'PB', value: parseFloat((valuation.pb_analysis.match(/([\d.]+)/) || [])[1] || 0), desc: valuation.pb_analysis });
  //   if (valuation.dividend_yield) items.push({ name: '股息率', value: parseFloat((valuation.dividend_yield.match(/([\d.]+)/) || [])[1] || 0), desc: valuation.dividend_yield });
  //   valuationChart = {
  //     tooltip: { trigger: 'item' },
  //     grid: { left: '5%', right: '5%', bottom: '10%', top: '10%' },
  //     xAxis: { type: 'category', data: items.map(i => i.name), axisLabel: { color: '#b0bec5' } },
  //     yAxis: { type: 'value', axisLabel: { color: '#b0bec5' } },
  //     series: [{
  //       data: items.map(i => i.value),
  //       type: 'bar',
  //       itemStyle: { color: '#13c2c2', borderRadius: [6,6,0,0] },
  //       label: { show: true, position: 'top', color: '#faad14' }
  //     }]
  //   };
  // }

  // 观点与理由合并
  const viewpointReasonList = viewpoints.map((vp, i) => ({
    vp,
    reason: reasons[i] || ''
  }));

  return (
    <div style={{ padding: 0 }}>
      {/* 总体评价 */}
      {summary && (
        <Card style={{ background: 'linear-gradient(90deg,#13c2c2,#1890ff)', color: '#fff', borderRadius: 12, marginBottom: 12, boxShadow: '0 2px 12px #13c2c244' }} bodyStyle={{ padding: 18 }}>
          <Title level={4} style={{ color: '#fff', margin: 0, display: 'flex', alignItems: 'center' }}>
            <StockOutlined style={{ marginRight: 10, fontSize: 22, color: '#fff' }} />{summary}
          </Title>
        </Card>
      )}
      {/* 观点与理由 */}
      {viewpointReasonList.length > 0 && (
        <Card style={{ background: '#181c24', borderRadius: 12, marginBottom: 12, border: 'none', boxShadow: '0 2px 8px #0002' }} bodyStyle={{ padding: 16 }}>
          <Title level={5} style={{ color: '#faad14', margin: 0, marginBottom: 8 }}><ThunderboltOutlined style={{ marginRight: 6, color: '#faad14' }} />核心观点</Title>
          <Row gutter={[12, 12]}>
            {viewpointReasonList.map((item, i) => (
              <Col span={12} key={i}>
                <Card size="small" style={{ background: '#232a36', borderRadius: 8, border: '1px solid #13c2c2', marginBottom: 0 }} bodyStyle={{ padding: 12 }}>
                  <div style={{ fontWeight: 700, color: '#13c2c2', fontSize: 15, marginBottom: 4 }}><ThunderboltOutlined style={{ marginRight: 4 }} />{item.vp}</div>
                  {item.reason && <div style={{ color: '#b0bec5', fontSize: 13, marginTop: 2 }}>{item.reason}</div>}
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}
      {/* 估值分析 */}
      {valuation && (
        <Card style={{ background: '#232a36', borderRadius: 12, marginBottom: 12, border: 'none', boxShadow: '0 2px 8px #0002' }} bodyStyle={{ padding: 16 }}>
          <Title level={5} style={{ color: '#faad14', margin: 0, marginBottom: 8 }}><PieChartOutlined style={{ marginRight: 6, color: '#faad14' }} />估值分析</Title>
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            {valuation.judgment && (
              <Tag color={getValuationColor(valuation.judgment)} style={{ fontSize: 16, fontWeight: 700, padding: '2px 18px' }}>{valuation.judgment}</Tag>
            )}
            <div style={{ color: '#b0bec5', fontSize: 14 }}>
              {valuation.pe_analysis && <div><b>PE：</b>{valuation.pe_analysis}</div>}
              {valuation.pb_analysis && <div><b>PB：</b>{valuation.pb_analysis}</div>}
              {valuation.dividend_yield && <div><b>股息率：</b>{valuation.dividend_yield}</div>}
              {valuation.historical_range && <div><b>历史区间：</b>{valuation.historical_range}</div>}
            </div>
          </Space>
        </Card>
      )}
      {/* 操作建议 */}
      {adviceText && (
        <Card style={{ background: 'linear-gradient(90deg,#1890ff,#13c2c2)', borderRadius: 12, marginBottom: 12, color: '#fff', boxShadow: '0 2px 8px #13c2c244', border: 'none' }} bodyStyle={{ padding: 16 }}>
          <Title level={5} style={{ color: '#fff', margin: 0, marginBottom: 4 }}><CheckCircleTwoTone twoToneColor="#52c41a" style={{ marginRight: 6 }} />操作建议</Title>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{adviceText}</div>
          {adviceReason && <div style={{ color: '#e6f7ff', fontSize: 14, marginTop: 2 }}>{adviceReason}</div>}
        </Card>
      )}
      {/* 未来预测 */}
      {forecastText && (
        <Card style={{ background: '#181c24', borderRadius: 12, marginBottom: 12, border: 'none', boxShadow: '0 2px 8px #0002' }} bodyStyle={{ padding: 16 }}>
          <Title level={5} style={{ color: '#faad14', margin: 0, marginBottom: 4 }}><BellOutlined style={{ marginRight: 6, color: '#faad14' }} />未来预测</Title>
          <div style={{ color: '#e6f7ff', fontSize: 15, fontWeight: 600 }}>{forecastText}</div>
          {forecastBasis && <div style={{ color: '#b0bec5', fontSize: 13, marginTop: 2 }}>{forecastBasis}</div>}
        </Card>
      )}
    </div>
  );
};

export default FundamentalAnalysisResult; 
