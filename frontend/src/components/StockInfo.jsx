import React from 'react';
import { Card, Row, Col, Typography, Statistic } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

const { Title } = Typography;

const StockInfo = ({ stockData }) => {
  // 计算涨跌幅和涨跌额
  const calculateChange = () => {
    if (!stockData || !stockData.current_price || !stockData.pre_close) {
      return { change: 0, changePercent: 0 };
    }
    const change = stockData.current_price - stockData.pre_close;
    const changePercent = (change / stockData.pre_close) * 100;
    return { change, changePercent };
  };

  const { change, changePercent } = calculateChange();
  const isPositive = change >= 0;

  return (
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Title level={4}>{stockData?.name || '未知'}</Title>
          <Title level={5} type="secondary">{stockData?.code || '未知'}</Title>
        </Col>
        <Col span={8}>
          <Statistic
            title="当前价格"
            value={stockData?.current_price || 0}
            precision={2}
            valueStyle={{ color: isPositive ? '#3f8600' : '#cf1322' }}
            prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="涨跌幅"
            value={changePercent}
            precision={2}
            valueStyle={{ color: isPositive ? '#3f8600' : '#cf1322' }}
            prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            suffix="%"
          />
          <Statistic
            title="涨跌额"
            value={change}
            precision={2}
            valueStyle={{ color: isPositive ? '#3f8600' : '#cf1322' }}
            prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          />
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={6}>
          <Statistic title="开盘价" value={stockData?.open_price || 0} precision={2} />
        </Col>
        <Col span={6}>
          <Statistic title="最高价" value={stockData?.high_price || 0} precision={2} />
        </Col>
        <Col span={6}>
          <Statistic title="最低价" value={stockData?.low_price || 0} precision={2} />
        </Col>
        <Col span={6}>
          <Statistic title="昨收价" value={stockData?.pre_close || 0} precision={2} />
        </Col>
      </Row>
    </Card>
  );
};

export default StockInfo; 
