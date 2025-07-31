import React, { useState, useEffect } from 'react';
import { Card, Spin, message, Tag, Button, Modal, Form, Input, Select } from 'antd';
import { ArrowLeftOutlined, BookOutlined, CalendarOutlined, TagOutlined, SaveOutlined, UserOutlined } from '@ant-design/icons';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

const { TextArea } = Input;
const { Option } = Select;

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// 添加全局样式来确保Select选项正确显示
const selectStyle = {
  '.ant-select-dropdown': {
    backgroundColor: '#181c24 !important',
    border: '1px solid #313a4d !important'
  },
  '.ant-select-item': {
    color: '#fff !important',
    backgroundColor: '#181c24 !important'
  },
  '.ant-select-item-option-selected': {
    backgroundColor: '#313a4d !important'
  },
  '.ant-select-item-option-active': {
    backgroundColor: '#313a4d !important'
  }
};

const ShareNote = () => {
  const { noteId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [note, setNote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveModalVisible, setSaveModalVisible] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveForm] = Form.useForm();

  useEffect(() => {
    const fetchNote = async () => {
      if (!noteId) {
        setError('笔记ID不能为空');
        setLoading(false);
        return;
      }

      const userId = searchParams.get('user_id');
      if (!userId) {
        setError('缺少用户ID参数');
        setLoading(false);
        return;
      }

      try {
        const response = await axios.get(`${API_BASE_URL}/share/note/${noteId}`, {
          params: { user_id: userId }
        });

        if (response.data.success) {
          setNote(response.data.note);
        } else {
          setError(response.data.msg || '获取笔记失败');
        }
      } catch (error) {
        console.error('获取笔记失败:', error);
        setError('获取笔记失败，请检查链接是否正确');
      } finally {
        setLoading(false);
      }
    };

    fetchNote();
  }, [noteId, searchParams]);

  // 处理保存笔记
  const handleSave = () => {
    const currentUserId = searchParams.get('user_id');
    if (!currentUserId) {
      message.error('缺少用户ID参数，无法保存笔记');
      return;
    }
    
    // 预填充表单数据
    saveForm.setFieldsValue({
      title: note.title,
      stock_code: note.stock_code,
      stock_name: note.stock_name,
      trade_type: note.trade_type,
      trade_price: note.trade_price,
      trade_amount: note.trade_amount,
      category: note.category,
      content: note.content,
      trade_reason: note.trade_reason,
      lessons: note.lessons,
      next_plan: note.next_plan,
      tags: note.tags || []
    });
    
    setSaveModalVisible(true);
  };

  // 执行保存
  const handleSaveSubmit = async (values) => {
    const currentUserId = searchParams.get('user_id');
    if (!currentUserId) {
      message.error('缺少用户ID参数，无法保存笔记');
      return;
    }

    setSaveLoading(true);
    try {
      const noteData = {
        ...values,
        user_id: currentUserId,
        tags: values.tags || [],
        created_time: new Date().toISOString(),
        updated_time: new Date().toISOString()
      };

      const response = await axios.post(`${API_BASE_URL}/api/trade/notes`, {
        user_id: currentUserId,
        note_data: noteData
      });

      if (response.data.success) {
        message.success('笔记保存成功！');
        setSaveModalVisible(false);
        saveForm.resetFields();
      } else {
        message.error(response.data.msg || '保存失败');
      }
    } catch (error) {
      console.error('保存笔记失败:', error);
      message.error('保存失败，请稍后重试');
    } finally {
      setSaveLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20
      }}>
        <div style={{ textAlign: 'center' }}>
          <Spin size="large" style={{ color: '#722ed1' }} />
          <div style={{ color: '#b0bec5', marginTop: 16, fontSize: 16 }}>正在加载笔记内容...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20
      }}>
        <Card style={{
          background: 'rgba(35, 42, 54, 0.95)',
          border: '1px solid #313a4d',
          borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          maxWidth: 500,
          width: '100%'
        }}>
          <div style={{ textAlign: 'center', color: '#ff4d4f' }}>
            <div style={{ fontSize: 24, marginBottom: 16 }}>⚠️</div>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>加载失败</div>
            <div style={{ color: '#b0bec5', marginBottom: 20 }}>{error}</div>
            <Button
              type="primary"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/')}
              style={{
                background: '#722ed1',
                border: 'none',
                borderRadius: 8,
                height: 40,
                padding: '0 24px'
              }}
            >
              返回首页
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!note) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20
      }}>
        <Card style={{
          background: 'rgba(35, 42, 54, 0.95)',
          border: '1px solid #313a4d',
          borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          maxWidth: 500,
          width: '100%'
        }}>
          <div style={{ textAlign: 'center', color: '#b0bec5' }}>
            <div style={{ fontSize: 24, marginBottom: 16 }}>📝</div>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>笔记不存在</div>
            <div style={{ marginBottom: 20 }}>该笔记可能已被删除或链接已失效</div>
            <Button
              type="primary"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/')}
              style={{
                background: '#722ed1',
                border: 'none',
                borderRadius: 8,
                height: 40,
                padding: '0 24px'
              }}
            >
              返回首页
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      padding: '20px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
    }}>
      {/* 添加Select样式 */}
      <style>
        {`
          .ant-select-dropdown {
            background-color: #181c24 !important;
            border: 1px solid #313a4d !important;
          }
          .ant-select-item {
            color: #fff !important;
            background-color: #181c24 !important;
          }
          .ant-select-item-option-selected {
            background-color: #313a4d !important;
          }
          .ant-select-item-option-active {
            background-color: #313a4d !important;
          }
          .ant-select-item-option-content {
            color: #fff !important;
          }
        `}
      </style>
      {/* 返回按钮 */}
      <div style={{ marginBottom: 20 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
          style={{
            color: '#b0bec5',
            fontSize: 16,
            height: 40,
            padding: '0 16px',
            borderRadius: 8,
            border: '1px solid #313a4d',
            background: 'rgba(35, 42, 54, 0.8)'
          }}
        >
          返回首页
        </Button>
      </div>

      {/* 笔记内容卡片 */}
      <Card style={{
        background: 'rgba(35, 42, 54, 0.95)',
        border: '1px solid #313a4d',
        borderRadius: 16,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
        maxWidth: 800,
        margin: '0 auto'
      }}>
        {/* 笔记标题和基本信息 */}
        <div style={{ marginBottom: 24 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            marginBottom: 16
          }}>
            <BookOutlined style={{ color: '#722ed1', fontSize: 24 }} />
            <h1 style={{
              color: '#fff',
              fontSize: 24,
              fontWeight: 700,
              margin: 0,
              flex: 1
            }}>
              {note.title}
            </h1>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              style={{
                background: '#722ed1',
                border: 'none',
                borderRadius: 8,
                height: 40,
                padding: '0 16px',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              保存到我的笔记
            </Button>
          </div>

          {/* 股票信息 */}
          <div style={{
            background: 'rgba(24, 28, 36, 0.8)',
            padding: 16,
            borderRadius: 12,
            border: '1px solid #313a4d',
            marginBottom: 16
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              flexWrap: 'wrap'
            }}>
              <div>
                <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>股票代码</div>
                <div style={{ color: '#40a9ff', fontSize: 16, fontWeight: 600 }}>{note.stock_code}</div>
              </div>
              <div>
                <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>股票名称</div>
                <div style={{ color: '#fff', fontSize: 16, fontWeight: 600 }}>{note.stock_name}</div>
              </div>
              {note.trade_type && (
                <div>
                  <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>交易类型</div>
                  <div style={{
                    color: note.trade_type === '买入' ? '#52c41a' : note.trade_type === '卖出' ? '#ff4d4f' : '#b0bec5',
                    fontSize: 16,
                    fontWeight: 600
                  }}>
                    {note.trade_type}
                  </div>
                </div>
              )}
              {note.category && (
                <div>
                  <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>分类</div>
                  <Tag color="#3a2d0c" style={{ fontSize: 12, color: '#faad14', border: 'none' }}>
                    {note.category}
                  </Tag>
                </div>
              )}
            </div>
          </div>

          {/* 交易信息 */}
          {(note.trade_price || note.trade_amount) && (
            <div style={{
              background: 'rgba(24, 28, 36, 0.8)',
              padding: 16,
              borderRadius: 12,
              border: '1px solid #313a4d',
              marginBottom: 16
            }}>
              <div style={{ color: '#faad14', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>交易信息</div>
              <div style={{
                display: 'flex',
                gap: 24,
                flexWrap: 'wrap'
              }}>
                {note.trade_price && (
                  <div>
                    <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>交易价格</div>
                    <div style={{ color: '#fff', fontSize: 16, fontWeight: 600 }}>¥{note.trade_price}</div>
                  </div>
                )}
                {note.trade_amount && (
                  <div>
                    <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>交易数量</div>
                    <div style={{ color: '#fff', fontSize: 16, fontWeight: 600 }}>{note.trade_amount}</div>
                  </div>
                )}
                {note.profit_loss !== null && note.profit_loss !== undefined && (
                  <div>
                    <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>盈亏金额</div>
                    <div style={{
                      color: note.profit_loss > 0 ? '#ff4d4f' : note.profit_loss < 0 ? '#52c41a' : '#fff',
                      fontSize: 16,
                      fontWeight: 700
                    }}>
                      {note.profit_loss > 0 ? '+' : ''}{note.profit_loss?.toFixed(2)}
                    </div>
                  </div>
                )}
                {note.profit_loss_rate !== null && note.profit_loss_rate !== undefined && (
                  <div>
                    <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 4 }}>盈亏率</div>
                    <div style={{
                      color: note.profit_loss_rate > 0 ? '#ff7875' : note.profit_loss_rate < 0 ? '#95de64' : '#b0bec5',
                      fontSize: 16,
                      fontWeight: 600
                    }}>
                      {note.profit_loss_rate > 0 ? '+' : ''}{(note.profit_loss_rate * 100).toFixed(2)}%
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 标签 */}
          {note.tags && note.tags.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: '#b0bec5', fontSize: 12, marginBottom: 8 }}>
                <TagOutlined style={{ marginRight: 4 }} />
                标签
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {note.tags.map((tag, index) => (
                  <Tag
                    key={index}
                    color="#11343a"
                    style={{
                      fontSize: 12,
                      color: '#13c2c2',
                      border: 'none',
                      borderRadius: 6,
                      padding: '4px 8px'
                    }}
                  >
                    {tag}
                  </Tag>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 笔记内容 */}
        {note.content && (
          <div style={{ marginBottom: 24 }}>
            <div style={{ color: '#faad14', fontSize: 16, fontWeight: 600, marginBottom: 12 }}>笔记内容</div>
            <div style={{
              background: 'rgba(24, 28, 36, 0.8)',
              padding: 20,
              borderRadius: 12,
              border: '1px solid #313a4d',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.8,
              color: '#fff',
              fontSize: 14
            }}>
              {note.content}
            </div>
          </div>
        )}

        {/* 交易理由 */}
        {note.trade_reason && (
          <div style={{ marginBottom: 24 }}>
            <div style={{ color: '#faad14', fontSize: 16, fontWeight: 600, marginBottom: 12 }}>交易理由</div>
            <div style={{
              background: 'rgba(24, 28, 36, 0.8)',
              padding: 20,
              borderRadius: 12,
              border: '1px solid #313a4d',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.8,
              color: '#fff',
              fontSize: 14
            }}>
              {note.trade_reason}
            </div>
          </div>
        )}

        {/* 经验教训和下次计划 */}
        {(note.lessons || note.next_plan) && (
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', gap: 20 }}>
              {note.lessons && (
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#faad14', fontSize: 16, fontWeight: 600, marginBottom: 12 }}>经验教训</div>
                  <div style={{
                    background: 'rgba(24, 28, 36, 0.8)',
                    padding: 20,
                    borderRadius: 12,
                    border: '1px solid #313a4d',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.8,
                    color: '#fff',
                    fontSize: 14
                  }}>
                    {note.lessons}
                  </div>
                </div>
              )}
              {note.next_plan && (
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#faad14', fontSize: 16, fontWeight: 600, marginBottom: 12 }}>下次计划</div>
                  <div style={{
                    background: 'rgba(24, 28, 36, 0.8)',
                    padding: 20,
                    borderRadius: 12,
                    border: '1px solid #313a4d',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.8,
                    color: '#fff',
                    fontSize: 14
                  }}>
                    {note.next_plan}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 时间信息 */}
        <div style={{
          background: 'rgba(24, 28, 36, 0.8)',
          padding: 16,
          borderRadius: 12,
          border: '1px solid #313a4d',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 16
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <CalendarOutlined style={{ color: '#b0bec5' }} />
            <span style={{ color: '#b0bec5', fontSize: 14 }}>创建时间：{note.created_time}</span>
          </div>
          {note.updated_time && note.updated_time !== note.created_time && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <CalendarOutlined style={{ color: '#b0bec5' }} />
              <span style={{ color: '#b0bec5', fontSize: 14 }}>更新时间：{note.updated_time}</span>
            </div>
          )}
          {note.follow_up_date && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <CalendarOutlined style={{ color: '#b0bec5' }} />
              <span style={{ color: '#b0bec5', fontSize: 14 }}>跟进日期：{note.follow_up_date}</span>
            </div>
          )}
        </div>
      </Card>

      {/* 保存笔记模态框 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SaveOutlined style={{ color: '#722ed1' }} />
            <span>保存到我的笔记</span>
          </div>
        }
        open={saveModalVisible}
        onCancel={() => {
          setSaveModalVisible(false);
          saveForm.resetFields();
        }}
        footer={null}
        width={600}
        styles={{ body: { background: '#232a36', color: '#fff' } }}
        style={{ background: '#232a36' }}
      >
        <Form
          form={saveForm}
          layout="vertical"
          onFinish={handleSaveSubmit}
          style={{ color: '#fff' }}
          labelCol={{ style: { color: '#fff' } }}
        >
          <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
            <Form.Item
              label={<span style={{ color: '#fff' }}>标题</span>}
              name="title"
              style={{ flex: 1, marginBottom: 16 }}
              rules={[{ required: true, message: '请输入标题' }]}
            >
              <Input
                placeholder="请输入笔记标题"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
            <Form.Item
              label={<span style={{ color: '#fff' }}>分类</span>}
              name="category"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <Select
                placeholder="请选择分类"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
                dropdownStyle={{
                  background: '#181c24',
                  border: '1px solid #313a4d'
                }}
              >
                <Option value="基本面分析">基本面分析</Option>
                <Option value="智能诊断">智能诊断</Option>
                <Option value="交易记录">交易记录</Option>
                <Option value="观察笔记">观察笔记</Option>
                <Option value="自动记录">自动记录</Option>
              </Select>
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
            <Form.Item
              label={<span style={{ color: '#fff' }}>股票代码</span>}
              name="stock_code"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <Input
                placeholder="股票代码"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
            <Form.Item
              label={<span style={{ color: '#fff' }}>股票名称</span>}
              name="stock_name"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <Input
                placeholder="股票名称"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
            <Form.Item
              label={<span style={{ color: '#fff' }}>交易类型</span>}
              name="trade_type"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <Select
                placeholder="请选择交易类型"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
                dropdownStyle={{
                  background: '#181c24',
                  border: '1px solid #313a4d'
                }}
              >
                <Option value="买入">买入</Option>
                <Option value="卖出">卖出</Option>
                <Option value="观察">观察</Option>
              </Select>
            </Form.Item>
            <Form.Item
              label={<span style={{ color: '#fff' }}>交易价格</span>}
              name="trade_price"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <Input
                placeholder="交易价格"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
            <Form.Item
              label={<span style={{ color: '#fff' }}>交易数量</span>}
              name="trade_amount"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <Input
                placeholder="交易数量"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
          </div>

          <Form.Item
            label={<span style={{ color: '#fff' }}>笔记内容</span>}
            name="content"
            style={{ marginBottom: 16 }}
          >
            <TextArea
              rows={4}
              placeholder="请输入笔记内容"
              style={{
                background: '#181c24',
                border: '1px solid #313a4d',
                color: '#fff',
                borderRadius: 8
              }}
            />
          </Form.Item>

          <Form.Item
            label={<span style={{ color: '#fff' }}>交易理由</span>}
            name="trade_reason"
            style={{ marginBottom: 16 }}
          >
            <TextArea
              rows={3}
              placeholder="请输入交易理由"
              style={{
                background: '#181c24',
                border: '1px solid #313a4d',
                color: '#fff',
                borderRadius: 8
              }}
            />
          </Form.Item>

          <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
            <Form.Item
              label={<span style={{ color: '#fff' }}>经验教训</span>}
              name="lessons"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <TextArea
                rows={3}
                placeholder="请输入经验教训"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
            <Form.Item
              label={<span style={{ color: '#fff' }}>下次计划</span>}
              name="next_plan"
              style={{ flex: 1, marginBottom: 16 }}
            >
              <TextArea
                rows={3}
                placeholder="请输入下次计划"
                style={{
                  background: '#181c24',
                  border: '1px solid #313a4d',
                  color: '#fff',
                  borderRadius: 8
                }}
              />
            </Form.Item>
          </div>

          <Form.Item
            label={<span style={{ color: '#fff' }}>标签</span>}
            name="tags"
            style={{ marginBottom: 24 }}
          >
            <Select
              mode="tags"
              placeholder="请输入标签，按回车确认"
              style={{
                background: '#181c24',
                border: '1px solid #313a4d',
                color: '#fff',
                borderRadius: 8
              }}
              dropdownStyle={{
                background: '#181c24',
                border: '1px solid #313a4d'
              }}
            />
          </Form.Item>

          {/* 用户ID提示 */}
          <div style={{
            background: 'rgba(24, 28, 36, 0.8)',
            padding: 12,
            borderRadius: 8,
            border: '1px solid #313a4d',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <UserOutlined style={{ color: '#722ed1' }} />
            <span style={{ color: '#b0bec5', fontSize: 12 }}>
              将保存到用户ID: <span style={{ color: '#40a9ff', fontWeight: 600 }}>
                {searchParams.get('user_id')}
              </span> 的笔记中
            </span>
          </div>

          {/* 操作按钮 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
            <Button
              onClick={() => {
                setSaveModalVisible(false);
                saveForm.resetFields();
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
              loading={saveLoading}
              icon={<SaveOutlined />}
              style={{
                background: '#722ed1',
                border: 'none',
                fontWeight: 600
              }}
            >
              保存笔记
            </Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default ShareNote; 
