import React, { useState, useEffect } from 'react';
import { Modal, Spin, Empty, Table, Tag, message } from 'antd';
import { WalletOutlined } from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const PositionAnalysis = ({ userId, visible, onClose }) => {
  const [accountInfo, setAccountInfo] = useState(null);
  const [accountLoading, setAccountLoading] = useState(false);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [showTradeHistory, setShowTradeHistory] = useState(false);
  const [positionDetails, setPositionDetails] = useState([]);
  const [positionDetailsLoading, setPositionDetailsLoading] = useState(false);
  const [showPositionDetails, setShowPositionDetails] = useState(false);

  const fetchAccountInfo = async () => {
    if (!userId) return;
    
    try {
      setAccountLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/quant/account?user_id=${userId}`);
      
      // 处理字符串JSON响应 - 使用更安全的解析方式
      let data;
      if (typeof response.data === 'string') {
        try {
          // 先尝试直接解析，如果失败则处理NaN
          data = JSON.parse(response.data.replace(/\bNaN\b/g, 'null'));
        } catch (parseError) {
          console.error('JSON解析失败:', parseError);
          console.error('原始响应:', response.data);
          message.error('数据格式错误，请稍后重试');
          return;
        }
      } else {
        data = response.data;
      }
      
      if (data && data.success) {
        setAccountInfo(data.data);
      } else {
        const errorMsg = data?.message || '获取账户信息失败';
        console.error('获取账户信息失败:', errorMsg, { response, parsedData: data });
        message.error('获取账户信息失败: ' + errorMsg);
      }
    } catch (error) {
      console.error('获取持仓信息失败:', error);
    } finally {
      setAccountLoading(false);
    }
  };

  const fetchTradeHistory = async () => {
    if (!userId) return;
    
    // 如果已经显示交易记录，则切换显示状态
    if (showTradeHistory) {
      setShowTradeHistory(false);
      return;
    }
    
    try {
      setTradeLoading(true);
      
      // 如果已经有数据，直接显示
      if (tradeHistory && tradeHistory.length > 0) {
        setShowTradeHistory(true);
        setShowPositionDetails(false); // 确保关闭持仓明细
        return;
      }
      
      // 计算近一个月的日期范围，结束时间加一天确保包含当天所有交易
      const endDate = new Date();
      endDate.setDate(endDate.getDate() + 1); // 加一天确保包含当天
      
      const startDate = new Date();
      startDate.setMonth(startDate.getMonth() - 1);
      
      const startDateStr = startDate.toISOString().split('T')[0];
      const endDateStr = endDate.toISOString().split('T')[0];
      
      const response = await axios.get(
        `${API_BASE_URL}/api/quant/user/trades?user_id=${userId}&start_date=${startDateStr}&end_date=${endDateStr}`
      );
      
      // 处理字符串JSON响应 - 使用更安全的解析方式
      let data;
      if (typeof response.data === 'string') {
        try {
          // 先尝试直接解析，如果失败则处理NaN
          data = JSON.parse(response.data.replace(/\bNaN\b/g, 'null'));
        } catch (parseError) {
          console.error('JSON解析失败:', parseError);
          console.error('原始响应:', response.data);
          message.error('数据格式错误，请稍后重试');
          return;
        }
      } else {
        data = response.data;
      }
      
      if (data && data.success) {
        // 按时间倒序排序
        const sortedTrades = (data.data || []).sort((a, b) => 
          new Date(b.timestamp || b.trade_date) - new Date(a.timestamp || a.trade_date)
        );
        setTradeHistory(sortedTrades);
        setShowTradeHistory(true);
        setShowPositionDetails(false); // 确保关闭持仓明细
        
        if (sortedTrades.length === 0) {
          message.info('暂无交易记录');
        }
      } else {
        const errorMsg = data?.message || '未知错误';
        console.error('API返回错误:', errorMsg, { response, parsedData: data });
        message.error('获取交易记录失败: ' + errorMsg);
      }
    } catch (error) {
      console.error('获取交易记录失败:', error);
      message.error('获取交易记录失败，请稍后重试');
    } finally {
      setTradeLoading(false);
    }
  };

  const fetchPositionDetails = async () => {
    if (!userId) return;
    
    // 如果已经显示持仓明细，则切换显示状态
    if (showPositionDetails) {
      setShowPositionDetails(false);
      return;
    }
    
    try {
      setPositionDetailsLoading(true);
      
      // 如果已经有数据，直接显示
      if (positionDetails && positionDetails.length > 0) {
        setShowPositionDetails(true);
        setShowTradeHistory(false); // 确保关闭交易记录
        return;
      }
      
      const response = await axios.get(`${API_BASE_URL}/api/quant/positions/details?user_id=${userId}&active_only=false`);
      
      // 处理字符串JSON响应 - 使用更安全的解析方式
      let data;
      if (typeof response.data === 'string') {
        try {
          // 先尝试直接解析，如果失败则处理NaN
          data = JSON.parse(response.data.replace(/\bNaN\b/g, 'null'));
        } catch (parseError) {
          console.error('JSON解析失败:', parseError);
          console.error('原始响应:', response.data);
          message.error('数据格式错误，请稍后重试');
          return;
        }
      } else {
        data = response.data;
      }
      
      if (data && data.success) {
        const details = data.position_details || [];
        setPositionDetails(details);
        setShowPositionDetails(true);
        setShowTradeHistory(false); // 确保关闭交易记录
        
        if (details.length === 0) {
          message.info('暂无持仓明细');
        }
      } else {
        const errorMsg = data?.message || '未知错误';
        console.error('API返回错误:', errorMsg, { response, parsedData: data });
        message.error('获取持仓明细失败: ' + errorMsg);
      }
    } catch (error) {
      console.error('获取持仓明细失败:', error);
      message.error('获取持仓明细失败，请稍后重试');
    } finally {
      setPositionDetailsLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchAccountInfo();
      // 重置状态，但只在弹窗打开时执行一次
      setShowTradeHistory(false);
      setTradeHistory([]);
      setShowPositionDetails(false);
      setPositionDetails([]);
    }
  }, [visible]);

  const positionColumns = [
    {
      title: '股票信息',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 100,
      render: (text, record) => (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 12 }}>{record.name}</span>
          <span style={{ color: '#b0bec5', fontSize: 11 }}>{text}</span>
        </div>
      )
    },
    
    {
      title: '持仓数量',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 80,
      align: 'left',
      render: (text) => <span style={{ color: '#b0bec5' }}>{text.toLocaleString()}</span>
    },
    {
      title: '成本价',
      dataIndex: 'avgPrice',
      key: 'avgPrice',
      width: 70,
      align: 'left',
      render: (text) => <span style={{ color: '#b0bec5' }}>¥{text}</span>
    },
    {
      title: '当前价',
      dataIndex: 'currentPrice',
      key: 'currentPrice',
      width: 70,
      align: 'left',
      render: (text) => <span style={{ color: '#13c2c2', fontWeight: 600 }}>¥{text}</span>
    },
    {
      title: '市值',
      dataIndex: 'currentValue',
      key: 'currentValue',
      width: 90,
      align: 'right',
      render: (text) => <span style={{ color: '#13c2c2', fontWeight: 600 }}>¥{text}</span>
    },
    {
      title: '盈亏',
      dataIndex: 'profitLoss',
      key: 'profitLoss',
      width: 90,
      align: 'right',
      render: (text) => (
        <span style={{ 
          color: parseFloat(text) >= 0 ? '#ff4d4f' : '#52c41a',
          fontWeight: 600
        }}>
          ¥{text}
        </span>
      )
    },
    {
      title: '盈亏率',
      dataIndex: 'profitRate',
      key: 'profitRate',
      width: 70,
      align: 'right',
      render: (text) => (
        <span style={{ 
          color: parseFloat(text) >= 0 ? '#ff4d4f' : '#52c41a',
          fontWeight: 600
        }}>
          {text}%
        </span>
      )
    },
    {
      title: '持仓天数',
      dataIndex: 'hold_days',
      key: 'hold_days',
      width: 70,
      align: 'right',
      render: (text) => (
        <span style={{ color: '#faad14', fontWeight: 600 }}>
          {text || 0}天
        </span>
      )
    }
  ];

  const tradeColumns = [
    {
      title: '交易时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 80,
      render: (text) => (
        <span style={{ color: '#ffffff', fontSize: 12 }}>
          {text}
        </span>
      )
    },
    {
      title: '股票信息',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 80,
      render: (text, record) => (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 12 }}>{record.stock_name || record.name || '--'}</span>
          <span style={{ color: '#b0bec5', fontSize: 11 }}>
            {text}
          </span>
        </div>
      )
    },
    {
      title: '交易类型',
      dataIndex: 'action',
      key: 'action',
      width: 60,
      render: (text) => (
        <span style={{ 
          color: text === 'buy' ? '#52c41a' : '#ff4d4f',
          fontWeight: 600,
          fontSize: 11
        }}>
          {text === 'buy' ? '买入' : '卖出'}
        </span>
      )
    },
    {
      title: '成交价',
      dataIndex: 'price',
      key: 'price',
      width: 60,
      align: 'left',
      render: (text) => (
        <span style={{ color: '#b0bec5', fontWeight: 600 }}>¥{Number(text).toFixed(2)}</span>
      )
    },
    {
      title: '成交数量',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 60,
      align: 'left',
      render: (text) => (
        <span style={{ color: '#b0bec5', fontWeight: 600 }}>{text.toLocaleString()}</span>
      )
    },
    {
      title: '建议止盈价',
      dataIndex: 'sell_price',
      key: 'sell_price',
      width: 70,
      align: 'left',
      render: (text) => (
        <span style={{ color: '#ff4d4f', fontWeight: 600 }}>
          {text ? `¥${Number(text).toFixed(2)}` : '--'}
        </span>
      )
    },
    {
      title: '建议止损价',
      dataIndex: 'stop_loss',
      key: 'stop_loss',
      width: 70,
      align: 'left',
      render: (text) => (
        <span style={{ color: '#52c41a', fontWeight: 600 }}>
          {text ? `¥${Number(text).toFixed(2)}` : '--'}
        </span>
      )
    },
    {
      title: '总金额',
      dataIndex: 'total_cost',
      key: 'total_cost',
      width: 80,
      align: 'left',
      render: (text) => (
        <span style={{ color: '#13c2c2', fontWeight: 600 }}>
          ¥{Number(text).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
        </span>
      )
    },
    {
      title: '盈亏',
      dataIndex: 'profit',
      key: 'profit',
      width: 60,
      align: 'left',
      render: (text) => {
        if (!text && text !== 0) return <span style={{ color: '#b0bec5' }}>--</span>;
        const profitValue = parseFloat(text);
        return (
          <span style={{ 
            color: profitValue >= 0 ? '#ff4d4f' : '#52c41a',
            fontWeight: 600
          }}>
            ¥{Number(text).toFixed(2)}
          </span>
        );
      }
    },
    {
      title: '手续费',
      dataIndex: 'commission',
      key: 'commission',
      width: 80,
      align: 'right',
      render: (text) => (
        <span style={{ color: '#b0bec5' }}>¥{Number(text || 0).toFixed(2)}</span>
      )
    }
  ];

  const positionDetailsColumns = [
    {
      title: '股票信息',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 100,
      render: (text, record) => (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 12 }}>
            {record.diagnosis_data?.name || record.name || text}
          </span>
          <span style={{ color: '#b0bec5', fontSize: 11 }}>{text}</span>
        </div>
      )
    },
    {
      title: '买入时间',
      dataIndex: 'buy_date',
      key: 'buy_date',
      width: 80,
      render: (text) => (
        <span style={{ color: '#b0bec5', fontSize: 11 }}>
          {text ? new Date(text).toLocaleDateString('zh-CN') : '--'}
        </span>
      )
    },
    {
      title: '买入价格',
      dataIndex: 'buy_price',
      key: 'buy_price',
      width: 70,
      align: 'left',
      render: (text) => <span style={{ color: '#b0bec5' }}>¥{Number(text || 0).toFixed(2)}</span>
    },
    {
      title: '买入数量',
      dataIndex: 'original_quantity',
      key: 'original_quantity',
      width: 80,
      align: 'left',
      render: (text) => <span style={{ color: '#b0bec5' }}>{text.toLocaleString()}</span>
    },
    {
      title: '当前价格',
      dataIndex: 'currentPrice',
      key: 'current_price',
      width: 70,
      align: 'left',
      render: (text) => (
        <span style={{ color: '#13c2c2', fontWeight: 600 }}>
          ¥{Number(text || 0).toFixed(2)}
        </span>
      )
    },
    {
      title: '持仓数量',
      dataIndex: 'remaining_quantity',
      key: 'remaining_quantity',
      width: 80,
      align: 'left',
      render: (text) => <span style={{ color: '#b0bec5' }}>{text.toLocaleString()}</span>
    },
    {
      title: '成交价',
      dataIndex: 'sellPrice',
      key: 'sell_price',
      width: 80,
      align: 'right',
      render: (text, record) => {
        // 只显示已平仓持仓的实际卖出价格，持仓中的不显示成交价
        if (record.status === 'closed' && record.sell_records && record.sell_records.length > 0) {
          const lastSell = record.sell_records[record.sell_records.length - 1];
          return (
            <span style={{ color: '#ff4d4f', fontWeight: 600 }}>
              ¥{Number(lastSell.sell_price || 0).toFixed(2)}
            </span>
          );
        }
        // 持仓中的不显示成交价
        return (
          <span style={{ color: '#b0bec5', fontSize: 11 }}>
            --
          </span>
        );
      }
    },
    {
      title: '总成本',
      dataIndex: 'total_cost',
      key: 'total_cost',
      width: 90,
      align: 'right',
      render: (text) => <span style={{ color: '#13c2c2', fontWeight: 600 }}>¥{Number(text || 0).toFixed(2)}</span>
    },
    {
      title: '当前市值',
      dataIndex: 'currentValue',
      key: 'current_value',
      width: 90,
      align: 'right',
      render: (text) => (
        <span style={{ color: '#13c2c2', fontWeight: 600 }}>¥{Number(text || 0).toFixed(2)}</span>
      )
    },
    {
      title: '浮动盈亏',
      dataIndex: 'profitLoss',
      key: 'profit_loss',
      width: 80,
      align: 'right',
      render: (text) => (
        <span style={{ 
          color: parseFloat(text || 0) >= 0 ? '#ff4d4f' : '#52c41a',
          fontWeight: 600
        }}>
          ¥{Number(text || 0).toFixed(2)}
        </span>
      )
    },
    {
      title: '盈亏率',
      dataIndex: 'profitRate',
      key: 'profit_rate',
      width: 70,
      align: 'right',
      render: (text) => (
        <span style={{ 
          color: parseFloat(text || 0) >= 0 ? '#ff4d4f' : '#52c41a',
          fontWeight: 600
        }}>
          {Number(text || 0).toFixed(2)}%
        </span>
      )
    },
    {
      title: '建议卖出价',
      dataIndex: 'diagnosis_data',
      key: 'sell_price',
      width: 80,
      align: 'right',
      render: (diagnosis_data) => (
        <span style={{ color: '#ff4d4f', fontWeight: 600 }}>
          ¥{Number(diagnosis_data?.sell_price || 0).toFixed(2)}
        </span>
      )
    },
    {
      title: '止损价',
      dataIndex: 'diagnosis_data',
      key: 'stop_loss',
      width: 70,
      align: 'right',
      render: (diagnosis_data) => (
        <span style={{ color: '#52c41a', fontWeight: 600 }}>
          ¥{Number(diagnosis_data?.stop_loss || 0).toFixed(2)}
        </span>
      )
    },
    {
      title: '综合评分',
      dataIndex: 'diagnosis_data',
      key: 'overall_score',
      width: 70,
      align: 'center',
      render: (diagnosis_data) => {
        const score = diagnosis_data?.overall_score || 0;
        let color = '#faad14';
        if (score >= 80) color = '#52c41a';
        else if (score < 60) color = '#ff4d4f';
        return (
          <span style={{ color, fontWeight: 600 }}>
            {score.toFixed(0)}
          </span>
        );
      }
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 60,
      align: 'center',
      render: (text) => (
        <span style={{ 
          color: text === 'active' ? '#52c41a' : '#ff4d4f',
          fontWeight: 600,
          fontSize: 11
        }}>
          {text === 'active' ? '持仓中' : '已平仓'}
        </span>
      )
    },
    {
      title: '订单ID',
      dataIndex: 'buy_order_id',
      key: 'buy_order_id',
      width: 100,
      render: (text) => (
        <span style={{ color: '#b0bec5', fontSize: 10 }}>
          {text?.substring(0, 8)}...
        </span>
      )
    }
  ];

  return (
    <Modal
      title={
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 8,
          color: '#ffffff',
          fontSize: 16,
          fontWeight: 600
        }}>
          <WalletOutlined style={{ color: '#722ed1' }} />
          📊 量化交易持仓分析
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      centered
      styles={{
        body: { 
          background: 'linear-gradient(135deg, #1a1d29 0%, #232a36 100%)', 
          color: '#ffffff',
          padding: 24
        },
        header: { background: '#1a1d29', borderBottom: '1px solid #313a4d' },
        mask: { background: 'rgba(0, 0, 0, 0.7)' }
      }}
    >
      {accountLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ color: '#b0bec5', marginTop: 12, fontSize: 14 }}>加载持仓数据中...</div>
        </div>
      ) : accountInfo ? (
        <div>
          <div style={{ 
            background: 'linear-gradient(135deg, #2a3a4f 0%, #1e2a3a 100%)', 
            borderRadius: 12, 
            padding: 16, 
            marginBottom: 20,
            border: '1px solid #3a4a5f'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
              <div>
                <div style={{ fontSize: 12, color: '#b0bec5', marginBottom: 4 }}>总资产</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#52c41a' }}>
                  ¥{accountInfo.account_value?.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '0.00'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#b0bec5', marginBottom: 4 }}>持仓市值</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#13c2c2' }}>
                  ¥{accountInfo.positions_value?.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '0.00'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#b0bec5', marginBottom: 4 }}>可用资金</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#faad14' }}>
                  ¥{accountInfo.current_cash?.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '0.00'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#b0bec5', marginBottom: 4 }}>初始资金</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#ffffff' }}>
                  ¥{accountInfo.initial_cash?.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '0.00'}
                </div>
              </div>
            </div>
            
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              marginTop: 12, 
              paddingTop: 12, 
              borderTop: '1px solid #3a4a5f'
            }}>
              <div>
                <div style={{ fontSize: 12, color: '#b0bec5' }}>总盈亏</div>
                <div style={{ 
                  fontSize: 16, 
                  fontWeight: 700, 
                  color: accountInfo.total_profit >= 0 ? '#ff4d4f' : '#52c41a' 
                }}>
                  {accountInfo.total_profit >= 0 ? '+' : ''}¥{accountInfo.total_profit?.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '0.00'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#b0bec5' }}>盈亏率</div>
                <div style={{ 
                  fontSize: 16, 
                  fontWeight: 700, 
                  color: accountInfo.profit_rate >= 0 ? '#ff4d4f' : '#52c41a' 
                }}>
                  {accountInfo.profit_rate >= 0 ? '+' : ''}{accountInfo.profit_rate?.toFixed(2) || '0.00'}%
                </div>
              </div>
            </div>

            {accountInfo.daily_profit_details && Object.keys(accountInfo.daily_profit_details).length > 0 && (
              <div style={{ marginTop: 16, marginBottom: 24 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>
                  � 每日盈亏趋势
                </div>
                <div style={{ height: 220, marginBottom: 12 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart 
                      data={Object.entries(accountInfo.daily_profit_details)
                        .sort(([a], [b]) => new Date(a) - new Date(b))
                        .map(([date, details]) => ({
                          date: new Date(date).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }),
                          fullDate: date,
                          profitAmount: details.profit_amount,
                          profitRate: details.profit_rate
                        }))}
                      margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
                      <XAxis 
                        dataKey="date" 
                        stroke="#b0bec5" 
                        fontSize={11}
                        tick={{ fill: '#b0bec5' }}
                      />
                      <YAxis 
                        yAxisId="left"
                        stroke="#ff4d4f"
                        fontSize={11}
                        tick={{ fill: '#b0bec5' }}
                        tickFormatter={(value) => `¥${value.toLocaleString()}`}
                      />
                      <YAxis 
                        yAxisId="right"
                        orientation="right"
                        stroke="#52c41a"
                        fontSize={11}
                        tick={{ fill: '#b0bec5' }}
                        tickFormatter={(value) => `${value}%`}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: 'rgba(0, 0, 0, 0.8)', 
                          border: '1px solid #1890ff',
                          borderRadius: 4,
                          color: '#fff'
                        }}
                        formatter={(value, name) => {
                          if (name === '盈亏金额') {
                            return [`¥${value.toLocaleString()}`, name];
                          }
                          return [`${value}%`, name];
                        }}
                        labelFormatter={(label) => `日期: ${label}`}
                      />
                      <Legend 
                        wrapperStyle={{ fontSize: 13, color: '#b0bec5' }}
                      />
                      <Line 
                        yAxisId="left"
                        type="monotone" 
                        dataKey="profitAmount" 
                        stroke="#ff4d4f" 
                        strokeWidth={2}
                        dot={{ fill: '#ff4d4f', strokeWidth: 2, r: 4 }}
                        activeDot={{ r: 6, stroke: '#ff4d4f', strokeWidth: 2 }}
                        name="盈亏金额"
                      />
                      <Line 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="profitRate" 
                        stroke="#52c41a" 
                        strokeWidth={2}
                        dot={{ fill: '#52c41a', strokeWidth: 2, r: 4 }}
                        activeDot={{ r: 6, stroke: '#52c41a', strokeWidth: 2 }}
                        name="盈亏率"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ fontSize: 11, color: '#b0bec5', textAlign: 'center', marginBottom: 8 }}>
                  💡 红色线：盈亏金额 | 绿色线：盈亏率
                </div>
              </div>
            )}

            {accountInfo.positions && Object.keys(accountInfo.positions).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>
                  📊 持仓详情
                </div>
                <Table
                  dataSource={Object.entries(accountInfo.positions).map(([symbol, position]) => ({
                    key: symbol,
                    symbol: symbol,
                    name: position.name || symbol,
                    quantity: position.quantity,
                    hold_days: position.hold_days,
                    avgPrice: position.avg_price?.toFixed(2) || '0.00',
                    currentPrice: position.current_price?.toFixed(2) || '0.00',
                    currentValue: position.current_value?.toFixed(2) || '0.00',
                    profitLoss: position.profit_loss?.toFixed(2) || '0.00',
                    profitRate: position.profit_rate?.toFixed(2) || '0.00'
                  }))}
                  columns={positionColumns}
                  pagination={false}
                  size="small"
                  scroll={{ y: 350 }}
                  style={{ 
                    backgroundColor: 'transparent',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 8
                  }}
                  rowClassName={() => 'custom-table-row'}
                />
              </div>
            )}

            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              marginTop: 16,
              fontSize: 12,
              padding: '12px 16px',
              background: 'rgba(255, 255, 255, 0.05)',
              borderRadius: 8,
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}>
              <span style={{ color: '#b0bec5' }}>📊 持仓股票: {accountInfo.positions_count || 0}只</span>
              <div style={{ display: 'flex', gap: 16 }}>
                <span 
                  style={{ 
                    color: '#1890ff', 
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                  onClick={fetchTradeHistory}
                >
                  🔄 交易次数: {accountInfo.trade_count || 0}次
                </span>
                <span 
                  style={{ 
                    color: '#52c41a', 
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                  onClick={fetchPositionDetails}
                >
                  📋 持仓明细
                </span>
              </div>
              <span style={{ color: '#b0bec5' }}>⏰ 更新时间: {new Date(accountInfo.last_update).toLocaleString('zh-CN')}</span>
            </div>

            {/* 交易记录展示区域 */}
            {showTradeHistory && (
              <div style={{ marginTop: 24 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>
                  📈 近一月交易记录
                </div>
                {tradeLoading ? (
                  <div style={{ textAlign: 'center', padding: 20 }}>
                    <Spin size="small" />
                    <div style={{ color: '#b0bec5', marginTop: 8, fontSize: 12 }}>加载交易记录中...</div>
                  </div>
                ) : tradeHistory && tradeHistory.length > 0 ? (
                  <Table
                    dataSource={tradeHistory.map((trade, index) => {
                      // 处理新的统一数据结构
                      let profit = 0;
                      let commission = 0;
                      let total_cost = 0;
                      
                      if (trade.action === 'sell') {
                        // 卖出记录使用新的数据结构
                        profit = trade.sell_reason?.profit_analysis?.profit_amount || 0;
                        total_cost = trade.total_amount || (trade.quantity * trade.price);
                        commission = Math.abs((trade.quantity * trade.price * 0.0003) || 0);
                      } else {
                        // 买入记录使用原有结构
                        profit = trade.profit || 0;
                        commission = trade.commission || 0;
                        total_cost = trade.total_cost || (trade.quantity * trade.price);
                      }
                      
                      return {
                        key: index,
                        timestamp: trade.trade_date || trade.date || new Date(trade.timestamp).toLocaleDateString('zh-CN'),
                        trade_date: trade.trade_date || trade.date || new Date(trade.timestamp).toLocaleDateString('zh-CN'),
                        symbol: trade.symbol,
                        name: trade.name || trade.stock_name || (trade.signal_data?.name) || '--',
                        action: trade.action,
                        quantity: trade.quantity,
                        price: trade.price,
                        total_cost: total_cost,
                        profit: profit,
                        commission: commission,
                        sell_price: trade.sell_price || (trade.signal_data?.sell_price) || (trade.sell_reason?.signal_analysis?.sell_price),
                        stop_loss: trade.stop_loss || (trade.signal_data?.stop_loss) || (trade.sell_reason?.signal_analysis?.stop_loss)
                      };
                    })}
                    columns={tradeColumns}
                    pagination={{ 
                      pageSize: 50, 
                      showSizeChanger: false,
                      showTotal: (total) => `共 ${total} 条记录`,
                      style: { color: '#b0bec5' }
                    }}
                    size="small"
                    scroll={{ x: 1000, y: 300 }}
                    style={{ 
                      backgroundColor: 'transparent',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: 8
                    }}
                    rowClassName={() => 'custom-table-row'}
                  />
                ) : (
                  <div style={{ textAlign: 'center', color: '#b0bec5', fontSize: 12, padding: 20 }}>
                    <Empty description="暂无交易记录" imageStyle={{ height: 40 }} />
                  </div>
                )}
                </div>
              )}

            {/* 持仓明细展示区域 */}
            {showPositionDetails && (
              <div style={{ marginTop: 24 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#52c41a', marginBottom: 12 }}>
                  📋 持仓明细详情
                </div>
                {positionDetailsLoading ? (
                  <div style={{ textAlign: 'center', padding: 20 }}>
                    <Spin size="small" />
                    <div style={{ color: '#b0bec5', marginTop: 8, fontSize: 12 }}>加载持仓明细中...</div>
                  </div>
                ) : positionDetails && positionDetails.length > 0 ? (
                  <div>
                    {(() => {
                      // 按股票分组并排序
                      const groupedData = positionDetails.reduce((groups, detail) => {
                        const symbol = detail.symbol;
                        if (!groups[symbol]) {
                          groups[symbol] = [];
                        }
                        groups[symbol].push(detail);
                        return groups;
                      }, {});

                      // 对每个分组内的数据按时间倒序排序
                      Object.keys(groupedData).forEach(symbol => {
                        groupedData[symbol].sort((a, b) => new Date(b.buy_date) - new Date(a.buy_date));
                      });

                      // 按股票代码排序
                      const sortedSymbols = Object.keys(groupedData).sort();

                      return sortedSymbols.map(symbol => {
                        const group = groupedData[symbol];
                        const totalQuantity = group.reduce((sum, item) => sum + item.remaining_quantity, 0);
                        const totalCost = group.reduce((sum, item) => sum + item.total_cost, 0);
                        const stockName = group[0]?.diagnosis_data?.name || symbol;
                        
                        // 计算总盈亏：包含已平仓和持仓中的股票
                        let totalProfit = 0;
                        
                        group.forEach(item => {
                          if (item.status === 'closed' && item.sell_records && item.sell_records.length > 0) {
                            // 已平仓的股票：使用实际卖出价格计算盈亏
                            const totalSellValue = item.sell_records.reduce((sum, record) => 
                              sum + (record.sell_price * record.sell_quantity), 0);
                            totalProfit += totalSellValue - item.total_cost;
                          } else {
                            // 持仓中的股票：使用当前价格计算盈亏
                            const position = accountInfo.positions?.[symbol];
                            const currentPrice = position?.current_price || 0;
                            const currentValue = currentPrice * item.remaining_quantity;
                            totalProfit += currentValue - item.total_cost;
                          }
                        });
                        
                        // 使用accountInfo中的当前价格数据计算当前市值（仅持仓部分）
                        const position = accountInfo.positions?.[symbol];
                        const currentPrice = position?.current_price || 0;
                        const currentValue = currentPrice * totalQuantity;
                        const profitRate = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;

                        return (
                          <div key={symbol} style={{ marginBottom: 16 }}>
                            <div style={{
                              background: 'linear-gradient(135deg, #2a3a4f 0%, #1e2a3a 100%)',
                              borderRadius: 8,
                              padding: '12px 16px',
                              marginBottom: 8,
                              border: '1px solid #3a4a5f',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center'
                            }}>
                              <div>
                                <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 14 }}>
                                  {stockName}
                                </span>
                                <span style={{ color: '#b0bec5', fontSize: 12, marginLeft: 8 }}>
                                  {symbol}
                                </span>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ color: '#b0bec5', fontSize: 11 }}>
                                  总持仓: {totalQuantity.toLocaleString()}股
                                </div>
                                <div style={{ color: '#13c2c2', fontSize: 11 }}>
                                  总成本: ¥{totalCost.toFixed(2)}
                                </div>
                                <div style={{ color: '#13c2c2', fontSize: 11 }}>
                                  当前市值: ¥{currentValue.toFixed(2)}
                                </div>
                                <div style={{ 
                                  color: totalProfit >= 0 ? '#ff4d4f' : '#52c41a', 
                                  fontSize: 11,
                                  fontWeight: 600
                                }}>
                                  总盈亏: ¥{totalProfit.toFixed(2)} ({profitRate.toFixed(2)}%)
                                </div>
                              </div>
                            </div>
                            <Table
                              dataSource={group.map((detail, index) => {
                                // 当前价格始终使用最新价格
                                const position = accountInfo.positions?.[symbol];
                                const currentPrice = position?.current_price || 0;
                                
                                let currentValue, profitLoss, profitRate;
                                
                                // 对于已平仓的持仓，使用实际卖出价格计算盈亏
                                if (detail.status === 'closed' && detail.sell_records && detail.sell_records.length > 0) {
                                  const lastSell = detail.sell_records[detail.sell_records.length - 1];
                                  const sellPrice = lastSell.sell_price || 0;
                                  const sellQuantity = lastSell.sell_quantity || detail.remaining_quantity;
                                  
                                  currentValue = sellPrice * sellQuantity;
                                  profitLoss = currentValue - detail.total_cost;
                                  profitRate = detail.total_cost > 0 ? ((currentValue - detail.total_cost) / detail.total_cost) * 100 : 0;
                                } else {
                                  // 对于持仓中的，使用最新价格计算
                                  currentValue = currentPrice * detail.remaining_quantity;
                                  profitLoss = currentValue - detail.total_cost;
                                  profitRate = detail.total_cost > 0 ? ((currentValue - detail.total_cost) / detail.total_cost) * 100 : 0;
                                }
                                
                                return {
                                  key: `${symbol}-${index}`,
                                  ...detail,
                                  currentPrice: currentPrice.toFixed(2),
                                  currentValue: currentValue.toFixed(2),
                                  profitLoss: profitLoss.toFixed(2),
                                  profitRate: profitRate.toFixed(2)
                                };
                              })}
                              columns={positionDetailsColumns}
                              pagination={false}
                              size="small"
                              scroll={{ x: 1200 }}
                              style={{ 
                                backgroundColor: 'transparent',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                borderRadius: 8,
                                marginBottom: 8
                              }}
                              rowClassName={() => 'custom-table-row'}
                            />
                          </div>
                        );
                      });
                    })()}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: '#b0bec5', fontSize: 12, padding: 20 }}>
                    <Empty description="暂无持仓明细" imageStyle={{ height: 40 }} />
                  </div>
                )}
              </div>
            )}

              <div style={{
                background: 'rgba(255, 77, 79, 0.1)',
                border: '1px solid rgba(255, 77, 79, 0.3)',
                borderRadius: 8,
                padding: 12,
                marginTop: 16
              }}>
                <div style={{ fontSize: 12, color: '#ffccc7', textAlign: 'center' }}>
                  ⚠️ 投资有风险，入市需谨慎
                </div>
              </div>
            </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', color: '#b0bec5', fontSize: 14, padding: 20 }}>
          <Empty description="暂无持仓信息" imageStyle={{ height: 60 }} />
        </div>
      )}
    </Modal>
  );
};

export default PositionAnalysis;
