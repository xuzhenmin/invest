import React from 'react';
import ReactECharts from 'echarts-for-react';

/**
 * 资金分布饼图组件
 * @param {Object[]} data - 资金分布数据，格式见 Futu/OpenD capital_distribution
 * @param {string} [title] - 图表标题
 */
export default function CapitalDistributionPie({ data = [], title = '资金分布' }) {
  // 取最新一条分布
  const latest = Array.isArray(data) && data.length > 0 ? data[data.length - 1] : null;
  // 组装饼图数据，健壮处理
  const getVal = (obj, key) => (obj && typeof obj[key] === 'number' ? obj[key] : 0);
  // 适配扁平字段格式
  const pieData = latest ? [
    { value: (latest.capital_in_super || 0) + (latest.capital_out_super || 0), name: '超级大户' },
    { value: (latest.capital_in_big || 0) + (latest.capital_out_big || 0), name: '大户' },
    { value: (latest.capital_in_mid || 0) + (latest.capital_out_mid || 0), name: '中户' },
    { value: (latest.capital_in_small || 0) + (latest.capital_out_small || 0), name: '小户' },
  ] : [];
  const option = {
    title: {
      text: title,
      left: 'center',
      top: 10,
      textStyle: { color: '#faad14', fontWeight: 700, fontSize: 16 }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 万元 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 10,
      top: 30,
      textStyle: { color: '#b0bec5', fontSize: 13 }
    },
    series: [
      {
        name: '资金分布',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#232a36',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          color: '#fff',
          fontWeight: 600,
          formatter: '{b}\n{d}%'
        },
        labelLine: {
          show: true,
          length: 16,
          length2: 10,
          lineStyle: { color: '#b0bec5' }
        },
        data: pieData
      }
    ]
  };
  return (
    <div style={{ width: '100%', height: 260, background: 'none' }}>
      {pieData.length > 0 ? (
        <ReactECharts option={option} style={{ width: '100%', height: 240 }} />
      ) : (
        <div style={{ color: '#b0bec5', textAlign: 'center', paddingTop: 60 }}>暂无资金分布数据</div>
      )}
    </div>
  );
} 
