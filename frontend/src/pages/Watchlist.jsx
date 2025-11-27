import React, { useEffect, useState, useRef } from 'react';
import { Row, Col, Form, Input, Button, Select, Table, Tag, message, Divider, Typography, Card, Modal, Tooltip, Collapse, Spin, Drawer, Tabs, InputNumber, DatePicker, Popconfirm, Statistic, Alert, Progress, Layout, Header, Content, Space } from 'antd';
import { UserOutlined, FundOutlined, BellOutlined, SettingOutlined, StockOutlined, CheckCircleTwoTone, ThunderboltOutlined, DownOutlined, UpOutlined, PieChartOutlined, ArrowUpOutlined, ArrowDownOutlined, EyeOutlined, EyeInvisibleOutlined, DollarCircleFilled, DollarCircleOutlined, UserAddOutlined, SaveOutlined, PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, BookOutlined, ExperimentOutlined, LoadingOutlined, ShareAltOutlined, CopyOutlined } from '@ant-design/icons';
import axios from 'axios';
import FundamentalAnalysisResult from '../components/FundamentalAnalysisResult';
import ReactMarkdown from 'react-markdown';
import CapitalDistributionPie from '../components/CapitalDistributionPie';
import TradingNotes from '../components/TradingNotes';
import PlateRanking from '../components/PlateRanking';
import QuantTradingPanel from '../components/QuantTradingPanel';


// K线图表组件
const KLineChart = ({ data, tradeHistory, symbol }) => {
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const chartId = useRef(`kline-${Date.now()}-${Math.random()}`);

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
      // 再次检查容器是否存在（可能在异步过程中被销毁）
      if (!chartRef.current) return;

      // 确保容器是空的
      chartContainer.innerHTML = '';

      // 创建图表
      const chart = createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
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
      });

      // 添加K线数据
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#52c41a',
        downColor: '#ff4d4f',
        borderDownColor: '#ff4d4f',
        borderUpColor: '#52c41a',
        wickDownColor: '#ff4d4f',
        wickUpColor: '#52c41a',
      });

      // 转换数据格式
      const klineData = data.map(item => ({
        time: Math.floor(new Date(item.time_key + 'T00:00:00Z').getTime() / 1000),
        open: parseFloat(item.open) || 0,
        high: parseFloat(item.high) || 0,
        low: parseFloat(item.low) || 0,
        close: parseFloat(item.close) || 0,
      })).filter(item => item.open > 0 && item.high > 0 && item.low > 0 && item.close > 0);

      candlestickSeries.setData(klineData);

      // 添加交易历史标记
      if (tradeHistory && tradeHistory.length > 0) {
        // 过滤掉rejected状态的交易记录，只保留filled状态的记录
        const validTrades = tradeHistory.filter(trade => trade.status === 'filled');
        
        const markers = validTrades.map(trade => {
          // 将交易时间戳转换为对应日期的UTC时间戳
          const tradeDate = new Date(trade.created_at * 1000);
          const tradeDateStr = tradeDate.toISOString().split('T')[0]; // 获取日期部分 YYYY-MM-DD
          const tradeDateUTC = Math.floor(new Date(tradeDateStr + 'T00:00:00Z').getTime() / 1000);
          
          return {
            time: tradeDateUTC,
            position: trade.side === 'buy' ? 'belowBar' : 'aboveBar',
            color: trade.side === 'buy' ? '#52c41a' : '#ff4d4f',
            shape: trade.side === 'buy' ? 'arrowUp' : 'arrowDown',
            text: `${trade.side === 'buy' ? '买入' : '卖出'} ${trade.amount}股 @ ¥${trade.price}`,
            size: 1,
          };
        });

        candlestickSeries.setMarkers(markers);
      }

      // 自适应大小
      const handleResize = () => {
        if (chartInstanceRef.current) {
          try {
            chartInstanceRef.current.applyOptions({
              width: chartContainer.clientWidth,
              height: chartContainer.clientHeight,
            });
          } catch (error) {
            console.log('Chart resize error:', error);
          }
        }
      };

      window.addEventListener('resize', handleResize);
      chartInstanceRef.current = chart;
    }).catch(error => {
      console.error('Failed to load lightweight-charts:', error);
    });

    return () => {
      if (chartInstanceRef.current) {
        try {
          chartInstanceRef.current.remove();
        } catch (error) {
          console.log('Chart cleanup error:', error);
        }
        chartInstanceRef.current = null;
      }
    };
  }, [data, tradeHistory, symbol]);

  return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />;
};

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const { Option } = Select;
const { Title } = Typography;

const defaultRules = [
  { label: '涨跌幅超过5%', value: 'pct_change_5', icon: <StockOutlined style={{ color: '#faad14', marginRight: 4 }} /> },
  { label: '上升通道开启', value: 'wave3_start', icon: <CheckCircleTwoTone twoToneColor="#52c41a" style={{ marginRight: 4 }} /> },
  { label: '下降通道开启', value: 'down_channel_start', icon: <CheckCircleTwoTone twoToneColor="#fa541c" style={{ marginRight: 4 }} /> },
  { label: '量价共振主力协同', value: 'multi_factor_entry_exit', icon: <ThunderboltOutlined style={{ color: '#722ed1', marginRight: 4 }} /> },
  { label: '低估股筛选', value: 'undervalued_stock', icon: <PieChartOutlined style={{ color: '#13c2c2', marginRight: 4 }} /> },
  { label: '中小盘活跃股', value: 'active_smallmidcap_stock', icon: <ThunderboltOutlined style={{ color: '#1890ff', marginRight: 4 }} /> },
];
const tagColors = ['#1890ff', '#faad14', '#52c41a', '#13c2c2', '#722ed1', '#eb2f96', '#fa541c'];

const ruleOptions = [
  { label: '上升通道开启', value: 'wave3_start', icon: <CheckCircleTwoTone twoToneColor="#52c41a" style={{ marginRight: 4 }} /> },
  { label: '下降通道开启', value: 'down_channel_start', icon: <CheckCircleTwoTone twoToneColor="#fa541c" style={{ marginRight: 4 }} /> },
  { label: '涨跌幅超过5%', value: 'pct_change_5', icon: <StockOutlined style={{ color: '#faad14', marginRight: 4 }} /> },
  { label: '量价共振主力协同', value: 'multi_factor_entry_exit', icon: <ThunderboltOutlined style={{ color: '#722ed1', marginRight: 4 }} /> },
  { label: '低估股筛选', value: 'undervalued_stock', icon: <PieChartOutlined style={{ color: '#13c2c2', marginRight: 4 }} /> },
  { label: '中小盘活跃股', value: 'active_smallmidcap_stock', icon: <ThunderboltOutlined style={{ color: '#1890ff', marginRight: 4 }} /> },
];

export default function Watchlist() {
  // 受控表单状态
  const [userId, setUserId] = useState(''); // 默认为空，不从localStorage读取
  const [stocks, setStocks] = useState('');
  const [alerts, setAlerts] = useState([]);
  const [quantTradingEnabled, setQuantTradingEnabled] = useState(false); // 量化交易开关，默认关闭
  const [execModal, setExecModal] = useState(false);
  const [execLoading, setExecLoading] = useState(false);
  const [execResult, setExecResult] = useState([]);
  const [selectedRule, setSelectedRule] = useState('');
  const [showAllStocks, setShowAllStocks] = useState(false);
  const [expandedExtraRows, setExpandedExtraRows] = useState({});
  const [authorizedRows, setAuthorizedRows] = useState({});
  const [authModal, setAuthModal] = useState({ visible: false, rowIndex: null });
  const [authCode, setAuthCode] = useState('');
  const [authError, setAuthError] = useState('');
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [stockSnapshots, setStockSnapshots] = useState({});
  const [snapLoading, setSnapLoading] = useState(false);
  const [sortPctOrder, setSortPctOrder] = useState(null); // null, 'asc', 'desc'
  const [flashRows, setFlashRows] = useState({}); // 记录需要闪烁的股票code
  const prevChgRef = useRef({});
  const [selectedStock, setSelectedStock] = useState(null);
  const [showStockDetail, setShowStockDetail] = useState(false);
  const [stockDetailData, setStockDetailData] = useState(null);
  const [klineData, setKlineData] = useState([]);
  const [minuteData, setMinuteData] = useState([]); // 占位，后续可接分时接口
  const [chartTab, setChartTab] = useState('kline');
  const [financials, setFinancials] = useState([]);
  const [financialsLoading, setFinancialsLoading] = useState(false);
  const [fundamentalLoading, setFundamentalLoading] = useState(false);
  const [fundamentalData, setFundamentalData] = useState(null);
  // 新增：一键诊断相关state
  const [diagnoseLoading, setDiagnoseLoading] = useState(false);
  const [diagnoseModalOpen, setDiagnoseModalOpen] = useState(false);
  const [diagnoseResult, setDiagnoseResult] = useState(null);
  // 新增：行情卡片和Tabs卡片折叠控制
  const [showMarketCard, setShowMarketCard] = useState(true);
  const [showTabsCard, setShowTabsCard] = useState(true);
  // 分时图容器ref
  const minuteChartRef = useRef();
  // 新增：原因详情弹窗控制
  const [showReasonModal, setShowReasonModal] = useState(false);
  const [reasonContent, setReasonContent] = useState('');
  // 右侧预警卡片折叠控制
  const [alertCardCollapsed, setAlertCardCollapsed] = useState(true);
  // 智能盯盘卡片折叠控制
  const [watchCardCollapsed, setWatchCardCollapsed] = useState(true);
  // 假设盯盘内容数据结构如下（后续可从后端获取）
  const [watchlistEvents, setWatchlistEvents] = useState([
    // 示例数据
    { stock: '00700.HK', name: '腾讯控股', time: '2024-07-15 10:05:00', content: '主力资金异动，量比升至1.8，短线关注。' },
    { stock: '600519.SH', name: '贵州茅台', time: '2024-07-15 10:03:00', content: '换手率突破10%，资金流入明显。' },
    { stock: '000001.SZ', name: '平安银行', time: '2024-07-15 09:58:00', content: '股价突破20日均线，短线有望走强。' },
    // ...
  ]);
  // 按时间倒序排列
  const sortedWatchlistEvents = [...watchlistEvents].sort((a, b) => new Date(b.time) - new Date(a.time));
  // 新增智能盯盘相关state
  const [watchlistEventsByStock, setWatchlistEventsByStock] = useState({});
  const [lastSignalTimeMap, setLastSignalTimeMap] = useState({});
  const [newSignalMap, setNewSignalMap] = useState({});
  const [timelineModal, setTimelineModal] = useState({ visible: false, symbol: '', signals: [] });
  // 智能盯盘折叠控制 - 默认折叠
  const [smartMonitorCollapsed, setSmartMonitorCollapsed] = useState(true);
  const [tradingNotesCollapsed, setTradingNotesCollapsed] = useState(true);
  // 量化交易折叠控制
  const [quantTradingCollapsed, setQuantTradingCollapsed] = useState(true);
  // 资金流相关 state
  const [capitalFlow, setCapitalFlow] = useState(null);
  const [capitalFlowLoading, setCapitalFlowLoading] = useState(false);
  // 在 Watchlist 组件内 state 区域添加资金分布相关 state
  const [capitalDistribution, setCapitalDistribution] = useState([]);
  const [capitalDistributionLoading, setCapitalDistributionLoading] = useState(false);
  // 页面级授权
  const [pageAuth, setPageAuth] = useState(false);
  const [pageAuthInput, setPageAuthInput] = useState('');
  const [pageAuthError, setPageAuthError] = useState('');
  // Watchlist 组件 state 区域添加
  const [showBlinkDot, setShowBlinkDot] = useState(true);
  // 定时刷新开关
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  // 1. 新增state
  const [orderBookModal, setOrderBookModal] = useState({ visible: false, symbol: '', name: '' });
  const [orderBookData, setOrderBookData] = useState(null);
  const [rtTickerData, setRtTickerData] = useState(null);
  const [orderBookLoading, setOrderBookLoading] = useState(false);
  const [rtTickerLoading, setRtTickerLoading] = useState(false);
  const [stockDetailModal, setStockDetailModal] = useState({ visible: false, stock: null });
  const [detailKlineData, setDetailKlineData] = useState(null);
  const [detailKlineLoading, setDetailKlineLoading] = useState(false);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [tradeHistoryLoading, setTradeHistoryLoading] = useState(false);
  // 1. 新增ref保存上一次orderBook/rtTicker数据
  const prevOrderBookRef = useRef(null);
  const prevRtTickerRef = useRef(null);
  const [hoveredTradeSignal, setHoveredTradeSignal] = useState(null); // 新增：记录当前hover的信号行
  const [tradeModal, setTradeModal] = useState({ visible: false, stock: null, signal: null });
  const [tradeType, setTradeType] = useState('buy');
  const [tradePrice, setTradePrice] = useState('');
  const [tradeAmount, setTradeAmount] = useState(100);
  const [hasAccount, setHasAccount] = useState(null); // null=未知, false=未创建, true=已创建
  const [createAccountModal, setCreateAccountModal] = useState(false);
  const [accountInfo, setAccountInfo] = useState({});
  const [showAccountPopover, setShowAccountPopover] = useState(false);

  // 页面加载时不自动查询账户信息，不读取localStorage

  // 获取股票详情K线数据
  const fetchStockDetailKline = async (symbol) => {
    setDetailKlineLoading(true);
    try {
      // end默认为今天+1天，确保能查到最新一天的数据
      const today = new Date();
      const tomorrow = new Date(today);
      tomorrow.setDate(today.getDate() + 1);
      const end = tomorrow.toISOString().split('T')[0];
      const start = new Date(Date.now() - 400 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      const response = await axios.get(`${API_BASE_URL}/quant/kline`, {
        params: { symbol, start, end }
      });
      setDetailKlineData(response.data);
    } catch (error) {
      console.error('获取K线数据失败:', error);
      setDetailKlineData(null);
    } finally {
      setDetailKlineLoading(false);
    }
  };

  // 获取交易历史
  const fetchTradeHistory = async (symbol) => {
    setTradeHistoryLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/trade/orders_by_symbol`, {
        params: { user_id: userId, symbol }
      });
      if (response.data.success) {
        setTradeHistory(response.data.orders || []);
      } else {
        setTradeHistory([]);
      }
    } catch (error) {
      console.error('获取交易历史失败:', error);
      setTradeHistory([]);
    } finally {
      setTradeHistoryLoading(false);
    }
  };

  // 获取量化交易信号 - 现在由QuantTradingPanel内部处理
  const fetchQuantSignals = () => {
    // 这个函数现在由QuantTradingPanel组件内部处理
    // 不再重复调用行情接口，直接共享stockSnapshots数据
  };

  // 拉取行情快照、K线和分时
  const fetchStockDetail = (code) => {
    setStockDetailData(null);
    setKlineData([]);
    setMinuteData([]);
    setFinancials([]);
    setFinancialsLoading(true);
    setFundamentalData(null); // 切换股票时清空分析内容
    setShowMarketCard(true); // 默认展开行情卡片
    setShowTabsCard(true);   // 默认展开分时/财务卡片
    
    // 获取基础股票数据
    axios.get(`${API_BASE_URL}/api/stock/${code}`).then(res => setStockDetailData(res.data));
    
    // 获取分时数据（无论当前Tab是什么都要获取）
    axios.get(`${API_BASE_URL}/api/stock/${code}/minute`)
      .then(res => setMinuteData(Array.isArray(res.data) ? res.data : []))
      .catch(() => setMinuteData([]));
    
    // 获取财务数据
    axios.get(`${API_BASE_URL}/api/stock/${code}/financials`)
      .then(res => setFinancials(Array.isArray(res.data) ? res.data : []))
      .catch(() => setFinancials([]))
      .finally(() => setFinancialsLoading(false));
    
    // 获取资金流数据
    setCapitalFlow(null);
    setCapitalFlowLoading(true);
    axios.get(`${API_BASE_URL}/api/stock/${code}/capital_flow`)
      .then(res => setCapitalFlow(res.data))
      .catch(() => setCapitalFlow(null))
      .finally(() => setCapitalFlowLoading(false));
    
    // 获取资金分布数据
    axios.get(`${API_BASE_URL}/quant/capital_distribution`, { params: { symbol: code } })
      .then(res => setCapitalDistribution(Array.isArray(res.data) ? res.data : []))
      .catch(() => setCapitalDistribution([]))
      .finally(() => setCapitalDistributionLoading(false));
  };

  useEffect(() => {
    // 页面初始不自动填充任何信息，所有表单项为空，用户需手动输入ID后查询
  }, []);

  // 获取监控股票快照（首次和stocks变化时，受开关控制）
  useEffect(() => {
    const stockArr = stocks.split(/[ ,，]+/).filter(Boolean);
    // 默认合并关键指数
    const indexCodes = ['000001.SH','399001.SZ','800000.HK','800700.HK'];
    const allSymbols = Array.from(new Set([...stockArr, ...indexCodes]));
    if (!allSymbols.length) {
      setStockSnapshots({});
      prevChgRef.current = {};
      return;
    }
    let timer = null;
    const fetchAll = () => {
      axios
        .get(`${API_BASE_URL}/api/stock/batch`, { params: { symbols: allSymbols.join(',') } })
        .then(res => {
          const snapMap = res.data || {};
          setStockSnapshots(prev => {
            const next = { ...snapMap };
            const newFlashRows = {};
            Object.entries(snapMap).forEach(([code, data]) => {
              if (!data || data.current_price === undefined || data.pre_close === undefined || data.pre_close === 0) return;
              const newPrice = Number(data.current_price);
              const newPreClose = Number(data.pre_close);
              const prevData = prev[code];
              const prevPrice = prevData && prevData.current_price !== undefined ? Number(prevData.current_price) : null;
              const prevPreClose = prevData && prevData.pre_close !== undefined ? Number(prevData.pre_close) : null;
              // 只要current_price或pre_close有变化就闪烁
              const priceChanged = prevPrice !== null && Math.abs(newPrice - prevPrice) > 1e-6;
              const preCloseChanged = prevPreClose !== null && Math.abs(newPreClose - prevPreClose) > 1e-6;
              if (priceChanged || preCloseChanged) {
                newFlashRows[code] = true;
              }
            });
            setFlashRows(newFlashRows);
            if (Object.keys(newFlashRows).length > 0) {
              setTimeout(() => {
                setFlashRows(f => {
                  const cleared = { ...f };
                  Object.keys(newFlashRows).forEach(code => { delete cleared[code]; });
                  return cleared;
                });
              }, 500);
            }
            return next;
          });
        })
        .catch(() => {
          setStockSnapshots({});
        });
    };
    fetchAll();
    if (autoRefreshEnabled) {
      timer = setInterval(fetchAll, 5000);
    }
    return () => clearInterval(timer);
  }, [stocks, autoRefreshEnabled]);

  // 分时图渲染副作用
  useEffect(() => {
    if (!minuteChartRef.current || !Array.isArray(minuteData) || minuteData.length === 0) return;
    
    // 动态引入lightweight-charts
    import('lightweight-charts').then(({ createChart }) => {
      // 清理旧图表
      if (minuteChartRef.current._tvChart) {
        try {
          minuteChartRef.current._tvChart.remove();
        } catch (error) {
          console.log('Chart already disposed');
        }
        minuteChartRef.current._tvChart = null;
      }
      
      const chart = createChart(minuteChartRef.current, {
        width: minuteChartRef.current.clientWidth,
        height: 220,
        layout: { background: { type: 'solid', color: '#232a36' }, textColor: '#b0bec5' },
        grid: { vertLines: { color: '#313a4d' }, horzLines: { color: '#313a4d' } },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#313a4d' },
        rightPriceScale: { borderColor: '#313a4d' },
      });
      
      const series = chart.addLineSeries({ color: '#1890ff', lineWidth: 2 });
      
      // 转换数据格式
      const tvData = Array.isArray(minuteData) ? minuteData.map(item => ({
        time: item.time.length > 10 ? Math.floor(new Date(item.time.replace(/-/g, '/')).getTime() / 1000) : item.time,
        value: Number(item.price)
      })).filter(d => d.time && d.value !== null && !isNaN(d.value)) : [];
      
      series.setData(tvData);
      chart.timeScale().fitContent();
      minuteChartRef.current._tvChart = chart;
    }).catch(error => {
      console.error('Failed to load lightweight-charts:', error);
    });
    
    // 卸载时清理
    return () => {
      if (minuteChartRef.current && minuteChartRef.current._tvChart) {
        try {
          minuteChartRef.current._tvChart.remove();
        } catch (error) {
          console.log('Chart cleanup error:', error);
        }
        minuteChartRef.current._tvChart = null;
      }
    };
  }, [minuteData, chartTab]); // 添加chartTab作为依赖，确保Tab切换时重新渲染

  const handleSave = async () => {
    try {
      const payload = {
        userId,
        stocks: stocks.split(/[ ,，]+/).filter(Boolean),
        alerts,
        quant_trading_enabled: quantTradingEnabled
      };
      console.log('handleSave payload', payload);
      localStorage.setItem('userId', userId);
      await axios.post(`${API_BASE_URL}/watchlist/save/monitor`, payload);
      message.success('设置已保存');
    } catch (e) {
      message.error('保存失败，请检查输入');
    }
  };

  const handleQuery = async () => {
    if (!userId) {
      message.warning('请输入用户ID');
      return;
    }
    try {
      // 查询监控配置
      const res = await axios.get(`${API_BASE_URL}/watchlist/query/monitor?userId=${userId}`);
      const data = res.data || {};
      setStocks(Array.isArray(data.stocks) ? data.stocks.join(',') : (data.stocks || ''));
      setAlerts(data.alerts || []);
      setQuantTradingEnabled(data.quant_trading_enabled || false);
      message.success('查询成功');
    } catch (e) {
      setStocks('');
      setAlerts([]);
      setQuantTradingEnabled(false);
      message.error('未查到该用户配置');
    }
    // 新增：查询账户信息
    try {
      const accRes = await axios.get(`${API_BASE_URL}/api/trade/query`, { params: { user_id: userId } });
      setHasAccount(accRes.data && accRes.data.success);
      setAccountInfo(accRes.data && accRes.data.success ? accRes.data : null);
    } catch (e) {
      setHasAccount(false);
      setAccountInfo(null);
    }
  };

  const handleExec = () => {
    console.log('handleExec called'); // 调试日志
    setExecModal(true);
  };

  const handleDoExec = async () => {
    console.log('handleDoExec called'); // 调试日志
    if (!selectedRule) {
      message.warning('请选择规则');
      return;
    }
    setExecLoading(true);
    try {
      const res = await axios.post(`${API_BASE_URL}/watchlist/${selectedRule}/execute`, { userId });
      setAlerts(res.data.results || []);
      setExecModal(false);
      setExecResult([]);
      setSelectedRule('');
    } catch (e) {
      setAlerts([{ error: e.message || '执行失败' }]);
      setExecModal(false);
      setExecResult([]);
      setSelectedRule('');
    }
    setExecLoading(false);
  };

  // 解析三浪分析结构
  function parseWaveResult(result) {
    if (!result) return {};
    if (typeof result === 'string') {
      try {
        const obj = JSON.parse(result);
        return obj;
      } catch {
        return { desc: result };
      }
    }
    return result;
  }

  // 规则ID到中文名映射
  const ruleNameMap = {
    'pct_change_5': '涨跌幅超过5%',
    'wave3_start': '上升通道开启',
    'down_channel_start': '下降通道开启',
    'multi_factor_entry_exit': '量价共振主力协同',
    'undervalued_stock': '低估股筛选',
    'active_smallmidcap_stock': '中小盘活跃股',
  };

  const columns = [
    { 
      title: <><StockOutlined style={{ color: '#1890ff', marginRight: 4 }} />股票</>, 
      dataIndex: 'stock', 
      key: 'stock', 
      align: 'center',
      render: (stock, record) => (
        <Tooltip title={stock} placement="top">
          <span style={{ color: '#e6f7ff', fontWeight: 600, cursor: 'pointer' }}>{record.name || stock}</span>
        </Tooltip>
      )
    },
    { title: <><SettingOutlined style={{ color: '#faad14', marginRight: 4 }} />预警规则</>, dataIndex: 'rule', key: 'rule', align: 'center', render: rule => <span style={{ color: '#e6f7ff', fontWeight: 500 }}>{ruleNameMap[rule] || rule}</span> },
    { 
      title: '命中状态', 
      dataIndex: 'hit', 
      key: 'hit_status', 
      align: 'center',
      render: hit => hit ? <Tag color="#faad14">命中</Tag> : <Tag>未命中</Tag>
    },
    {
      title: '入场时间',
      dataIndex: 'hit_start_time',
      key: 'hit_start_time',
      render: (text) => text || '—',
    },
    {
      title: '出场时间',
      dataIndex: 'hit_end_time',
      key: 'hit_end_time',
      render: (text) => text || '—',
    },
    {
      title: '原因描述',
      dataIndex: 'extra',
      key: 'extra',
      align: 'center',
      width: 150,
      render: (extra, record, rowIndex) => {
        if (!isAuthorized) {
          return (
            <span style={{ color: '#b0bec5', whiteSpace: 'pre-line', fontSize: 11, lineHeight: 1.2, padding: 0 }}>
              ***
              <a
                style={{ marginLeft: 4, color: '#1890ff', cursor: 'pointer', fontSize: 11 }}
                onClick={e => {
                  e.preventDefault();
                  setAuthModal({ visible: true, rowIndex });
                  setAuthCode('');
                  setAuthError('');
                }}
              >
                授权
              </a>
            </span>
          );
        }
        return (
          <a
            style={{ color: '#1890ff', cursor: 'pointer', fontSize: 12 }}
            onClick={e => {
              e.preventDefault();
              setReasonContent(extra);
              setShowReasonModal(true);
            }}
          >
            查看原因
          </a>
        );
      }
    },
    { 
      title: '价格', 
      dataIndex: 'market_data', 
      key: 'price', 
      align: 'center',
      render: data => (data && typeof data === 'object' && 'close' in data) ? <span style={{ color: '#e6f7ff', fontWeight: 600 }}>{data.close}</span> : null
    },
    { 
      title: <div style={{ textAlign: 'left', width: '100%' }}>涨跌幅</div>,
      dataIndex: 'market_data', 
      key: 'pct_change', 
      align: 'center',
      render: data => {
        if (!data || typeof data !== 'object' || typeof data.pct_change !== 'number') return null;
        const pct = data.pct_change;
        const color = pct > 0 ? '#ff4d4f' : pct < 0 ? '#52c41a' : '#fff';
        const sign = pct > 0 ? '+' : '';
        return <span style={{ color, fontWeight: 600 }}>{sign}{pct}%</span>;
      }
    },
    { title: <><BellOutlined style={{ color: '#eb2f96', marginRight: 4 }} />执行时间</>, dataIndex: 'execute_time', key: 'execute_time', align: 'center', render: t => <span style={{ color: '#e6f7ff' }}>{t}</span> },
    { title: '执行状态', dataIndex: 'status', key: 'status', align: 'center', render: status => status === 'success' ? <Tag color="#52c41a">成功</Tag> : <Tag color="#ff4d4f">失败</Tag> },
  ];

  const stockTags = stocks.split(/[ ,，]+/).filter(Boolean);
  const maxShow = 10;
  const showTags = showAllStocks ? stockTags : stockTags.slice(0, maxShow);
  const hasMoreStocks = stockTags.length > maxShow;

  // 命中和未命中分组
  const hitAlerts = alerts.filter(item => item.hit === true);
  const unhitAlerts = alerts.filter(item => item.hit !== true);

  // 监控股票排序逻辑
  let stockRows = stocks.split(/[ ,，]+/).filter(Boolean);
  if (sortPctOrder) {
    stockRows = stockRows.slice().sort((a, b) => {
      const snapA = stockSnapshots[a];
      const snapB = stockSnapshots[b];
      const priceA = snapA && snapA.current_price !== undefined ? snapA.current_price : null;
      const preCloseA = snapA && snapA.pre_close !== undefined ? snapA.pre_close : null;
      const priceB = snapB && snapB.current_price !== undefined ? snapB.current_price : null;
      const preCloseB = snapB && snapB.pre_close !== undefined ? snapB.pre_close : null;
      let pctA = null, pctB = null;
      if (priceA !== null && preCloseA !== null && preCloseA !== 0) pctA = ((priceA - preCloseA) / preCloseA) * 100;
      if (priceB !== null && preCloseB !== null && preCloseB !== 0) pctB = ((priceB - preCloseB) / preCloseB) * 100;
      if (pctA === null && pctB === null) return 0;
      if (pctA === null) return 1;
      if (pctB === null) return -1;
      return sortPctOrder === 'asc' ? pctA - pctB : pctB - pctA;
    });
  }

  const handleFetchFundamental = async () => {
    if (!selectedStock) return;
    setFundamentalLoading(true);
    setFundamentalData(null);
    setShowMarketCard(true); // 每次点击前先展开
    setShowTabsCard(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/stock/${selectedStock}/fundamental`);
      setFundamentalData(res.data);
      setShowMarketCard(false); // 基本面分析返回后自动折叠
      setShowTabsCard(false);
    } catch (e) {
      setFundamentalData({ error: e.message || '分析失败' });
    }
    setFundamentalLoading(false);
  };

  const handleDiagnose = async () => {
    if (!selectedStock) return;
    setDiagnoseLoading(true);
    setDiagnoseResult(null);
    setDiagnoseModalOpen(true);
    try {
      const res = await axios.post(`${API_BASE_URL}/api/stock/${selectedStock}/diagnose`);
      setDiagnoseResult(res.data);
    } catch (e) {
      setDiagnoseResult({ error: e.message || '诊断失败' });
    }
    setDiagnoseLoading(false);
  };

  const highlightKeys = ['估值', 'valuation', 'fundamental', '命中情况', '详细分析', 'reason', 'desc', '分析', '分析结果'];
  function formatReasonContent(obj, indent = 0) {
    if (obj == null) return null;
    if (typeof obj === 'number') {
      return (
        <div style={{ marginLeft: indent * 16, color: '#fff', fontSize: 13 }}>
          {obj.toFixed(2)}
        </div>
      );
    }
    if (typeof obj === 'string' || typeof obj === 'boolean') {
      return (
        <div style={{ marginLeft: indent * 16, color: '#fff', fontSize: 13 }}>
          {String(obj)}
        </div>
      );
    }
    if (Array.isArray(obj)) {
      return obj.map((item, idx) => (
        <div key={idx} style={{ marginLeft: indent * 16 }}>
          {formatReasonContent(item, indent + 1)}
        </div>
      ));
    }
    // 对象
    return Object.entries(obj).map(([key, value], idx) => {
      const isHighlight = highlightKeys.some(hk => key.toLowerCase().includes(hk.toLowerCase()));
      return (
        <div key={key + idx} style={{ marginLeft: indent * 16, marginBottom: 2 }}>
          <span style={{ color: isHighlight ? '#40a9ff' : '#faad14', fontWeight: isHighlight ? 700 : 500 }}>
            {key}：
          </span>
          {typeof value === 'object' && value !== null
            ? <div style={{ marginTop: 2 }}>{formatReasonContent(value, indent + 1)}</div>
            : (typeof value === 'number' ? <span style={{ color: '#fff', fontWeight: 500 }}>{value.toFixed(2)}</span> : <span style={{ color: '#fff', fontWeight: 500 }}>{String(value)}</span>)}
        </div>
      );
    });
  }

  // 智能盯盘定时轮询（受开关控制）
  useEffect(() => {
    return;
    if (!stocks) return;
    const stockArr = stocks.split(/[ ,，]+/).filter(Boolean);
    if (!stockArr.length) return;

    let timer = null;
    const fetchMonitorSignals = async () => {
      try {
        const res = await axios.post(`${API_BASE_URL}/quant/smart_monitor_signals_by_stock`, {
          symbols: stockArr,
          limit: 5
        });
        const data = res.data || {};
        setWatchlistEventsByStock(data);
        // 新消息提示逻辑
        setNewSignalMap(prev => {
          const newMap = {};
          stockArr.forEach(symbol => {
            const events = data[symbol] || [];
            if (!events.length) return;
            const latestTime = events[0].time;
            if (prev[symbol] !== latestTime) {
              newMap[symbol] = true;
            } else {
              newMap[symbol] = false;
            }
          });
          return newMap;
        });
        setLastSignalTimeMap(prev => {
          const newMap = { ...prev };
          stockArr.forEach(symbol => {
            const events = data[symbol] || [];
            if (events.length) {
              newMap[symbol] = events[0].time;
            }
          });
          return newMap;
        });
      } catch (e) {
        // 可选：错误处理
      }
    };
    fetchMonitorSignals();
    if (autoRefreshEnabled) {
   //   timer = setInterval(fetchMonitorSignals, 30000);
    }
    return () => clearInterval(timer);
  }, [stocks, autoRefreshEnabled]);

  // 智能盯盘渲染逻辑
  const sortedStocks = Object.keys(watchlistEventsByStock)
    .filter(symbol => (watchlistEventsByStock[symbol] || []).length > 0)
    .sort((a, b) => {
      const aTime = watchlistEventsByStock[a][0]?.time || '';
      const bTime = watchlistEventsByStock[b][0]?.time || '';
      return new Date(bTime) - new Date(aTime);
    });

  // 新增：将 watchlistEventsByStock 转为 monitorData 数组结构，供卡片渲染
  let monitorData = Object.entries(watchlistEventsByStock)
    .filter(([symbol, signals]) => Array.isArray(signals) && signals.length > 0)
    .map(([symbol, signals]) => {
      // 优先用信号里的 name，其次用 stockSnapshots 里的 name
      const nameFromSignal = signals[0]?.name;
      const nameFromSnap = stockSnapshots[symbol]?.name;
      return {
        symbol,
        name: nameFromSignal || nameFromSnap || symbol,
        signals: signals.map(ev => ({
          time: ev.time,
          content: ev.signal || ev.content
        }))
      };
    });
  // 按每只股票的最新事件时间倒序排序
  monitorData = monitorData.sort((a, b) => {
    const aTime = a.signals[0]?.time || '';
    const bTime = b.signals[0]?.time || '';
    return new Date(bTime) - new Date(aTime);
  });

  // 括号内字体更小更淡，且内容始终一行展示
  function renderSignalContent(content, isNew) {
    if (!content) return null;
    const match = content.match(/^(.*?)(（.*）)$/);
    let icon = null;
    if (content.includes('涨速异动')) {
      icon = <ArrowUpOutlined style={{ color: '#ff4d4f', fontSize: 13, marginLeft: 4, verticalAlign: 'middle' }} />;
    } else if (content.includes('跌速异动')) {
      icon = <ArrowDownOutlined style={{ color: '#52c41a', fontSize: 13, marginLeft: 4, verticalAlign: 'middle' }} />;
    }
    if (match) {
      return <span style={{ display: 'flex', alignItems: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }} title={content}>
        <span style={{ color: isNew ? '#ffd666' : '#fff', fontWeight: isNew ? 700 : 500, fontSize: 13, letterSpacing: isNew ? 0.2 : 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '55%' }} title={content}>{match[1]}</span>
        <span style={{ color: isNew ? '#ffe58f' : '#b0bec5', fontWeight: 500, fontSize: 11, marginLeft: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '45%' }} title={content}>{match[2]}</span>
        {icon}
      </span>;
    } else {
      return <span style={{ display: 'flex', alignItems: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }} title={content}>
        <span style={{ color: isNew ? '#ffd666' : '#fff', fontWeight: isNew ? 700 : 500, fontSize: 13, letterSpacing: isNew ? 0.2 : 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }} title={content}>{content}</span>
        {icon}
      </span>;
    }
  }

  // 1. 新增定时刷新 useEffect（优化：定时刷新不再设置loading）
  useEffect(() => {
    let timer = null;
    if (orderBookModal.visible && orderBookModal.symbol) {
      // 首次打开时显示loading
      setOrderBookLoading(true);
      setRtTickerLoading(true);
      const fetchData = (showLoading = false) => {
        if (showLoading) setOrderBookLoading(true);
        axios.get(`${API_BASE_URL}/api/stock/${orderBookModal.symbol}/order_book?num=10`)
          .then(res => setOrderBookData(res.data.data))
          .catch(() => setOrderBookData({ error: '获取摆盘失败' }))
          .finally(() => { if (showLoading) setOrderBookLoading(false); });
        if (showLoading) setRtTickerLoading(true);
        axios.get(`${API_BASE_URL}/api/stock/${orderBookModal.symbol}/rt_ticker?num=20`)
          .then(res => setRtTickerData(res.data.data))
          .catch(() => setRtTickerData({ error: '获取逐笔失败' }))
          .finally(() => { if (showLoading) setRtTickerLoading(false); });
      };
      fetchData(true); // 首次显示loading
      timer = setInterval(() => fetchData(false), 5000); // 后续只更新数据
    }
    return () => { if (timer) clearInterval(timer); };
  }, [orderBookModal.visible, orderBookModal.symbol]);

  // 2. 摆盘表格渲染，买一/卖一高亮，价格变动高亮
  useEffect(() => { if (orderBookData) prevOrderBookRef.current = orderBookData; }, [orderBookData]);
  useEffect(() => { if (rtTickerData) prevRtTickerRef.current = rtTickerData; }, [rtTickerData]);

  // 创建账户后刷新账户信息
  const handleCreateAccount = () => {
    if (!userId.trim()) {
      message.error('请先输入用户ID');
      return;
    }
    setCreateAccountModal(false);
    axios.post(`${API_BASE_URL}/api/trade/init`, { user_id: userId })
      .then(res => {
        if (res.data.success) {
          message.success('模拟账户创建成功');
          // 创建成功后查询账户信息
          axios.get(`${API_BASE_URL}/api/trade/query?user_id=${userId}`)
            .then(r2 => setAccountInfo(r2.data && r2.data.account ? r2.data.account : null));
        } else {
          message.error(res.data.msg || '创建失败');
        }
      })
      .catch(err => {
        console.error('创建账户失败:', err);
        message.error('创建账户失败');
      });
  };

  // 手动保存诊断结果到交易笔记
  const handleSaveDiagnosisToNote = async () => {
    if (!userId) {
      message.error('请先输入用户ID');
      return;
    }
    
    if (!selectedStock || !diagnoseResult || diagnoseResult.error) {
      message.error('没有可保存的诊断结果');
      return;
    }

    try {
      // 获取股票名称
      let stockName = selectedStock;
      
      // 方式1：从智能盯盘数据中获取
      if (watchlistEventsByStock[selectedStock] && watchlistEventsByStock[selectedStock].length > 0) {
        stockName = watchlistEventsByStock[selectedStock][0].name || selectedStock;
      }
      
      // 方式2：从股票快照数据中获取
      if (stockSnapshots[selectedStock] && stockSnapshots[selectedStock].name) {
        stockName = stockSnapshots[selectedStock].name;
      }
      
      // 方式3：从股票详情数据中获取
      if (stockDetailData && stockDetailData.name) {
        stockName = stockDetailData.name;
      }
      
      // 如果还是没有获取到名称，使用股票代码
      if (!stockName || stockName === selectedStock) {
        stockName = selectedStock;
      }
      
      // 构建笔记标题和内容
      const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
      const title = `${stockName} 智能诊断 - ${today}`;
      
      // 格式化诊断内容
      let content = `🔬 智能诊断报告\n\n`;
      content += `📈 股票信息\n`;
      content += `• 股票代码：${selectedStock}\n`;
      content += `• 股票名称：${stockName}\n`;
      content += `• 诊断日期：${today}\n\n`;
      
      if (diagnoseResult.diagnosis_markdown) {
        content += `📝 诊断内容\n`;
        // 将markdown转换为纯文本
        const markdownText = diagnoseResult.diagnosis_markdown
          .replace(/#{1,6}\s+/g, '') // 移除标题标记
          .replace(/\*\*(.*?)\*\*/g, '$1') // 移除粗体标记
          .replace(/\*(.*?)\*/g, '$1') // 移除斜体标记
          .replace(/`(.*?)`/g, '$1') // 移除代码标记
          .replace(/>\s*(.*)/g, '$1') // 移除引用标记
          .replace(/\n\n/g, '\n') // 合并多余换行
          .trim();
        content += markdownText;
      }
      
      if (diagnoseResult.result) {
        content += `\n\n🎯 诊断结果\n`;
        content += formatAnalysisData(diagnoseResult.result);
      }
      
      if (diagnoseResult.reason) {
        content += `\n\n💡 诊断理由\n`;
        content += formatAnalysisData(diagnoseResult.reason);
      }
      
      if (diagnoseResult.details) {
        content += `\n\n📋 详细信息\n`;
        content += formatAnalysisData(diagnoseResult.details);
      }
      
      // 创建笔记数据
      const noteData = {
        title: title,
        content: content,
        category: '智能诊断',
        tags: ['手动保存', '诊断报告'],
        stock_code: selectedStock,
        stock_name: stockName,
        trade_type: '观察',
        trade_reason: '手动保存的智能诊断结果',
        mood: '平静',
        lessons: '系统生成的智能诊断报告，用于后续参考',
        risk_level: '中等',
        is_important: false,
        is_public: false,
        weather: '',
        market_sentiment: '',
        technical_indicators: {},
        fundamental_analysis: '',
        news_events: [],
        follow_up_date: ''
      };

      const response = await axios.post(`${API_BASE_URL}/api/trade/notes`, {
        user_id: userId,
        note_data: noteData
      });

      if (response.data.success) {
        const isUpdated = response.data.is_updated;
        if (isUpdated) {
          message.success(`${stockName}的智能诊断结果已更新到交易笔记`);
          console.log(`已更新${stockName}的智能诊断记录`);
        } else {
          message.success(`${stockName}的智能诊断结果已保存到交易笔记`);
          console.log(`已保存${stockName}的智能诊断记录`);
        }
      } else {
        message.error(response.data.msg || '保存失败');
      }
      
    } catch (error) {
      console.error('保存诊断结果到交易笔记失败:', error);
      message.error('保存失败，请稍后重试');
    }
  };

  // 手动保存基本面分析结果到交易笔记
  const handleSaveFundamentalToNote = async () => {
    if (!userId) {
      message.error('请先输入用户ID');
      return;
    }
    
    if (!selectedStock || !fundamentalData || fundamentalData.error) {
      message.error('没有可保存的基本面分析结果');
      return;
    }

    try {
      // 获取股票名称
      let stockName = selectedStock;
      
      // 方式1：从智能盯盘数据中获取
      if (watchlistEventsByStock[selectedStock] && watchlistEventsByStock[selectedStock].length > 0) {
        stockName = watchlistEventsByStock[selectedStock][0].name || selectedStock;
      }
      
      // 方式2：从股票快照数据中获取
      if (stockSnapshots[selectedStock] && stockSnapshots[selectedStock].name) {
        stockName = stockSnapshots[selectedStock].name;
      }
      
      // 方式3：从股票详情数据中获取
      if (stockDetailData && stockDetailData.name) {
        stockName = stockDetailData.name;
      }
      
      // 如果还是没有获取到名称，使用股票代码
      if (!stockName || stockName === selectedStock) {
        stockName = selectedStock;
      }
      
      // 构建笔记标题和内容
      const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
      const title = `${stockName} 基本面分析 - ${today}`;
      
      // 格式化基本面分析内容
      let content = `📊 基本面分析报告\n\n`;
      content += `📈 股票信息\n`;
      content += `• 股票代码：${selectedStock}\n`;
      content += `• 股票名称：${stockName}\n`;
      content += `• 分析日期：${today}\n\n`;
      
      if (fundamentalData.valuation) {
        content += `💰 估值分析\n`;
        content += formatAnalysisData(fundamentalData.valuation);
        content += `\n`;
      }
      
      if (fundamentalData.fundamental) {
        content += `📋 基本面数据\n`;
        content += formatAnalysisData(fundamentalData.fundamental);
        content += `\n`;
      }
      
      if (fundamentalData.analysis) {
        content += `🔍 分析结果\n`;
        content += formatAnalysisData(fundamentalData.analysis);
        content += `\n`;
      }
      
      // 创建笔记数据
      const noteData = {
        title: title,
        content: content,
        category: '基本面分析',
        tags: ['手动保存', '分析报告'],
        stock_code: selectedStock,
        stock_name: stockName,
        trade_type: '观察',
        trade_reason: '手动保存的基本面分析结果',
        mood: '平静',
        lessons: '系统生成的基本面分析报告，用于后续参考',
        risk_level: '中等',
        is_important: false,
        is_public: false,
        weather: '',
        market_sentiment: '',
        technical_indicators: {},
        fundamental_analysis: '',
        news_events: [],
        follow_up_date: ''
      };

      const response = await axios.post(`${API_BASE_URL}/api/trade/notes`, {
        user_id: userId,
        note_data: noteData
      });

      if (response.data.success) {
        const isUpdated = response.data.is_updated;
        if (isUpdated) {
          message.success(`${stockName}的基本面分析结果已更新到交易笔记`);
          console.log(`已更新${stockName}的基本面分析记录`);
        } else {
          message.success(`${stockName}的基本面分析结果已保存到交易笔记`);
          console.log(`已保存${stockName}的基本面分析记录`);
        }
      } else {
        message.error(response.data.msg || '保存失败');
      }
      
    } catch (error) {
      console.error('保存基本面分析结果到交易笔记失败:', error);
      message.error('保存失败，请稍后重试');
    }
  };

  // 格式化分析数据为易读的文本
  const formatAnalysisData = (data, indent = 0) => {
    if (!data) return '';
    
    const prefix = '  '.repeat(indent);
    let result = '';
    
    if (typeof data === 'string') {
      return `${prefix}${data}\n`;
    } else if (typeof data === 'number') {
      return `${prefix}${data.toFixed(2)}\n`;
    } else if (typeof data === 'boolean') {
      return `${prefix}${data ? '是' : '否'}\n`;
    } else if (Array.isArray(data)) {
      data.forEach((item, index) => {
        result += `${prefix}${index + 1}. ${formatAnalysisData(item, indent + 1)}`;
      });
    } else if (typeof data === 'object') {
      Object.entries(data).forEach(([key, value]) => {
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          result += `${prefix}${key}：\n`;
          result += formatAnalysisData(value, indent + 1);
        } else {
          const formattedValue = typeof value === 'number' ? value.toFixed(2) : String(value);
          result += `${prefix}• ${key}：${formattedValue}\n`;
        }
      });
    }
    
    return result;
  };

  // 在tradeModal弹窗中，买入/卖出按钮点击时调用下单接口
  const handleSimTrade = (side) => {
    if (!userId) {
      message.error('请先输入用户ID');
      return;
    }
    if (!tradeModal.stock || !tradeModal.signal) {
      message.error('未选中股票');
      return;
    }
    // 新增：数量必须为100的倍数
    if (tradeAmount % 100 !== 0) {
      message.error('买入/卖出数量必须为100的整数倍');
      return;
    }
    axios.post(`${API_BASE_URL}/api/trade/order`, {
      user_id: userId,
      symbol: tradeModal.stock.symbol,
      price: tradePrice,
      amount: tradeAmount,
      side,
      order_reason: tradeModal.signal?.content || '',
      order_reason_time: tradeModal.signal?.time || ''
    }).then(res => {
      if (res.data && res.data.success) {
        message.success(res.data.msg || '下单成功');
        setTradeModal({ visible: false, stock: null, signal: null });
        // 刷新账户信息
        axios.get(`${API_BASE_URL}/api/trade/query`, { params: { user_id: userId } })
          .then(r2 => setAccountInfo(r2.data && r2.data.account ? r2.data.account : null));
        // 自动记笔记
        try {
          const stockCode = tradeModal.stock.symbol;
          const stockName = tradeModal.stock.name || stockCode;
          const today = new Date();
          const yyyy = today.getFullYear();
          const mm = String(today.getMonth() + 1).padStart(2, '0');
          const dd = String(today.getDate()).padStart(2, '0');
          const dateStr = `${yyyy}-${mm}-${dd}`;
          const noteTitle = `${stockName} - ${side === 'buy' ? '买入' : '卖出'} - ${dateStr}`;
          
          // 构建包含信号事件的笔记内容
          const signalInfo = tradeModal.signal ? 
            `\n触发信号：${tradeModal.signal.content}\n信号时间：${tradeModal.signal.time}` : 
            '';
          
          const noteContent = `自动记录：${side === 'buy' ? '买入' : '卖出'}${stockName}，数量${tradeAmount}，价格${tradePrice}${signalInfo}`;
                      axios.post(`${API_BASE_URL}/api/trade/notes`, {
              user_id: userId,
              note_data: {
                title: noteTitle,
                stock_code: stockCode,
                stock_name: stockName,
                trade_type: side === 'buy' ? '买入' : '卖出',
                trade_price: tradePrice,
                trade_amount: tradeAmount,
                category: '自动记录',
                content: noteContent,
                created_time: today.toISOString(),
                tags: ['自动记录'],
                // 信号相关字段
                order_reason: tradeModal.signal?.content || '',
                order_reason_time: tradeModal.signal?.time || '',
                // 其他字段可按需补充
              }
            });
        } catch (e) { /* 忽略自动记笔记异常 */ }
      } else {
        message.error(res.data && res.data.msg || '下单失败');
      }
    }).catch(() => message.error('下单失败'));
  };

  // 定时刷新账户信息（每10秒，受开关控制）
  useEffect(() => {
    if (!userId || !autoRefreshEnabled) return;
    const fetchAccount = async () => {
      try {
        const accRes = await axios.get(`${API_BASE_URL}/api/trade/query`, { params: { user_id: userId } });
        setHasAccount(accRes.data && accRes.data.success);
        setAccountInfo(accRes.data && accRes.data.success ? accRes.data : null);
      } catch (e) {
        setHasAccount(false);
        setAccountInfo(null);
      }
    };
    fetchAccount();
    const timer = setInterval(fetchAccount, 10000);
    return () => clearInterval(timer);
  }, [userId, autoRefreshEnabled]);

  return (
    <>
      {/* 页面级授权浮层 */}
      {!pageAuth && (
        <div style={{
          position: 'fixed',
          zIndex: 3000,
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          background: 'rgba(24,28,36,0.98)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
        }}>
          <div style={{
            background: '#232a36',
            borderRadius: 16,
            boxShadow: '0 4px 24px 0 rgba(20,30,60,0.18), 0 1.5px 6px 0 #101622',
            padding: '36px 32px 28px 32px',
            minWidth: 320,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}>
            {/* 去掉"访问授权"标题，仅保留输入框和按钮 */}
            <input
              type="password"
              value={pageAuthInput}
              onChange={e => { setPageAuthInput(e.target.value); setPageAuthError(''); }}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  if (pageAuthInput === '888') {
                    setPageAuth(true);
                    setPageAuthError('');
                  } else {
                    setPageAuthError('授权码错误，请重试');
                  }
                }
              }}
              placeholder="请输入授权码"
              style={{
                width: 200,
                padding: '10px 14px',
                borderRadius: 8,
                border: '1.5px solid #313a4d',
                background: '#181c24',
                color: '#fff',
                fontSize: 16,
                marginBottom: 10,
                outline: 'none',
                textAlign: 'center',
                fontWeight: 600,
                letterSpacing: 2,
              }}
              autoFocus
            />
            <button
              onClick={() => {
                if (pageAuthInput === '888') {
                  setPageAuth(true);
                  setPageAuthError('');
                } else {
                  setPageAuthError('授权码错误，请重试');
                }
              }}
              style={{
                width: 200,
                padding: '8px 0',
                borderRadius: 8,
                border: 'none',
                background: '#faad14',
                color: '#232a36',
                fontWeight: 700,
                fontSize: 16,
                marginBottom: 6,
                cursor: 'pointer',
                boxShadow: '0 2px 8px #faad1433',
                transition: 'all 0.2s',
              }}
            >
              进入
            </button>
            {pageAuthError && <div style={{ color: '#ff4d4f', fontWeight: 600, marginTop: 4 }}>{pageAuthError}</div>}
          </div>
        </div>
      )}
      {/* 其余页面内容 */}
      {pageAuth && (
        <>
          <Modal
            title="选择要执行的规则"
            open={execModal}
            onOk={handleDoExec}
            onCancel={() => setExecModal(false)}
            okText="确认"
            cancelText="取消"
            confirmLoading={execLoading}
          >
            <Select
              style={{ width: '100%' }}
              placeholder="请选择规则"
              value={selectedRule}
              onChange={setSelectedRule}
            >
              {ruleOptions.map(rule => (
                <Option key={rule.value} value={rule.value}>{rule.icon}{rule.label}</Option>
              ))}
            </Select>
          </Modal>
          <Modal
            title="请输入授权码"
            open={authModal.visible}
            onOk={() => {
              if (authCode === '888888') {
                setIsAuthorized(true);
                setAuthModal({ visible: false, rowIndex: null });
                setAuthError('');
                message.success('授权成功');
              } else {
                setAuthError('授权码错误，请重试');
              }
            }}
            onCancel={() => {
              setAuthModal({ visible: false, rowIndex: null });
              setAuthCode('');
              setAuthError('');
            }}
            okText="确认"
            cancelText="取消"
          >
            <Input.Password
              placeholder="请输入授权码"
              value={authCode}
              onChange={e => {
                setAuthCode(e.target.value);
                setAuthError('');
              }}
              onPressEnter={() => {
                if (authCode === '888888') {
                  setIsAuthorized(true);
                  setAuthModal({ visible: false, rowIndex: null });
                  setAuthError('');
                  message.success('授权成功');
                } else {
                  setAuthError('授权码错误，请重试');
                }
              }}
            />
            {authError && <div style={{ color: 'red', marginTop: 8 }}>{authError}</div>}
          </Modal>
          {/* 使 Drawer 始终贴在页面最左侧 */}
          <Drawer
            title={
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>{stockDetailData?.name || selectedStock || '股票详情'}</span>
                {selectedStock && (
                  <span style={{ color: '#b0bec5', fontSize: 13, fontWeight: 500, marginLeft: 4 }}>{selectedStock}</span>
                )}
              </span>
            }
            placement="left"
            width={400}
            onClose={() => setShowStockDetail(false)}
            open={showStockDetail}
            styles={{ body: { padding: 0, background: '#181c24' } }}
            getContainer={() => document.body}
            zIndex={2000}
          >
            <div style={{ padding: 16 }}>
              {/* --- 行情区块：移到顶部，紧凑对齐 --- */}
              {!showMarketCard && (
                <div
                  style={{ cursor: 'pointer', color: '#13c2c2', marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  onClick={() => setShowMarketCard(true)}
                >
                  <DownOutlined style={{ fontSize: 18, marginRight: 6 }} />
                  <span style={{ fontWeight: 600 }}>展开行情卡片</span>
                </div>
              )}
              {showMarketCard && (
                <div style={{ background: '#232a36', borderRadius: 8, padding: '12px 12px 8px 12px', marginBottom: 16 }}>
                  <div style={{ fontSize: 28, color: stockDetailData?.current_price > stockDetailData?.pre_close ? '#ff4d4f' : '#52c41a', fontWeight: 700, display: 'flex', alignItems: 'center' }}>
                    {stockDetailData?.current_price !== undefined && stockDetailData?.current_price !== null ? Number(stockDetailData.current_price).toFixed(3) : '--'}
                    {stockDetailData?.pre_close !== undefined && stockDetailData?.current_price !== undefined && (
                      <span style={{ fontSize: 16, marginLeft: 10, fontWeight: 500 }}>
                        {stockDetailData.current_price > stockDetailData.pre_close ? '↑' : stockDetailData.current_price < stockDetailData.pre_close ? '↓' : ''}
                        {stockDetailData.pre_close !== 0 ? (((stockDetailData.current_price - stockDetailData.pre_close) / stockDetailData.pre_close) * 100).toFixed(2) : '--'}%
                      </span>
                    )}
                  </div>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 0,
                    marginTop: 10,
                    fontSize: 14,
                    color: '#e6f7ff',
                    borderTop: '1px solid #232a36',
                    borderBottom: '1px solid #313a4d',
                    background: 'none',
                  }}>
                    {/* 每个指标一行，左对齐，右侧有分割线 */}
                    <div style={{ padding: '6px 0 6px 0', borderRight: '1px solid #313a4d', borderBottom: '1px solid #232a36' }}>最高价：<span style={{ fontWeight: 500 }}>{stockDetailData?.high_price ?? '--'}</span></div>
                    <div style={{ padding: '6px 0 6px 12px', borderBottom: '1px solid #232a36' }}>最低价：<span style={{ fontWeight: 500 }}>{stockDetailData?.low_price ?? '--'}</span></div>
                    <div style={{ padding: '6px 0 6px 0', borderRight: '1px solid #313a4d', borderBottom: '1px solid #232a36' }}>开盘价：<span style={{ fontWeight: 500 }}>{stockDetailData?.open_price ?? '--'}</span></div>
                    <div style={{ padding: '6px 0 6px 12px', borderBottom: '1px solid #232a36' }}>昨收价：<span style={{ fontWeight: 500 }}>{stockDetailData?.pre_close ?? '--'}</span></div>
                    <div style={{ padding: '6px 0 6px 0', borderRight: '1px solid #313a4d' }}>成交量：<span style={{ fontWeight: 500 }}>{stockDetailData?.volume !== undefined ? (stockDetailData.volume / 10000).toFixed(2) + '万' : '--'}</span></div>
                    <div style={{ padding: '6px 0 6px 12px' }}>成交额：<span style={{ fontWeight: 500 }}>{stockDetailData?.turnover !== undefined ? (stockDetailData.turnover / 100000000).toFixed(2) + '亿' : '--'}</span></div>
                  </div>
                  {/* 新增扩展指标区块 */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 0,
                    marginTop: 6,
                    fontSize: 13,
                    color: '#b0bec5',
                    background: 'none',
                  }}>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>换手率：<span style={{ fontWeight: 500 }}>{stockDetailData?.turnover_rate !== undefined && stockDetailData?.turnover_rate !== null ? Number(stockDetailData.turnover_rate).toFixed(2) + '%' : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 12px' }}>振幅：<span style={{ fontWeight: 500 }}>{stockDetailData?.amplitude !== undefined && stockDetailData?.amplitude !== null ? Number(stockDetailData.amplitude).toFixed(2) + '%' : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>均价：<span style={{ fontWeight: 500 }}>{stockDetailData?.avg_price !== undefined && stockDetailData?.avg_price !== null ? Number(stockDetailData.avg_price).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 12px' }}>量比：<span style={{ fontWeight: 500 }}>{stockDetailData?.volume_ratio !== undefined && stockDetailData?.volume_ratio !== null ? Number(stockDetailData.volume_ratio).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>52周最高：<span style={{ fontWeight: 500 }}>{stockDetailData?.highest52weeks_price !== undefined && stockDetailData?.highest52weeks_price !== null ? Number(stockDetailData.highest52weeks_price).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 12px' }}>52周最低：<span style={{ fontWeight: 500 }}>{stockDetailData?.lowest52weeks_price !== undefined && stockDetailData?.lowest52weeks_price !== null ? Number(stockDetailData.lowest52weeks_price).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>总市值：<span style={{ fontWeight: 500 }}>{stockDetailData?.total_market_val !== undefined && stockDetailData?.total_market_val !== null ? (stockDetailData.total_market_val / 100000000).toFixed(2) + '亿' : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 12px' }}>流通市值：<span style={{ fontWeight: 500 }}>{stockDetailData?.circular_market_val !== undefined && stockDetailData?.circular_market_val !== null ? (stockDetailData.circular_market_val / 100000000).toFixed(2) + '亿' : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>市盈率：<span style={{ fontWeight: 500 }}>{stockDetailData?.pe_ratio !== undefined && stockDetailData?.pe_ratio !== null ? Number(stockDetailData.pe_ratio).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 12px' }}>市净率：<span style={{ fontWeight: 500 }}>{stockDetailData?.pb_ratio !== undefined && stockDetailData?.pb_ratio !== null ? Number(stockDetailData.pb_ratio).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>股息TTM：<span style={{ fontWeight: 500 }}>{stockDetailData?.dividend_ttm !== undefined && stockDetailData?.dividend_ttm !== null ? Number(stockDetailData.dividend_ttm).toFixed(2) : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 12px' }}>股息率TTM：<span style={{ fontWeight: 500 }}>{stockDetailData?.dividend_ratio_ttm !== undefined && stockDetailData?.dividend_ratio_ttm !== null ? Number(stockDetailData.dividend_ratio_ttm).toFixed(2) + '%' : '--'}</span></div>
                    <div style={{ padding: '4px 0 4px 0', borderRight: '1px solid #313a4d' }}>每股收益：<span style={{ fontWeight: 500 }}>{stockDetailData?.earning_per_share !== undefined && stockDetailData?.earning_per_share !== null ? Number(stockDetailData.earning_per_share).toFixed(2) : '--'}</span></div>
                  </div>
                 
                </div>
              )}
              {/* Tab 切换分时/日K/财务 */}
              {!showTabsCard && (
                <div
                  style={{ cursor: 'pointer', color: '#13c2c2', marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  onClick={() => setShowTabsCard(true)}
                >
                  <DownOutlined style={{ fontSize: 18, marginRight: 6 }} />
                  <span style={{ fontWeight: 600 }}>展开分时/财务卡片</span>
                </div>
              )}
              {showTabsCard && (
                <Tabs activeKey={chartTab} onChange={setChartTab} style={{ marginBottom: 16 }} items={[
                  { key: 'kline', label: <span className="tab-label">K线</span>, children: (
                    <div style={{ height: 260, background: '#232a36', borderRadius: 8, padding: 8 }}>
                      {detailKlineLoading ? (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                          <Spin size="large" />
                        </div>
                      ) : detailKlineData && detailKlineData.length > 0 ? (
                        <KLineChart 
                          data={detailKlineData} 
                          tradeHistory={tradeHistory}
                          symbol={selectedStock}
                        />
                      ) : (
                        <span style={{ color: '#b0bec5' }}>暂无K线数据</span>
                      )}
                    </div>
                  ) },
                  { key: 'minute', label: <span className="tab-label">分时</span>, children: (
                    <div style={{ height: 260, background: '#232a36', borderRadius: 8, padding: 8 }}>
                      {Array.isArray(minuteData) && minuteData.length > 0 ? (
                        <div ref={minuteChartRef} style={{ width: '100%', height: 220 }} />
                      ) : (
                        <span style={{ color: '#b0bec5' }}>暂无分时数据</span>
                      )}
                    </div>
                  ) },
                  { key: 'financials', label: <span className="tab-label">财务</span>, children: (
                    <div style={{ minHeight: 220, background: '#232a36', borderRadius: 8, padding: 8 }}>
                      {financialsLoading ? <Spin /> : (
                        Array.isArray(financials) && financials.length > 0 ? (() => {
                          // 获取所有字段
                          const keys = Object.keys(financials[0]);
                          // 找到报告期字段
                          const periodKey = keys.find(k => k === '报告期' || k.toLowerCase().includes('period'));
                          // 其余字段
                          const otherKeys = periodKey ? keys.filter(k => k !== periodKey) : keys;
                          // 新顺序
                          const orderedKeys = periodKey ? [periodKey, ...otherKeys] : keys;
                          return (
                            <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                              <table style={{ width: '100%', color: '#b0bec5', fontSize: 12, borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr>
                                    {orderedKeys.map(key => (
                                      <th key={key} style={{ borderBottom: '1px solid #313a4d', padding: '2px 4px', background: '#232a36', color: '#faad14', fontWeight: 700 }}>{key}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {financials.map((row, idx) => (
                                    <tr key={idx} style={{ background: idx % 2 === 0 ? '#232a36' : '#181c24' }}>
                                      {orderedKeys.map((key, i) => {
                                        const val = row[key];
                                        let display;
                                        // 判断是否为报告期字段
                                        const isPeriod = key === '报告期' || key.toLowerCase().includes('period');
                                        if (val === '' || val === null) {
                                          display = '-';
                                        } else if (isPeriod) {
                                          display = val;
                                        } else if (typeof val === 'number' && !isNaN(val)) {
                                          display = val.toFixed(2);
                                        } else if (!isNaN(Number(val)) && val !== true && val !== false && val !== '') {
                                          display = Number(val).toFixed(2);
                                        } else {
                                          display = val;
                                        }
                                        return (
                                          <td
                                            key={i}
                                            style={{
                                              padding: '2px 4px',
                                              borderBottom: '1px solid #232a36',
                                              whiteSpace: 'nowrap',
                                              maxWidth: 120,
                                              overflow: 'hidden',
                                              textOverflow: 'ellipsis'
                                            }}
                                          >
                                            {display}
                                          </td>
                                        );
                                      })}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })() : <span style={{ color: '#b0bec5' }}>暂无财务数据</span>
                      )}
                    </div>
                  ) },
                  { key: 'capitalflow', label: <span className="tab-label">资金流</span>, children: (
                    <div style={{ minHeight: 220, background: '#232a36', borderRadius: 8, padding: 8 }}>
                      {capitalFlowLoading ? <Spin size="small" /> : capitalFlow && Array.isArray(capitalFlow.historical) && capitalFlow.historical.length > 0 ? (
                        <div>
                          <div style={{ marginBottom: 4, color: '#faad14', fontWeight: 600, fontSize: 14 }}>
                            近5日主力净流入：
                            <span style={{ color: capitalFlow.historical.slice(-5).reduce((sum, d) => sum + (d.main_net_in || 0), 0) > 0 ? '#ff7875' : '#52c41a', fontWeight: 700, marginLeft: 4 }}>
                              {capitalFlow.historical.slice(-5).reduce((sum, d) => sum + (d.main_net_in || 0), 0).toFixed(2)} 万元
                            </span>
                          </div>
                          <div style={{ maxHeight: 120, overflowY: 'auto', borderRadius: 6, background: '#181c24', padding: 4 }}>
                            <table style={{ width: '100%', color: '#b0bec5', fontSize: 13, borderCollapse: 'collapse' }}>
                              <thead>
                                <tr>
                                  <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>日期</th>
                                  <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>主力净流入(万)</th>
                                  <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>流入(万)</th>
                                  <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>流出(万)</th>
                                </tr>
                              </thead>
                              <tbody>
                                {capitalFlow.historical.slice(-5).reverse().map((d, i) => (
                                  <tr key={i} style={{ background: i % 2 === 0 ? '#232a36' : '#181c24' }}>
                                    <td style={{ padding: '2px 4px' }}>{d.date || d.time || '-'}</td>
                                    <td style={{ padding: '2px 4px', color: d.main_net_in > 0 ? '#ff7875' : d.main_net_in < 0 ? '#52c41a' : '#b0bec5', fontWeight: 600 }}>{d.main_net_in?.toFixed(2) ?? '-'}</td>
                                    <td style={{ padding: '2px 4px' }}>{d.in_flow?.toFixed(2) ?? '-'}</td>
                                    <td style={{ padding: '2px 4px' }}>{d.out_flow?.toFixed(2) ?? '-'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ) : <span style={{ color: '#b0bec5' }}>暂无资金流数据</span>}
                    </div>
                  ) },
                ]} />
              )}
              {/* 基本面分析按钮和内容展示 */}
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <Button
                  type="primary"
                  loading={fundamentalLoading}
                  onClick={handleFetchFundamental}
                  style={{ background: '#13c2c2', border: 'none', fontWeight: 600, fontSize: 15, borderRadius: 6, boxShadow: '0 2px 8px #13c2c233', marginBottom: 8, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                >
                  <PieChartOutlined style={{ color: '#13c2c2', background: '#fff', borderRadius: '50%', fontSize: 18, marginRight: 4 }} />
                  {fundamentalLoading ? '分析中...' : '基本面分析'}
                </Button>
                <Button
                  type="default"
                  loading={diagnoseLoading}
                  onClick={handleDiagnose}
                  style={{ background: '#faad14', border: 'none', fontWeight: 600, fontSize: 15, borderRadius: 6, boxShadow: '0 2px 8px #faad1433', marginBottom: 8, flex: 1, color: '#232a36', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                >
                  <ThunderboltOutlined style={{ color: '#faad14', background: '#fff', borderRadius: '50%', fontSize: 18, marginRight: 4 }} />
                  {diagnoseLoading ? '诊断中...' : '一键诊断'}
                </Button>
              </div>
              {fundamentalData && !fundamentalLoading && (
                fundamentalData.error ? (
                  <Card style={{ background: '#232a36', borderRadius: 10, boxShadow: '0 2px 8px #0003', border: 'none', padding: 0 }} styles={{ body: { padding: 16 } }}>
                    {fundamentalData.error}
                  </Card>
                ) : (
                  <Card 
                    style={{ background: '#232a36', borderRadius: 10, boxShadow: '0 2px 8px #0003', border: 'none', padding: 0 }} 
                    styles={{ body: { padding: 16 } }}
                    title={
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ color: '#fff', fontSize: 16, fontWeight: 600 }}>基本面分析结果</span>
                        <div style={{ marginRight: 30 }}>
                          <Tooltip title="保存到交易笔记">
                            <Button
                              type="text"
                              icon={<SaveOutlined />}
                              style={{ 
                                color: '#722ed1', 
                                border: 'none',
                                background: 'transparent',
                                fontSize: 16
                              }}
                              onClick={handleSaveFundamentalToNote}
                            />
                          </Tooltip>
                        </div>
                      </div>
                    }
                  >
                    <FundamentalAnalysisResult data={fundamentalData} />
                  </Card>
                )
              )}
              {/* 一键诊断结果弹窗 */}
              <Modal
                title={
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>一键诊断</span>
                    {diagnoseResult && !diagnoseResult.error && (
                      <div style={{ marginRight: 30 }}>
                        <Tooltip title="保存到交易笔记">
                          <Button
                            type="text"
                            icon={<SaveOutlined />}
                            style={{ 
                              color: '#722ed1', 
                              border: 'none',
                              background: 'transparent',
                              fontSize: 16
                            }}
                            onClick={handleSaveDiagnosisToNote}
                          />
                        </Tooltip>
                      </div>
                    )}
                  </div>
                }
                open={diagnoseModalOpen}
                onCancel={() => setDiagnoseModalOpen(false)}
                footer={null}
                width={700}
                styles={{ body: { background: '#232a36', color: '#fff', maxHeight: 600, overflowY: 'auto' } }}
                style={{ background: '#232a36' }}
              >
                {diagnoseLoading ? (
                  <Spin />
                ) : diagnoseResult && diagnoseResult.error ? (
                  <div style={{ color: '#ff4d4f', fontWeight: 600 }}>{diagnoseResult.error}</div>
                ) : diagnoseResult && diagnoseResult.diagnosis_markdown ? (
                  <div style={{ color: '#fff', fontSize: 15 }}>
                    <div className="diagnosis-markdown" style={{ color: '#fff' }}>
                      <ReactMarkdown
                        children={diagnoseResult.diagnosis_markdown}
                        components={{
                          h1: ({node, ...props}) => <h1 style={{color:'#faad14', fontSize:22, fontWeight:700, margin:'18px 0 8px 0'}} {...props} />,
                          h2: ({node, ...props}) => <h2 style={{color:'#13c2c2', fontSize:18, fontWeight:700, margin:'14px 0 6px 0'}} {...props} />,
                          h3: ({node, ...props}) => <h3 style={{color:'#40a9ff', fontSize:16, fontWeight:700, margin:'10px 0 4px 0'}} {...props} />,
                          li: ({node, ...props}) => <li style={{marginBottom:4, fontSize:15}} {...props} />,
                          strong: ({node, ...props}) => <strong style={{color:'#faad14'}} {...props} />,
                          p: ({node, ...props}) => <p style={{margin:'6px 0', fontSize:15, color:'#fff'}} {...props} />,
                          ul: ({node, ...props}) => <ul style={{paddingLeft:22, margin:'8px 0'}} {...props} />,
                          ol: ({node, ...props}) => <ol style={{paddingLeft:22, margin:'8px 0'}} {...props} />,
                          code: ({node, ...props}) => <code style={{background:'#181c24', color:'#faad14', borderRadius:4, padding:'2px 4px', fontSize:14}} {...props} />,
                          blockquote: ({node, ...props}) => <blockquote style={{borderLeft:'4px solid #faad14', margin:'8px 0', padding:'4px 0 4px 12px', color:'#b0bec5', fontStyle:'italic', background:'#181c24'}} {...props} />
                        }}
                      />
                    </div>
                  </div>
                ) : null}
              </Modal>
              

              {showTabsCard && (
                <div style={{ marginTop: 12, marginBottom: 8 }}>
                  <Card style={{ background: '#232a36', borderRadius: 10, boxShadow: '0 2px 8px #0003', border: 'none', padding: 0 }} styles={{ body: { padding: 8 } }}>
                    <div style={{ color: '#faad14', fontWeight: 700, fontSize: 15, marginBottom: 4, display: 'flex', alignItems: 'center' }}>
                      <PieChartOutlined style={{ color: '#faad14', marginRight: 6, fontSize: 18 }} />资金分布
                    </div>
                    {capitalDistributionLoading ? <Spin size="small" /> : (
                      <CapitalDistributionPie data={capitalDistribution} />
                    )}
                  </Card>
                </div>
              )}
            </div>
          </Drawer>
          
          {/* TimelineModal - 移到Drawer外面，确保不被遮挡 */}
          <Modal
            open={timelineModal.visible}
            onCancel={() => {
              setTimelineModal({ visible: false, symbol: '', signals: [] });
            }}
            footer={null}
            width={400}
            styles={{ 
              body: { background: '#232a36', color: '#fff', maxHeight: 600, overflowY: 'auto', borderRadius: 12, padding: 0 },
              mask: { zIndex: 99999 },
              wrapper: { zIndex: 100000 }
            }}
            style={{ top: 80, borderRadius: 12, zIndex: 100001 }}
            closeIcon={<span style={{ color: '#fff', fontSize: 20 }}>×</span>}
            title={null}

            destroyOnHidden
            forceRender={true}
            getContainer={() => document.body}
            maskClosable={true}
            keyboard={true}
          >
            <div style={{ padding: '18px 18px 0 18px', borderBottom: '1px solid #2b2f3a', background: 'none', borderTopLeftRadius: 12, borderTopRightRadius: 12, marginBottom: 0 }}>
              <span style={{ color: '#40a9ff', fontWeight: 700, fontSize: 15 }}>{timelineModal.symbol}</span>
              <div style={{ color: '#b0bec5', fontSize: 12, marginTop: 4 }}>
                信号数量: {timelineModal.signals?.length || 0}
              </div>
            </div>
            <div style={{ padding: '12px 18px 18px 18px', position: 'relative' }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 5, borderRadius: 5, background: 'linear-gradient(180deg,#13c2c2 0%,#40a9ff 100%)', opacity: 0.7 }} />
              <div style={{ marginLeft: 18, display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {Array.isArray(timelineModal.signals) && timelineModal.signals.length > 0
                  ? timelineModal.signals.map((event, idx) => (
                        <div key={event.time + event.content} style={{ display: 'flex', alignItems: 'flex-start', minHeight: 36, position: 'relative' }}>
                          <div style={{ position: 'absolute', left: -14, top: 6, width: 16, height: 16, background: 'radial-gradient(circle,#40a9ff 60%,#13c2c2 100%)', border: '2px solid #fff', borderRadius: '50%', boxShadow: '0 0 6px #13c2c2', zIndex: 2 }} />
                          <div style={{ marginLeft: 10, background: 'linear-gradient(90deg,#232a36 60%,#181c24 100%)', borderRadius: 7, boxShadow: '0 2px 8px #0003', padding: '4px 8px', minWidth: 120, maxWidth: 260, color: '#fff', border: '1.2px solid #313a4d', fontSize: 12 }}>
                            <div style={{ fontWeight: 700, fontSize: 13, color: '#40a9ff', marginBottom: 1 }}>{renderSignalContent(event.content, false)}</div>
                            <div style={{ color: '#b0bec5', fontSize: 11, marginTop: 1 }}>{event.time}</div>
                          </div>
                        </div>
                      ))
                    : <div style={{ color: '#b0bec5', fontSize: 13, padding: 12 }}>暂无事件</div>}
              </div>
            </div>
          </Modal>
          
          <Modal
            title="原因详情"
            open={showReasonModal}
            onOk={() => setShowReasonModal(false)}
            onCancel={() => setShowReasonModal(false)}
            footer={null}
            styles={{ body: { background: '#232a36', color: '#fff' } }}
            style={{ background: '#232a36' }}
          >
            {formatReasonContent(reasonContent)}
          </Modal>
          <Row style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #181c24 0%, #232a36 100%)', color: '#fff' }}>
            <Col span={6} style={{ padding: 12, borderRight: '1px solid #222', background: 'rgba(24,28,36,0.98)', boxShadow: '2px 0 12px #0002' }}>
              <Collapse 
                defaultActiveKey={[]} 
                style={{ background: '#232a36', borderRadius: 10, boxShadow: '0 2px 8px #0003', border: 'none', marginBottom: 8 }}
                expandIconPosition="end"
                items={[
                  {
                    key: '1',
                    label: <span style={{ color: '#faad14', fontWeight: 700, fontSize: 16 }}> <SettingOutlined style={{ color: '#faad14', marginRight: 8 }} />自选股监控设置</span>,
                    children: (
                      <Form layout="vertical">
                        <Form.Item label={<span style={{ color: '#1890ff', fontSize: 13 }}><UserOutlined style={{ marginRight: 4 }} />用户ID</span>} style={{ marginBottom: 10 }}>
                          <Space.Compact style={{ width: '100%' }}>
                            <Input
                              value={userId}
                              onChange={e => setUserId(e.target.value)}
                              placeholder="请输入用户ID"
                              style={{ width: '70%', minWidth: 80, borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
                            />
                            <Button
                              type="default"
                              size="small"
                              onClick={handleQuery}
                              style={{
                                width: '30%',
                                minWidth: 60,
                                background: '#232a36',
                                border: '1.5px solid #52c41a',
                                color: '#52c41a',
                                fontWeight: 600,
                                height: 32,
                                boxShadow: '0 0 0 1px #52c41a33',
                                transition: 'all 0.2s',
                                borderTopLeftRadius: 0,
                                borderBottomLeftRadius: 0
                              }}
                              onMouseOver={e => {
                                e.currentTarget.style.border = '1.5px solid #7cffb2';
                                e.currentTarget.style.color = '#7cffb2';
                              }}
                              onMouseOut={e => {
                                e.currentTarget.style.border = '1.5px solid #52c41a';
                                e.currentTarget.style.color = '#52c41a';
                              }}
                            >
                              <UserOutlined /> 查询
                            </Button>
                          </Space.Compact>
                        </Form.Item>
                        <Form.Item label={<span style={{ color: '#1890ff', fontSize: 13 }}><FundOutlined style={{ marginRight: 4 }} />监控股票列表</span>}>
                          <Input.TextArea value={stocks} onChange={e => setStocks(e.target.value)} placeholder="输入股票代码，用逗号或空格分隔" rows={2} />
                        </Form.Item>
                        <Form.Item label={<span style={{ color: '#1890ff', fontSize: 13 }}><SettingOutlined style={{ marginRight: 4 }} />量化交易开关</span>}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div 
                              style={{
                                width: 40,
                                height: 20,
                                background: quantTradingEnabled ? '#52c41a' : '#313a4d',
                                borderRadius: 10,
                                cursor: 'pointer',
                                position: 'relative',
                                transition: 'all 0.3s ease',
                                border: '1px solid #313a4d'
                              }}
                              onClick={() => setQuantTradingEnabled(!quantTradingEnabled)}
                            >
                              <div 
                                style={{
                                  width: 16,
                                  height: 16,
                                  background: '#fff',
                                  borderRadius: '50%',
                                  position: 'absolute',
                                  top: 1,
                                  left: quantTradingEnabled ? 22 : 2,
                                  transition: 'all 0.3s ease',
                                  boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
                                }}
                              />
                            </div>
                            <span style={{ color: quantTradingEnabled ? '#52c41a' : '#b0bec5', fontSize: 12 }}>
                              {quantTradingEnabled ? '已开启' : '已关闭'}
                            </span>
                          </div>
                        </Form.Item>
                        <Form.Item style={{ marginBottom: 0 }}>
                          <Button
                            type="button"
                            onClick={handleSave}
                            style={{ background: '#1890ff', border: 'none', fontWeight: 600, height: 38, fontSize: 16, color: '#fff' }}
                            block
                          >
                            <SettingOutlined /> 保存设置
                          </Button>
                        </Form.Item>
                      </Form>
                    ),
                    style: { background: '#232a36', borderRadius: 10, border: 'none', color: '#e6f7ff' }
                  }
                ]}
              />
              {/* 监控股票列表展示 */}
              <Card style={{ background: '#232a36', borderRadius: 10, marginTop: 8, marginBottom: 8, boxShadow: '0 2px 8px #0003', border: 'none', padding: 0 }} styles={{ body: { padding: 10 } }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div style={{ color: '#faad14', fontWeight: 700, fontSize: 15 }}>
                    <StockOutlined style={{ marginRight: 6 }} />监控股票列表
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ color: '#b0bec5', fontSize: 12, fontWeight: 500 }}>
                      {autoRefreshEnabled ? '自动刷新' : '已暂停'}
                    </span>
                    <div 
                      style={{
                        width: 40,
                        height: 20,
                        background: autoRefreshEnabled ? '#52c41a' : '#313a4d',
                        borderRadius: 10,
                        cursor: 'pointer',
                        position: 'relative',
                        transition: 'all 0.3s ease',
                        border: '1px solid #313a4d'
                      }}
                      onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
                    >
                      <div 
                        style={{
                          width: 16,
                          height: 16,
                          background: '#fff',
                          borderRadius: '50%',
                          position: 'absolute',
                          top: 1,
                          left: autoRefreshEnabled ? 22 : 2,
                          transition: 'all 0.3s ease',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
                        }}
                      />
                    </div>
                  </div>
                </div>
                {/* 表头 */}
                <div style={{ display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 700, color: '#b0bec5', marginBottom: 4, paddingLeft: 2 }}>
                  <span style={{ flex: '0 0 50%', maxWidth: '50%', textAlign: 'left' }}>股票名称</span>
                  <span style={{ flex: '0 0 15%', maxWidth: '15%', textAlign: 'center' }}>最新价</span>
                  <span
                    style={{ flex: '0 0 35%', maxWidth: '35%', textAlign: 'center', cursor: 'pointer', userSelect: 'none', color: sortPctOrder ? '#faad14' : '#b0bec5' }}
                    onClick={() => setSortPctOrder(order => order === 'desc' ? 'asc' : order === 'asc' ? null : 'desc')}
                  >
                    涨跌幅
                    {sortPctOrder === 'desc' && <span style={{ marginLeft: 2 }}>▼</span>}
                    {sortPctOrder === 'asc' && <span style={{ marginLeft: 2 }}>▲</span>}
                  </span>
                </div>
                {snapLoading ? <Spin size="small" /> : null}
                <div style={{ maxHeight: 480, overflowY: 'auto' }}>
                  {stockRows.length === 0 && <div style={{ color: '#b0bec5', fontSize: 12 }}>暂无股票</div>}
                  {stockRows.map((code, idx, arr) => {
                    const snap = stockSnapshots[code];
                    const price = snap && snap.current_price !== undefined ? Number(snap.current_price) : null;
                    const preClose = snap && snap.pre_close !== undefined ? Number(snap.pre_close) : null;
                    let chg = null;
                    let pct = null;
                    if (snap && price !== null && preClose !== null && preClose !== 0) {
                      chg = price - preClose;
                      pct = ((price - preClose) / preClose) * 100;
                    }
                    let up = false, down = false;
                    if (pct !== null && !isNaN(pct)) {
                      if (pct > 0) up = true;
                      else if (pct < 0) down = true;
                    }
                    const color = up ? '#ff4d4f' : down ? '#52c41a' : '#b0bec5';
                    const pctBgColor = up ? '#ff4d4f' : down ? '#52c41a' : '#b0bec5';
                    let priceBg = '';
                    if (snap && price !== null && preClose !== null && preClose !== 0) {
                      if (price > preClose) priceBg = 'rgba(24,144,255,0.18)';
                      else if (price < preClose) priceBg = '#232a36';
                    }
                    // 判断闪烁类型
                    let flashType = '';
                    if (flashRows[code]) {
                      if (snap && price !== null && preClose !== null && preClose !== 0) {
                        if (price > preClose) flashType = 'flash-up';
                        else if (price < preClose) flashType = 'flash-down';
                      }
                    }
                    const name = snap && snap.name ? snap.name : code;
                    const market = code.includes('.') ? code.split('.')[1].toUpperCase() : '';
                    const marketColor = market === 'HK' ? '#722ed1' : market === 'SH' ? '#faad14' : market === 'SZ' ? '#13c2c2' : '#b0bec5';
                    const codeMain = code.includes('.') ? code.split('.')[0] : code;
                    return (
                      <div key={code} className={`watchlist-stock-row${flashType ? ' ' + flashType : ''}`}
                        style={{ display: 'flex', alignItems: 'center', minHeight: 36, fontSize: 12, borderBottom: idx !== arr.length-1 ? '1px solid #313a4d' : 'none', padding: '4px 0 2px 0', transition: 'background 0.3s', cursor: 'pointer' }}
                        onClick={() => {
                          setSelectedStock(code);
                          setShowStockDetail(true);
                          fetchStockDetail(code);
                          // 同时获取K线数据和交易历史
                          fetchStockDetailKline(code);
                          fetchTradeHistory(code);
                        }}
                      >
                        <span style={{ flex: '0 0 50%', maxWidth: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-start' }}>
                          <span style={{ width: 24, minWidth: 24, maxWidth: 24, height: 15, background: marketColor, color: '#fff', borderRadius: 5, fontSize: 11, fontWeight: 700, textAlign: 'center', lineHeight: '15px', marginRight: 4, flex: '0 0 24px', display: 'inline-block' }}>{market || '—'}</span>
                          <span style={{ flex: 1, color: '#e6f7ff', fontWeight: 700, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                        </span>
                        <span style={{ flex: '0 0 15%', maxWidth: '15%', color, fontWeight: 700, fontVariantNumeric: 'tabular-nums', fontSize: 13, textAlign: 'left', borderRadius: 5, padding: '0 6px' }}>{
                          price !== null && !isNaN(price) ? price.toFixed(3) : '-'
                        }</span>
                        <span style={{ flex: '0 0 35%', maxWidth: '35%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <span style={{
                            display: 'inline-block',
                            width: '60%',
                            background: pctBgColor,
                            color: '#fff',
                            fontWeight: 700,
                            fontVariantNumeric: 'tabular-nums',
                            fontSize: 12,
                            textAlign: 'center',
                            borderRadius: 5,
                            padding: '0 6px'
                          }}>{pct !== null && !isNaN(pct) ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '-'}</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>
              {/* 市场行情卡片 */}
              <Card style={{ background: '#232a36', borderRadius: 10, marginTop: 0, marginBottom: 8, boxShadow: '0 2px 8px #0003', border: 'none', padding: 0 }} styles={{ body: { padding: 10 } }}>
                <div style={{ color: '#faad14', fontWeight: 700, fontSize: 15, marginBottom: 6, display: 'flex', alignItems: 'center' }}>
                  <StockOutlined style={{ marginRight: 6 }} />市场行情
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {[
                    { code: '000001.SH', name: '上证指数' },
                    { code: '399001.SZ', name: '深成指数' },
                    { code: '800000.HK', name: '恒生综合' },
                    { code: '800700.HK', name: '恒生科技' },
                  ].map(idx => {
                    const snap = stockSnapshots[idx.code];
                    const price = snap && snap.current_price !== undefined ? Number(snap.current_price) : null;
                    const preClose = snap && snap.pre_close !== undefined ? Number(snap.pre_close) : null;
                    let pct = null;
                    if (snap && price !== null && preClose !== null && preClose !== 0) {
                      pct = ((price - preClose) / preClose) * 100;
                    }
                    const up = pct !== null && pct > 0;
                    const down = pct !== null && pct < 0;
                    const color = up ? '#ff4d4f' : down ? '#52c41a' : '#b0bec5';
                    // 更新特效
                    const priceChanged = false; // 可根据需要加高亮
                    const flashClass = priceChanged ? (up ? 'flash-up' : down ? 'flash-down' : '') : '';
                    return (
                      <div key={idx.code} className={flashClass} style={{ flex: '1 1 120px', minWidth: 110, maxWidth: 160, background: '#181c24', borderRadius: 7, padding: '8px 10px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', boxShadow: '0 1px 4px #0002', border: '1px solid #232a36', transition: 'background 0.3s' }}>
                        <span style={{ color: '#b0bec5', fontWeight: 600, fontSize: 12, marginBottom: 2 }}>{idx.name}</span>
                        <span style={{ color, fontWeight: 700, fontSize: 16 }}>{price !== null ? price.toFixed(2) : '--'}</span>
                        <span style={{ color, fontWeight: 600, fontSize: 12 }}>{pct !== null ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '--'}</span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </Col>
            <Col span={18} style={{ padding: 18 }}>
              {/* 量化交易模块 - 支持折叠，高度与其他卡片一致 */}
              <Card 
                style={{ 
                  background: 'rgba(30,34,44,0.98)', 
                  borderRadius: 10, 
                  boxShadow: '0 2px 8px #0003', 
                  border: 'none', 
                  marginTop: 16,
                  marginBottom: 16,
                  minHeight: quantTradingCollapsed ? 60 : 'auto'
                }}
                styles={{ 
                  body: { 
                    padding: quantTradingCollapsed ? '16px' : 16,
                    minHeight: quantTradingCollapsed ? 28 : 'auto'
                  } 
                }}
              >
                <div
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    margin: 0,
                    cursor: 'pointer', 
                    userSelect: 'none',
                    height: 28
                  }}
                  onClick={() => setQuantTradingCollapsed(v => !v)}
                >
                  <Title level={5} style={{ color: '#faad14', fontWeight: 700, fontSize: 17, margin: 0, display: 'flex', alignItems: 'center' }}>
                    <DollarCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />量化交易
                    <span style={{ marginLeft: 8, fontSize: 16 }}>{quantTradingCollapsed ? <DownOutlined /> : <UpOutlined />}</span>
                  </Title>
                </div>
                {!quantTradingCollapsed && (
                  <div style={{ marginTop: 12 }}>
                    <QuantTradingPanel 
                      userId={userId}
                      selectedStock={selectedStock}
                      stocks={stocks}
                      stockSnapshots={stockSnapshots}
                      onTradeSignal={(signal) => {
                        message.success(`交易信号: ${signal.symbol} - ${signal.signal}`);
                      }}
                    />
                  </div>
                )}
              </Card>

              {/* 智能盯盘模块 - 高端紧凑卡片实现（主内容区） */}
              <Card style={{ background: 'rgba(30,34,44,0.98)', borderRadius: 10, boxShadow: '0 2px 8px #0003', border: 'none', marginTop: 18 }} styles={{ body: { padding: 16 } }}>
                <div
                  style={{ color: '#13c2c2', fontWeight: 700, fontSize: 17, display: 'flex', alignItems: 'center', marginBottom: 8, cursor: 'pointer', userSelect: 'none', justifyContent: 'space-between' }}
                  onClick={() => setSmartMonitorCollapsed(v => !v)}
                >
                  <span style={{ display: 'flex', alignItems: 'center' }}>
                    <ThunderboltOutlined style={{ color: '#13c2c2', marginRight: 8 }} />智能盯盘
                    <span style={{ marginLeft: 8, fontSize: 16 }}>{smartMonitorCollapsed ? <DownOutlined /> : <UpOutlined />}</span>
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    {/* 创建账户图标，仅未创建时显示 */}
                    {hasAccount === false && (
                      <Tooltip title="创建模拟账户">
                        <UserAddOutlined
                          style={{ color: '#40a9ff', fontSize: 22, marginRight: 16, cursor: 'pointer' }}
                          onClick={e => { e.stopPropagation(); setCreateAccountModal(true); }}
                        />
                      </Tooltip>
                    )}
                    {/* 账户信息展示 */}
                    {hasAccount && accountInfo && accountInfo.account && accountInfo.success !== false && (
                      <div
                        style={{
                          marginRight: 12,
                          display: 'flex',
                          alignItems: 'center',
                          background: '#181c24',
                          borderRadius: 8,
                          padding: '2px 12px',
                          color: '#faad14',
                          fontWeight: 700,
                          fontSize: 14,
                          cursor: 'pointer',
                          boxShadow: '0 2px 8px #0003',
                          border: '1px solid #232a36',
                          position: 'relative',
                          transition: 'background 0.2s',
                        }}
                        onMouseEnter={() => setShowAccountPopover(true)}
                        onMouseLeave={() => setShowAccountPopover(false)}
                      >
                        <UserOutlined style={{ color: '#40a9ff', marginRight: 6, fontSize: 18 }} />
                        <span style={{ marginRight: 8 }}>
                          总资产: <span style={{ 
                            color: accountInfo.total_pnl > 0 ? '#ff4d4f' : accountInfo.total_pnl < 0 ? '#52c41a' : '#fff'
                          }}>{accountInfo.total_asset?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span> 元
                        </span>
                        <span style={{ color: '#b0bec5', fontWeight: 500, fontSize: 13 }}>持仓: {Object.keys(accountInfo.account?.positions || {}).length}只</span>
                        {/* 账户详细信息卡片 */}
                        {showAccountPopover && (
                          <div style={{
                            position: 'absolute',
                            top: '110%',
                            right: 0,
                            minWidth: 320,
                            background: '#232a36',
                            color: '#fff',
                            borderRadius: 10,
                            boxShadow: '0 4px 24px #0008',
                            border: '1.5px solid #313a4d',
                            zIndex: 100,
                            padding: 20,
                            fontSize: 13
                          }}>
                            <div style={{ color: '#faad14', fontWeight: 700, fontSize: 16, marginBottom: 10 }}>账户信息</div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                              <span style={{ color: '#b0bec5' }}>初始资金</span>
                              <span style={{ color: '#fff', fontWeight: 600 }}>{accountInfo.initial_cash?.toLocaleString(undefined, { maximumFractionDigits: 2 })} 元</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                              <span style={{ color: '#b0bec5' }}>现金余额</span>
                              <span style={{ color: '#fff', fontWeight: 600 }}>{accountInfo.account?.cash?.toLocaleString(undefined, { maximumFractionDigits: 2 })} 元</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                              <span style={{ color: '#b0bec5' }}>总资产</span>
                              <span style={{ color: '#fff', fontWeight: 600 }}>{accountInfo.total_asset?.toLocaleString(undefined, { maximumFractionDigits: 2 })} 元</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                              <span style={{ color: '#b0bec5' }}>总盈亏</span>
                              <span style={{ color: accountInfo.total_pnl > 0 ? '#ff4d4f' : accountInfo.total_pnl < 0 ? '#52c41a' : '#fff', fontWeight: 700 }}>
                                {accountInfo.total_pnl > 0 ? '+' : ''}{accountInfo.total_pnl?.toFixed(2)} 元
                                <span style={{ marginLeft: 8, fontWeight: 500, fontSize: 12, color: accountInfo.total_pnl > 0 ? '#ff7875' : accountInfo.total_pnl < 0 ? '#95de64' : '#b0bec5' }}>
                                  ({accountInfo.total_pnl_ratio > 0 ? '+' : ''}{(accountInfo.total_pnl_ratio * 100).toFixed(2)}%)
                                </span>
                              </span>
                            </div>
                            <div style={{ borderTop: '1px solid #313a4d', margin: '12px 0 10px 0' }} />
                            <div style={{ color: '#faad14', fontWeight: 600, fontSize: 14, marginBottom: 8 }}>持仓明细</div>
                            <div style={{ maxWidth: '100%', overflowX: 'auto', paddingBottom: 4 }}>
                              <table style={{ minWidth: 320, borderCollapse: 'collapse', background: 'none', fontSize: 12 }}>
                                <thead>
                                  <tr style={{ color: '#b0bec5', borderBottom: '1px solid #313a4d', whiteSpace: 'nowrap' }}>
                                    <th style={{ textAlign: 'left', fontWeight: 500, padding: '2px 0', minWidth: 70 }}>名称/代码</th>
                                    <th style={{ textAlign: 'right', fontWeight: 500, padding: '2px 0', minWidth: 36 }}>数量</th>
                                    <th style={{ textAlign: 'right', fontWeight: 500, padding: '2px 0', minWidth: 36 }}>成本</th>
                                    <th style={{ textAlign: 'right', fontWeight: 500, padding: '2px 0', minWidth: 36 }}>盈亏</th>
                                    <th style={{ textAlign: 'right', fontWeight: 500, padding: '2px 0', minWidth: 44 }}>盈亏率</th>
                                    <th style={{ textAlign: 'right', fontWeight: 500, padding: '2px 0', minWidth: 44 }}>持仓天数</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.entries(accountInfo.account?.positions || {}).length === 0 ? (
                                    <tr><td colSpan={6} style={{ color: '#b0bec5', fontSize: 13, padding: 12, textAlign: 'center' }}>暂无持仓</td></tr>
                                  ) : (
                                    Object.entries(accountInfo.account?.positions || {}).map(([code, pos]) => {
                                      const name = stockSnapshots[code]?.name || code;
                                      const amount = pos.amount;
                                      const cost = pos.cost;
                                      const pnl = accountInfo.positions_pnl?.[code] ?? null;
                                      const pnlRatio = accountInfo.positions_pnl_ratio?.[code] ?? null;
                                      const days = accountInfo.positions_days?.[code];
                                      return (
                                        <tr key={code} style={{ borderBottom: '1px solid #232a36', whiteSpace: 'nowrap' }}>
                                          <td style={{ color: '#40a9ff', fontWeight: 600, padding: '2px 0' }}>{name}<br /><span style={{ color: '#b0bec5', fontSize: 11 }}>{code}</span></td>
                                          <td style={{ textAlign: 'right', color: '#fff', padding: '2px 0' }}>{amount}</td>
                                          <td style={{ textAlign: 'right', color: '#fff', padding: '2px 0' }}>{cost?.toFixed(2)}</td>
                                          <td style={{ textAlign: 'right', fontWeight: 700, color: pnl > 0 ? '#ff4d4f' : pnl < 0 ? '#52c41a' : '#fff', padding: '2px 0' }}>{pnl > 0 ? '+' : ''}{pnl?.toFixed(2)}</td>
                                          <td style={{ textAlign: 'right', fontWeight: 600, color: pnlRatio > 0 ? '#ff7875' : pnlRatio < 0 ? '#95de64' : '#b0bec5', padding: '2px 0' }}>{pnlRatio !== null && pnlRatio !== undefined ? ((pnlRatio > 0 ? '+' : '') + (pnlRatio * 100).toFixed(2) + '%') : '-'}</td>
                                          <td style={{ textAlign: 'right', color: '#faad14', fontWeight: 600, padding: '2px 0' }}>{days !== undefined && days !== null ? days : '-'}</td>
                                        </tr>
                                      );
                                    })
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    <span
                      style={{ marginLeft: 12, cursor: 'pointer', color: '#faad14', fontSize: 20, display: 'flex', alignItems: 'center' }}
                      title={showBlinkDot ? '隐藏特效' : '显示特效'}
                      onClick={e => { e.stopPropagation(); setShowBlinkDot(v => !v); }}
                    >
                      {showBlinkDot ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                    </span>
                  </div>
                </div>
                {!smartMonitorCollapsed && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 12px', background: 'none', padding: 0 }}>
                    {monitorData.map(stock => {
                      if (!stock.signals || !stock.signals.length) return null;
                      const showSignals = stock.signals.slice(0, 3);
                      const hasMore = stock.signals.length > 3;
                      const latestTime = stock.signals[0]?.time ? new Date(stock.signals[0].time) : null;
                      const now = new Date();
                      const within1Hour = latestTime && (now - latestTime) <= 3600 * 1000;
                      // 新增：近10分钟内是否有任意信号
                      const hasRecentSignal = stock.signals.some(ev => {
                        const t = ev.time ? new Date(ev.time) : null;
                        return t && (now - t) <= 10 * 60 * 1000;
                      });
                      const shouldBlink = hasRecentSignal && newSignalMap[stock.symbol] && timelineModal.symbol !== stock.symbol;
                      const shouldShowDot = hasRecentSignal && newSignalMap[stock.symbol];
                      // 新增：近10分钟内是否有涨速/跌速异动信号
                      const hasRecentUp = stock.signals.some(ev => {
                        const t = ev.time ? new Date(ev.time) : null;
                        return t && (now - t) <= 10 * 60 * 1000 && ev.content && ev.content.includes('涨速异动');
                      });
                      const hasRecentDown = stock.signals.some(ev => {
                        const t = ev.time ? new Date(ev.time) : null;
                        return t && (now - t) <= 10 * 60 * 1000 && ev.content && ev.content.includes('跌速异动');
                      });
                      return (
                        <div key={stock.symbol} style={{
                          background: 'linear-gradient(135deg,rgba(36,44,66,0.92) 60%,rgba(24,28,36,0.98) 100%)',
                          borderRadius: 14,
                          boxShadow: '0 4px 24px 0 rgba(20,30,60,0.18), 0 1.5px 6px 0 #101622',
                          minWidth: 216,
                          maxWidth: 264,
                          flex: '1 1 180px',
                          padding: '0',
                          margin: 0,
                          border: '1.5px solid #2b3140',
                          backdropFilter: 'blur(2.5px)',
                          display: 'flex',
                          flexDirection: 'column',
                          transition: 'box-shadow 0.2s, border 0.2s',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', padding: '10px 14px 6px 14px', borderBottom: '1px solid #232a36', background: 'none', borderTopLeftRadius: 14, borderTopRightRadius: 14, position: 'relative' }}>
                            {stock.name ? (
                              <>
                                <span style={{ color: '#5cc6ff', fontWeight: 800, fontSize: 16, marginRight: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110, letterSpacing: 0.5 }}>{stock.name}</span>
                                <span
                                  style={{ color: '#b0bec5', fontWeight: 600, fontSize: 12, marginRight: 4, whiteSpace: 'nowrap', opacity: 0.85, cursor: 'pointer', textDecoration: 'underline dotted' }}
                                  title="点击查看股票详情"
                                  onClick={e => {
                                    e.stopPropagation();
                                    setOrderBookModal({ visible: true, symbol: stock.symbol, name: stock.name });
                                    // 同时获取K线数据和交易历史
                                    fetchStockDetailKline(stock.symbol);
                                    fetchTradeHistory(stock.symbol);
                                  }}
                                >
                                  {stock.symbol}
                                </span>
                                {/* 新增：异动箭头图标 */}
                                {hasRecentUp && <ArrowUpOutlined style={{ color: '#ff4d4f', fontSize: 18, marginLeft: 2, verticalAlign: 'middle' }} />}
                                {hasRecentDown && <ArrowDownOutlined style={{ color: '#52c41a', fontSize: 18, marginLeft: 2, verticalAlign: 'middle' }} />}
                              </>
                            ) : (
                              <span style={{ color: '#5cc6ff', fontWeight: 800, fontSize: 16, marginRight: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>{stock.symbol}</span>
                            )}
                            {showBlinkDot && shouldShowDot && (
                              <span style={{
                                display: 'inline-block',
                                width: 12,
                                height: 12,
                                borderRadius: '50%',
                                background: 'radial-gradient(circle,#ff4d4f 60%,#ff7875 100%)',
                                marginLeft: 2,
                                boxShadow: '0 0 6px #ff4d4f',
                                animation: shouldBlink ? 'blink-dot 1s infinite' : 'none',
                                verticalAlign: 'middle',
                                border: '1.5px solid #fff'
                              }} title="有新异动" />
                            )}
                            {hasMore && (
                              <span
                                style={{ marginLeft: 'auto', color: '#faad14', fontSize: 16, cursor: 'pointer', transition: 'color 0.2s', lineHeight: 1 }}
                                title="查看更多"
                                onClick={e => {
                                  e.stopPropagation();
                                  setTimelineModal({ 
                                    visible: true, 
                                    symbol: stock.symbol, 
                                    signals: Array.isArray(stock.signals) ? stock.signals : [] 
                                  });
                                }}
                                onMouseOver={e => e.currentTarget.style.color = '#ffd666'}
                                onMouseOut={e => e.currentTarget.style.color = '#faad14'}
                              >
                                &#8942;
                              </span>
                            )}
                          </div>
                          <div style={{ padding: '6px 0 6px 0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {showSignals.map((signal, idx) => {
                              const eventTime = signal.time ? new Date(signal.time) : null;
                              const isNew = eventTime && (now - eventTime) <= 15 * 60 * 1000;
                              const isHovered = hoveredTradeSignal && hoveredTradeSignal.symbol === stock.symbol && hoveredTradeSignal.idx === idx;
                              return (
                                <div
                                  key={signal.time + signal.content}
                                  onMouseEnter={() => setHoveredTradeSignal({ symbol: stock.symbol, idx })}
                                  onMouseLeave={() => setHoveredTradeSignal(null)}
                                  style={{
                                    position: 'relative',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'flex-start',
                                    background: isNew ? 'linear-gradient(90deg,rgba(36,60,100,0.10) 60%,rgba(36,44,66,0.08) 100%)' : 'transparent',
                                    borderRadius: 7,
                                    boxShadow: isNew ? '0 2px 8px #1890ff18' : '0 1px 4px #0001',
                                    padding: '5px 10px',
                                    margin: '0 8px',
                                    border: isNew ? '1.5px solid rgba(64,169,255,0.18)' : '1px solid #232a36',
                                    fontSize: 12,
                                    transition: 'background 0.2s, border 0.2s',
                                    minHeight: 32,
                                    justifyContent: 'center',
                                  }}
                                >
                                  <span style={{ color: isNew ? '#8fd6ff' : '#b0bec5', fontSize: 10, minWidth: 60, marginBottom: 2, fontWeight: isNew ? 700 : 400 }}>{signal.time}</span>
                                  <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                                    {renderSignalContent(signal.content, isNew)}
                                    {isHovered && hasAccount && accountInfo && accountInfo.account && accountInfo.success !== false && (
                                      <span
                                        style={{
                                          position: 'absolute',
                                          right: 12,
                                          top: '50%',
                                          transform: 'translateY(-50%)',
                                          color: '#bfae7a',
                                          textShadow: '0 0 4px #bfae7a',
                                          fontSize: 22,
                                          cursor: 'pointer',
                                          zIndex: 2,
                                          opacity: 1,
                                          transition: 'opacity 0.18s',
                                        }}
                                        title="快捷交易"
                                        onClick={e => {
                                          e.stopPropagation();
                                          setTradeModal({ visible: true, stock, signal });
                                          setTradeType('buy');
                                          setTradeAmount(100);
                                          setTradePrice(stockSnapshots[stock.symbol]?.current_price || '');
                                        }}
                                      >
                                        <DollarCircleFilled />
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
              <TradingNotes 
                userId={userId}
                visible={!tradingNotesCollapsed}
                onToggle={() => setTradingNotesCollapsed(!tradingNotesCollapsed)}
                stockSnapshots={stockSnapshots}
              />
              
              {/* 市场行情板块排行 */}
              <PlateRanking />
              
              {/* 触发预警模块 */}
              <Card style={{ background: 'rgba(30,34,44,0.98)', borderRadius: 10, boxShadow: '0 2px 8px #0003', border: 'none', marginTop: 18 }} styles={{ body: { padding: 16 } }}>
                <div
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 0, cursor: 'pointer', userSelect: 'none' }}
                  onClick={() => setAlertCardCollapsed(v => !v)}
                >
                  <Title level={5} style={{ color: '#faad14', fontWeight: 700, fontSize: 17, margin: 0, display: 'flex', alignItems: 'center' }}>
                    <BellOutlined style={{ color: '#faad14', marginRight: 8 }} />触发预警
                    <span style={{ marginLeft: 8, fontSize: 16 }}>{alertCardCollapsed ? <DownOutlined /> : <UpOutlined />}</span>
                  </Title>
                  <Button
                    type="default"
                    size="small"
                    style={{
                      background: '#232a36',
                      border: '1.5px solid #faad14',
                      color: '#faad14',
                      fontWeight: 600,
                      height: 30,
                      marginLeft: 8,
                      boxShadow: '0 0 0 1px #faad1433',
                      transition: 'all 0.2s',
                      borderRadius: 6,
                      padding: '0 14px'
                    }}
                    onMouseOver={e => {
                      e.currentTarget.style.border = '1.5px solid #ffe58f';
                      e.currentTarget.style.color = '#ffe58f';
                    }}
                    onMouseOut={e => {
                      e.currentTarget.style.border = '1.5px solid #faad14';
                      e.currentTarget.style.color = '#faad14';
                    }}
                    onClick={e => { e.stopPropagation(); handleExec(); }}
                  >
                    <ThunderboltOutlined /> 立即执行
                  </Button>
                </div>
                {!alertCardCollapsed && <>
                  <Divider style={{ background: 'linear-gradient(90deg,#faad14,#1890ff)', margin: '8px 0' }} />
                  {/* 命中优先展示 */}
                  <Table
                    columns={columns}
                    dataSource={hitAlerts}
                    rowKey="code"
                    pagination={false}
                    style={{ background: '#181c24', color: '#e6f7ff', borderRadius: 8, boxShadow: '0 2px 8px #0003' }}
                    bordered
                    size="small"
                    scroll={{ y: 320 }}
                    rowClassName={(record) => record.hit === true ? 'watchlist-table-row-hit' : 'watchlist-table-row'}
                    locale={{ emptyText: <span style={{ color: '#b0bec5' }}>暂无命中预警</span> }}
                  />
                  {/* 未命中折叠展示 */}
                  {unhitAlerts.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <Divider style={{ background: 'linear-gradient(90deg,#1890ff,#faad14)', margin: '8px 0' }} />
                      <Typography.Text style={{ color: '#b0bec5', fontWeight: 600, fontSize: 15 }}>
                        未命中规则列表
                      </Typography.Text>
                      <div style={{ marginTop: 6 }}>
                        <Table
                          columns={columns}
                          dataSource={unhitAlerts}
                          rowKey="code"
                          pagination={false}
                          style={{ background: '#181c24', color: '#e6f7ff', borderRadius: 8, boxShadow: '0 2px 8px #0003' }}
                          bordered
                          size="small"
                          scroll={{ y: 240 }}
                          rowClassName="watchlist-table-row"
                          locale={{ emptyText: <span style={{ color: '#b0bec5' }}>暂无未命中预警</span> }}
                          expandable={{
                            defaultExpandAllRows: false,
                            expandedRowRender: record => null,
                            showExpandColumn: false
                          }}
                        />
                      </div>
                    </div>
                  )}
                </>}
              </Card>
            </Col>
          </Row>
          <style>{`
            .watchlist-table-row:hover td {
              background: rgba(24,144,255,0.08) !important;
            }
            .ant-table-thead > tr > th {
              background: #232a36 !important;
              color: #faad14 !important;
              font-weight: 700;
              font-size: 12px;
              border-bottom: 2px solid #313a4d !important;
            }
            .ant-table-tbody > tr > td {
              background: #181c24 !important;
              color: #e6f7ff !important;
              font-size: 12px;
              padding: 4px 6px !important;
              border-bottom: 1px solid #232a36 !important;
            }
            .watchlist-table-row-hit td {
              background: #232a36 !important;
              color: #e6f7ff !important;
              font-weight: 600;
            }
            .ant-card-body {
              padding: 12px !important;
            }
            .ant-form-item {
              margin-bottom: 10px !important;
            }
            .ant-collapse {
              background: #232a36 !important;
              border-radius: 10px !important;
              border: none !important;
            }
            .ant-collapse > .ant-collapse-item > .ant-collapse-header {
              background: #232a36 !important;
              color: #faad14 !important;
              font-weight: 700;
              font-size: 18px;
              border-radius: 10px 10px 0 0 !important;
              border: none !important;
            }
            .ant-collapse-content {
              background: #232a36 !important;
              color: #e6f7ff !important;
              border-radius: 0 0 10px 10px !important;
              border: none !important;
            }
            .watchlist-stock-row {
              transition: background 0.18s;
            }
            .watchlist-stock-row.flash-up {
              animation: flash-up-bg 0.6s cubic-bezier(0.4,0,0.2,1);
            }
            .watchlist-stock-row.flash-down {
              animation: flash-down-bg 0.6s cubic-bezier(0.4,0,0.2,1);
            }
            @keyframes flash-up-bg {
              0% { background: #232a36; }
              30% { background: linear-gradient(90deg, rgba(255,77,79,0.5) 0%, rgba(255,0,0,0.5) 100%); }
              60% { background: linear-gradient(90deg, rgba(255,77,79,0.5) 0%, rgba(255,0,0,0.5) 100%); }
              100% { background: #232a36; }
            }
            @keyframes flash-down-bg {
              0% { background: #232a36; }
              30% { background: linear-gradient(90deg, rgba(0,255,102,0.5) 0%, rgba(0,200,0,0.5) 100%); }
              60% { background: linear-gradient(90deg, rgba(0,255,102,0.5) 0%, rgba(0,200,0,0.5) 100%); }
              100% { background: #232a36; }
            }
            .watchlist-stock-row:hover {
              background: rgba(24,144,255,0.08) !important;
            }
            .ant-card, .ant-card-body, .ant-row, .ant-col {
              overflow: visible !important;
              position: static !important;
            }
            .ant-tabs-tab .tab-label {
              color: #6c757d !important;
              font-weight: 600;
            }
            .ant-tabs-tab-active .tab-label {
              color: #1890ff !important;
            }
            
            /* 板块排行样式 */
            .top-ranking-row {
              background: linear-gradient(90deg, rgba(250,173,20,0.1) 0%, rgba(250,173,20,0.05) 100%) !important;
            }
            .top-ranking-row:hover {
              background: linear-gradient(90deg, rgba(64,64,64,0.95) 0%, rgba(64,64,64,0.95) 100%) !important;
            }
            
            /* 板块排行表格样式 */
            .plate-ranking-table .ant-table-thead > tr > th {
              background: #232a36 !important;
              color: #faad14 !important;
              font-weight: 700;
              font-size: 12px;
              border-bottom: 2px solid #313a4d !important;
            }
            .plate-ranking-table .ant-table-tbody > tr > td {
              background: #181c24 !important;
              color: #e6f7ff !important;
              font-size: 12px;
              padding: 4px 6px !important;
              border-bottom: 1px solid #232a36 !important;
            }
            .plate-ranking-table .ant-table-tbody > tr:hover > td {
              background: rgba(64,64,64,0.95) !important;
            }
            .plate-ranking-table .ant-pagination-item {
              background: #232a36 !important;
              border-color: #313a4d !important;
            }
            .plate-ranking-table .ant-pagination-item a {
              color: #e6f7ff !important;
            }
            .plate-ranking-table .ant-pagination-item-active {
              background: #1890ff !important;
              border-color: #1890ff !important;
            }
            .plate-ranking-table .ant-pagination-item-active a {
              color: white !important;
            }
            }
            @keyframes blink-dot {
              0% { opacity: 1; }
              50% { opacity: 0.2; }
              100% { opacity: 1; }
            }
            .price-up-flash { animation: price-up-flash 0.6s; background: rgba(82,196,26,0.18)!important; }
            .price-down-flash { animation: price-down-flash 0.6s; background: rgba(255,77,79,0.18)!important; }
            @keyframes price-up-flash { 0% { background: #232a36; } 40% { background: rgba(82,196,26,0.18); } 100% { background: #232a36; } }
            @keyframes price-down-flash { 0% { background: #232a36; } 40% { background: rgba(255,77,79,0.18); } 100% { background: #232a36; } }
            .trade-input-white input {
              color: #fff !important;
              background: #181c24 !important;
              caret-color: #faad14 !important;
            }
            .trade-input-white input::placeholder {
              color: #b0bec5 !important;
              opacity: 1 !important;
            }
          `}</style>
          {/* 3. 页面底部新增Modal浮层 */}
          <Modal
            open={orderBookModal.visible}
            onCancel={() => setOrderBookModal({ visible: false, symbol: '', name: '' })}
            footer={null}
            width={1000}
            styles={{ body: { background: '#232a36', color: '#fff', borderRadius: 16, padding: 0, minHeight: 600 } }}
            style={{ top: 80, borderRadius: 16 }}
            title={
              <span style={{ color: '#40a9ff', fontWeight: 700, fontSize: 18 }}>
                {orderBookModal.name} <span style={{ color: '#b0bec5', fontSize: 15, marginLeft: 8 }}>{orderBookModal.symbol}</span>
                <span style={{ color: '#faad14', fontSize: 15, marginLeft: 18 }}>实时摆盘 & 逐笔</span>
              </span>
            }
          >
                        <div style={{ padding: 24 }}>
              {/* 上半部分：历史K线和实时逐笔 */}
              <div style={{ display: 'flex', gap: 24, marginBottom: 8, height: 330 }}>
                {/* 历史K线 */}
                <div style={{ flex: 1, minWidth: 320 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ color: '#fff', fontWeight: 600, fontSize: 16 }}>历史K线趋势</span>
                    {detailKlineLoading && <Spin size="small" />}
                  </div>
                  <div 
                    style={{ 
                      width: '100%', 
                      height: 300, 
                      background: '#181c24',
                      borderRadius: 8,
                      border: '1px solid #313a4d'
                    }}
                  >
                    {detailKlineLoading ? (
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                        <Spin size="large" />
                      </div>
                    ) : detailKlineData && detailKlineData.length > 0 ? (
                      <KLineChart 
                        data={detailKlineData} 
                        tradeHistory={tradeHistory}
                        symbol={orderBookModal.symbol}
                      />
                    ) : (
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: '#b0bec5' }}>
                        暂无K线数据
                      </div>
                    )}
                  </div>
                </div>
                {/* 逐笔 */}
                <div style={{ flex: 1, minWidth: 320 }}>
                  <div style={{ color: '#40a9ff', fontWeight: 700, fontSize: 16, marginBottom: 8 }}>实时逐笔</div>
                  {rtTickerLoading ? <Spin /> : Array.isArray(rtTickerData) && rtTickerData.length > 0 ? (
                    <div style={{ maxHeight: 600, overflowY: 'auto', background: '#181c24', borderRadius: 8 }}>
                      <table style={{ width: '100%', color: '#fff', fontSize: 13, borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>时间</th>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>价格</th>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>数量</th>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>方向</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rtTickerData.slice().reverse().slice(0, 30).map((row, i, arr) => {
                            const prevRow = prevRtTickerRef.current?.[arr.length - 1 - i];
                            const priceUp = prevRow && row.price > prevRow.price;
                            const priceDown = prevRow && row.price < prevRow.price;
                            return (
                              <tr key={i} style={{ background: i === 0 ? 'rgba(64,169,255,0.10)' : 'none' }}>
                                <td style={{ color: '#b0bec5', padding: '2px 4px' }}>{row.time}</td>
                                <td className={priceUp ? 'price-up-flash' : priceDown ? 'price-down-flash' : ''} style={{ color: row.ticker_direction === 'BUY' ? '#ff4d4f' : row.ticker_direction === 'SELL' ? '#52c41a' : '#fff', fontWeight: 700, padding: '2px 4px' }}>{row.price}</td>
                                <td style={{ color: '#fff', padding: '2px 4px' }}>{row.volume}</td>
                                <td style={{ color: row.ticker_direction === 'BUY' ? '#ff4d4f' : row.ticker_direction === 'SELL' ? '#52c41a' : '#b0bec5', padding: '2px 4px' }}>{row.ticker_direction}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                        </div>
                  ) : <div style={{ color: '#ff4d4f' }}>{rtTickerData?.error || '暂无数据'}</div>}
                </div>
              </div>

              {/* 下半部分：实时摆盘 */}
              <div>
                {/* 实时摆盘 */}
                <div style={{ width: '50%' }}>
                  <div style={{ color: '#faad14', fontWeight: 700, fontSize: 16, marginBottom: 8 }}>实时摆盘</div>
                  {orderBookLoading ? <Spin /> : orderBookData && !orderBookData.error ? (
                    <div style={{ maxHeight: 300, overflowY: 'auto', background: '#181c24', borderRadius: 8 }}>
                      <table style={{ width: '100%', color: '#fff', fontSize: 13, borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>买价</th>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>买量</th>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>卖价</th>
                            <th style={{ color: '#faad14', fontWeight: 700, padding: '2px 4px' }}>卖量</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(orderBookData.Bid || []).slice(0, 10).map((bid, i) => {
                            const prevBid = prevOrderBookRef.current?.Bid?.[i];
                            const prevAsk = prevOrderBookRef.current?.Ask?.[i];
                            const priceUp = prevBid && bid[0] > prevBid[0];
                            const priceDown = prevBid && bid[0] < prevBid[0];
                            const askUp = prevAsk && orderBookData.Ask[i]?.[0] > prevAsk[0];
                            const askDown = prevAsk && orderBookData.Ask[i]?.[0] < prevAsk[0];
                            return (
                              <tr key={i} style={{ background: i === 0 ? 'rgba(250,173,20,0.10)' : 'none' }}>
                                <td className={priceUp ? 'price-up-flash' : priceDown ? 'price-down-flash' : ''} style={{ color: '#52c41a', fontWeight: 700, padding: '2px 4px' }}>{bid[0]}</td>
                                <td style={{ color: '#52c41a', padding: '2px 4px' }}>{bid[1]}</td>
                                <td className={askUp ? 'price-up-flash' : askDown ? 'price-down-flash' : ''} style={{ color: '#ff4d4f', fontWeight: 700, padding: '2px 4px' }}>{orderBookData.Ask[i]?.[0] ?? '-'}</td>
                                <td style={{ color: '#ff4d4f', padding: '2px 4px' }}>{orderBookData.Ask[i]?.[1] ?? '-'}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                        </div>
                  ) : <div style={{ color: '#ff4d4f' }}>{orderBookData?.error || '暂无数据'}</div>}
                </div>
              </div>
            </div>
          </Modal>
          {/* 股票详情Modal */}
          <Modal
            open={stockDetailModal.visible}
            onCancel={() => setStockDetailModal({ visible: false, stock: null })}
            footer={null}
            width={800}
            styles={{ body: { background: '#232a36', color: '#fff', borderRadius: 10, padding: 0 } }}
            title={null}
            destroyOnHidden
          >
            {stockDetailModal.stock && (
              <div style={{ padding: 18, background: '#232a36', borderRadius: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                  <span style={{ color: '#faad14', fontWeight: 600, fontSize: 18, marginRight: 8 }}>{stockDetailModal.stock.name}</span>
                  <span style={{ color: '#b0bec5', fontSize: 14, fontWeight: 500 }}>{stockDetailModal.stock.symbol}</span>
                </div>
                
                {/* K线图表区域 */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ color: '#fff', fontWeight: 600, fontSize: 14 }}>历史K线趋势</span>
                    {detailKlineLoading && <Spin size="small" />}
                  </div>
                  <div 
                    id="kline-chart" 
                    style={{ 
                      width: '100%', 
                      height: 400, 
                      background: '#181c24',
                      borderRadius: 8,
                      border: '1px solid #313a4d'
                    }}
                  >
                    {detailKlineLoading ? (
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                        <Spin size="large" />
                      </div>
                    ) : detailKlineData && detailKlineData.length > 0 ? (
                      <KLineChart 
                        data={detailKlineData} 
                        tradeHistory={tradeHistory}
                        symbol={stockDetailModal.stock.symbol}
                      />
                    ) : (
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: '#b0bec5' }}>
                        暂无K线数据
                      </div>
                    )}
                  </div>
                </div>

                {/* 交易历史区域 */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ color: '#fff', fontWeight: 600, fontSize: 14 }}>交易历史</span>
                    {tradeHistoryLoading && <Spin size="small" />}
                  </div>
                  <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                    {tradeHistoryLoading ? (
                      <div style={{ textAlign: 'center', padding: 20 }}>
                        <Spin size="large" />
                      </div>
                    ) : tradeHistory.length > 0 ? (
                      <Table
                        dataSource={tradeHistory}
                        columns={[
                          {
                            title: '时间',
                            dataIndex: 'created_at',
                            key: 'created_at',
                            render: (text) => new Date(text).toLocaleString(),
                            width: 150
                          },
                          {
                            title: '类型',
                            dataIndex: 'side',
                            key: 'side',
                            render: (text) => (
                              <Tag color={text === 'buy' ? '#52c41a' : '#ff4d4f'}>
                                {text === 'buy' ? '买入' : '卖出'}
                              </Tag>
                            ),
                            width: 80
                          },
                          {
                            title: '价格',
                            dataIndex: 'price',
                            key: 'price',
                            render: (text) => `¥${text}`,
                            width: 100
                          },
                          {
                            title: '数量',
                            dataIndex: 'amount',
                            key: 'amount',
                            width: 100
                          },
                          {
                            title: '依据',
                            dataIndex: 'order_reason',
                            key: 'order_reason',
                            render: (text) => text || '-',
                            ellipsis: true
                          }
                        ]}
                        pagination={false}
                        size="small"
                        style={{ background: '#181c24' }}
                        rowKey={(record, index) => index}
                      />
                    ) : (
                      <div style={{ textAlign: 'center', padding: 20, color: '#b0bec5' }}>
                        暂无交易记录
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </Modal>
          <Modal
            open={tradeModal.visible}
            onCancel={() => setTradeModal({ visible: false, stock: null, signal: null })}
            footer={null}
            width={360}
            styles={{ body: { background: '#232a36', color: '#fff', borderRadius: 10, padding: 0 } }}
            title={null}
            destroyOnHidden
          >
            {tradeModal.stock && tradeModal.signal && (
              <div style={{ padding: 18, background: '#232a36', borderRadius: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ color: '#faad14', fontWeight: 600, fontSize: 15, marginRight: 8 }}>{tradeModal.stock.name}</span>
                  <span style={{ color: '#b0bec5', fontSize: 12, fontWeight: 500 }}>{tradeModal.stock.symbol}</span>
                </div>
                <div style={{ color: '#b0bec5', fontSize: 11, marginBottom: 8, background: '#181c24', borderRadius: 4, padding: '6px 10px', fontWeight: 500, border: '1px solid #232a36' }}>
                  <ThunderboltOutlined style={{ color: '#faad14', marginRight: 4, fontSize: 13 }} />{tradeModal.signal.content}
                </div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <Button
                    type={tradeType === 'buy' ? 'primary' : 'default'}
                    style={{ flex: 1, background: tradeType === 'buy' ? '#237a3b' : '#232a36', color: tradeType === 'buy' ? '#fff' : '#b0bec5', fontWeight: 600, fontSize: 13, borderRadius: 4, border: 'none', boxShadow: 'none', height: 32, padding: 0 }}
                    onClick={() => setTradeType('buy')}
                  >买入</Button>
                  <Button
                    type={tradeType === 'sell' ? 'primary' : 'default'}
                    style={{ flex: 1, background: tradeType === 'sell' ? '#a03a3a' : '#232a36', color: tradeType === 'sell' ? '#fff' : '#b0bec5', fontWeight: 600, fontSize: 13, borderRadius: 4, border: 'none', boxShadow: 'none', height: 32, padding: 0 }}
                    onClick={() => setTradeType('sell')}
                  >卖出</Button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ color: '#b0bec5', fontSize: 12, width: 38 }}>价格</span>
                  <InputNumber
                    min={0}
                    value={tradePrice}
                    onChange={v => setTradePrice(v)}
                    style={{ flex: 1, background: '#181c24', color: '#fff', border: '1px solid #313a4d', borderRadius: 4, fontWeight: 600, fontSize: 13, marginLeft: 6, height: 28, lineHeight: '28px', caretColor: '#faad14' }}
                    stringMode
                    size="small"
                    placeholder="输入价格"
                    className="trade-input-white"
                  />
                  <span style={{ color: '#b0bec5', fontSize: 11, marginLeft: 6 }}>元</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
                  <span style={{ color: '#b0bec5', fontSize: 12, width: 38 }}>数量</span>
                  <InputNumber
                    min={1}
                    step={100}
                    value={tradeAmount}
                    onChange={v => setTradeAmount(v)}
                    style={{ flex: 1, background: '#181c24', color: '#fff', border: '1px solid #313a4d', borderRadius: 4, fontWeight: 600, fontSize: 13, marginLeft: 6, height: 28, lineHeight: '28px', caretColor: '#faad14' }}
                    size="small"
                    placeholder="输入数量"
                    className="trade-input-white"
                  />
                  <span style={{ color: '#b0bec5', fontSize: 11, marginLeft: 6 }}>股</span>
                </div>
                <Button
                  type="primary"
                  block
                  style={{ background: tradeType === 'buy' ? '#237a3b' : '#a03a3a', border: 'none', fontWeight: 700, fontSize: 14, borderRadius: 5, height: 36, boxShadow: 'none', letterSpacing: 1 }}
                  onClick={() => handleSimTrade(tradeType)}
                >{tradeType === 'buy' ? '买入' : '卖出'}</Button>
              </div>
            )}
          </Modal>
          <Modal
            open={createAccountModal}
            onCancel={() => setCreateAccountModal(false)}
            onOk={handleCreateAccount}
            okText="创建"
            cancelText="取消"
            title="创建模拟账户"
            styles={{ body: { padding: 24, background: '#232a36', color: '#fff', borderRadius: 12 }, mask: { background: 'rgba(24,28,36,0.92)' } }}
            okButtonProps={{ style: { background: '#40a9ff', border: 'none', fontWeight: 700, fontSize: 15, borderRadius: 6 } }}
            cancelButtonProps={{ style: { background: '#181c24', color: '#b0bec5', border: '1px solid #313a4d', fontWeight: 600, fontSize: 15, borderRadius: 6 } }}
            centered
          >
            <div style={{ color: '#fff', fontSize: 16, fontWeight: 600, marginBottom: 8 }}>是否创建一个新的模拟账户？</div>
            <div style={{ color: '#b0bec5', fontSize: 14 }}>创建后可进行模拟买卖、持仓管理等操作。</div>
          </Modal>
        </>
      )}
    </>
  );
}
