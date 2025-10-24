import React, { useState, useEffect } from 'react';
import { Card, Table, Tag, Spin, Alert, Select, Button, Space, Typography, Tooltip } from 'antd';
import { 
  TrophyOutlined, 
  RiseOutlined, 
  FallOutlined, 
  ReloadOutlined,
  BarChartOutlined,
  GlobalOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

const PlateRanking = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const [selectedMarket, setSelectedMarket] = useState('HK');
  const [selectedType, setSelectedType] = useState('CONCEPT');
  const [selectedDate, setSelectedDate] = useState('latest'); // 新增：选中的日期
  const [lastUpdate, setLastUpdate] = useState(null);
  const [collapsed, setCollapsed] = useState(true);

  // 生成最近7天的日期选项
  const generateDateOptions = () => {
    const options = [
      { value: 'latest', label: '最新数据', icon: '🕐' }
    ];
    
    const today = new Date();
    for (let i = 1; i <= 7; i++) {
      const date = new Date(today);
      date.setDate(today.getDate() - i);
      const dateStr = date.toISOString().slice(0, 10).replace(/-/g, '');
      const displayDate = date.toISOString().slice(0, 10);
      const dayName = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()];
      
      options.push({
        value: dateStr,
        label: `${displayDate} ${dayName}`,
        icon: '📅'
      });
    }
    
    return options;
  };

  const dateOptions = generateDateOptions();

  const markets = [
    { value: 'HK', label: '港股', icon: '🇭🇰' },
    { value: 'SH', label: '上证', icon: '🇨🇳' },
    { value: 'SZ', label: '深证', icon: '🇨🇳' },
    { value: 'US', label: '美股', icon: '🇺🇸' }
  ];

  const plateTypes = [
    { value: 'CONCEPT', label: '概念板块', icon: '💡' },
    { value: 'INDUSTRY', label: '行业板块', icon: '🏭' }
  ];

  const fetchPlateRanking = async (market = selectedMarket, type = selectedType, date = selectedDate) => {
    setLoading(true);
    setError(null);
    
    try {
      let url = `http://localhost:5001/api/plate/ranking/${market}/${type}`;
      
      // 如果不是最新数据，添加日期参数
      if (date !== 'latest') {
        url += `?date=${date}`;
      }
      
      const response = await fetch(url);
      const result = await response.json();
      
      if (result.success) {
        const rankings = result.rankings || [];
        // 为每条记录添加排名
        const rankedData = rankings.map((item, index) => ({
          ...item,
          rank: index + 1
        }));
        setData(rankedData);
        setLastUpdate(new Date());
      } else {
        setError(result.error || '获取板块排行失败');
        setData([]);
      }
    } catch (err) {
      setError('网络请求失败，请检查后端服务');
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlateRanking();
  }, []);

  const handleRefresh = (e) => {
    e.stopPropagation(); // 阻止事件冒泡
    fetchPlateRanking();
  };

  const handleMarketChange = (market) => {
    setSelectedMarket(market);
    fetchPlateRanking(market, selectedType, selectedDate);
  };

  const handleTypeChange = (type) => {
    setSelectedType(type);
    fetchPlateRanking(selectedMarket, type, selectedDate);
  };

  const handleDateChange = (date) => {
    setSelectedDate(date);
    fetchPlateRanking(selectedMarket, selectedType, date);
  };

  const handleSelectClick = (e) => {
    e.stopPropagation(); // 阻止事件冒泡
  };

  const getChangeColor = (changePercent) => {
    if (changePercent > 0) return '#ff4d4f'; // 红涨
    if (changePercent < 0) return '#52c41a'; // 绿跌
    return '#8c8c8c';
  };

  const getChangeIcon = (changePercent) => {
    if (changePercent > 0) return <RiseOutlined style={{ color: '#ff4d4f' }} />; // 红涨
    if (changePercent < 0) return <FallOutlined style={{ color: '#52c41a' }} />; // 绿跌
    return null;
  };

  const columns = [
    {
      title: '排名',
      dataIndex: 'rank',
      key: 'rank',
      width: 80,
      render: (_, __, index) => {
        const rank = index + 1;
        let color = '#8c8c8c';
        let icon = null;
        
        if (rank === 1) {
          color = '#faad14';
          icon = <TrophyOutlined style={{ color: '#faad14' }} />;
        } else if (rank === 2) {
          color = '#d9d9d9';
          icon = <TrophyOutlined style={{ color: '#d9d9d9' }} />;
        } else if (rank === 3) {
          color = '#b87333';
          icon = <TrophyOutlined style={{ color: '#b87333' }} />;
        }
        
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {icon}
            <span style={{ color, fontWeight: 'bold', fontSize: '14px' }}>{rank}</span>
          </div>
        );
      },
    },
    {
      title: '板块名称',
      dataIndex: 'plate_name',
      key: 'plate_name',
      render: (name, record) => (
        <div>
          <div style={{ fontWeight: 'bold', fontSize: '14px', color: '#e6f7ff' }}>{name}</div>
          <div style={{ fontSize: '12px', color: '#8c8c8c' }}>{record.plate_code}</div>
        </div>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'current_price',
      key: 'current_price',
      width: 100,
      render: (price) => (
        <Text strong style={{ fontSize: '14px', color: '#e6f7ff' }}>
          {price?.toFixed(2) || '-'}
        </Text>
      ),
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_percent',
      key: 'change_percent',
      width: 120,
      render: (changePercent) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {getChangeIcon(changePercent)}
          <Text 
            strong 
            style={{ 
              color: getChangeColor(changePercent),
              fontSize: '14px',
              fontWeight: 'bold'
            }}
          >
            {changePercent > 0 ? '+' : ''}{changePercent?.toFixed(2) || '0.00'}%
          </Text>
        </div>
      ),
      sorter: (a, b) => a.change_percent - b.change_percent,
      defaultSortOrder: 'descend',
    },
    {
      title: '涨跌额',
      dataIndex: 'change',
      key: 'change',
      width: 100,
      render: (change) => (
        <Text style={{ color: getChangeColor(change), fontSize: '13px', fontWeight: 'bold' }}>
          {change > 0 ? '+' : ''}{change?.toFixed(2) || '0.00'}
        </Text>
      ),
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 120,
      render: (volume) => (
        <Text style={{ fontSize: '13px', color: '#e6f7ff' }}>
          {volume ? (volume / 10000).toFixed(0) + '万' : '-'}
        </Text>
      ),
    },
    {
      title: '成交额',
      dataIndex: 'turnover',
      key: 'turnover',
      width: 120,
      render: (turnover) => (
        <Text style={{ fontSize: '13px', color: '#e6f7ff' }}>
          {turnover ? (turnover / 100000000).toFixed(2) + '亿' : '-'}
        </Text>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'update_time',
      key: 'update_time',
      width: 140,
      render: (time) => (
        <Text style={{ fontSize: '12px', color: '#8c8c8c' }}>
          {time ? time.split(' ')[1] : '-'}
        </Text>
      ),
    },
  ];

  return (
    <Card
      style={{
        background: 'rgba(30,34,44,0.98)',
        borderRadius: 10,
        boxShadow: '0 2px 8px #0003',
        border: 'none',
        marginTop: 18
      }}
      styles={{ body: { padding: 16 } }}
    >
      <div
        style={{
          color: '#faad14',
          fontWeight: 700,
          fontSize: 17,
          display: 'flex',
          alignItems: 'center',
          marginBottom: 8,
          cursor: 'pointer',
          userSelect: 'none',
          justifyContent: 'space-between'
        }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <span style={{ display: 'flex', alignItems: 'center' }}>
          <BarChartOutlined style={{ color: '#faad14', marginRight: 8, fontSize: '18px' }} />
          板块排行
          <span style={{ marginLeft: 8, fontSize: 16 }}>
            {collapsed ? <DownOutlined /> : <UpOutlined />}
          </span>
        </span>
        
        <Space>
          <Select
            value={selectedMarket}
            onChange={handleMarketChange}
            onClick={handleSelectClick}
            style={{ width: 100 }}
            size="small"
            styles={{ popup: { root: { background: '#ffffff', color: '#000000' } } }}
          >
            {markets.map(market => (
              <Option key={market.value} value={market.value}>
                <span style={{ marginRight: 4 }}>{market.icon}</span>
                <span style={{ color: '#000000' }}>{market.label}</span>
              </Option>
            ))}
          </Select>
          
          <Select
            value={selectedType}
            onChange={handleTypeChange}
            onClick={handleSelectClick}
            style={{ width: 120 }}
            size="small"
            styles={{ popup: { root: { background: '#ffffff', color: '#000000' } } }}
          >
            {plateTypes.map(type => (
              <Option key={type.value} value={type.value}>
                <span style={{ marginRight: 4 }}>{type.icon}</span>
                <span style={{ color: '#000000' }}>{type.label}</span>
              </Option>
            ))}
          </Select>
          
          <Select
            value={selectedDate}
            onChange={handleDateChange}
            onClick={handleSelectClick}
            style={{ width: 140 }}
            size="small"
            styles={{ popup: { root: { background: '#ffffff', color: '#000000' } } }}
          >
            {dateOptions.map(date => (
              <Option key={date.value} value={date.value}>
                <span style={{ marginRight: 4 }}>{date.icon}</span>
                <span style={{ color: '#000000' }}>{date.label}</span>
              </Option>
            ))}
          </Select>
          
          <Tooltip title="刷新数据">
            <Button
              type="text"
              icon={<ReloadOutlined style={{ color: '#faad14' }} />}
              onClick={handleRefresh}
              loading={loading}
              size="small"
            />
          </Tooltip>
        </Space>
      </div>
      
      {!collapsed && (
        <>
      {error && (
        <Alert
          message="获取数据失败"
          description={error}
          type="error"
          showIcon
          style={{ 
            marginBottom: 12,
            background: '#232a36',
            border: '1px solid #ff4d4f',
            color: '#e6f7ff'
          }}
        />
      )}
      
      <div style={{ marginTop: 12 }}>
        {lastUpdate && (
          <div style={{ 
            marginBottom: 12, 
            fontSize: '12px', 
            color: '#8c8c8c',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            <GlobalOutlined style={{ color: '#8c8c8c' }} />
            {selectedDate === 'latest' ? (
              <>最后更新: {lastUpdate.toLocaleString()}</>
            ) : (
              <>历史数据: {selectedDate.slice(0, 4)}-{selectedDate.slice(4, 6)}-{selectedDate.slice(6, 8)}</>
            )}
          </div>
        )}
        
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={data}
            rowKey="plate_code"
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => 
                `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
            }}
            size="small"
            scroll={{ x: 800 }}
            className="plate-ranking-table"
            style={{
              background: '#181c24',
              color: '#e6f7ff',
              borderRadius: 8,
              boxShadow: '0 2px 8px #0003'
            }}
            rowClassName={(record, index) => {
              if (index < 3) return 'top-ranking-row';
              return '';
            }}
          />
        </Spin>
        
        {data.length === 0 && !loading && !error && (
          <div style={{ 
            textAlign: 'center', 
            padding: '40px 0',
            color: '#8c8c8c',
            fontSize: '14px'
          }}>
            暂无数据
          </div>
        )}
      </div>
        </>
      )}
    </Card>
  );
};

export default PlateRanking; 
