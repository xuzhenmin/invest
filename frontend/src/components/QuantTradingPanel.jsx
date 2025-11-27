import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Button, Table, Tag, Modal, message, Spin, Empty, DatePicker, Popover } from 'antd';
import { RiseOutlined, FallOutlined, BarChartOutlined, ThunderboltOutlined, LineChartOutlined, WalletOutlined } from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';
import dayjs from 'dayjs';
import PositionAnalysis from './statistics/PositionAnalysis';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const QuantTradingPanel = ({ 
  userId, 
  selectedStock, 
  onTradeSignal, 
  stocks = '', 
  stockSnapshots = {}
}) => {
  const [quantSignals, setQuantSignals] = useState({});
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [processingStocks, setProcessingStocks] = useState(new Set());
  
  // 新增：历史预测趋势相关状态
  const [historyModalVisible, setHistoryModalVisible] = useState(false);
  const [historyData, setHistoryData] = useState({});
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryStock, setSelectedHistoryStock] = useState(null);
  const [klineData, setKlineData] = useState([]);
  const [klineLoading, setKlineLoading] = useState(false);
  
  // 新增：日期选择相关状态
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [diagnosisReports, setDiagnosisReports] = useState({});
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  
  // 新增：持仓信息相关状态
  const [accountVisible, setAccountVisible] = useState(false);

  // 获取监控股票列表
  const getMonitorStocks = useMemo(() => {
    return stocks.split(/[ ,，]+/).filter(Boolean);
  }, [stocks]);

  // 获取股票行情数据 - 优先使用实时行情数据
  const getStockData = useCallback((symbol) => {
    const data = stockSnapshots[symbol];
    if (!data) {
      return {
        last_price: null,
        change_rate: null,
        volume: null,
        name: symbol,
        isLoading: true
      };
    }
    
    // 统一字段映射，确保数据格式一致
    const lastPrice = Number(data.last_price || data.current_price || data.price || 0);
    const preClose = Number(data.pre_close || data.preClose || 0);
    const changeRate = preClose > 0 ? ((lastPrice - preClose) / preClose) * 100 : 0;
    
    return {
      last_price: lastPrice || null,
      change_rate: changeRate || null,
      volume: Number(data.volume || 0),
      name: data.name || symbol,
      open: Number(data.open || 0),
      high: Number(data.high || 0),
      low: Number(data.low || 0),
      pre_close: preClose,
      ...data,
      isLoading: false
    };
  }, [stockSnapshots]);

  // 新增：获取股票历史预测数据
  const fetchHistoryPredictions = async (symbol) => {
    try {
      setHistoryLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/quant/predictions/history/${symbol}`);
      
      if (response.data.success) {
        setHistoryData(response.data.data);
        return response.data.data;
      }
      return {};
    } catch (error) {
      console.error(`获取 ${symbol} 历史预测数据失败:`, error);
      message.error('获取历史预测数据失败');
      return {};
    } finally {
      setHistoryLoading(false);
    }
  };

  // 新增：获取股票K线数据
  const fetchKlineData = async (symbol) => {
    try {
      setKlineLoading(true);
      const endDate = new Date();
      const startDate = new Date();
      startDate.setMonth(startDate.getMonth() - 3); // 获取3个月K线数据
      
      const response = await axios.get(
        `${API_BASE_URL}/quant/kline?symbol=${symbol}&start=${startDate.toISOString().split('T')[0]}&end=${endDate.toISOString().split('T')[0]}`
      );
      
      let klineData = [];
      
      if (Array.isArray(response.data)) {
        klineData = response.data;
      } else if (response.data && Array.isArray(response.data.data)) {
        klineData = response.data.data;
      }
      
      setKlineData(klineData);
      return klineData;
      
    } catch (error) {
      console.error(`获取 ${symbol} K线数据失败:`, error);
      setKlineData([]);
      return [];
    } finally {
      setKlineLoading(false);
    }
  };

  // 新增：打开历史预测趋势模态框
  const openHistoryModal = async (symbol, stockName) => {
    setSelectedHistoryStock({ symbol, name: stockName });
    setHistoryModalVisible(true);

    // 并行获取历史预测和K线数据
    await Promise.all([
      fetchHistoryPredictions(symbol),
      fetchKlineData(symbol)
    ]);
  };

  // 生成单个股票的交易信号
  const generateStockSignal = async (symbol) => {
    if (processingStocks.has(symbol)) return;
    
    setProcessingStocks(prev => new Set(prev).add(symbol));
    try {
      const stockData = getStockData(symbol);
      
      // 获取诊断报告（使用新的诊断接口）
      const diagnosisResponse = await axios.get(`${API_BASE_URL}/api/quant/diagnosis/${symbol}`);
      const diagnosisResult = diagnosisResponse.data;
      
      if (diagnosisResult.success) {
        setQuantSignals(prev => ({
          ...prev,
          [symbol]: diagnosisResult.data
        }));
      }
    } catch (error) {
      console.error(`获取 ${symbol} 交易信号失败:`, error);
    } finally {
      setProcessingStocks(prev => {
        const newSet = new Set(prev);
        newSet.delete(symbol);
        return newSet;
      });
    }
  };

  // 批量生成所有监控股票的交易信号
  const generateAllSignals = async () => {
    const stockList = getMonitorStocks;
    if (stockList.length === 0) {
      message.info('请先添加监控股票');
      return;
    }

    setLoading(true);
    try {
      await Promise.all(stockList.map(symbol => generateStockSignal(symbol)));
      message.success(`已生成 ${stockList.length} 只股票的交易信号`);
    } catch (error) {
      console.error('批量生成信号失败:', error);
      message.error('生成信号失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取信号颜色
  const getSignalColor = (signal) => {
    switch (signal) {
      case 'strong_buy': return '#52c41a';
      case 'buy': return '#13c2c2';
      case 'hold': return '#faad14';
      case 'sell': return '#fa541c';
      case 'strong_sell': return '#ff4d4f';
      default: return '#b0bec5';
    }
  };

  // 新增：查询指定日期的诊断报告
  const fetchDiagnosisReports = async (date) => {
    try {
      setDiagnosisLoading(true);
      const stockList = getMonitorStocks;
      
      if (stockList.length === 0) {
        message.warning('请先添加监控股票');
        return;
      }

      const response = await axios.get(
        `${API_BASE_URL}/api/quant/diagnosis/query?symbols=${stockList.join(',')}&date=${date.format('YYYY-MM-DD')}`
      );

      if (response.data.success) {
        const reports = response.data.data.results || {};
        setDiagnosisReports(reports);
        
        // 更新量化信号 - 确保正确映射数据结构
        const newQuantSignals = { ...quantSignals };
        Object.keys(reports).forEach(symbol => {
          const report = reports[symbol];
          
          // 处理可能的嵌套结构
          const diagnosisData = report.diagnosis || report;
          
          newQuantSignals[symbol] = {
            ...diagnosisData,
            name: report.name || diagnosisData.name || symbol,
            symbol: symbol,
            timestamp: date.format('YYYY-MM-DD'),
            // 确保关键字段存在
            recommendation: diagnosisData.recommendation || diagnosisData.signal || 'hold',
            overall_score: diagnosisData.overall_score || diagnosisData.score || 0,
            risk_level: diagnosisData.risk_level || 'unknown',
            // 价格相关字段
            support: diagnosisData.support || 0,
            resistance: diagnosisData.resistance || 0,
            target_price: diagnosisData.target_price || 0,
            stop_loss: diagnosisData.stop_loss || 0,
            buy_price: diagnosisData.buy_price || 0,
            sell_price: diagnosisData.sell_price || 0
          };
        });
        setQuantSignals(newQuantSignals);
        
        message.success(`成功获取 ${Object.keys(reports).length} 只股票的诊断报告`);
      } else {
        message.error('获取诊断报告失败');
      }
    } catch (error) {
      console.error('获取诊断报告失败:', error);
      message.error('获取诊断报告失败');
    } finally {
      setDiagnosisLoading(false);
    }
  };

  // 新增：处理日期变化
  const handleDateChange = (date) => {
    setSelectedDate(date);
    fetchDiagnosisReports(date);
  };

  // 新增：处理持仓图标点击
  const handleAccountClick = () => {
    console.log('打开持仓分析');
    setAccountVisible(true);
  };

  // 股票列表表格列定义
  const columns = [
    {
      title: '股票',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (text, record) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div>
            <div style={{ fontSize: 12, color: '#ffffff', cursor: 'pointer' }}>
              {record.name || record.symbol}
            </div>
            <div style={{ fontWeight: 600, color: '#b0bec5', cursor: 'pointer' }}>{record.symbol}</div>
          </div>
          <Button
            type="text"
            size="small"
            icon={<LineChartOutlined />}
            style={{ 
              color: '#13c2c2', 
              fontSize: 12,
              padding: '2px 4px',
              height: 'auto'
            }}
            onClick={() => openHistoryModal(record.symbol, record.name)}
            title="查看历史预测趋势"
          />
        </div>
      )
    },
    {
      title: '最新价',
      dataIndex: 'last_price',
      key: 'last_price',
      render: (text, record) => {
        const price = record.last_price || 0;
        const change = record.change_rate || 0;
        const isLoading = !record.hasRealTimeData && price === 0;
        
        if (isLoading) {
          return (
            <div>
              <div style={{ color: '#b0bec5', fontWeight: 600 }}>
                --
              </div>
              <div style={{ color: '#b0bec5', fontSize: 11 }}>
                加载中...
              </div>
            </div>
          );
        }
        
        return (
          <div>
            <div style={{ color: '#ffffff', fontWeight: 600 }}>
              ¥{price.toFixed(2)}
            </div>
            <div style={{ 
              color: change === 0 ? '#b0bec5' : 
                     change > 0 ? '#ff4d4f' : '#52c41a',
              fontSize: 12 
            }}>
              {change === 0 ? '' : 
               change > 0 ? '+' : ''}{change.toFixed(2)}%
            </div>
          </div>
        );
      }
    },
    {
      title: '支撑位',
      dataIndex: 'support',
      key: 'support',
      render: (text, record) => {
        const symbol = record.symbol;
        const signal = quantSignals[symbol];
        const support = record.support || signal?.support || signal?.diagnosis?.support || 0;
        return (
          <div style={{ position: 'relative' }}>
            <div style={{ color: '#52c41a', fontWeight: 600 }}>
              ¥{Number(support).toFixed(2)}
            </div>
          </div>
        );
      }
    },
    {
      title: '压力位',
      dataIndex: 'resistance',
      key: 'resistance',
      render: (text, record) => {
        const symbol = record.symbol;
        const signal = quantSignals[symbol];
        const resistance = record.resistance || signal?.resistance || signal?.diagnosis?.resistance || 0;
        return (
          <div style={{ position: 'relative' }}>
            <div style={{ color: '#ff4d4f', fontWeight: 600 }}>
              ¥{Number(resistance).toFixed(2)}
            </div>
          </div>
        );
      }
    },
    {
      title: '目标价',
      dataIndex: 'target_price',
      key: 'target_price',
      render: (text, record) => {
        const targetPrice = record.target_price || 0;
        const currentPrice = record.last_price || 0;
        const isTriggered = record.triggers?.some(t => t.type === 'TARGET');
        
        // 计算当前价到目标价的涨跌幅
        let pctToTarget = 0;
        if (currentPrice > 0 && targetPrice > 0) {
          pctToTarget = ((targetPrice - currentPrice) / currentPrice) * 100;
        }
        
        return (
          <div style={{ position: 'relative' }}>
            <div style={{ color: '#722ed1', fontWeight: 600 }}>
              ¥{targetPrice.toFixed(2)}
            </div>
            {currentPrice > 0 && targetPrice > 0 && (
              <div style={{ 
                fontSize: 11, 
                color: pctToTarget >= 0 ? '#52c41a' : '#ff4d4f',
                marginTop: 1
              }}>
                {pctToTarget >= 0 ? '+' : ''}{pctToTarget.toFixed(2)}%
              </div>
            )}
            {isTriggered && (
              <Tag 
                color="#722ed1"
                style={{ 
                  fontSize: 10, 
                  padding: '0 4px',
                  marginTop: 1,
                  backgroundColor: 'rgba(114, 46, 209, 0.1)',
                  border: '1px solid #722ed1'
                }}
              >
                目标
              </Tag>
            )}
          </div>
        );
      }
    },
    {
      title: '建仓价',
      dataIndex: 'buy_price',
      key: 'buy_price',
      render: (text, record) => {
        const buyPrice = record.buy_price || 0;
        const currentPrice = record.last_price || 0;
        const isTriggered = record.triggers?.some(t => t.type === 'BUY');
        
        return (
          <div style={{ position: 'relative' }}>
            <div style={{ color: '#52c41a', fontWeight: 600 }}>
              ¥{buyPrice.toFixed(2)}
            </div>
            {isTriggered && (
              <Tag 
                color="#52c41a"
                style={{ 
                  fontSize: 10, 
                  padding: '0 4px',
                  marginTop: 2,
                  backgroundColor: 'rgba(82, 196, 26, 0.1)',
                  border: '1px solid #52c41a'
                }}
              >
                建仓
              </Tag>
            )}
          </div>
        );
      }
    },
    {
      title: '止损价',
      dataIndex: 'stop_loss',
      key: 'stop_loss',
      render: (text, record) => {
        const stopLoss = record.stop_loss || 0;
        const isTriggered = record.triggers?.some(t => t.type === 'STOP');
        
        return (
          <div style={{ position: 'relative' }}>
            <div style={{ color: '#faad14', fontWeight: 600 }}>
              ¥{stopLoss.toFixed(2)}
            </div>
            {isTriggered && (
              <Tag 
                color="#faad14"
                style={{ 
                  fontSize: 10, 
                  padding: '0 4px',
                  marginTop: 2,
                  backgroundColor: 'rgba(250, 173, 20, 0.1)',
                  border: '1px solid #faad14'
                }}
              >
                止损
              </Tag>
            )}
          </div>
        );
      }
    },
    {
      title: '止盈价',
      dataIndex: 'sell_price',
      key: 'sell_price',
      render: (text, record) => {
        const sellPrice = record.sell_price || 0;
        const isTriggered = record.triggers?.some(t => t.type === 'SELL');
        
        return (
          <div style={{ position: 'relative' }}>
            <div style={{ color: '#ff4d4f', fontWeight: 600 }}>
              ¥{sellPrice.toFixed(2)}
            </div>
            {isTriggered && (
              <Tag 
                color="#ff4d4f"
                style={{ 
                  fontSize: 10, 
                  padding: '0 4px',
                  marginTop: 2,
                  backgroundColor: 'rgba(255, 77, 79, 0.1)',
                  border: '1px solid #ff4d4f'
                }}
              >
                止盈
              </Tag>
            )}
          </div>
        );
      }
    },
    {
      title: '信号时间',
      dataIndex: 'signal_time',
      key: 'signal_time',
      render: (text, record) => {
        const symbol = record.symbol;
        const signal = quantSignals[symbol];
        const timestamp = signal?.timestamp || '';
        
        if (!timestamp) {
          return <span style={{ color: '#b0bec5' }}>--</span>;
        }
        
        try {
          const date = new Date(timestamp);
          const formattedTime = date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
          });
          return (
            <span style={{ color: '#ffffff', fontSize: 12, fontWeight: 500 }}>
              {formattedTime}
            </span>
          );
        } catch (error) {
          return <span style={{ color: '#b0bec5' }}>{timestamp}</span>;
        }
      }
    },
    {
      title: '交易信号',
      dataIndex: 'signal',
      key: 'signal',
      render: (text, record) => {
        const symbol = record.symbol;
        const signal = quantSignals[symbol];
        const signalText = signal?.recommendation || '暂无';  // ← 修正字段名
        
        // 信号含义映射
        const signalMeanings = {
          'buy': '建议买入',
          'sell': '建议卖出', 
          'hold': '建议持有',
          'strong_buy': '强烈买入',
          'strong_sell': '强烈卖出'
        };
        
        // 信号字体颜色映射（背景色改为字体颜色）
        const signalFontColors = {
          '建议买入': '#52c41a',      // 绿色
          '建议卖出': '#ff4d4f',     // 红色
          '建议持有': '#faad14',     // 黄色
          '强烈买入': '#13c2c2',     // 青色
          '强烈卖出': '#f5222d'      // 深红色
        };
        
        const displayText = signalMeanings[signalText.toLowerCase()] || '暂无信号';
        const color = signalFontColors[displayText] || '#b0bec5';
        
        return (
          <span 
            style={{ 
              color: color,
              fontSize: '12px', 
              fontWeight: 600,
              whiteSpace: 'nowrap'
            }}
          >
            {displayText}
          </span>
        );
      }
    },
    {
      title: '综合评分',
      dataIndex: 'confidence',
      key: 'confidence',
      render: (text, record) => {
        const symbol = record.symbol;
        const signal = quantSignals[symbol];
        const confidence = signal?.overall_score || 0;
        return (
          <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 12 }}>
            {confidence.toFixed(1)}%
          </span>
        );
      }
    },
    {
      title: '风险级别',
      dataIndex: 'risk_level',
      key: 'risk_level',
      render: (text, record) => {
        const symbol = record.symbol;
        const signal = quantSignals[symbol];
        const riskLevel = signal?.risk_level || signal?.diagnosis?.risk_level || '未知';
        
        // 风险级别颜色映射
        const riskColors = {
          'low': '#52c41a',      // 低风险 - 绿色
          'medium': '#faad14',   // 中风险 - 黄色
          'high': '#ff4d4f',     // 高风险 - 红色
          'unknown': '#b0bec5'   // 未知 - 灰色
        };
        
        const riskLabels = {
          'low': '低风险',
          'medium': '中风险',
          'high': '高风险',
          'unknown': '未知'
        };
        
        const displayRisk = riskLabels[riskLevel.toLowerCase()] || '未知';
        const color = riskColors[riskLevel.toLowerCase()] || '#b0bec5';
        
        return (
          <span style={{ color: color, fontWeight: 600, fontSize: 12 }}>
            {displayRisk}
          </span>
        );
      }
    },
    {
      title: '操作',
      key: 'action',
      render: (text, record) => {
        const symbol = record.symbol;
        const isProcessing = processingStocks.has(symbol);
        const hasSignal = !!quantSignals[symbol];
        
        // 无信号时只展示生成信号按钮
        if (!hasSignal) {
          return (
            <Button 
              size="small" 
              type="text"
              loading={isProcessing}
              style={{ 
                color: '#faad14',
                fontSize: 11,
                minWidth: 60,
                border: 'none',
                background: 'transparent'
              }}
              onClick={() => generateStockSignal(symbol)}
            >
              {isProcessing ? '生成中' : '生成信号'}
            </Button>
          );
        }
        
        // 有信号时展示详情和更新按钮
        return (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <Button 
              size="small" 
              type="text" 
              style={{ 
                color: '#13c2c2', 
                fontSize: 11
              }}
              onClick={() => {
                setSelectedSignal(quantSignals[symbol]);
                setModalVisible(true);
              }}
            >
              详情
            </Button>
            <Button 
              size="small" 
              type="text" 
              loading={isProcessing}
              style={{ 
                color: '#52c41a', 
                fontSize: 11
              }}
              onClick={() => generateStockSignal(symbol)}
            >
              {isProcessing ? '更新中' : '更新'}
            </Button>
          </div>
        );
      }
    }
  ];

  // 自动查询诊断结果（展开卡片时触发）
  const queryDiagnosisResults = async (symbols) => {
    if (!symbols || symbols.length === 0) return;
    
    try {
      setLoading(true);
      
      // 使用GET方式查询，股票代码用逗号分隔，不指定日期
      const symbolsStr = symbols.join(',');
      
      const response = await axios.get(
        `${API_BASE_URL}/api/quant/diagnosis/query?symbols=${symbolsStr}`
      );
      
      if (response.data.success) {
        const results = response.data.data.results;
        const newSignals = {};
        
        // 更新所有查询到的信号
        Object.keys(results).forEach(symbol => {
          newSignals[symbol] = results[symbol].diagnosis;
        });
        
        setQuantSignals(prev => ({ ...prev, ...newSignals }));
        message.success(`已自动查询${Object.keys(results).length}只股票的诊断结果`);
      }
    } catch (error) {
      console.error('自动查询诊断结果失败:', error);
      message.error('自动查询诊断结果失败');
    } finally {
      setLoading(false);
    }
  };

  // 监听监控股票列表变化，自动查询诊断结果
  useEffect(() => {
    const stockList = getMonitorStocks;
    if (stockList.length > 0) {
      // 延迟执行，避免频繁查询
      const timer = setTimeout(() => {
        queryDiagnosisResults(stockList);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [getMonitorStocks]);

  // 新增：行情触发条件判断状态
  const [triggeredSignals, setTriggeredSignals] = useState({});
  const [flashingRows, setFlashingRows] = useState({});

  // 行情触发条件判断函数
  const checkTriggerConditions = (symbol, currentPrice, signal) => {
    if (!signal || !currentPrice || currentPrice <= 0) return null;
    
    const conditions = {
      buy_price: signal?.buy_price || signal?.diagnosis?.buy_price,
      sell_price: signal?.sell_price || signal?.diagnosis?.sell_price,
      stop_loss: signal?.stop_loss || signal?.diagnosis?.stop_loss,
      target_price: signal?.target_price || signal?.diagnosis?.target_price
    };
    
    const triggers = [];
    
    // 建仓条件：当前价 <= 建仓价（向下触发），且当前价不能高于建仓价
    if (conditions.buy_price && currentPrice <= conditions.buy_price) {
      triggers.push({
        type: 'BUY',
        label: '建仓',
        price: conditions.buy_price,
        current: currentPrice,
        diff: ((currentPrice - conditions.buy_price) / conditions.buy_price * 100).toFixed(2),
        color: '#52c41a',
        bgColor: 'rgba(82, 196, 26, 0.1)'
      });
    }
    
    // 止盈条件：当前价 >= 止盈价（向上触发），且当前价不能低于止盈价
    if (conditions.sell_price && currentPrice >= conditions.sell_price) {
      triggers.push({
        type: 'SELL',
        label: '止盈',
        price: conditions.sell_price,
        current: currentPrice,
        diff: ((currentPrice - conditions.sell_price) / conditions.sell_price * 100).toFixed(2),
        color: '#ff4d4f',
        bgColor: 'rgba(255, 77, 79, 0.1)'
      });
    }
    
    // 止损条件：当前价 <= 止损价（向下触发）
    if (conditions.stop_loss && currentPrice <= conditions.stop_loss) {
      triggers.push({
        type: 'STOP',
        label: '止损',
        price: conditions.stop_loss,
        current: currentPrice,
        diff: ((currentPrice - conditions.stop_loss) / conditions.stop_loss * 100).toFixed(2),
        color: '#faad14',
        bgColor: 'rgba(250, 173, 20, 0.1)'
      });
    }
    
    // 目标价条件：只在当前价 = 目标价时触发（精确触发，去掉接近提示）
    if (conditions.target_price && conditions.target_price > 0) {
      const targetPrice = conditions.target_price;
      
      // 只在当前价 = 目标价时触发（精确匹配）
      if (currentPrice === targetPrice) {
        triggers.push({
          type: 'TARGET',
          label: '目标达成',
          price: targetPrice,
          current: currentPrice,
          diff: '0.00',
          color: '#722ed1',
          bgColor: 'rgba(114, 46, 209, 0.1)'
        });
      }
      // 当前价 ≠ 目标价时不触发任何提醒
    }
    
    return triggers.length > 0 ? triggers : null;
  };

  // 使用useEffect监听行情变化，触发条件判断
  useEffect(() => {
    const newTriggeredSignals = {};
    const newFlashingRows = {};
    
    getMonitorStocks.forEach(symbol => {
      const stockData = getStockData(symbol);
      const signal = quantSignals[symbol];
      const currentPrice = stockData?.last_price;
      
      if (currentPrice && currentPrice > 0) {
        const triggers = checkTriggerConditions(symbol, currentPrice, signal);
        if (triggers) {
          newTriggeredSignals[symbol] = triggers;
          newFlashingRows[symbol] = true;
          
          // 3秒后清除闪烁效果
          setTimeout(() => {
            setFlashingRows(prev => {
              const updated = { ...prev };
              delete updated[symbol];
              return updated;
            });
          }, 3000);
        }
      }
    });
    
    setTriggeredSignals(newTriggeredSignals);
    setFlashingRows(newFlashingRows);
  }, [stockSnapshots, quantSignals, getMonitorStocks, getStockData]);

  // 获取表格数据源 - 优先使用实时行情数据，增加触发信号标识
  const tableDataSource = useMemo(() => {
    const stockList = getMonitorStocks;
    return stockList.map(symbol => {
      const stockData = getStockData(symbol); // 实时行情数据
      const signal = quantSignals[symbol];    // 诊断数据
      const triggers = triggeredSignals[symbol] || []; // 触发信号
      
        return {
          key: symbol,
          symbol: symbol,
          // 价格数据：优先使用实时行情，诊断数据仅作补充
          last_price: stockData?.last_price || stockData?.current_price || 0,
          change_rate: stockData?.change_rate || 0,
          volume: stockData?.volume || 0,
          name: stockData?.name || signal?.name || symbol,
          // 诊断相关数据：使用诊断API返回的数据
          support: signal?.support || signal?.diagnosis?.support || 0,
          resistance: signal?.resistance || signal?.diagnosis?.resistance || 0,
          stop_loss: signal?.stop_loss || signal?.diagnosis?.stop_loss || 0,
          target_price: signal?.target_price || signal?.diagnosis?.target_price || 0,
          buy_price: signal?.buy_price || signal?.diagnosis?.buy_price || 0,
          sell_price: signal?.sell_price || signal?.diagnosis?.sell_price || 0,
          signal_time: signal?.timestamp || '',
          // 新增：触发信号标识
          triggers: triggers,
          hasTriggers: triggers.length > 0,
          // 标记数据来源
          hasRealTimeData: !stockData?.isLoading && stockData?.last_price > 0,
          hasSignalData: !!signal
        };
    });
  }, [getMonitorStocks, stockSnapshots, quantSignals, triggeredSignals, getStockData]);

  return (
    <div style={{ padding: '8px 0' }}>
      <style>{`
        @keyframes quant-flash {
          0% { 
            background-color: #181c24;
            box-shadow: 0 0 0px rgba(250, 173, 20, 0);
          }
          50% { 
            background-color: rgba(250, 173, 20, 0.2);
            box-shadow: 0 0 15px rgba(250, 173, 20, 0.5);
          }
          100% { 
            background-color: #181c24;
            box-shadow: 0 0 0px rgba(250, 173, 20, 0);
          }
        }
        
        .quant-flashing-row {
          animation: quant-flash 1s ease-in-out 3;
        }
        
        .quant-trigger-row {
          transition: all 0.3s ease;
        }
        
        .quant-trigger-row:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
      `}</style>
      {/* 股票列表表格 */}
      <div style={{ background: 'transparent', border: 'none' }}>
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#b0bec5', fontSize: 12 }}>
              共 {tableDataSource.length} 只监控股票
            </span>
            
            {/* 新增：持仓信息按钮 - 使用Modal确保点击触发 */}
            <Button 
              type="text" 
              size="small" 
              icon={<WalletOutlined />}
              style={{ color: '#722ed1', fontSize: 11, cursor: 'pointer' }}
              title="点击查看持仓分析"
              onClick={() => {
                console.log('直接点击持仓分析按钮');
                setAccountVisible(true);
              }}
            >
              持仓分析
            </Button>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <DatePicker
              size="small"
              value={selectedDate}
              onChange={handleDateChange}
              style={{ 
                background: '#181c24', 
                border: '1px solid #313a4d',
                color: '#ffffff',
                fontSize: 11,
                width: 110
              }}
              placeholder="选择日期"
              allowClear={false}
            />
            
            <Button 
              type="text" 
              size="small" 
              icon={<ThunderboltOutlined />}
              onClick={generateAllSignals}
              loading={loading}
              style={{ color: '#faad14', fontSize: 11 }}
            >
              生成/更新交易信号
            </Button>
          </div>
        </div>
        

        
        {tableDataSource.length > 0 ? (
          <Table
            dataSource={tableDataSource}
            columns={columns}
            pagination={false}
            size="small"
            style={{ background: 'transparent' }}
            rowClassName={(record) => {
              const baseClass = 'quant-trading-row';
              const flashClass = flashingRows[record.symbol] ? 'quant-flashing-row' : '';
              const triggerClass = record.hasTriggers ? 'quant-trigger-row' : '';
              return `${baseClass} ${flashClass} ${triggerClass}`.trim();
            }}
            rowStyle={(record) => {
              const baseStyle = { 
                background: '#181c24', 
                borderBottom: '1px solid #313a4d',
                transition: 'all 0.3s ease'
              };
              
              if (flashingRows[record.symbol]) {
                return {
                  ...baseStyle,
                  animation: 'quant-flash 1s ease-in-out 3',
                  boxShadow: '0 0 10px rgba(250, 173, 20, 0.3)'
                };
              }
              
              if (record.hasTriggers) {
                const primaryTrigger = record.triggers[0];
                return {
                  ...baseStyle,
                  borderLeft: `3px solid ${primaryTrigger.color}`,
                  background: `linear-gradient(90deg, ${primaryTrigger.bgColor} 0%, #181c24 100%)`
                };
              }
              
              return baseStyle;
            }}
            scroll={{ x: 'max-content' }}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Empty 
              description={
                <div style={{ color: '#b0bec5' }}>
                  <p>请先添加监控股票</p>
                  <p style={{ fontSize: 12 }}>添加股票后点击"手动生成交易信号"按钮</p>
                </div>
              }
              imageStyle={{ height: 80 }}
            />
          </div>
        )}
      </div>

      {/* 高端风格信号详情模态框 */}
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
            <BarChartOutlined style={{ color: '#faad14' }} />
            量化诊断详情
          </div>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={700}
        centered
        styles={{
          body: { 
            background: 'linear-gradient(135deg, #1a1d29 0%, #232a36 100%)', 
            color: '#ffffff',
            padding: 0
          },
          header: { background: '#1a1d29', borderBottom: '1px solid #313a4d' },
          mask: { background: 'rgba(0, 0, 0, 0.7)' }
        }}
        className="quant-detail-modal"
      >
        {selectedSignal && (
          <div style={{ padding: 24 }}>
            {/* 头部信息卡片 */}
            <div style={{
              background: 'linear-gradient(135deg, #2a3a4f 0%, #1e2a3a 100%)',
              borderRadius: 12,
              padding: 20,
              marginBottom: 20,
              border: '1px solid #3a4a5f'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#ffffff' }}>
                    {selectedSignal.name || selectedSignal.symbol}
                  </div>
                  <div style={{ fontSize: 14, color: '#b0bec5' }}>
                    {selectedSignal.symbol}
                  </div>
                  <div style={{ fontSize: 12, color: '#faad14', marginTop: 4 }}>
                    📅 诊断日期: {selectedSignal.timestamp || new Date().toLocaleDateString('zh-CN')}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#13c2c2' }}>
                    ¥{Number(selectedSignal.current_price || selectedSignal.diagnosis?.current_price || 0).toFixed(2)}
                  </div>
                  <Tag 
                    color={getSignalColor(selectedSignal.recommendation || selectedSignal.signal)}
                    style={{ fontSize: 12, fontWeight: 600, marginTop: 4 }}
                  >
                    {selectedSignal.recommendation?.toUpperCase() || selectedSignal.signal?.toUpperCase()}
                  </Tag>
                </div>
              </div>
            </div>

            {/* 评分卡片 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
              {[
                { label: '综合评分', value: selectedSignal.overall_score || selectedSignal.diagnosis?.overall_score || 0, color: '#13c2c2' },
                { label: '基本面', value: selectedSignal.fundamental_score || selectedSignal.diagnosis?.fundamental_score || 0, color: '#52c41a' },
                { label: '技术面', value: selectedSignal.technical_score || selectedSignal.diagnosis?.technical_score || 0, color: '#faad14' },
                { label: '资金面', value: selectedSignal.capital_score || selectedSignal.diagnosis?.capital_score || 0, color: '#722ed1' },
                { label: '估值面', value: selectedSignal.valuation_score || selectedSignal.diagnosis?.valuation_score || 0, color: '#ff4d4f' }
              ].map(item => (
                <div key={item.label} style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  borderRadius: 8,
                  padding: 12,
                  textAlign: 'center',
                  border: '1px solid rgba(255, 255, 255, 0.1)'
                }}>
                  <div style={{ fontSize: 11, color: '#b0bec5', marginBottom: 4 }}>{item.label}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: item.color }}>
                    {Number(item.value).toFixed(1)}
                  </div>
                </div>
              ))}
            </div>

            {/* 关键指标网格 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 20 }}>
              {/* 价格区间 */}
              <div style={{
                background: 'rgba(255, 255, 255, 0.05)',
                borderRadius: 12,
                padding: 16,
                border: '1px solid rgba(255, 255, 255, 0.1)'
              }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>价格区间</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>支撑位</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#52c41a' }}>
                      ¥{Number(selectedSignal.support || selectedSignal.diagnosis?.support || 0).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>压力位</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#ff4d4f' }}>
                      ¥{Number(selectedSignal.resistance || selectedSignal.diagnosis?.resistance || 0).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>目标价</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#52c41a' }}>
                      ¥{Number(selectedSignal.target_price || selectedSignal.diagnosis?.target_price || 0).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>建仓价</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#13c2c2' }}>
                      ¥{Number(selectedSignal.buy_price || selectedSignal.diagnosis?.buy_price || 0).toFixed(2)}
                    </div>
                  </div>
                   <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>止损价</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#ff4d4f' }}>
                      ¥{Number(selectedSignal.stop_loss || selectedSignal.diagnosis?.stop_loss || 0).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>止盈价</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#722ed1' }}>
                      ¥{Number(selectedSignal.sell_price || selectedSignal.diagnosis?.sell_price || 0).toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>

              {/* 风险控制 */}
              <div style={{
                background: 'rgba(255, 255, 255, 0.05)',
                borderRadius: 12,
                padding: 16,
                border: '1px solid rgba(255, 255, 255, 0.1)'
              }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>风险控制</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>止损价</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#ff4d4f' }}>
                      ¥{Number(selectedSignal.stop_loss || selectedSignal.diagnosis?.stop_loss || 0).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>目标价</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#52c41a' }}>
                      ¥{Number(selectedSignal.target_price || selectedSignal.diagnosis?.target_price || 0).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>风险等级</div>
                    <Tag 
                      color={
                        (selectedSignal.risk_level || selectedSignal.diagnosis?.risk_level) === 'low' ? 'green' :
                        (selectedSignal.risk_level || selectedSignal.diagnosis?.risk_level) === 'medium' ? 'orange' : 'red'
                      }
                      style={{ fontSize: 11, margin: 0 }}
                    >
                      {selectedSignal.risk_level || selectedSignal.diagnosis?.risk_level || '未知'}
                    </Tag>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: '#b0bec5' }}>置信度</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#13c2c2' }}>
                      {Number(selectedSignal.overall_score || selectedSignal.diagnosis?.overall_score || 0).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 分析理由 */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.05)',
              borderRadius: 12,
              padding: 16,
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>投资分析</div>
              <div style={{ 
                fontSize: 13, 
                color: '#b0bec5', 
                lineHeight: 1.6,
                whiteSpace: 'pre-line'
              }}>
                {selectedSignal.investment_reason || selectedSignal.diagnosis?.investment_reason || '暂无分析数据'}
              </div>
            </div>

            {/* 关键指标 */}
            {(selectedSignal.key_indicators || selectedSignal.diagnosis?.key_indicators) && (
              <div style={{
                background: 'rgba(255, 255, 255, 0.05)',
                borderRadius: 12,
                padding: 16,
                border: '1px solid rgba(255, 255, 255, 0.1)',
                marginTop: 16
              }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#faad14', marginBottom: 12 }}>关键指标</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {(selectedSignal.key_indicators || selectedSignal.diagnosis?.key_indicators || []).map((indicator, index) => (
                    <Tag key={index} style={{ fontSize: 11, margin: 0 }}>
                      {indicator}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {/* 风险提示 */}
            {(selectedSignal.risk_warnings || selectedSignal.diagnosis?.risk_warnings) && (
              <div style={{
                background: 'rgba(255, 77, 79, 0.1)',
                border: '1px solid rgba(255, 77, 79, 0.3)',
                borderRadius: 12,
                padding: 16,
                marginTop: 16
              }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#ff4d4f', marginBottom: 12 }}>
                  ⚠️ 风险提示
                </div>
                <div style={{ fontSize: 12, color: '#ffccc7', lineHeight: 1.5 }}>
                  {(selectedSignal.risk_warnings || selectedSignal.diagnosis?.risk_warnings || []).map((warning, index) => (
                    <div key={index} style={{ marginBottom: 4 }}>• {warning}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 历史预测趋势模态框 */}
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
            <LineChartOutlined style={{ color: '#13c2c2' }} />
            {selectedHistoryStock?.name || selectedHistoryStock?.symbol} - 历史预测趋势
          </div>
        }
        open={historyModalVisible}
        onCancel={() => setHistoryModalVisible(false)}
        footer={null}
        width={900}
        centered
        styles={{
          body: { 
            background: 'linear-gradient(135deg, #1a1d29 0%, #232a36 100%)', 
            color: '#ffffff',
            padding: 24,
            maxHeight: '70vh',
            overflow: 'auto'
          },
          header: { background: '#1a1d29', borderBottom: '1px solid #313a4d' },
          mask: { background: 'rgba(0, 0, 0, 0.7)' }
        }}
      >
        {historyLoading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
            <div style={{ color: '#b0bec5', marginTop: 16 }}>加载历史数据中...</div>
          </div>
        ) : (
          <div>
            {/* K线图表区域 */}
            <div style={{ 
              background: 'rgba(255, 255, 255, 0.05)', 
              borderRadius: 12, 
              padding: 20, 
              marginBottom: 20,
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#faad14', marginBottom: 16 }}>
                K线图表
              </div>
              {klineLoading ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <Spin size="large" />
                  <div style={{ color: '#b0bec5', marginTop: 16 }}>加载K线数据中...</div>
                </div>
              ) : klineData && klineData.length > 0 ? (
                <KLineChart 
                  data={klineData} 
                  symbol={selectedHistoryStock?.symbol}
                  signals={selectedHistoryStock?.symbol ? [quantSignals[selectedHistoryStock.symbol]] : []}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <Empty 
                    description={
                      <div style={{ color: '#b0bec5' }}>
                        <p>暂无K线数据</p>
                        <p style={{ fontSize: 12 }}>无法获取该股票的K线数据</p>
                      </div>
                    }
                  />
                </div>
              )}
            </div>

            {/* 历史预测数据表格 */}
            {Object.keys(historyData).length > 0 && (
              <div style={{ 
                background: 'rgba(255, 255, 255, 0.05)', 
                borderRadius: 12, 
                padding: 20,
                border: '1px solid rgba(255, 255, 255, 0.1)'
              }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#faad14', marginBottom: 16 }}>
                  历史预测详情
                </div>
                <div style={{ maxHeight: 300, overflow: 'auto' }}>
                  {Object.entries(historyData)
                    .sort(([dateA], [dateB]) => new Date(dateB) - new Date(dateA)) // 按时间倒序排列
                    .map(([date, prediction]) => {
                      const diagnosis = prediction.diagnosis || prediction;
                      return (
                        <div key={date} style={{
                          background: 'rgba(255, 255, 255, 0.03)',
                          borderRadius: 8,
                          padding: 12,
                          marginBottom: 8,
                          border: '1px solid rgba(255, 255, 255, 0.05)'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <span style={{ color: '#ffffff', fontWeight: 600 }}>{date}</span>
                            <Tag color={
                              diagnosis.recommendation === 'buy' ? 'green' :
                              diagnosis.recommendation === 'sell' ? 'red' :
                              diagnosis.recommendation === 'hold' ? 'orange' : 'default'
                            }>
                              {diagnosis.recommendation?.toUpperCase()}
                            </Tag>
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, fontSize: 12 }}>
                            <div><span style={{ color: '#b0bec5' }}>当前价:</span> ¥{diagnosis.current_price?.toFixed(2)}</div>
                            <div><span style={{ color: '#b0bec5' }}>目标价:</span> ¥{diagnosis.target_price?.toFixed(2)}</div>
                            <div><span style={{ color: '#b0bec5' }}>建仓价:</span> ¥{diagnosis.buy_price?.toFixed(2)}</div>
                            <div><span style={{ color: '#b0bec5' }}>止损价:</span> ¥{diagnosis.stop_loss?.toFixed(2)}</div>
                            <div><span style={{ color: '#b0bec5' }}>支撑位:</span> ¥{diagnosis.support?.toFixed(2)}</div>
                            <div><span style={{ color: '#b0bec5' }}>压力位:</span> ¥{diagnosis.resistance?.toFixed(2)}</div>
                            <div><span style={{ color: '#b0bec5' }}>综合评分:</span> {diagnosis.overall_score}</div>
                            <div><span style={{ color: '#b0bec5' }}>风险等级:</span> {diagnosis.risk_level}</div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 持仓分析组件 */}
      <PositionAnalysis 
        userId={userId}
        visible={accountVisible}
        onClose={() => setAccountVisible(false)}
      />
    </div>
  );
};

// K线图表组件 - 增加鼠标悬停显示详细价格信息
const KLineChart = ({ data, symbol, signals }) => {
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const chartContainer = chartRef.current;
    if (!chartContainer) return;

    // 清理之前的图表
    if (chartInstanceRef.current) {
      try {
        chartInstanceRef.current.remove();
      } catch (error) {
        console.log('Chart already disposed');
      }
      chartInstanceRef.current = null;
    }

    // 动态导入lightweight-charts
    import('lightweight-charts').then(({ createChart, ColorType }) => {
      if (!chartRef.current) return;

      // 确保容器是空的
      chartContainer.innerHTML = '';

      // 创建图表
      const chart = createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: 300,
        layout: {
          background: { type: ColorType.Solid, color: '#181c24' },
          textColor: '#b0bec5',
        },
        grid: {
          vertLines: { color: '#313a4d' },
          horzLines: { color: '#313a4d' },
        },
        crosshair: {
          mode: 1,
        },
        rightPriceScale: {
          borderColor: '#313a4d',
        },
        timeScale: {
          borderColor: '#313a4d',
          timeVisible: true,
          secondsVisible: false,
        },
        // 配置tooltip
        localization: {
          priceFormatter: (price) => `¥${price.toFixed(2)}`,
          timeFormatter: (time) => {
            const date = new Date(time * 1000);
            return date.toLocaleDateString('zh-CN');
          },
        },
      });

      // 创建蜡烛图
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#52c41a',
        downColor: '#ff4d4f',
        borderDownColor: '#ff4d4f',
        borderUpColor: '#52c41a',
        wickDownColor: '#ff4d4f',
        wickUpColor: '#52c41a',
      });

      // 创建成交量柱状图
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });

      // 转换数据格式 - 确保时间格式正确
      const chartData = data.map(item => {
        let timeValue = item.time_key || item.date;
        
        // 处理不同时间格式
        if (typeof timeValue === 'string') {
          // 如果是字符串格式，直接使用
          timeValue = timeValue;
        } else if (typeof timeValue === 'number') {
          // 如果是Unix时间戳，转换为TradingView格式
          timeValue = Math.floor(timeValue / 1000);
        }
        
        return {
          time: timeValue,
          open: parseFloat(item.open || 0),
          high: parseFloat(item.high || 0),
          low: parseFloat(item.low || 0),
          close: parseFloat(item.close || 0),
          volume: parseInt(item.volume || 0)
        };
      });

      // 设置K线数据
      candlestickSeries.setData(chartData);

      // 设置成交量数据
      const volumeData = chartData.map(item => ({
        time: item.time,
        value: item.volume,
        color: item.close >= item.open ? '#26a69a' : '#ff5252'
      }));
      //volumeSeries.setData(volumeData);

      // 配置悬停提示
      chart.applyOptions({
        crosshair: {
          mode: 1,
          vertLine: {
            width: 1,
            color: '#758696',
            style: 1,
          },
          horzLine: {
            width: 1,
            color: '#758696',
            style: 1,
          },
        },
        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
        },
        handleScale: {
          axisPressedMouseMove: true,
          mouseWheel: true,
          pinch: true,
        },
      });

      // 创建自定义tooltip
      const toolTip = document.createElement('div');
      toolTip.style.position = 'absolute';
      toolTip.style.display = 'none';
      toolTip.style.padding = '8px';
      toolTip.style.background = 'rgba(26, 29, 41, 0.9)';
      toolTip.style.color = '#ffffff';
      toolTip.style.border = '1px solid #313a4d';
      toolTip.style.borderRadius = '4px';
      toolTip.style.fontSize = '12px';
      toolTip.style.pointerEvents = 'none';
      toolTip.style.zIndex = '1000';
      toolTip.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.3)';
      chartContainer.appendChild(toolTip);

      // 监听鼠标移动事件
      chart.subscribeCrosshairMove((param) => {
        if (!param.time || !param.point) {
          toolTip.style.display = 'none';
          return;
        }

        const data = param.seriesData.get(candlestickSeries);
        const volumeData = param.seriesData.get(volumeSeries);
        
        if (!data) {
          toolTip.style.display = 'none';
          return;
        }

        let formattedDate;
        try {
          // 处理不同时间格式
          let timeValue = param.time;
          if (typeof timeValue === 'string') {
            formattedDate = new Date(timeValue).toLocaleDateString('zh-CN');
          } else if (typeof timeValue === 'number') {
            // 处理Unix时间戳
            formattedDate = new Date(timeValue * 1000).toLocaleDateString('zh-CN');
          } else {
            formattedDate = timeValue.toString();
          }
        } catch (error) {
          formattedDate = param.time.toString();
        }
        
        // 构建详细信息
        toolTip.innerHTML = `
          <div style="font-weight: bold; margin-bottom: 4px; color: #faad14;">${formattedDate}</div>
          <div style="display: grid; grid-template-columns: auto auto; gap: 4px 8px;">
            <span style="color: #b0bec5;">开盘:</span>
            <span style="color: #ffffff; font-weight: bold;">¥${data.open?.toFixed(2)}</span>
            
            <span style="color: #b0bec5;">最高:</span>
            <span style="color: #52c41a; font-weight: bold;">¥${data.high?.toFixed(2)}</span>
            
            <span style="color: #b0bec5;">最低:</span>
            <span style="color: #ff4d4f; font-weight: bold;">¥${data.low?.toFixed(2)}</span>
            
            <span style="color: #b0bec5;">收盘:</span>
            <span style="color: #ffffff; font-weight: bold;">¥${data.close?.toFixed(2)}</span>
            
          </div>
        `;

        // 计算位置
        const chartRect = chartContainer.getBoundingClientRect();
        const x = param.point.x + 10;
        const y = param.point.y - 10;
        
        // 确保tooltip不超出边界
        const tooltipWidth = 200;
        const tooltipHeight = 120;
        const adjustedX = Math.min(x, chartRect.width - tooltipWidth - 10);
        const adjustedY = Math.max(10, Math.min(y, chartRect.height - tooltipHeight - 10));
        
        toolTip.style.left = adjustedX + 'px';
        toolTip.style.top = adjustedY + 'px';
        toolTip.style.display = 'block';
      });

      // 自适应时间范围
      chart.timeScale().fitContent();

      chartInstanceRef.current = chart;

      // 响应式处理
      const handleResize = () => {
        if (chartInstanceRef.current && chartContainer) {
          chartInstanceRef.current.applyOptions({
            width: chartContainer.clientWidth,
          });
        }
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        if (chartInstanceRef.current) {
          chartInstanceRef.current.remove();
          chartInstanceRef.current = null;
        }
        if (toolTip && toolTip.parentNode) {
          toolTip.parentNode.removeChild(toolTip);
        }
      };
    }).catch(error => {
      console.error('Failed to load lightweight-charts:', error);
    });

    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
      }
    };
  }, [data, symbol, signals]);

  return (
    <div 
      ref={chartRef} 
      style={{ 
        width: '100%', 
        height: 300,
        background: '#181c24',
        borderRadius: 8,
        border: '1px solid #313a4d',
        position: 'relative'
      }} 
    />
  );
};

export default QuantTradingPanel;
