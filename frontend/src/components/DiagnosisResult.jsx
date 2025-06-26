import React from 'react';
import { Card, Row, Col, Typography, Spin } from 'antd';
import ReactECharts from 'echarts-for-react';

const { Title, Text } = Typography;

const DiagnosisResult = ({ loading, result }) => {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0' }}>
        <Spin size="large" tip="AI 正在分析中..." />
      </div>
    );
  }

  if (!result) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0' }}>
        <Text>暂无诊断结果</Text>
      </div>
    );
  }

  // 打印技术指标数据用于调试
  console.log('DiagnosisResult 技术指标数据:', result.historical_data);

  // 技术面分析图表配置
  const technicalChartOption = {
    title: {
      text: '技术指标分析',
      textStyle: { color: '#fff' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['EMA5', 'EMA20', 'EMA60'],
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: result.historical_data?.map(item => item.time) || [],
      axisLabel: { color: '#fff' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#fff' }
    },
    series: [
      {
        name: 'EMA5',
        type: 'line',
        data: result.historical_data?.map(item => item.EMA5) || [],
        smooth: true,
        lineStyle: { color: '#FFD700' }
      },
      {
        name: 'EMA20',
        type: 'line',
        data: result.historical_data?.map(item => item.EMA20) || [],
        smooth: true,
        lineStyle: { color: '#87CEEB' }
      },
      {
        name: 'EMA60',
        type: 'line',
        data: result.historical_data?.map(item => item.EMA60) || [],
        smooth: true,
        lineStyle: { color: '#FF69B4' }
      }
    ]
  };

  // 资金流向分析图表配置
  const capitalFlowChartOption = {
    title: {
      text: '资金流向分析',
      textStyle: { color: '#fff' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['主力资金', '超大单', '大单', '中单', '小单'],
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: result.capital_flow?.historical?.map(item => item.date) || [],
      axisLabel: { color: '#fff' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#fff' }
    },
    series: [
      {
        name: '主力资金',
        type: 'line',
        data: result.capital_flow?.historical?.map(item => item.main_in_flow) || [],
        smooth: true
      },
      {
        name: '超大单',
        type: 'line',
        data: result.capital_flow?.historical?.map(item => item.super_in_flow) || [],
        smooth: true
      },
      {
        name: '大单',
        type: 'line',
        data: result.capital_flow?.historical?.map(item => item.big_in_flow) || [],
        smooth: true
      },
      {
        name: '中单',
        type: 'line',
        data: result.capital_flow?.historical?.map(item => item.mid_in_flow) || [],
        smooth: true
      },
      {
        name: '小单',
        type: 'line',
        data: result.capital_flow?.historical?.map(item => item.sml_in_flow) || [],
        smooth: true
      }
    ]
  };

  // 资金分布图表配置
  const capitalDistributionChartOption = {
    title: {
      text: '资金分布分析',
      textStyle: { color: '#fff' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['买入量', '卖出量'],
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: result.capital_distribution?.distribution?.map(item => item.update_time) || [],
      axisLabel: { color: '#fff' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#fff' }
    },
    series: [
      {
        name: '买入量',
        type: 'bar',
        data: result.capital_distribution?.distribution?.map(item => 
          item.capital_in.super + item.capital_in.big + item.capital_in.mid + item.capital_in.small
        ) || [],
        itemStyle: {
          color: '#00b578'
        }
      },
      {
        name: '卖出量',
        type: 'bar',
        data: result.capital_distribution?.distribution?.map(item => 
          item.capital_out.super + item.capital_out.big + item.capital_out.mid + item.capital_out.small
        ) || [],
        itemStyle: {
          color: '#ff4d4f'
        }
      }
    ]
  };

  // 基本面分析图表配置
  const fundamentalChartOption = {
    title: {
      text: '基本面指标分析',
      textStyle: { color: '#fff' }
    },
    tooltip: {
      trigger: 'item'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      textStyle: { color: '#fff' }
    },
    series: [
      {
        name: '基本面指标',
        type: 'pie',
        radius: '50%',
        data: [
          { value: 1048, name: '盈利能力' },
          { value: 735, name: '成长性' },
          { value: 580, name: '运营效率' },
          { value: 484, name: '偿债能力' },
          { value: 300, name: '现金流' }
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  };

  // 期权市场分析图表配置
  const optionsChartOption = {
    title: {
      text: '期权市场分析',
      textStyle: { color: '#fff' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['看涨期权', '看跌期权'],
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月'],
      axisLabel: { color: '#fff' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#fff' }
    },
    series: [
      {
        name: '看涨期权',
        type: 'bar',
        data: [320, 332, 301, 334, 390, 330]
      },
      {
        name: '看跌期权',
        type: 'bar',
        data: [220, 182, 191, 234, 290, 330]
      }
    ]
  };

  return (
    <div style={{ padding: '20px' }}>
      <Row gutter={[16, 16]}>
        {/* 技术面分析 */}
        <Col span={24}>
          <Card
            title={<Title level={4} style={{ margin: 0, color: '#fff' }}>技术面分析</Title>}
            style={{ background: '#1a1a1a', border: '1px solid #333' }}
          >
            <Row gutter={[16, 16]}>
              <Col span={16}>
                <ReactECharts
                  option={technicalChartOption}
                  style={{ height: '300px' }}
                  theme="dark"
                />
              </Col>
              <Col span={8}>
                <Text style={{ color: '#fff' }}>{result.technical}</Text>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 资金面分析 */}
        <Col span={24}>
          <Card
            title={<Title level={4} style={{ margin: 0, color: '#fff' }}>资金面分析</Title>}
            style={{ background: '#1a1a1a', border: '1px solid #333' }}
          >
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <ReactECharts
                  option={capitalFlowChartOption}
                  style={{ height: '300px' }}
                  theme="dark"
                />
              </Col>
              <Col span={12}>
                <ReactECharts
                  option={capitalDistributionChartOption}
                  style={{ height: '300px' }}
                  theme="dark"
                />
              </Col>
            </Row>
            <Row style={{ marginTop: '16px' }}>
              <Col span={24}>
                <Text style={{ color: '#fff' }}>{result.capital}</Text>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 基本面分析 */}
        <Col span={24}>
          <Card
            title={<Title level={4} style={{ margin: 0, color: '#fff' }}>基本面分析</Title>}
            style={{ background: '#1a1a1a', border: '1px solid #333' }}
          >
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <ReactECharts
                  option={fundamentalChartOption}
                  style={{ height: '300px' }}
                  theme="dark"
                />
              </Col>
              <Col span={12}>
                <Text style={{ color: '#fff' }}>{result.fundamental}</Text>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 期权市场分析 */}
        <Col span={24}>
          <Card
            title={<Title level={4} style={{ margin: 0, color: '#fff' }}>期权市场分析</Title>}
            style={{ background: '#1a1a1a', border: '1px solid #333' }}
          >
            <Row gutter={[16, 16]}>
              <Col span={16}>
                <ReactECharts
                  option={optionsChartOption}
                  style={{ height: '300px' }}
                  theme="dark"
                />
              </Col>
              <Col span={8}>
                <Text style={{ color: '#fff' }}>{result.options}</Text>
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 综合建议 */}
        <Col span={24}>
          <Card
            title={<Title level={4} style={{ margin: 0, color: '#fff' }}>综合建议</Title>}
            style={{ background: '#1a1a1a', border: '1px solid #333' }}
          >
            <Text style={{ color: '#fff' }}>{result.recommendation}</Text>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DiagnosisResult; 
