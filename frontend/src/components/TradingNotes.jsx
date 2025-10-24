import React, { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Input, Select, DatePicker, Table, Popconfirm, message, Spin, Tag, Tooltip, Drawer } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, BookOutlined, EyeOutlined, EyeInvisibleOutlined, ShareAltOutlined, CopyOutlined } from '@ant-design/icons';
import axios from 'axios';

const { TextArea } = Input;
const { Option } = Select;
const { RangePicker } = DatePicker;

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// 日期格式化辅助函数
const formatDate = (date) => {
  if (!date) return null;
  const d = new Date(date);
  return d.toISOString().split('T')[0];
};

const TradingNotes = ({ userId, visible, onToggle, stockSnapshots = {} }) => {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [viewNote, setViewNote] = useState(null);
  const [viewModalVisible, setViewModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [searchForm] = Form.useForm();
  const [searchVisible, setSearchVisible] = useState(false);
  const [statistics, setStatistics] = useState({});
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [shareModalVisible, setShareModalVisible] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [currentNote, setCurrentNote] = useState(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0
  });
  const [currentFilters, setCurrentFilters] = useState({});

  // 获取笔记列表
  const fetchNotes = async (filters = {}, page = 1, pageSize = 10) => {
    if (!userId) return;
    setLoading(true);
    try {
      const params = { 
        user_id: userId, 
        page, 
        page_size: pageSize,
        ...filters 
      };
      const res = await axios.get(`${API_BASE_URL}/api/trade/notes`, { params });
      if (res.data.success) {
        setNotes(res.data.notes || []);
        setPagination({
          current: res.data.page || page,
          pageSize: res.data.page_size || pageSize,
          total: res.data.total || 0
        });
        setCurrentFilters(filters);
      }
    } catch (error) {
      message.error('获取笔记失败');
    } finally {
      setLoading(false);
    }
  };

  // 根据笔记ID获取单个笔记详情
  const fetchNoteById = async (noteId) => {
    if (!userId || !noteId) return null;
    try {
      const res = await axios.get(`${API_BASE_URL}/api/trade/notes/${noteId}`, {
        params: { user_id: userId }
      });
      if (res.data.success) {
        return res.data.note;
      } else {
        message.error(res.data.msg || '获取笔记详情失败');
        return null;
      }
    } catch (error) {
      message.error('获取笔记详情失败');
      return null;
    }
  };

  // 获取统计数据
  const fetchStatistics = async () => {
    if (!userId) return;
    try {
      const [statsRes, categoriesRes, tagsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/trade/notes/statistics`, { params: { user_id: userId } }),
        axios.get(`${API_BASE_URL}/api/trade/notes/categories`, { params: { user_id: userId } }),
        axios.get(`${API_BASE_URL}/api/trade/notes/tags`, { params: { user_id: userId } })
      ]);
      // 兼容后端返回的 statistics 字段结构
      if (statsRes.data.success) setStatistics(statsRes.data.statistics || {});
      if (categoriesRes.data.success) setCategories(categoriesRes.data.categories || []);
      if (tagsRes.data.success) setTags(tagsRes.data.tags || []);
    } catch (error) {
      console.error('获取统计数据失败:', error);
    }
  };

  useEffect(() => {
    if (visible && userId) {
      fetchNotes({}, 1, pagination.pageSize);
      fetchStatistics();
    }
  }, [visible, userId]);

  // 监听stockSnapshots变化，实时更新盈亏计算
  useEffect(() => {
    if (modalVisible && editingNote) {
      // 当编辑模态框打开时，实时更新盈亏
      updateProfitLossWithLatestPrice();
    }
  }, [stockSnapshots, modalVisible, editingNote]);

  // 保存笔记
  const handleSave = async (values) => {
    if (!userId) return;
    
    const noteData = {
      ...values,
      user_id: userId,
      tags: values.tags || [],
      technical_indicators: values.technical_indicators || {},
      news_events: values.news_events || [],
      attachments: values.attachments || [],
      follow_up_date: values.follow_up_date ? formatDate(values.follow_up_date) : null
    };

    try {
      let res;
      if (editingNote) {
        // 编辑模式：调用PUT接口更新笔记
        res = await axios.put(`${API_BASE_URL}/api/trade/notes/${editingNote.id}`, {
          user_id: userId,
          update_data: noteData
        });
      } else {
        // 新增模式：调用POST接口创建笔记
        res = await axios.post(`${API_BASE_URL}/api/trade/notes`, {
          user_id: userId,
          note_data: noteData
        });
      }
      
      if (res.data.success) {
        message.success(editingNote ? '笔记更新成功' : '笔记创建成功');
        setModalVisible(false);
        form.resetFields();
        setEditingNote(null);
        // 刷新当前页数据
        fetchNotes(currentFilters, pagination.current, pagination.pageSize);
        fetchStatistics();
      } else {
        message.error(res.data.msg || '操作失败');
      }
    } catch (error) {
      message.error(editingNote ? '更新失败' : '保存失败');
    }
  };

  // 删除笔记
  const handleDelete = async (noteId) => {
    if (!userId) return;
    try {
      const res = await axios.delete(`${API_BASE_URL}/api/trade/notes/${noteId}`, {
        params: { user_id: userId }
      });
      if (res.data.success) {
        message.success('删除成功');
        // 刷新当前页数据
        fetchNotes(currentFilters, pagination.current, pagination.pageSize);
        fetchStatistics();
      } else {
        message.error(res.data.msg || '删除失败');
      }
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 查看笔记
  const handleView = async (note) => {
    // 通过API获取最新的笔记详情
    const freshNote = await fetchNoteById(note.id);
    if (freshNote) {
      setViewNote(freshNote);
      setViewModalVisible(true);
    }
  };

  // 编辑笔记
  const handleEdit = (note) => {
    setEditingNote(note);
    form.setFieldsValue({
      ...note,
      follow_up_date: note.follow_up_date ? new Date(note.follow_up_date) : null
    });
    setModalVisible(true);
  };

  // 分享笔记
  const handleShare = (note) => {
    setCurrentNote(note);
    // 生成分享链接
    const shareUrl = `${window.location.origin}/share/note/${note.id}?user_id=${userId}`;
    setShareLink(shareUrl);
    setShareModalVisible(true);
  };

  // 复制分享链接
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareLink);
      message.success('分享链接已复制到剪贴板');
    } catch (error) {
      // 降级方案：使用传统方法复制
      const textArea = document.createElement('textarea');
      textArea.value = shareLink;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      message.success('分享链接已复制到剪贴板');
    }
  };

  // 获取最新实时价格
  const getLatestPrice = (stockCode) => {
    if (!stockCode || !stockSnapshots[stockCode]) return 0;
    const stock = stockSnapshots[stockCode];
    // 优先使用current_price，如果没有则使用last_price
    return stock.current_price || stock.last_price || 0;
  };

  // 计算盈亏
  const calculateProfitLoss = (currentPrice) => {
    const values = form.getFieldsValue();
    const tradePrice = values.trade_price || 0;
    const tradeAmount = values.trade_amount || 0;
    const tradeType = values.trade_type || '买入';
    const stockCode = values.stock_code;
    
    // 如果没有传入currentPrice，则从实时行情获取
    if (!currentPrice && stockCode) {
      currentPrice = getLatestPrice(stockCode);
    }
    
    if (tradePrice > 0 && tradeAmount > 0 && currentPrice > 0) {
      let profitLoss, profitLossRate;
      
      if (tradeType === '买入') {
        // 买入：当前价格 - 买入价格
        profitLoss = (currentPrice - tradePrice) * tradeAmount;
        profitLossRate = tradePrice > 0 ? (currentPrice - tradePrice) / tradePrice : 0;
      } else if (tradeType === '卖出') {
        // 卖出：卖出价格 - 当前价格（假设当前价格是成本价）
        profitLoss = (tradePrice - currentPrice) * tradeAmount;
        profitLossRate = currentPrice > 0 ? (tradePrice - currentPrice) / currentPrice : 0;
      } else {
        // 观察或其他类型：不计算盈亏
        profitLoss = 0;
        profitLossRate = 0;
      }
      
      // 计算手续费（简化计算，假设0.03%）
      const fee = tradePrice * tradeAmount * 0.0003;
      profitLoss = profitLoss - fee;
      
      form.setFieldsValue({
        profit_loss: parseFloat(profitLoss.toFixed(2)),
        profit_loss_rate: parseFloat(profitLossRate.toFixed(4))
      });
    }
  };

  // 实时更新盈亏计算
  const updateProfitLossWithLatestPrice = () => {
    const stockCode = form.getFieldValue('stock_code');
    if (stockCode) {
      const latestPrice = getLatestPrice(stockCode);
      if (latestPrice > 0) {
        calculateProfitLoss(latestPrice);
      }
    }
  };

  // 处理表格分页变化
  const handleTableChange = (pagination, filters, sorter) => {
    fetchNotes(currentFilters, pagination.current, pagination.pageSize);
  };

  // 搜索
  const handleSearch = (values) => {
    const filters = {};
    if (values.title) filters.search_text = values.title;
    if (values.category) filters.category = values.category;
    if (values.tags && values.tags.length > 0) filters.tags = values.tags;
    if (values.date_range && values.date_range.length === 2) {
      filters.date_from = formatDate(values.date_range[0]);
      filters.date_to = formatDate(values.date_range[1]);
    }
    // 搜索时重置到第一页
    fetchNotes(filters, 1, pagination.pageSize);
    setSearchVisible(false);
  };

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      render: (text, record) => (
        <div>
          <div 
            style={{ 
              color: '#40a9ff', 
              fontWeight: 600, 
              fontSize: 13, 
              cursor: 'pointer',
              textDecoration: 'underline dotted'
            }}
            onClick={() => handleView(record)}
            title="点击查看笔记内容"
          >
            {text}
          </div>
          <div style={{ color: '#b0bec5', fontSize: 11 }}>{record.stock_code} {record.stock_name}</div>
        </div>
      )
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (text) => (
        <Tag color="#3a2d0c" style={{ fontSize: 11, color: '#faad14', border: 'none' }}>{text}</Tag>
      )
    },
    {
      title: '交易类型',
      dataIndex: 'trade_type',
      key: 'trade_type',
      width: 80,
      render: (text) => {
        const color = text === '买入' ? '#52c41a' : text === '卖出' ? '#ff4d4f' : '#b0bec5';
        return <span style={{ color, fontWeight: 600, fontSize: 12 }}>{text || '-'}</span>;
      }
    },
    {
      title: '盈亏',
      dataIndex: 'profit_loss',
      key: 'profit_loss',
      width: 100,
      render: (value, record) => {
        // 基于最新实时价格计算盈亏
        const latestPrice = getLatestPrice(record.stock_code);
        const tradePrice = record.trade_price || 0;
        const tradeAmount = record.trade_amount || 0;
        const tradeType = record.trade_type;
        
        let realTimeProfitLoss = value;
        let realTimeProfitLossRate = record.profit_loss_rate;
        
        // 如果有实时价格且交易信息完整，重新计算
        if (latestPrice > 0 && tradePrice > 0 && tradeAmount > 0 && tradeType) {
          if (tradeType === '买入') {
            realTimeProfitLoss = (latestPrice - tradePrice) * tradeAmount;
            realTimeProfitLossRate = tradePrice > 0 ? (latestPrice - tradePrice) / tradePrice : 0;
          } else if (tradeType === '卖出') {
            realTimeProfitLoss = (tradePrice - latestPrice) * tradeAmount;
            realTimeProfitLossRate = latestPrice > 0 ? (tradePrice - latestPrice) / latestPrice : 0;
          }
          
          // 计算手续费
          const fee = tradePrice * tradeAmount * 0.0003;
          realTimeProfitLoss = realTimeProfitLoss - fee;
        }
        
        const color = realTimeProfitLoss > 0 ? '#ff4d4f' : realTimeProfitLoss < 0 ? '#52c41a' : '#b0bec5';
        return (
          <div>
            <div style={{ color, fontWeight: 700, fontSize: 12 }}>
              {realTimeProfitLoss > 0 ? '+' : ''}{realTimeProfitLoss.toFixed(2)}
            </div>
            {realTimeProfitLossRate !== null && realTimeProfitLossRate !== undefined && (
              <div style={{ color, fontSize: 10 }}>
                {realTimeProfitLossRate > 0 ? '+' : ''}{(realTimeProfitLossRate * 100).toFixed(2)}%
              </div>
            )}
            {latestPrice > 0 && (
              <div style={{ color: '#b0bec5', fontSize: 9 }}>
                实时: ¥{latestPrice.toFixed(2)}
              </div>
            )}
          </div>
        );
      }
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 120,
      render: (tags) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {tags && tags.slice(0, 2).map((tag, index) => (
            <Tag key={index} color="#11343a" style={{ fontSize: 10, margin: 0, color: '#13c2c2', border: 'none' }}>
              {tag}
            </Tag>
          ))}
          {tags && tags.length > 2 && (
            <Tag color="#b0bec5" style={{ fontSize: 10, margin: 0 }}>
              +{tags.length - 2}
            </Tag>
          )}
        </div>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_time',
      key: 'created_time',
      width: 100,
      render: (text) => (
        <span style={{ color: '#b0bec5', fontSize: 11 }}>
          {text ? new Date(text).toLocaleDateString() : '-'}
        </span>
      )
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, record) => (
        <div style={{ display: 'flex', gap: 4 }}>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
              style={{ color: '#40a9ff' }}
            />
          </Tooltip>
          <Tooltip title="分享">
            <Button
              type="text"
              size="small"
              icon={<ShareAltOutlined />}
              onClick={() => handleShare(record)}
              style={{ color: '#722ed1' }}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除这条笔记吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined />}
                style={{ color: '#ff4d4f' }}
              />
            </Tooltip>
          </Popconfirm>
        </div>
      )
    }
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
          color: '#722ed1', 
          fontWeight: 700, 
          fontSize: 17, 
          display: 'flex', 
          alignItems: 'center', 
          marginBottom: 8, 
          cursor: 'pointer', 
          userSelect: 'none', 
          justifyContent: 'space-between' 
        }}
        onClick={onToggle}
      >
        <span style={{ display: 'flex', alignItems: 'center' }}>
          <BookOutlined style={{ color: '#722ed1', marginRight: 8 }} />炒股笔记
          <span style={{ marginLeft: 8, fontSize: 16 }}>
            {visible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
          </span>
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* 统计信息 */}
          <div style={{ display: 'flex', gap: 12, marginRight: 16 }}>
            <span style={{ color: '#b0bec5', fontSize: 12 }}>
              总数: <span style={{ color: '#40a9ff', fontWeight: 600 }}>{statistics.total_notes || 0}</span>
            </span>
            <span style={{ color: '#b0bec5', fontSize: 12 }}>
              分类: <span style={{ color: '#faad14', fontWeight: 600 }}>{Object.keys(statistics.category_stats || {}).length}</span>
            </span>
            <span style={{ color: '#b0bec5', fontSize: 12 }}>
              标签: <span style={{ color: '#13c2c2', fontWeight: 600 }}>{tags.length}</span>
            </span>
          </div>
          
          {/* 搜索按钮 */}
          <Tooltip title="搜索笔记">
            <Button
              type="text"
              size="small"
              icon={<SearchOutlined />}
              onClick={(e) => { e.stopPropagation(); setSearchVisible(true); }}
              style={{ color: '#faad14' }}
            />
          </Tooltip>
          
          {/* 新增按钮 */}
          <Tooltip title="新增笔记">
            <Button
              type="text"
              size="small"
              icon={<PlusOutlined />}
              onClick={(e) => { 
                e.stopPropagation(); 
                setEditingNote(null);
                form.resetFields();
                setModalVisible(true);
              }}
              style={{ color: '#52c41a' }}
            />
          </Tooltip>
        </div>
      </div>

      {visible && (
        <div style={{ marginTop: 12 }}>
          <Table
            columns={columns}
            dataSource={notes}
            rowKey="id"
            pagination={{
              ...pagination,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
              style: { color: '#b0bec5' }
            }}
            onChange={handleTableChange}
            loading={loading}
            size="small"
            style={{ 
              background: '#181c24', 
              color: '#e6f7ff', 
              borderRadius: 8, 
              boxShadow: '0 2px 8px #0003' 
            }}
            scroll={{ x: 800 }}
            locale={{ 
              emptyText: <span style={{ color: '#b0bec5' }}>暂无笔记</span> 
            }}
          />
        </div>
      )}

      {/* 新增/编辑笔记模态框 */}
      <Modal
        title={
          <span style={{ color: '#40a9ff', fontWeight: 700, fontSize: 16 }}>
            {editingNote ? '编辑笔记' : ''}
          </span>
        }
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingNote(null);
          form.resetFields();
        }}
        footer={null}
        width={800}
        styles={{ 
          body: { background: '#232a36', color: '#fff', borderRadius: 14, padding: 20 },
          header: { background: '#232a36', borderBottom: '1px solid #313a4d' }
        }}
        style={{ top: 50, borderRadius: 14 }}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          style={{ color: '#fff' }}
        >
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Form.Item
                name="title"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>标题</span>}
                rules={[{ required: true, message: '请输入标题' }]}
              >
                <Input placeholder="自动填充标题" style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} />
              </Form.Item>

              <Form.Item
                name="stock_code"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>股票代码</span>}
              >
                <Select 
                  placeholder="请选择股票" 
                  style={{ background: '#181c24', border: '1px solid #313a4d' }}
                  showSearch
                  filterOption={(input, option) =>
                    (option?.children ?? '').toLowerCase().includes(input.toLowerCase())
                  }
                  onChange={(value) => {
                    const selectedStock = stockSnapshots[value];
                    if (selectedStock) {
                      const currentPrice = getLatestPrice(value);
                      // 获取当前日期字符串
                      const today = new Date();
                      const yyyy = today.getFullYear();
                      const mm = String(today.getMonth() + 1).padStart(2, '0');
                      const dd = String(today.getDate()).padStart(2, '0');
                      const dateStr = `${yyyy}-${mm}-${dd}`;
                      form.setFieldsValue({
                        stock_name: selectedStock.name || '',
                        title: `${selectedStock.name || value} - 交易笔记 - ${dateStr}`,
                        trade_price: currentPrice
                      });
                      // 自动计算盈亏
                      calculateProfitLoss(currentPrice);
                    }
                  }}
                >
                  {Object.entries(stockSnapshots).map(([code, stock]) => (
                    <Option key={code} value={code}>
                      {stock.name || code} ({code})
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                name="stock_name"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>股票名称</span>}
              >
                <Input placeholder="自动填充" style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} readOnly />
              </Form.Item>

              <Form.Item
                name="category"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>分类</span>}
                initialValue="其他"
              >
                <Select style={{ background: '#181c24', border: '1px solid #313a4d' }}>
                  <Option value="技术分析">技术分析</Option>
                  <Option value="基本面分析">基本面分析</Option>
                  <Option value="交易记录">交易记录</Option>
                  <Option value="市场观察">市场观察</Option>
                  <Option value="其他">其他</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="trade_type"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>交易类型</span>}
              >
                <Select 
                  placeholder="请选择交易类型" 
                  style={{ background: '#181c24', border: '1px solid #313a4d' }}
                  onChange={(value) => {
                    const stockCode = form.getFieldValue('stock_code');
                    const currentPrice = getLatestPrice(stockCode);
                    if (currentPrice > 0) {
                      calculateProfitLoss(currentPrice);
                    }
                  }}
                >
                  <Option value="买入">买入</Option>
                  <Option value="卖出">卖出</Option>
                  <Option value="观察">观察</Option>
                </Select>
              </Form.Item>
            </div>

            <div style={{ flex: 1 }}>
              <Form.Item
                name="trade_price"
                label={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ color: '#faad14', fontSize: 13 }}>交易价格</span>
                    {(() => {
                      const stockCode = form.getFieldValue('stock_code');
                      const latestPrice = getLatestPrice(stockCode);
                      return latestPrice > 0 ? (
                        <span style={{ color: '#40a9ff', fontSize: 11 }}>
                          实时: ¥{latestPrice.toFixed(2)}
                        </span>
                      ) : null;
                    })()}
                  </div>
                }
              >
                <Input 
                  type="number" 
                  placeholder="自动填充当前价格" 
                  style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
                  onChange={(e) => {
                    const stockCode = form.getFieldValue('stock_code');
                    const currentPrice = getLatestPrice(stockCode);
                    if (currentPrice > 0) {
                      calculateProfitLoss(currentPrice);
                    }
                  }}
                />
              </Form.Item>

              <Form.Item
                name="trade_amount"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>交易数量</span>}
              >
                <Input 
                  type="number" 
                  placeholder="0" 
                  style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
                  onChange={(e) => {
                    const stockCode = form.getFieldValue('stock_code');
                    const currentPrice = getLatestPrice(stockCode);
                    if (currentPrice > 0) {
                      calculateProfitLoss(currentPrice);
                    }
                  }}
                />
              </Form.Item>

              <Form.Item
                name="profit_loss"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>盈亏金额</span>}
              >
                <Input 
                  type="number" 
                  placeholder="自动计算" 
                  style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
                  readOnly
                />
              </Form.Item>

              <Form.Item
                name="profit_loss_rate"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>盈亏率</span>}
              >
                <Input 
                  type="number" 
                  placeholder="自动计算" 
                  style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
                  readOnly
                />
              </Form.Item>

              <Form.Item
                name="risk_level"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>风险等级</span>}
                initialValue="中等"
              >
                <Select style={{ background: '#181c24', border: '1px solid #313a4d' }}>
                  <Option value="低">低</Option>
                  <Option value="中等">中等</Option>
                  <Option value="高">高</Option>
                </Select>
              </Form.Item>
            </div>
          </div>

          <Form.Item
            name="content"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>笔记内容</span>}
          >
            <TextArea 
              rows={4} 
              placeholder="请输入笔记内容..." 
              style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
            />
          </Form.Item>

          <Form.Item
            name="trade_reason"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>交易理由</span>}
          >
            <TextArea 
              rows={2} 
              placeholder="请输入交易理由..." 
              style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
            />
          </Form.Item>

          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Form.Item
                name="lessons"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>经验教训</span>}
              >
                <TextArea 
                  rows={2} 
                  placeholder="请输入经验教训..." 
                  style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
                />
              </Form.Item>
            </div>

            <div style={{ flex: 1 }}>
              <Form.Item
                name="next_plan"
                label={<span style={{ color: '#faad14', fontSize: 13 }}>下次计划</span>}
              >
                <TextArea 
                  rows={2} 
                  placeholder="请输入下次计划..." 
                  style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} 
                />
              </Form.Item>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item
              name="tags"
              label={<span style={{ color: '#faad14', fontSize: 13 }}>标签</span>}
            >
              <Select
                mode="tags"
                placeholder="请输入标签"
                style={{ background: '#181c24', border: '1px solid #313a4d', minWidth: 200 }}
                styles={{ popup: { root: { minWidth: 250 } } }}
                optionLabelProp="label"
              >
                {tags.map(tag => (
                  <Option key={tag.tag} value={tag.tag} label={`${tag.tag} (${tag.count})`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minWidth: 200 }}>
                      <span>{tag.tag}</span>
                      <span style={{ color: '#b0bec5', fontSize: 12 }}>({tag.count})</span>
                    </div>
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="follow_up_date"
              label={<span style={{ color: '#faad14', fontSize: 13 }}>跟进日期</span>}
            >
              <DatePicker 
                style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }}
                placeholder="选择跟进日期"
              />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 20 }}>
            <Button
              onClick={() => {
                setModalVisible(false);
                setEditingNote(null);
                form.resetFields();
              }}
              style={{ 
                background: '#232a36', 
                border: '1px solid #313a4d', 
                color: '#b0bec5' 
              }}
            >
              取消
            </Button>
            <Button
              type="primary"
              htmlType="submit"
              style={{ 
                background: '#1890ff', 
                border: 'none', 
                fontWeight: 600 
              }}
            >
              {editingNote ? '更新' : '保存'}
            </Button>
          </div>
        </Form>
      </Modal>

      {/* 搜索抽屉 */}
      <Drawer
        title={
          <span style={{ color: '#40a9ff', fontWeight: 700, fontSize: 16 }}>
            <SearchOutlined style={{ marginRight: 8 }} />搜索笔记
          </span>
        }
        open={searchVisible}
        onClose={() => setSearchVisible(false)}
        width={400}
        styles={{
          body: { background: '#232a36', color: '#fff', padding: 20 },
          header: { background: '#232a36', borderBottom: '1px solid #313a4d' }
        }}
        style={{ background: '#232a36' }}
      >
        <Form
          form={searchForm}
          layout="vertical"
          onFinish={handleSearch}
          style={{ color: '#fff' }}
        >
          <Form.Item
            name="title"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>标题关键词</span>}
          >
            <Input placeholder="请输入标题关键词" style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} />
          </Form.Item>

          <Form.Item
            name="stock_code"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>股票代码</span>}
          >
            <Input placeholder="如: 00700.HK" style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }} />
          </Form.Item>

          <Form.Item
            name="category"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>分类</span>}
          >
            <Select placeholder="请选择分类" style={{ background: '#181c24', border: '1px solid #313a4d' }}>
              {categories.map(cat => (
                <Option key={cat} value={cat}>{cat}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="tags"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>标签</span>}
          >
            <Select
              mode="multiple"
              placeholder="请选择标签"
              style={{ background: '#181c24', border: '1px solid #313a4d', minWidth: 200 }}
              styles={{ popup: { root: { minWidth: 250 } } }}
              optionLabelProp="label"
            >
              {tags.map(tag => (
                <Option key={tag.tag} value={tag.tag} label={`${tag.tag} (${tag.count})`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minWidth: 200 }}>
                    <span>{tag.tag}</span>
                    <span style={{ color: '#b0bec5', fontSize: 12 }}>({tag.count})</span>
                  </div>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="date_range"
            label={<span style={{ color: '#faad14', fontSize: 13 }}>创建时间</span>}
          >
            <RangePicker 
              style={{ background: '#181c24', border: '1px solid #313a4d', color: '#fff' }}
              placeholder={['开始日期', '结束日期']}
            />
          </Form.Item>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 20 }}>
            <Button
              onClick={() => {
                searchForm.resetFields();
                fetchNotes();
                setSearchVisible(false);
              }}
              style={{ 
                background: '#232a36', 
                border: '1px solid #313a4d', 
                color: '#b0bec5' 
              }}
            >
              重置
            </Button>
            <Button
              type="primary"
              htmlType="submit"
              style={{ 
                background: '#1890ff', 
                border: 'none', 
                fontWeight: 600 
              }}
            >
              搜索
            </Button>
          </div>
        </Form>
      </Drawer>

      {/* 查看笔记模态框 */}
      <Modal
        title={
          <span style={{ color: '#40a9ff', fontWeight: 700, fontSize: 16 }}>
            查看笔记
          </span>
        }
        open={viewModalVisible}
        onCancel={() => {
          setViewModalVisible(false);
          setViewNote(null);
        }}
        footer={null}
        width={800}
        styles={{ 
          body: { background: '#232a36', color: '#fff', borderRadius: 14, padding: 20 },
          header: { background: '#232a36', borderBottom: '1px solid #313a4d' }
        }}
        style={{ top: 50, borderRadius: 14 }}
      >
        {viewNote && (
          <div style={{ color: '#fff' }}>
            {/* 基本信息 */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
              <div style={{ flex: 1 }}>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>标题：</span>
                  <span style={{ color: '#fff', fontSize: 14, fontWeight: 600 }}>{viewNote.title}</span>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>股票：</span>
                  <span style={{ color: '#40a9ff', fontSize: 14 }}>{viewNote.stock_name} ({viewNote.stock_code})</span>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>分类：</span>
                  <span style={{ color: '#fff', fontSize: 14 }}>{viewNote.category}</span>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>标签：</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {viewNote.tags && viewNote.tags.map((tag, index) => (
                      <Tag key={index} color="#13c2c2" style={{ fontSize: 11 }}>
                        {tag}
                      </Tag>
                    ))}
                  </div>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>交易类型：</span>
                  <span style={{ 
                    color: viewNote.trade_type === '买入' ? '#52c41a' : viewNote.trade_type === '卖出' ? '#ff4d4f' : '#b0bec5', 
                    fontSize: 14, 
                    fontWeight: 600 
                  }}>
                    {viewNote.trade_type || '-'}
                  </span>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>交易价格：</span>
                  <span style={{ color: '#fff', fontSize: 14 }}>{viewNote.trade_price || '-'}</span>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>交易数量：</span>
                  <span style={{ color: '#fff', fontSize: 14 }}>{viewNote.trade_amount || '-'}</span>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <span style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>风险等级：</span>
                  <span style={{ color: '#fff', fontSize: 14 }}>{viewNote.risk_level || '-'}</span>
                </div>
              </div>
            </div>

            {/* 盈亏信息 */}
            {(viewNote.profit_loss !== null && viewNote.profit_loss !== undefined) && (
              <div style={{ 
                background: '#181c24', 
                padding: 12, 
                borderRadius: 8, 
                marginBottom: 20,
                border: '1px solid #313a4d'
              }}>
                <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>盈亏信息</div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div>
                    <span style={{ color: '#b0bec5', fontSize: 12 }}>盈亏金额：</span>
                    <span style={{ 
                      color: viewNote.profit_loss > 0 ? '#ff4d4f' : viewNote.profit_loss < 0 ? '#52c41a' : '#fff', 
                      fontSize: 14, 
                      fontWeight: 700 
                    }}>
                      {viewNote.profit_loss > 0 ? '+' : ''}{viewNote.profit_loss?.toFixed(2)}
                    </span>
                  </div>
                  {viewNote.profit_loss_rate !== null && viewNote.profit_loss_rate !== undefined && (
                    <div>
                      <span style={{ color: '#b0bec5', fontSize: 12 }}>盈亏率：</span>
                      <span style={{ 
                        color: viewNote.profit_loss_rate > 0 ? '#ff7875' : viewNote.profit_loss_rate < 0 ? '#95de64' : '#b0bec5', 
                        fontSize: 14, 
                        fontWeight: 600 
                      }}>
                        {viewNote.profit_loss_rate > 0 ? '+' : ''}{(viewNote.profit_loss_rate * 100).toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 笔记内容 */}
            {viewNote.content && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>笔记内容</div>
                <div style={{ 
                  background: '#181c24', 
                  padding: 12, 
                  borderRadius: 8, 
                  border: '1px solid #313a4d',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.6
                }}>
                  {viewNote.content}
                </div>
              </div>
            )}

            {/* 交易理由 */}
            {viewNote.trade_reason && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>交易理由</div>
                <div style={{ 
                  background: '#181c24', 
                  padding: 12, 
                  borderRadius: 8, 
                  border: '1px solid #313a4d',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.6
                }}>
                  {viewNote.trade_reason}
                </div>
              </div>
            )}

            {/* 经验教训和下次计划 */}
            <div style={{ display: 'flex', gap: 16 }}>
              {viewNote.lessons && (
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>经验教训</div>
                  <div style={{ 
                    background: '#181c24', 
                    padding: 12, 
                    borderRadius: 8, 
                    border: '1px solid #313a4d',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.6
                  }}>
                    {viewNote.lessons}
                  </div>
                </div>
              )}
              {viewNote.next_plan && (
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>下次计划</div>
                  <div style={{ 
                    background: '#181c24', 
                    padding: 12, 
                    borderRadius: 8, 
                    border: '1px solid #313a4d',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.6
                  }}>
                    {viewNote.next_plan}
                  </div>
                </div>
              )}
            </div>

            {/* 时间信息 */}
            <div style={{ 
              marginTop: 20, 
              padding: 12, 
              background: '#181c24', 
              borderRadius: 8, 
              border: '1px solid #313a4d',
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
              color: '#b0bec5'
            }}>
              <span>创建时间：{viewNote.created_time}</span>
              <span>更新时间：{viewNote.updated_time}</span>
              {viewNote.follow_up_date && (
                <span>跟进日期：{viewNote.follow_up_date}</span>
              )}
            </div>

            {/* 操作按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 20 }}>
              <Button
                onClick={() => {
                  setViewModalVisible(false);
                  setViewNote(null);
                }}
                style={{ 
                  background: '#232a36', 
                  border: '1px solid #313a4d', 
                  color: '#b0bec5' 
                }}
              >
                关闭
              </Button>
              <Button
                onClick={() => {
                  setViewModalVisible(false);
                  setViewNote(null);
                  handleEdit(viewNote);
                }}
                type="primary"
                style={{ 
                  background: '#1890ff', 
                  border: 'none', 
                  fontWeight: 600 
                }}
              >
                编辑
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* 分享笔记模态框 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShareAltOutlined style={{ color: '#722ed1' }} />
            <span>分享笔记</span>
          </div>
        }
        open={shareModalVisible}
        onCancel={() => {
          setShareModalVisible(false);
          setShareLink('');
          setCurrentNote(null);
        }}
        footer={null}
        width={500}
        styles={{ body: { background: '#232a36', color: '#fff' } }}
        style={{ background: '#232a36' }}
      >
        {currentNote && (
          <div>
            {/* 笔记基本信息 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ color: '#faad14', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
                {currentNote.title}
              </div>
              <div style={{ color: '#b0bec5', fontSize: 12 }}>
                {currentNote.stock_code} {currentNote.stock_name}
              </div>
            </div>

            {/* 分享链接 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                分享链接
              </div>
              <div style={{ 
                background: '#181c24', 
                padding: 12, 
                borderRadius: 8, 
                border: '1px solid #313a4d',
                wordBreak: 'break-all',
                fontSize: 12,
                color: '#b0bec5'
              }}>
                {shareLink}
              </div>
            </div>

            {/* 操作按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <Button
                onClick={() => {
                  setShareModalVisible(false);
                  setShareLink('');
                  setCurrentNote(null);
                }}
                style={{ 
                  background: '#232a36', 
                  border: '1px solid #313a4d', 
                  color: '#b0bec5' 
                }}
              >
                取消
              </Button>
              <Button
                onClick={handleCopyLink}
                type="primary"
                icon={<CopyOutlined />}
                style={{ 
                  background: '#722ed1', 
                  border: 'none', 
                  fontWeight: 600 
                }}
              >
                复制链接
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </Card>
  );
};

export default TradingNotes; 
