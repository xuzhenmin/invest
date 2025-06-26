import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Layout, Select, Card, Row, Col, Typography, Statistic, Space, Divider, Alert, Spin, Table, Button, Modal, Input, message, Tag, Tooltip } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, ExperimentOutlined, LoadingOutlined } from '@ant-design/icons';
import axios from 'axios';
import { createChart, CandlestickSeries, BarSeries, BaselineSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import '../styles/table.css';
import ReactECharts from 'echarts-for-react';
import { Progress } from 'antd';
import ReactMarkdown from 'react-markdown';

const { Header, Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';
console.log('API_BASE_URL:', API_BASE_URL);

const tagColors = ['magenta', 'red', 'volcano', 'orange', 'gold', 'lime', 'green', 'cyan', 'blue', 'geekblue', 'purple'];

// 自定义主题颜色
const theme = {
  background: 'linear-gradient(to bottom, #1a1a1a, #0d0d0d)', // 略带渐变的深色背景
  cardBackground: '#2a2a2a',
  text: '#ffffff',
  textSecondary: '#a0a0a0',
  border: '#333333',
  upColor: '#00b578',
  downColor: '#ff4d4f',
  headerBg: '#2a2a2a',
  fontSize: {
    title: '20px',
    subtitle: '16px',
    value: '24px',
    small: '14px'
  },
  // 移动平均线颜色
  maColors: {
    ma5: '#FFD700',  // 金色
    ma20: '#87CEEB', // 天蓝色
    ma60: '#FF69B4', // 热粉色
  }
};

const Dashboard = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('00700.HK');
  const [stockData, setStockData] = useState(null);
  const [klineData, setKlineData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [chartType, setChartType] = useState('candlestick'); 
  const [optionChainData, setOptionChainData] = useState([]);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [diagnosisResult, setDiagnosisResult] = useState(null);
  const [diagnosisModalVisible, setDiagnosisModalVisible] = useState(false);
  const [shouldFetchData, setShouldFetchData] = useState(false);
  const [newsData, setNewsData] = useState([]);
  const [newsModalVisible, setNewsModalVisible] = useState(false);
  const [selectedNews, setSelectedNews] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summary, setSummary] = useState('');
  const [summaryError, setSummaryError] = useState('');
  const [newsSummaryLoading, setNewsSummaryLoading] = useState(false);
  const [newsSummary, setNewsSummary] = useState('');
  const [newsSummaryError, setNewsSummaryError] = useState('');
  const [newsSummaryModalVisible, setNewsSummaryModalVisible] = useState(false);

  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const mainSeriesRef = useRef(null);
  const ma5SeriesRef = useRef(null);
  const ma20SeriesRef = useRef(null);
  const ma60SeriesRef = useRef(null);
  const lastKlineTimeRef = useRef(null);

  // 将 fetchData 移到组件级别
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [stockResponse, klineResponse, optionChainResponse, newsResponse] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/stock/${selectedSymbol}`),
        axios.get(`${API_BASE_URL}/api/stock/${selectedSymbol}/kline`),
        axios.get(`${API_BASE_URL}/api/stock/${selectedSymbol}/option_chain`),
        axios.get(`${API_BASE_URL}/api/stock/${selectedSymbol}/news`),
      ]);
      setStockData(stockResponse.data);
      setKlineData(klineResponse.data);
      setOptionChainData(optionChainResponse.data.optionChain || []);
      if (newsResponse.data.news && newsResponse.data.news.length > 0) {
        setNewsData(newsResponse.data.news);
      } else {
        setNewsData([]);
      }
    } catch (error) {
      console.error('Error details:', {
        message: error.message,
        response: error.response,
        request: error.request,
        config: error.config
      });
      setError(error.response?.data?.error || '获取数据失败，请检查后端服务是否正常运行');
      setOptionChainData([]);
      setNewsData([]);
    } finally {
      setLoading(false);
      setShouldFetchData(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    if (shouldFetchData) {
      fetchData();
    }
  }, [shouldFetchData, fetchData]);

  // New helper function to robustly format any value for display
  const formatDisplayValue = (value) => {
    if (typeof value === 'object' && value !== null) {
      return JSON.stringify(value, null, 2); // Pretty print JSON objects
    }
    return value;
  };

  // 初始化K线图 (只运行一次)
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 350,
      layout: {
        background: { color: theme.cardBackground },
        textColor: theme.text,
      },
      grid: {
        vertLines: { color: theme.border },
        horzLines: { color: theme.border },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      priceScales: {
        right: {
          scaleMargins: { 
            top: 0.1,  
            bottom: 0,
          },
        },
      },
    });

    chartRef.current = chart;
    
    const handleResize = () => {
      chart.applyOptions({
        width: chartContainerRef.current.clientWidth,
      });
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        mainSeriesRef.current = null;
        ma5SeriesRef.current = null;
        ma20SeriesRef.current = null;
        ma60SeriesRef.current = null;
        lastKlineTimeRef.current = null;
      }
    };
  }, []); // 空依赖数组，只运行一次

  // 动态创建和更新图表系列
  useEffect(() => {
    if (!chartRef.current || !klineData.length) return;

    const chart = chartRef.current;

    // 移除旧的主图表系列（如果有）
    if (mainSeriesRef.current) {
      chart.removeSeries(mainSeriesRef.current);
      mainSeriesRef.current = null;
    }
    // 移除旧的移动平均线系列（如果有）
    if (ma5SeriesRef.current) { chart.removeSeries(ma5SeriesRef.current); ma5SeriesRef.current = null; }
    if (ma20SeriesRef.current) { chart.removeSeries(ma20SeriesRef.current); ma20SeriesRef.current = null; }
    if (ma60SeriesRef.current) { chart.removeSeries(ma60SeriesRef.current); ma60SeriesRef.current = null; }

    let newMainSeries;
    let mainData;

    switch (chartType) {
      case 'candlestick':
        newMainSeries = chart.addCandlestickSeries({
          upColor: theme.upColor,
          downColor: theme.downColor,
          borderVisible: false,
          wickUpColor: theme.upColor,
          wickDownColor: theme.downColor,
          priceScaleId: 'right',
        });
        mainData = klineData.map(item => ({
          time: item.time.split(' ')[0],
          open: item.open,
          high: item.high,
          low: item.low,
          close: item.close,
        }));
        break;
      case 'bar':
        newMainSeries = chart.addBarSeries({
          upColor: theme.upColor,
          downColor: theme.downColor,
          priceScaleId: 'right',
        });
        mainData = klineData.map(item => ({
          time: item.time.split(' ')[0],
          open: item.open,
          high: item.high,
          low: item.low,
          close: item.close,
        }));
        break;
      case 'baseline':
        newMainSeries = chart.addBaselineSeries({
          baseValue: { type: 'price', price: klineData[0]?.close || 0 }, 
          topLineColor: theme.upColor,
          topFillColor1: 'rgba(0, 181, 120, 0.28)',
          topFillColor2: 'rgba(0, 181, 120, 0.05)',
          bottomLineColor: theme.downColor,
          bottomFillColor1: 'rgba(255, 77, 79, 0.05)',
          bottomFillColor2: 'rgba(255, 77, 79, 0.28)',
          priceScaleId: 'right',
        });
        mainData = klineData.map(item => ({
          time: item.time.split(' ')[0],
          value: item.close,
        }));
        break;
      case 'histogram':
        newMainSeries = chart.addHistogramSeries({
          color: theme.textSecondary,
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: 'right',
        });
        mainData = klineData.map(item => ({
          time: item.time.split(' ')[0],
          value: item.close,
          color: item.close >= item.open ? theme.upColor : theme.downColor,
        }));
        break;
      default:
        newMainSeries = chart.addCandlestickSeries({
          upColor: theme.upColor,
          downColor: theme.downColor,
          borderVisible: false,
          wickUpColor: theme.upColor,
          wickDownColor: theme.downColor,
          priceScaleId: 'right',
        });
        mainData = klineData.map(item => ({
          time: item.time.split(' ')[0],
          open: item.open,
          high: item.high,
          low: item.low,
          close: item.close,
        }));
        break;
    }

    mainSeriesRef.current = newMainSeries;
    mainSeriesRef.current.setData(mainData);

    // 添加移动平均线 (所有图表类型都显示)
    const ma5Series = chart.addLineSeries({ color: theme.maColors.ma5, lineWidth: 1, crosshairMarkerVisible: false, priceLineVisible: false });
    const ma20Series = chart.addLineSeries({ color: theme.maColors.ma20, lineWidth: 1, crosshairMarkerVisible: false, priceLineVisible: false });
    const ma60Series = chart.addLineSeries({ color: theme.maColors.ma60, lineWidth: 1, crosshairMarkerVisible: false, priceLineVisible: false });

    ma5SeriesRef.current = ma5Series;
    ma20SeriesRef.current = ma20Series;
    ma60SeriesRef.current = ma60Series;

    // Ensure EMA data is mapped correctly and set
    const ema5Data = klineData
      .filter(item => item.EMA5 !== null && item.EMA5 !== undefined)
      .map(item => ({ time: item.time.split(' ')[0], value: item.EMA5 }));
    const ema20Data = klineData
      .filter(item => item.EMA20 !== null && item.EMA20 !== undefined)
      .map(item => ({ time: item.time.split(' ')[0], value: item.EMA20 }));
    const ema60Data = klineData
      .filter(item => item.EMA60 !== null && item.EMA60 !== undefined)
      .map(item => ({ time: item.time.split(' ')[0], value: item.EMA60 }));

    ma5Series.setData(ema5Data);
    ma20Series.setData(ema20Data);
    ma60Series.setData(ema60Data);

    // Ensure the chart is correctly updated when klineData changes
    chart.timeScale().fitContent();

  }, [klineData, chartType, theme]);

  const calculateChange = () => {
    if (!stockData) return { change: 0, changePercent: 0 };
    const change = stockData.current_price - stockData.pre_close;
    const changePercent = (change / stockData.pre_close) * 100;
    return { change, changePercent };
  };

  const { change, changePercent } = calculateChange();
  const isPositive = change >= 0;

  const optionChainColumns = [
    {
      title: '到期日',
      dataIndex: 'strikeTime',
      key: 'strikeTime',
      width: 120,
      render: (text) => <Text style={{ color: theme.text }}>{text}</Text>,
    },
    {
      title: '行权价',
      dataIndex: 'strikePrice',
      key: 'strikePrice',
      width: 100,
      render: (text) => <Text style={{ color: theme.text }}>{text}</Text>,
    },
    {
      title: '看涨期权',
      children: [
        {
          title: '代码',
          dataIndex: ['call', 'basic', 'code'],
          key: 'callCode',
          width: 120,
          render: (text) => <Text style={{ color: theme.text }}>{text}</Text>,
        },
        {
          title: '名称',
          dataIndex: ['call', 'basic', 'name'],
          key: 'callName',
          width: 180,
          render: (text) => <Text style={{ color: theme.text }}>{text}</Text>,
        },
      ],
    },
    {
      title: '看跌期权',
      children: [
        {
          title: '代码',
          dataIndex: ['put', 'basic', 'code'],
          key: 'putCode',
          width: 120,
          render: (text) => <Text style={{ color: theme.text }}>{text}</Text>,
        },
        {
          title: '名称',
          dataIndex: ['put', 'basic', 'name'],
          key: 'putName',
          width: 180,
          render: (text) => <Text style={{ color: theme.text }}>{text}</Text>,
        },
      ],
    },
  ];

  const processOptionChainData = (data) => {
    const processed = [];
    data.forEach(chain => {
      chain.option.forEach(opt => {
        // 确保 call 和 put 都存在
        if (opt.call || opt.put) {
          const callBasic = opt.call?.basic;
          const putBasic = opt.put?.basic;
          const callExData = opt.call?.optionExData;
          const putExData = opt.put?.optionExData;

          processed.push({
            key: `${callBasic?.id || putBasic?.id || Math.random().toString(36).substr(2, 9)}`,
            strikeTime: callExData?.strikeTime || putExData?.strikeTime || chain.strikeTime,
            strikePrice: callExData?.strikePrice || putExData?.strikePrice,
            call: opt.call,
            put: opt.put,
          });
        }
      });
    });
    return processed;
  };

  const displayedOptionChainData = processOptionChainData(optionChainData);

  const handleDiagnosis = async () => {
    // 先验证股票代码
    if (!validateStockCode(selectedSymbol)) {
      message.error('请输入正确的股票代码格式，例如：00700.HK, 600300.SH');
      return;
    }

    try {
      setDiagnosisLoading(true);
      setError(null);
      setDiagnosisModalVisible(true);
      
      // 直接发送诊断请求，让后端自己获取K线数据
      console.log('Making diagnosis request for:', selectedSymbol);
      const response = await axios.post(`${API_BASE_URL}/api/stock/${selectedSymbol}/diagnose`);
      console.log('Diagnosis response:', response.data);
      
      // 尝试解析返回的文本内容为JSON
      let parsedData;
      try {
        // 如果返回的是字符串，尝试解析为JSON
        if (typeof response.data === 'string') {
          parsedData = JSON.parse(response.data);
        } else {
          parsedData = response.data;
        }
        setDiagnosisResult(parsedData);
      } catch (parseError) {
        console.error('Failed to parse diagnosis result:', parseError);
        setError('诊断结果格式错误，请稍后重试');
      }
    } catch (err) {
      console.error('Diagnosis error:', err);
      setError(err.message || err.response?.data?.error || '诊断分析失败，请稍后重试');
    } finally {
      setDiagnosisLoading(false);
    }
  };

  // 新增：格式化技术分析内容
  const formatTechnicalAnalysis = (data) => {
    if (!data) return <span style={{ color: theme.text }}>无技术分析数据。</span>;

    if (typeof data !== 'object' || data === null) {
      return <span style={{ color: theme.text }}>{formatDisplayValue(data)}</span>;
    }

    const { ema_crosses, ema_trends, price_ema_relation, trend_judgment } = data;

    // Fallback if none of the expected keys are present (e.g., if the structure changes again)
    if (!ema_crosses && !ema_trends && !price_ema_relation && !trend_judgment) {
        return <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(data)}</span>;
    }

    return (
      <div>
        {ema_crosses && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>EMA 交叉情况:</Title>
            {typeof ema_crosses === 'string' ? (
              <span style={{ color: theme.text }}>{ema_crosses}</span>
            ) : (
              typeof ema_crosses === 'object' && ema_crosses !== null && Object.keys(ema_crosses).length > 0 ? (
                <ul>
                  {Object.entries(ema_crosses).map(([key, value]) => (
                    <li key={key} style={{ color: theme.textSecondary }}>
                      <span style={{ color: theme.text }}>{key}: </span>{formatDisplayValue(value)}
                    </li>
                  ))}
                </ul>
              ) : (
                <span style={{ color: theme.text }}>无数据。</span>
              )
            )}
          </div>
        )}

        {ema_trends && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>EMA 趋势:</Title>
            {typeof ema_trends === 'string' ? (
              <span style={{ color: theme.text }}>{ema_trends}</span>
            ) : (
              typeof ema_trends === 'object' && ema_trends !== null && Object.keys(ema_trends).length > 0 ? (
                <ul>
                  {Object.entries(ema_trends).map(([key, value]) => (
                    <li key={key} style={{ color: theme.textSecondary }}>
                      <span style={{ color: theme.text }}>{key}: </span>{formatDisplayValue(value)}
                    </li>
                  ))}
                </ul>
              ) : (
                <span style={{ color: theme.text }}>无数据。</span>
              )
            )}
          </div>
        )}

        {price_ema_relation && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>价格与EMA关系:</Title>
            {typeof price_ema_relation === 'string' ? (
              <span style={{ color: theme.text }}>{price_ema_relation}</span>
            ) : (
              typeof price_ema_relation === 'object' && price_ema_relation !== null && Object.keys(price_ema_relation).length > 0 ? (
                <ul>
                  {Object.entries(price_ema_relation).map(([key, value]) => (
                    <li key={key} style={{ color: theme.textSecondary }}>
                      <span style={{ color: theme.text }}>{key}: </span>{formatDisplayValue(value)}
                    </li>
                  ))}
                </ul>
              ) : (
                <span style={{ color: theme.text }}>无数据。</span>
              )
            )}
          </div>
        )}

        {trend_judgment && (
          <div>
            <Title level={5} style={{ color: theme.text }}>趋势判断:</Title>
            <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(trend_judgment)}</span>
          </div>
        )}
      </div>
    );
  };

  // 新增：格式化资金流向分析内容
  const formatCapitalFlowAnalysis = (data) => {
    if (!data) return <span style={{ color: theme.text }}>无资金流向分析数据。</span>;

    if (typeof data !== 'object' || data === null) {
      return <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(data)}</span>;
    }

    const { "30d_trend": trend_30d, main_capital, strength_assessment } = data;

    return (
      <div>
        {trend_30d && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>近30日资金流向趋势:</Title>
            {typeof trend_30d === 'string' ? (
              <span style={{ color: theme.text }}>{trend_30d}</span>
            ) : (
              typeof trend_30d === 'object' && trend_30d !== null && Object.keys(trend_30d).length > 0 ? (
                <ul>
                  {Object.entries(trend_30d).map(([key, value]) => (
                    <li key={key} style={{ color: theme.textSecondary }}>
                      <span style={{ color: theme.text }}>{key}: </span>{formatDisplayValue(value)}
                    </li>
                  ))}
                </ul>
              ) : (
                <span style={{ color: theme.text }}>无数据。</span>
              )
            )}
          </div>
        )}

        {main_capital && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>主力资金动向:</Title>
            {typeof main_capital === 'string' ? (
              <span style={{ color: theme.text }}>{main_capital}</span>
            ) : (
              typeof main_capital === 'object' && main_capital !== null && Object.keys(main_capital).length > 0 ? (
                <ul>
                  {Object.entries(main_capital).map(([key, value]) => (
                    <li key={key} style={{ color: theme.textSecondary }}>
                      <span style={{ color: theme.text }}>{key}: </span>{formatDisplayValue(value)}
                    </li>
                  ))}
                </ul>
              ) : (
                <span style={{ color: theme.text }}>无数据。</span>
              )
            )}
          </div>
        )}

        {strength_assessment && (
          <div>
            <Title level={5} style={{ color: theme.text }}>资金实力分析:</Title>
            <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(strength_assessment)}</span>
          </div>
        )}
      </div>
    );
  };

  // 新增：格式化资金分布分析内容
  const formatCapitalDistributionAnalysis = (data) => {
    if (!data) return <span style={{ color: theme.text }}>无资金分布分析数据。</span>;

    // 如果data是对象，但缺少预期的顶级键，则将其字符串化显示
    if (typeof data === 'object' && data !== null &&
        (!data.hasOwnProperty('main_capital_distribution') || !data.hasOwnProperty('retail_capital_distribution') || !data.hasOwnProperty('capital_structure'))) {
      return <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(data)}</span>;
    }

    const { main_capital_distribution, retail_capital_distribution, capital_structure } = data;

    return (
      <div>
        {main_capital_distribution && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>主力资金分布情况:</Title>
            {typeof main_capital_distribution === 'string' ? (
              <span style={{ color: theme.text }}>{main_capital_distribution}</span>
            ) : (
              <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(main_capital_distribution)}</span>
            )}
          </div>
        )}

        {retail_capital_distribution && (
          <div style={{ marginBottom: '8px' }}>
            <Title level={5} style={{ color: theme.text }}>散户资金分布情况:</Title>
            {typeof retail_capital_distribution === 'string' ? (
              <span style={{ color: theme.text }}>{retail_capital_distribution}</span>
            ) : (
              <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(retail_capital_distribution)}</span>
            )}
          </div>
        )}

        {capital_structure && (
          <div>
            <Title level={5} style={{ color: theme.text }}>资金结构特征:</Title>
            {typeof capital_structure === 'string' ? (
              <span style={{ color: theme.text }}>{capital_structure}</span>
            ) : (
              <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(capital_structure)}</span>
            )}
          </div>
        )}
      </div>
    );
  };

  // 新增：格式化投资建议内容
  const formatInvestmentAdvice = (data) => {
    if (!data) return <span style={{ color: theme.text }}>无投资建议。</span>;
    // If data is an object (unexpected for investment advice), stringify it.
    return <span style={{ color: theme.text, whiteSpace: 'pre-wrap' }}>{formatDisplayValue(data)}</span>;
  };

  // 新增：格式化风险提示内容
  const formatRiskWarning = (data) => {
    if (!data || (Array.isArray(data) && data.length === 0)) return <span style={{ color: theme.text }}>无风险提示。</span>;

    if (typeof data === 'string') {
      return <span style={{ color: '#cf1322' }}>{data}</span>;
    }

    if (Array.isArray(data)) {
      return (
        <ul>
          {data.map((item, index) => (
            <li key={index} style={{ color: theme.textSecondary }}><span style={{ color: '#cf1322' }}>{formatDisplayValue(item)}</span></li>
          ))}
        </ul>
      );
    }

    // Fallback for unexpected object type or other types
    return <span style={{ color: '#cf1322', whiteSpace: 'pre-wrap' }}>{formatDisplayValue(data)}</span>; 
  };

  const renderDiagnosisModal = () => {
    // 格式化数值，保留两位小数
    const formatValue = (value) => {
      return value ? Number(value).toFixed(2) : '';
    };

    const getChartOption = () => {
      if (!diagnosisResult?.charts_data?.technical) return {};

      const { dates, prices, ema5, ema10, ema20, ema60 } = diagnosisResult.charts_data.technical;
      
      // 计算所有数据的最大值和最小值，用于Y轴范围
      const allValues = [...prices, ...ema5, ...ema10, ...ema20, ...ema60].filter(v => v !== null && v !== undefined);
      const maxValue = Math.max(...allValues);
      const minValue = Math.min(...allValues);
      
      // 计算Y轴的范围，留出一定的边距
      const padding = (maxValue - minValue) * 0.05;
      const yAxisMin = Math.floor(minValue - padding);
      const yAxisMax = Math.ceil(maxValue + padding);
      
      return {
        backgroundColor: '#1a1a1a',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          },
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          borderColor: '#333',
          textStyle: {
            color: '#fff'
          },
          formatter: function(params) {
            let result = params[0].axisValue + '<br/>';
            params.forEach(param => {
              result += param.marker + ' ' + param.seriesName + ': ' + formatValue(param.value) + '<br/>';
            });
            return result;
          }
        },
        legend: {
          data: ['价格', 'EMA5', 'EMA10', 'EMA20', 'EMA60'],
          textStyle: {
            color: '#fff'
          },
          top: 0
        },
        grid: {
          left: '2%',
          right: '2%',
          bottom: '2%',
          top: '20px',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLine: {
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#999',
            fontSize: 12
          },
          splitLine: {
            show: true,
            lineStyle: {
              color: '#333'
            }
          }
        },
        yAxis: {
          type: 'value',
          min: yAxisMin,
          max: yAxisMax,
          axisLine: {
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#999',
            fontSize: 12,
            formatter: function(value) {
              return formatValue(value);
            }
          },
          splitLine: {
            lineStyle: {
              color: '#333'
            }
          }
        },
        series: [
          {
            name: '价格',
            type: 'line',
            data: prices.map(formatValue),
            smooth: true,
            lineStyle: {
              width: 2,
              color: '#8884d8'
            },
            itemStyle: {
              color: '#8884d8'
            }
          },
          {
            name: 'EMA5',
            type: 'line',
            data: ema5.map(formatValue),
            smooth: true,
            lineStyle: {
              width: 1,
              color: '#82ca9d'
            },
            itemStyle: {
              color: '#82ca9d'
            }
          },
          {
            name: 'EMA10',
            type: 'line',
            data: ema10.map(formatValue),
            smooth: true,
            lineStyle: {
              width: 1,
              color: '#ffc658'
            },
            itemStyle: {
              color: '#ffc658'
            }
          },
          {
            name: 'EMA20',
            type: 'line',
            data: ema20.map(formatValue),
            smooth: true,
            lineStyle: {
              width: 1,
              color: '#ff8042'
            },
            itemStyle: {
              color: '#ff8042'
            }
          },
          {
            name: 'EMA60',
            type: 'line',
            data: ema60.map(formatValue),
            smooth: true,
            lineStyle: {
              width: 1,
              color: '#0088fe'
            },
            itemStyle: {
              color: '#0088fe'
            }
          }
        ]
      };
    };

    const getCapitalFlowChartOption = () => {
      if (!diagnosisResult?.charts_data?.capital_flow?.historical) return {};

      const historicalData = diagnosisResult.charts_data.capital_flow.historical;
      console.log('Historical Data:', historicalData); // 添加日志以查看原始数据结构
      
      // 确保 historicalData 是数组且每个元素都有 date 和 in_flow 属性
      if (!Array.isArray(historicalData)) {
        console.error('Historical data is not an array:', historicalData);
        return {};
      }

      const dates = historicalData.map(item => {
        if (!item || typeof item !== 'object') {
          console.error('Invalid item in historical data:', item);
          return '';
        }
        // 确保日期格式正确
        const date = item.date || '';
        if (date.includes('T')) {
          // 如果是 ISO 格式，只取日期部分
          return date.split('T')[0];
        }
        return date;
      });
      
      const inFlows = historicalData.map(item => {
        if (!item || typeof item !== 'object') {
          console.error('Invalid item in historical data:', item);
          return 0;
        }
        return item.in_flow || 0;
      });

      console.log('Capital Flow Dates:', dates);
      console.log('Capital Flow InFlows:', inFlows);
      
      return {
        backgroundColor: '#1a1a1a',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          },
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          borderColor: '#333',
          textStyle: {
            color: '#fff'
          },
          formatter: function(params) {
            return params[0].name + ': ' + formatValue(params[0].value);
          }
        },
        legend: {
          data: ['资金流入'],
          textStyle: {
            color: '#fff'
          },
          top: 0
        },
        grid: {
          left: '2%',
          right: '2%',
          bottom: '2%',
          top: '20px',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLine: {
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#999',
            fontSize: 12,
            formatter: function(value) {
              if (!value) return '';
              // 尝试解析日期
              try {
                const date = new Date(value);
                if (!isNaN(date.getTime())) {
                  // 如果是有效日期，显示 MM-DD 格式
                  return `${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                }
              } catch (e) {
                console.error('Date parsing error:', e);
              }
              // 如果不是有效日期，尝试直接截取
              if (typeof value === 'string' && value.length >= 10) {
                return value.substring(5, 10);
              }
              return value;
            }
          },
          splitLine: {
            show: true,
            lineStyle: {
              color: '#333'
            }
          }
        },
        yAxis: {
          type: 'value',
          axisLine: {
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#999',
            fontSize: 12,
            formatter: function(value) {
              return formatValue(value);
            }
          },
          splitLine: {
            lineStyle: {
              color: '#333'
            }
          }
        },
        series: [
          {
            name: '资金流入',
            type: 'line',
            data: inFlows.map(formatValue),
            smooth: true,
            lineStyle: {
              width: 2,
              color: theme.upColor
            },
            itemStyle: {
              color: theme.upColor
            }
          }
        ]
      };
    };

    return (
      <Modal
        title={<span style={{ color: '#fff' }}>股票诊断分析</span>}
        open={diagnosisModalVisible}
        onCancel={() => setDiagnosisModalVisible(false)}
        footer={null}
        width={1000}
        bodyStyle={{ padding: '8px', background: theme.cardBackground }}
        headerStyle={{ padding: '4px 8px', background: theme.headerBg, borderBottom: `1px solid ${theme.border}` }}
        style={{
          top: 20,
          paddingBottom: 20,
        }}
      >
        {diagnosisLoading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '10px', color: '#fff' }}>正在分析中，请稍候...</div>
          </div>
        ) : error ? (
          <Alert
            message="诊断失败"
            description={error}
            type="error"
            showIcon
            style={{
              background: '#2a2a2a',
              border: '1px solid #333'
            }}
          />
        ) : diagnosisResult ? (
          <>
            {console.log('诊断结果全量数据', diagnosisResult)}
            {/* 自动检测 diagnosisResult 里所有为对象的字段 */}
            {(() => {
              function findObjectFields(obj, path = '') {
                if (typeof obj !== 'object' || obj === null) return [];
                let result = [];
                for (const key in obj) {
                  if (!obj.hasOwnProperty(key)) continue;
                  const value = obj[key];
                  const currentPath = path ? `${path}.${key}` : key;
                  if (typeof value === 'object' && value !== null) {
                    result.push({ path: currentPath, type: Array.isArray(value) ? 'array' : 'object', value });
                    result = result.concat(findObjectFields(value, currentPath));
                  }
                }
                return result;
              }
              if (diagnosisResult) {
                const objectFields = findObjectFields(diagnosisResult);
                if (objectFields.length > 0) {
                  console.warn('诊断结果中为对象/数组的字段:', objectFields.map(f => ({ path: f.path, type: f.type, sample: f.value })));
                }
              }
              return null;
            })()}
            <div>
              {/* 评分展示区块（移到最上方，优化样式） */}
              <Card
                title={<span style={{ color: '#fff', letterSpacing: 2 }}>评分总览</span>}
                style={{
                  background: 'linear-gradient(90deg, #232526 0%, #414345 100%)',
                  border: '1px solid #444',
                  marginBottom: '10px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                  borderRadius: 10
                }}
                bodyStyle={{ padding: '10px 18px' }}
              >
                <Row gutter={[24, 8]} justify="center" align="middle">
                  <Col>
                    <div style={{ textAlign: 'center', minWidth: 120 }}>
                      <div style={{ color: '#ffb300', fontSize: 36, fontWeight: 700, lineHeight: 1 }}>{typeof diagnosisResult.overall_score === 'object' ? (diagnosisResult.overall_score.score ?? 'N/A') : (diagnosisResult.overall_score ?? 'N/A')}</div>
                      <div style={{ color: '#fff', fontSize: 14, marginTop: 2 }}>综合得分</div>
                      <div style={{ color: '#ff7043', fontSize: 22, fontWeight: 600, marginTop: 2 }}>{typeof diagnosisResult.overall_score === 'object' ? (diagnosisResult.overall_score.rating ?? 'N/A') : (diagnosisResult.score?.grade ?? 'N/A')}</div>
                      <div style={{ color: '#ffd54f', fontSize: 14 }}>{typeof diagnosisResult.overall_score === 'object' ? (diagnosisResult.overall_score.rating_desc ?? '') : ''}</div>
                    </div>
                  </Col>
                  <Col>
                    <div style={{ textAlign: 'center', minWidth: 110 }}>
                      <div style={{ color: '#00e676', fontSize: 28, fontWeight: 700 }}>{typeof diagnosisResult.technical_score === 'object' ? (diagnosisResult.technical_score.score ?? 'N/A') : (diagnosisResult.technical_score ?? 'N/A')}</div>
                      <div style={{ color: '#fff', fontSize: 13, marginTop: 2 }}>技术面得分</div>
                      <div style={{ color: '#40c4ff', fontSize: 16, fontWeight: 600 }}>{typeof diagnosisResult.technical_score === 'object' ? (diagnosisResult.technical_score.rating ?? '') : (diagnosisResult.score?.technical_grade ?? '')}</div>
                    </div>
                  </Col>
                  <Col>
                    <div style={{ textAlign: 'center', minWidth: 110 }}>
                      <div style={{ color: '#ff5252', fontSize: 28, fontWeight: 700 }}>{typeof diagnosisResult.capital_score === 'object' ? (diagnosisResult.capital_score.score ?? 'N/A') : (diagnosisResult.capital_score ?? 'N/A')}</div>
                      <div style={{ color: '#fff', fontSize: 13, marginTop: 2 }}>资金面得分</div>
                      <div style={{ color: '#ffd740', fontSize: 16, fontWeight: 600 }}>{typeof diagnosisResult.capital_score === 'object' ? (diagnosisResult.capital_score.rating ?? '') : (diagnosisResult.score?.capital_grade ?? '')}</div>
                    </div>
                  </Col>
                  <Col flex="auto">
                    <div style={{ color: '#b0bec5', fontSize: 13, textAlign: 'left', marginLeft: 16, maxWidth: 320, whiteSpace: 'pre-line' }}>
                      {typeof diagnosisResult.overall_score === 'object' ? (diagnosisResult.overall_score.evaluation ?? '') : ''}
                    </div>
                  </Col>
                </Row>
              </Card>

              {/* 技术分析图表 */}
              <Card 
                title={<span style={{ color: '#fff' }}>技术分析图表</span>}
                style={{
                  background: '#2a2a2a',
                  border: '1px solid #333',
                  marginBottom: '6px'
                }}
                bodyStyle={{ padding: '8px' }}
              >
                <ReactECharts
                  option={getChartOption()}
                  style={{ width: '100%', height: '300px' }}
                  theme="dark"
                />
              </Card>

              {/* 分析结果 */}
              <Row gutter={[2, 2]}>
                <Col span={12}>
                  <Card
                    title={<span style={{ color: '#fff' }}>技术分析</span>}
                    style={{
                      background: '#2a2a2a',
                      border: '1px solid #333'
                    }}
                    bodyStyle={{ padding: '8px' }}
                  >
                    {formatTechnicalAnalysis(diagnosisResult.technical_analysis)}
                  </Card>
                </Col>
                <Col span={12}>
                  <Card
                    title={<span style={{ color: '#fff' }}>资金流向分析</span>}
                    style={{
                      background: '#2a2a2a',
                      border: '1px solid #333'
                    }}
                    bodyStyle={{ padding: '8px' }}
                  >
                    {formatCapitalFlowAnalysis(diagnosisResult.capital_flow_analysis)}
                  </Card>
                </Col>
              </Row>

              {/* 历史资金流向图表 */}
              <Card
                title={<span style={{ color: '#fff' }}>历史资金流向图表</span>}
                style={{
                  background: '#2a2a2a',
                  border: '1px solid #333',
                  marginTop: '6px',
                  marginBottom: '6px'
                }}
                bodyStyle={{ padding: '8px' }}
              >
                <ReactECharts
                  option={getCapitalFlowChartOption()}
                  style={{ width: '100%', height: '250px' }}
                  theme="dark"
                />
              </Card>

              {/* 资金分布分析 */}
              <Row gutter={[2, 2]} style={{ marginTop: '6px' }}>
                <Col span={24}>
                  <Card
                    title={<span style={{ color: '#fff' }}>资金分布分析</span>}
                    style={{
                      background: '#2a2a2a',
                      border: '1px solid #333'
                    }}
                    bodyStyle={{ padding: '8px' }}
                  >
                    {formatCapitalDistributionAnalysis(diagnosisResult.capital_distribution_analysis)}
                  </Card>
                </Col>
              </Row>

              {/* 投资建议和风险提示 */}
              <Row gutter={[2, 2]} style={{ marginTop: '6px' }}>
                <Col span={12}>
                  <Card
                    title={<span style={{ color: '#fff' }}>投资建议</span>}
                    type="inner"
                    style={{
                      background: '#2a2a2a',
                      border: '1px solid #333'
                    }}
                    bodyStyle={{ padding: '8px' }}
                  >
                    {formatInvestmentAdvice(diagnosisResult.investment_advice)}
                  </Card>
                </Col>
                <Col span={12}>
                  <Card
                    title={<span style={{ color: '#fff' }}>风险提示</span>}
                    type="inner"
                    style={{
                      background: '#2a2a2a',
                      border: '1px solid #333'
                    }}
                    bodyStyle={{ padding: '8px' }}
                  >
                    {formatRiskWarning(diagnosisResult.risk_warning)}
                  </Card>
                </Col>
              </Row>

              {/* AI诊断报告 */}
              {diagnosisResult?.diagnosis_markdown && (
                <Card
                  title={<span style={{ color: '#1976d2', fontWeight: 700, fontSize: 18 }}>AI诊断报告</span>}
                  style={{
                    background: 'linear-gradient(135deg, #232526 0%, #1a1a2e 100%)',
                    border: '1px solid #444',
                    marginBottom: '10px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                    borderRadius: 10
                  }}
                  bodyStyle={{ padding: '10px 18px' }}
                >
                  <ReactMarkdown
                    children={diagnosisResult.diagnosis_markdown}
                    components={{
                      h1: ({node, ...props}) => <h1 style={{color:'#40c4ff', fontSize:26, fontWeight:700, margin:'12px 0 6px 0'}} {...props} />,
                      h2: ({node, ...props}) => <h2 style={{color:'#40c4ff', fontSize:22, fontWeight:700, margin:'10px 0 4px 0'}} {...props} />,
                      h3: ({node, ...props}) => <h3 style={{color:'#40c4ff', fontSize:18, fontWeight:700, margin:'8px 0 2px 0'}} {...props} />,
                      p: ({node, ...props}) => <p style={{margin:'2px 0 6px 0', color:'#fff', fontSize:16, lineHeight:1.65}} {...props} />,
                      ul: ({node, ...props}) => <ul style={{margin:'4px 0 8px 22px', padding:0, color:'#fff', fontSize:16}} {...props} />,
                      ol: ({node, ...props}) => <ol style={{margin:'4px 0 8px 22px', padding:0, color:'#fff', fontSize:16}} {...props} />,
                      li: ({node, ...props}) => <li style={{margin:'2px 0', color:'#fff', fontSize:16}} {...props} />,
                      strong: ({node, ...props}) => <strong style={{color:'#ffd54f'}} {...props} />,
                      em: ({node, ...props}) => <em style={{color:'#ffd54f'}} {...props} />,
                      blockquote: ({node, ...props}) => <blockquote style={{borderLeft:'3px solid #1976d2', margin:'6px 0', padding:'4px 0 4px 14px', color:'#b0bec5', fontStyle:'italic', background:'rgba(25,118,210,0.05)'}} {...props} />
                    }}
                  />
                </Card>
              )}
            </div>
          </>
        ) : null}
      </Modal>
    );
  };

  // 添加股票代码验证函数
  const validateStockCode = (code) => {
    // 股票代码格式：数字.市场代码
    // 市场代码：HK(港股), SH(上证), SZ(深证), BJ(北交所), US(美股)
    const pattern = /^(\d+)\.(HK|SH|SZ|BJ|US)$/;
    return pattern.test(code);
  };

  // 添加股票代码输入处理函数
  const handleStockCodeChange = (e) => {
    const value = e.target.value.toUpperCase();
    // 只允许输入数字、点和市场代码字母
    const filteredValue = value.replace(/[^0-9.HKSZBJUS]/g, '');
    setSelectedSymbol(filteredValue);
  };

  // 添加股票代码确认处理函数
  const handleStockCodeConfirm = () => {
    if (!validateStockCode(selectedSymbol)) {
      message.error('请输入正确的股票代码格式，例如：00700.HK, 600300.SH');
      return;
    }
    // 设置标志以触发数据刷新
    setShouldFetchData(true);
  };

  return (
    <Layout style={{ 
      minHeight: '100vh', 
      background: theme.background,
      color: theme.text 
    }}>
      <Header style={{ 
        background: theme.headerBg, 
        padding: '0 12px', 
        borderBottom: `1px solid ${theme.border}`,
        height: '48px',
        lineHeight: '48px'
      }}>
        <Row align="middle" justify="space-between">
          <Col>
            <Title level={4} style={{ margin: 0, color: theme.text, fontSize: theme.fontSize.title }}>量化交易系统</Title>
          </Col>
          <Col>
            <Space>
              <Input
                style={{ width: 180 }}
                value={selectedSymbol}
                onChange={handleStockCodeChange}
                onPressEnter={handleStockCodeConfirm}
                placeholder="输入股票代码，如：00700.HK"
                suffix={
                  <Button
                    type="text"
                    size="small"
                    onClick={handleStockCodeConfirm}
                    style={{ color: theme.textSecondary }}
                  >
                    确认
                  </Button>
                }
              />
              <Button
                type="primary"
                icon={<ExperimentOutlined />}
                onClick={handleDiagnosis}
                loading={diagnosisLoading}
                style={{
                  background: theme.upColor,
                  borderColor: theme.upColor,
                }}
              >
                一键诊断
              </Button>
            </Space>
          </Col>
        </Row>
      </Header>
      <Content style={{ padding: '6px' }}>
        {error && (
          <Alert
            message="错误"
            description={error}
            type="error"
            showIcon
            style={{ marginBottom: '6px' }}
          />
        )}
        <Card 
          style={{ 
            background: theme.cardBackground,
            border: `1px solid ${theme.border}`,
            borderRadius: '6px',
            marginBottom: '6px'
          }}
        >
          {loading ? (
            <div style={{ textAlign: 'center', padding: '16px' }}>
              <Spin size="large" tip="加载数据中..." />
            </div>
          ) : (
            <Row gutter={[4, 4]}>
              {/* 股票基本信息 */}
              <Col span={24}>
                <Row gutter={[4, 4]} align="middle">
                  <Col>
                    <Title level={3} style={{ margin: 0, color: theme.text, fontSize: theme.fontSize.title }}>{stockData?.name || '未知'}</Title>
                    <Text type="secondary" style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>{stockData?.code || '未知'}</Text>
                  </Col>
                  <Col flex="auto">
                    <Space size="middle">
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>当前价格</span>}
                        value={stockData?.current_price || 0}
                        precision={2}
                        valueStyle={{ 
                          color: isPositive ? theme.upColor : theme.downColor,
                          fontSize: theme.fontSize.value,
                          fontWeight: 'bold'
                        }}
                        prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                      />
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>涨跌幅</span>}
                        value={changePercent}
                        precision={2}
                        valueStyle={{ 
                          color: isPositive ? theme.upColor : theme.downColor,
                          fontSize: theme.fontSize.value,
                          fontWeight: 'bold'
                        }}
                        prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                        suffix="%"
                      />
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>涨跌额</span>}
                        value={change}
                        precision={2}
                        valueStyle={{ 
                          color: isPositive ? theme.upColor : theme.downColor,
                          fontSize: theme.fontSize.value,
                          fontWeight: 'bold'
                        }}
                        prefix={isPositive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                      />
                    </Space>
                  </Col>
                </Row>
              </Col>

              <Divider style={{ margin: '6px 0', borderColor: theme.border }} />

              {/* 详细行情数据 */}
              <Col span={24}>
                <Row gutter={[4, 4]}>
                  <Col span={6}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>开盘价</span>}
                        value={stockData?.open_price || 0}
                        precision={2}
                        valueStyle={{ color: theme.text, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>最高价</span>}
                        value={stockData?.high_price || 0}
                        precision={2}
                        valueStyle={{ color: theme.upColor, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>最低价</span>}
                        value={stockData?.low_price || 0}
                        precision={2}
                        valueStyle={{ color: theme.downColor, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>昨收价</span>}
                        value={stockData?.pre_close || 0}
                        precision={2}
                        valueStyle={{ color: theme.text, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                </Row>
              </Col>

              {/* 成交信息 */}
              <Col span={24}>
                <Row gutter={[4, 4]}>
                  <Col span={8}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>成交量</span>}
                        value={stockData?.volume || 0}
                        formatter={(value) => `${(value / 10000).toFixed(2)}万`}
                        valueStyle={{ color: theme.text, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>成交额</span>}
                        value={stockData?.turnover || 0}
                        formatter={(value) => `${(value / 100000000).toFixed(2)}亿`}
                        valueStyle={{ color: theme.text, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={{ background: theme.cardBackground, border: `1px solid ${theme.border}` }} bodyStyle={{ padding: '8px' }}>
                      <Statistic
                        title={<span style={{ color: theme.textSecondary, fontSize: theme.fontSize.small }}>更新时间</span>}
                        value={stockData?.update_time || '--:--:--'}
                        valueStyle={{ color: theme.text, fontSize: theme.fontSize.subtitle }}
                      />
                    </Card>
                  </Col>
                </Row>
              </Col>
            </Row>
          )}
        </Card>

        {/* K线图 */}
        <Card 
          style={{ 
            background: theme.cardBackground,
            border: `1px solid ${theme.border}`,
            borderRadius: '6px',
            marginBottom: '6px'
          }}
          bodyStyle={{ padding: '8px' }}
        >
          {/* New wrapper div for chart and overlay */}
          <div ref={chartContainerRef} style={{ position: 'relative', width: '100%', height: '400px' }}>
            {/* 图表类型切换浮层 */}
            <div style={{
              position: 'absolute',
              top: '10px',
              left: '10px',
              zIndex: 10, // 确保浮层在图表之上
              background: theme.cardBackground, // 与卡片背景一致
              borderRadius: '4px',
              padding: '4px 8px',
              display: 'flex',
              gap: '8px',
              border: `1px solid ${theme.border}`,
            }}>
              {[
                { type: 'candlestick', label: 'K线图' },
                { type: 'bar', label: '美国线' },
                { type: 'baseline', label: '基准线' },
                { type: 'histogram', label: '直方图' }
              ].map((item) => (
                <span
                  key={item.type}
                  onClick={() => setChartType(item.type)}
                  style={{
                    cursor: 'pointer',
                    color: chartType === item.type ? theme.upColor : theme.textSecondary,
                    fontWeight: chartType === item.type ? 'bold' : 'normal',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    backgroundColor: chartType === item.type ? 'rgba(0, 181, 120, 0.1)' : 'transparent',
                    transition: 'background-color 0.2s',
                    whiteSpace: 'nowrap', // 防止文字换行
                  }}
                >
                  {item.label}
                </span>
              ))}
            </div>
            {/* Chart container div, now fills the wrapper */}
            {/* The chart will be drawn directly into this div by lightweight-charts */}
          </div>
        </Card>

        {/* 期权链表格 */}
        <Card
          title={<Title level={4} style={{ margin: 0, color: theme.text }}>期权链</Title>}
          style={{
            background: theme.cardBackground,
            border: `1px solid ${theme.border}`,
            borderRadius: '6px',
            marginTop: '6px',
          }}
        >
          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px' }}>
              <Spin size="large" tip="加载期权链数据中..." />
            </div>
          ) : (
            displayedOptionChainData.length > 0 ? (
              <Table
                columns={optionChainColumns}
                dataSource={displayedOptionChainData}
                pagination={{ pageSize: 10 }} // 每页显示10条
                scroll={{ x: 'max-content' }} // 允许水平滚动
                rowKey="key"
                size="small"
                bordered
                style={{ 
                  background: '#1a1a1a', 
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                }}
                // 自定义表格行的背景色，以便在深色主题下可见
                rowClassName={(record, index) => index % 2 === 0 ? 'dark-table-row-even' : 'dark-table-row-odd'}
                locale={{
                  emptyText: <Text style={{ color: theme.textSecondary }}>暂无期权链数据</Text>
                }}
              />
            ) : (
              <Text style={{ color: theme.textSecondary }}>无期权链数据</Text>
            )
          )}
        </Card>

        {/* 新闻瀑布流部分 */}
        {newsData.length > 0 && (
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#e0e0e0', fontSize: '18px' }}>相关资讯</span>
              </div>
            }
            style={{ 
              marginTop: '20px',
              background: theme.cardBackground,
              border: `1px solid ${theme.border}`,
              borderRadius: '6px',
            }}
            headStyle={{ borderBottom: `1px solid ${theme.border}` }}
          >
            <Spin spinning={loading}>
              <Row gutter={[16, 16]}>
                {newsData.map((news, index) => (
                  <Col xs={24} sm={12} md={8} lg={6} key={index}>
                    <Card
                      hoverable
                      style={{ 
                        height: '100%',
                        background: 'linear-gradient(145deg, #2E2E2E, #242424)',
                        border: '1px solid #4a4a4a',
                        borderRadius: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        transition: 'all 0.3s',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                      }}
                      bodyStyle={{
                          padding: '16px',
                          flex: '1',
                          display: 'flex',
                          flexDirection: 'column',
                      }}
                      onClick={() => { setSelectedNews(news); setNewsModalVisible(true); }}
                    >
                      <Typography.Title level={5} ellipsis={{ rows: 2 }} style={{ color: '#87CEEB', marginBottom: '12px', minHeight: '44px' }}>
                        {news.title}
                      </Typography.Title>
                      <Typography.Paragraph ellipsis={{ rows: 3 }} style={{ color: '#c7c7c7', flexGrow: 1, minHeight: '63px' }}>
                        {news.content}
                      </Typography.Paragraph>
                      <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid #4a4a4a' }}>
                        <Space>
                          <Tag color={tagColors[index % tagColors.length]}>{news.source}</Tag>
                          <Typography.Text style={{ fontSize: '12px', color: '#b0bec5' }}>
                            {new Date(news.publish_time).toLocaleString()}
                          </Typography.Text>
                        </Space>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Spin>
          </Card>
        )}

        {/* 资讯明细浮层 */}
        <Modal
          open={newsModalVisible}
          onCancel={() => { setNewsModalVisible(false); setSelectedNews(null); }}
          footer={null}
          width={520}
          bodyStyle={{ background: 'linear-gradient(135deg, #232526 0%, #1a1a2e 100%)', padding: 4, borderRadius: 16 }}
          style={{ 
            top: 80, 
            borderRadius: 16, 
            boxShadow: '0 8px 32px 0 rgba(31,38,135,0.37)'
          }}
          closeIcon={<span style={{ color: '#fff', fontSize: 20 }}>×</span>}
          title={null}
        >
          {selectedNews && (
            <div style={{ padding: 0, borderRadius: 12, overflow: 'hidden', background: 'none' }}>
              {/* 顶部标题区+一键总结按钮 */}
              <div style={{
                background: 'none',
                padding: '12px 12px 6px 12px',
                borderBottom: '1px solid #333',
                borderTopLeftRadius: 12,
                borderTopRightRadius: 12,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8
              }}>
                <div>
                  <div style={{
                    color: '#40c4ff',
                    fontSize: 22,
                    fontWeight: 700,
                    letterSpacing: 1,
                    lineHeight: 1.3,
                    textShadow: '0 2px 8px rgba(64,196,255,0.08)'
                  }}>{selectedNews.title}</div>
                  <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Tag color={tagColors[Math.floor(Math.random()*tagColors.length)]} style={{ fontSize: 13, fontWeight: 500, padding: '2px 10px' }}>{selectedNews.source}</Tag>
                    <span style={{ color: '#ffd54f', fontSize: 13, fontWeight: 500 }}>{new Date(selectedNews.publish_time).toLocaleString()}</span>
                  </div>
                </div>
              </div>
              {/* 内容区 */}
              <div style={{ padding: '10px 12px 6px 12px', background: 'none' }}>
                <div style={{
                  color: '#fff',
                  fontSize: 16,
                  fontWeight: 500,
                  marginBottom: 10,
                  lineHeight: 1.8,
                  textShadow: '0 1px 4px rgba(0,0,0,0.12)',
                  whiteSpace: 'pre-line',
                  wordBreak: 'break-word'
                }}>{selectedNews.content}</div>
                {/* 总结区块 */}
                {summaryLoading && <div style={{ color: '#40c4ff', margin: '8px 0' }}>正在生成总结...</div>}
                {summary && (
                  <div style={{
                    background: 'rgba(25,118,210,0.08)',
                    color: '#fff',
                    borderLeft: '4px solid #1976d2',
                    padding: '10px 14px',
                    borderRadius: 8,
                    margin: '10px 0 0 0',
                    fontSize: 15,
                    fontWeight: 500,
                    whiteSpace: 'pre-line'
                  }}>
                    <span style={{ color: '#1976d2', fontWeight: 700, marginRight: 6 }}>专家总结：</span>
                    {summary}
                  </div>
                )}
                {summaryError && <div style={{ color: '#ff5252', margin: '8px 0' }}>{summaryError}</div>}
                <div style={{ borderTop: '1px solid #333', margin: '10px 0 0 0', paddingTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                  <a href={selectedNews.url} target="_blank" rel="noopener noreferrer" style={{
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: 15,
                    background: '#1976d2',
                    padding: '4px 18px',
                    borderRadius: 8,
                    textDecoration: 'none',
                    boxShadow: '0 2px 8px rgba(25,118,210,0.10)',
                    transition: 'background 0.2s, color 0.2s',
                    border: 'none',
                    marginLeft: 8
                  }}>
                    查看原文
                  </a>
                </div>
              </div>
            </div>
          )}
        </Modal>
        {renderDiagnosisModal()}
        <Modal
          open={newsSummaryModalVisible}
          onCancel={() => setNewsSummaryModalVisible(false)}
          footer={null}
          width={680}
          bodyStyle={{ background: 'linear-gradient(135deg, #232526 0%, #1a1a2e 100%)', padding: 18, borderRadius: 14 }}
          style={{ top: 100, borderRadius: 14 }}
          title={<span style={{ color: '#1976d2', fontWeight: 700, fontSize: 20 }}>专家资讯总结</span>}
        >
          {newsSummary && (
            <div style={{ color: '#fff', fontSize: 16, fontWeight: 500, lineHeight: 1.65 }}>
              <ReactMarkdown
                children={newsSummary}
                components={{
                  h1: ({node, ...props}) => <h1 style={{color:'#40c4ff', fontSize:26, fontWeight:700, margin:'12px 0 6px 0'}} {...props} />,
                  h2: ({node, ...props}) => <h2 style={{color:'#40c4ff', fontSize:22, fontWeight:700, margin:'10px 0 4px 0'}} {...props} />,
                  h3: ({node, ...props}) => <h3 style={{color:'#40c4ff', fontSize:18, fontWeight:700, margin:'8px 0 2px 0'}} {...props} />,
                  p: ({node, ...props}) => <p style={{margin:'2px 0 6px 0', color:'#fff', fontSize:16, lineHeight:1.65}} {...props} />,
                  ul: ({node, ...props}) => <ul style={{margin:'4px 0 8px 22px', padding:0, color:'#fff', fontSize:16}} {...props} />,
                  ol: ({node, ...props}) => <ol style={{margin:'4px 0 8px 22px', padding:0, color:'#fff', fontSize:16}} {...props} />,
                  li: ({node, ...props}) => <li style={{margin:'2px 0', color:'#fff', fontSize:16}} {...props} />,
                  strong: ({node, ...props}) => <strong style={{color:'#ffd54f'}} {...props} />,
                  em: ({node, ...props}) => <em style={{color:'#ffd54f'}} {...props} />,
                  blockquote: ({node, ...props}) => <blockquote style={{borderLeft:'3px solid #1976d2', margin:'6px 0', padding:'4px 0 4px 14px', color:'#b0bec5', fontStyle:'italic', background:'rgba(25,118,210,0.05)'}} {...props} />
                }}
              />
            </div>
          )}
        </Modal>
      </Content>
    </Layout>
  );
};

export default Dashboard; 
