import time
import uuid
import json
import os
import threading
from datetime import datetime, timedelta

class UserTradeService:
    """
    用户交易服务，包括账户初始化、持仓、下单、订单历史、撤单、手续费、交易笔记等功能。
    所有数据持久化到本地文件。
    """
    DATA_FILE = 'user_trade_data.json'
    TRADE_NOTES_FILE = 'user_trade_notes.json'
    _lock = threading.Lock()

    def __init__(self):
        self.user_accounts = {}
        self.order_history = {}
        self.trade_notes = {}  # 新增：交易笔记数据
        self._load()

    def _save(self):
        data = {
            'user_accounts': self.user_accounts,
            'order_history': self.order_history
        }
        tmp_file = self.DATA_FILE + '.tmp'
        try:
            with self._lock:
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_file, self.DATA_FILE)
        except Exception as e:
            print(f'[UserTradeService] 写入数据文件失败: {e}')

    def _save_notes(self):
        """保存交易笔记数据"""
        tmp_file = self.TRADE_NOTES_FILE + '.tmp'
        try:
            with self._lock:
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.trade_notes, f, ensure_ascii=False, indent=2)
                os.replace(tmp_file, self.TRADE_NOTES_FILE)
        except Exception as e:
            print(f'[UserTradeService] 写入交易笔记文件失败: {e}')

    def _load(self):
        if os.path.exists(self.DATA_FILE):
            try:
                with self._lock:
                    with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.user_accounts = data.get('user_accounts', {})
                        self.order_history = data.get('order_history', {})
            except Exception as e:
                print(f'[UserTradeService] 读取数据文件失败: {e}')
                self.user_accounts = {}
                self.order_history = {}

        # 加载交易笔记数据
        if os.path.exists(self.TRADE_NOTES_FILE):
            try:
                with self._lock:
                    with open(self.TRADE_NOTES_FILE, 'r', encoding='utf-8') as f:
                        self.trade_notes = json.load(f)
            except Exception as e:
                print(f'[UserTradeService] 读取交易笔记文件失败: {e}')
                self.trade_notes = {}

    def get_market_state(self, market):
        """
        按市场查询交易状态
        :param market: 市场代码，如 'SH', 'SZ', 'HK', 'US' 等
        :return: 市场状态信息
        """
        try:
            # 导入 futu 相关模块
            from futu import OpenQuoteContext, RET_OK
            
            # 创建行情上下文
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            
            # 获取全局状态
            ret, data = quote_ctx.get_global_state()
            
            # 关闭连接
            quote_ctx.close()
            
            if ret != RET_OK:
                return {
                    "success": False,
                    "msg": f"获取市场状态失败: {data}",
                    "market": market,
                    "state": None
                }
            
            # 根据市场代码获取对应状态
            market_state_map = {
                'SH': data.get('market_sh'),
                'SZ': data.get('market_sz'), 
                'HK': data.get('market_hk'),
                'US': data.get('market_us'),
                'HKFUTURE': data.get('market_hkfuture'),
                'USFUTURE': data.get('market_usfuture'),
                'SGFUTURE': data.get('market_sgfuture'),
                'JPFUTURE': data.get('market_jpfuture')
            }
            
            state = market_state_map.get(market.upper())
            if state is None:
                return {
                    "success": False,
                    "msg": f"不支持的市场代码: {market}",
                    "market": market,
                    "state": None
                }
            
            # 市场状态说明
            state_desc_map = {
                'UNKNOWN': '未知状态',
                'AUCTION': '竞价阶段',
                'MORNING': '早盘交易',
                'REST': '休市',
                'AFTERNOON': '午盘交易',
                'CLOSED': '已收盘',
                'PRE_MORNING': '早盘前',
                'PRE_AFTERNOON': '午盘前',
                'END': '收盘后',
                'NIGHT_OPEN': '夜盘开盘',
                'NIGHT_END': '夜盘收盘',
                'FUTURE_DAY_OPEN': '期货日盘开盘',
                'FUTURE_DAY_CLOSE': '期货日盘收盘',
                'FUTURE_NIGHT_OPEN': '期货夜盘开盘',
                'FUTURE_NIGHT_CLOSE': '期货夜盘收盘',
                'FUTURE_OPEN': '期货开盘',
                'FUTURE_CLOSE': '期货收盘',
                'FUTURE_BREAK': '期货休市',
                'FUTURE_DAY_BREAK': '期货日盘休市',
                'FUTURE_NIGHT_BREAK': '期货夜盘休市',
                'AFTER_HOURS_BEGIN': '盘后开始',
                'AFTER_HOURS_END': '盘后结束',
                'AFTER_HOURS_END': '盘后结束'
            }
            
            return {
                "success": True,
                "msg": "获取市场状态成功",
                "market": market.upper(),
                "state": state,
                "state_desc": state_desc_map.get(state, '未知状态'),
                "global_state": data
            }
            
        except ImportError:
            return {
                "success": False,
                "msg": "futu 模块未安装，请先安装 futu-api",
                "market": market,
                "state": None
            }
        except Exception as e:
            return {
                "success": False,
                "msg": f"获取市场状态异常: {str(e)}",
                "market": market,
                "state": None
            }

    def get_ipo_list(self, market):
        """
        获取指定市场的IPO信息
        :param market: 市场代码，如 'SH', 'SZ', 'HK', 'US' 等
        :return: IPO信息列表
        """
        try:
            # 导入 futu 相关模块
            from futu import OpenQuoteContext, RET_OK, Market
            
            # 市场代码映射
            market_map = {
                'SH': Market.SH_MARKET,
                'SZ': Market.SZ_MARKET,
                'HK': Market.HK_MARKET,
                'US': Market.US_MARKET
            }
            
            futu_market = market_map.get(market.upper())
            if futu_market is None:
                return {
                    "success": False,
                    "msg": f"不支持的市场代码: {market}",
                    "market": market,
                    "ipo_list": []
                }
            
            # 创建行情上下文
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            
            # 获取IPO列表
            ret, data = quote_ctx.get_ipo_list(futu_market)
            
            # 关闭连接
            quote_ctx.close()
            
            if ret != RET_OK:
                return {
                    "success": False,
                    "msg": f"获取IPO信息失败: {data}",
                    "market": market,
                    "ipo_list": []
                }
            
            # 转换DataFrame为字典列表
            ipo_list = []
            if not data.empty:
                for _, row in data.iterrows():
                    ipo_item = {
                        "code": row.get('code', ''),
                        "name": row.get('name', ''),
                        "list_time": row.get('list_time', ''),
                        "list_timestamp": row.get('list_timestamp', 0),
                        "apply_code": row.get('apply_code', ''),
                        "issue_size": row.get('issue_size', 0),
                        "online_issue_size": row.get('online_issue_size', 0),
                        "apply_upper_limit": row.get('apply_upper_limit', 0),
                        "apply_limit_market_value": row.get('apply_limit_market_value', 0),
                        "is_estimate_ipo_price": row.get('is_estimate_ipo_price', False),
                        "ipo_price": row.get('ipo_price', 0.0),
                        "industry_pe_rate": row.get('industry_pe_rate', 0.0),
                        "is_estimate_winning_ratio": row.get('is_estimate_winning_ratio', False),
                        "winning_ratio": row.get('winning_ratio', 0.0),
                        "issue_pe_rate": row.get('issue_pe_rate', 0.0),
                        "apply_time": row.get('apply_time', ''),
                        "apply_timestamp": row.get('apply_timestamp', 0),
                        "winning_time": row.get('winning_time', ''),
                        "winning_timestamp": row.get('winning_timestamp', 0),
                        "is_has_won": row.get('is_has_won', False),
                        "winning_num_data": row.get('winning_num_data', ''),
                        "ipo_price_min": row.get('ipo_price_min', 0.0),
                        "ipo_price_max": row.get('ipo_price_max', 0.0),
                        "list_price": row.get('list_price', 0.0),
                        "lot_size": row.get('lot_size', 0),
                        "entrance_price": row.get('entrance_price', 0.0),
                        "is_subscribe_status": row.get('is_subscribe_status', False),
                        "apply_end_time": row.get('apply_end_time', ''),
                        "apply_end_timestamp": row.get('apply_end_timestamp', 0)
                    }
                    ipo_list.append(ipo_item)
            
            return {
                "success": True,
                "msg": "获取IPO信息成功",
                "market": market.upper(),
                "ipo_list": ipo_list,
                "total_count": len(ipo_list)
            }
            
        except ImportError:
            return {
                "success": False,
                "msg": "futu 模块未安装，请先安装 futu-api",
                "market": market,
                "ipo_list": []
            }
        except Exception as e:
            return {
                "success": False,
                "msg": f"获取IPO信息异常: {str(e)}",
                "market": market,
                "ipo_list": []
            }

    def get_trading_days(self, market=None, start=None, end=None, code=None):
        """
        获取指定市场或指定标的的交易日历
        :param market: 市场代码，如 'SH', 'SZ', 'HK', 'US' 等
        :param start: 开始日期，格式：yyyy-MM-dd
        :param end: 结束日期，格式：yyyy-MM-dd
        :param code: 股票代码，如 'HK.00700'
        :return: 交易日历信息
        """
        try:
            # 导入 futu 相关模块
            from futu import OpenQuoteContext, RET_OK, TradeDateMarket
            
            # 市场代码映射 - 使用正确的枚举值
            market_map = {
                'SH': TradeDateMarket.CN,  # A股市场（包括沪市和深市）
                'SZ': TradeDateMarket.CN,  # A股市场（包括沪市和深市）
                'HK': TradeDateMarket.HK,  # 港股市场
                'US': TradeDateMarket.US,  # 美股市场
                'CN': TradeDateMarket.CN,  # A股市场
                'NT': TradeDateMarket.NT,  # 深（沪）股通
                'ST': TradeDateMarket.ST,  # 港股通（深、沪）
                'JP_FUTURE': TradeDateMarket.JP_FUTURE,  # 日本期货
                'SG_FUTURE': TradeDateMarket.SG_FUTURE   # 新加坡期货
            }
            
            futu_market = None
            if market:
                futu_market = market_map.get(market.upper())
                if futu_market is None:
                    return {
                        "success": False,
                        "msg": f"不支持的市场代码: {market}",
                        "market": market,
                        "trading_days": []
                    }
            
            # 创建行情上下文
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            
            # 获取交易日历
            if code:
                # 如果指定了股票代码，忽略市场参数
                ret, data = quote_ctx.request_trading_days(start=start, end=end, code=code)
            else:
                # 使用市场参数
                ret, data = quote_ctx.request_trading_days(market=futu_market, start=start, end=end)
            
            # 关闭连接
            quote_ctx.close()
            
            if ret != RET_OK:
                return {
                    "success": False,
                    "msg": f"获取交易日历失败: {data}",
                    "market": market,
                    "code": code,
                    "trading_days": []
                }
            
            # 转换交易日数据
            trading_days = []
            if data:
                for item in data:
                    trading_day = {
                        "time": item.get('time', ''),
                        "timestamp": item.get('timestamp', 0),
                        "trade_date_type": item.get('trade_date_type', ''),
                        "trade_date_type_desc": self._get_trade_date_type_desc(item.get('trade_date_type', ''))
                    }
                    trading_days.append(trading_day)
            
            return {
                "success": True,
                "msg": "获取交易日历成功",
                "market": market.upper() if market else None,
                "code": code,
                "start": start,
                "end": end,
                "trading_days": trading_days,
                "total_count": len(trading_days)
            }
            
        except ImportError:
            return {
                "success": False,
                "msg": "futu 模块未安装，请先安装 futu-api",
                "market": market,
                "code": code,
                "trading_days": []
            }
        except Exception as e:
            return {
                "success": False,
                "msg": f"获取交易日历异常: {str(e)}",
                "market": market,
                "code": code,
                "trading_days": []
            }

    def _get_trade_date_type_desc(self, trade_date_type):
        """
        获取交易日类型描述
        :param trade_date_type: 交易日类型
        :return: 类型描述
        """
        type_desc_map = {
            'WHOLE': '全天交易',
            'MORNING': '上午交易',
            'AFTERNOON': '下午交易',
            'NIGHT': '夜盘交易',
            'NIGHT_OPEN': '夜盘开盘',
            'NIGHT_END': '夜盘收盘',
            'FUTURE_DAY_OPEN': '期货日盘开盘',
            'FUTURE_DAY_CLOSE': '期货日盘收盘',
            'FUTURE_NIGHT_OPEN': '期货夜盘开盘',
            'FUTURE_NIGHT_CLOSE': '期货夜盘收盘',
            'FUTURE_OPEN': '期货开盘',
            'FUTURE_CLOSE': '期货收盘',
            'FUTURE_BREAK': '期货休市',
            'FUTURE_DAY_BREAK': '期货日盘休市',
            'FUTURE_NIGHT_BREAK': '期货夜盘休市'
        }
        return type_desc_map.get(trade_date_type, '未知类型')

    # ==================== 交易笔记功能 ====================

    def create_trade_note(self, user_id, note_data):
        """
        创建交易笔记
        :param user_id: 用户ID
        :param note_data: 笔记数据
        :return: 创建结果
        """
        try:
            if user_id not in self.trade_notes:
                self.trade_notes[user_id] = []

            title = note_data.get('title', '')
            stock_code = note_data.get('stock_code', '')
            
            # 检查是否已存在相同title和stock_code的记录
            existing_note = None
            existing_index = -1
            
            for i, note in enumerate(self.trade_notes[user_id]):
                if (note.get('title') == title and 
                    note.get('stock_code') == stock_code and
                    note.get('status') != 'deleted'):
                    existing_note = note
                    existing_index = i
                    break
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if existing_note:
                # 更新现有记录
                existing_note.update({
                    'content': note_data.get('content', existing_note.get('content', '')),
                    'category': note_data.get('category', existing_note.get('category', '其他')),
                    'tags': note_data.get('tags', existing_note.get('tags', [])),
                    'stock_name': note_data.get('stock_name', existing_note.get('stock_name', '')),
                    'trade_type': note_data.get('trade_type', existing_note.get('trade_type', '')),
                    'trade_price': note_data.get('trade_price', existing_note.get('trade_price', 0.0)),
                    'trade_amount': note_data.get('trade_amount', existing_note.get('trade_amount', 0)),
                    'trade_reason': note_data.get('trade_reason', existing_note.get('trade_reason', '')),
                    'trade_result': note_data.get('trade_result', existing_note.get('trade_result', '')),
                    'profit_loss': note_data.get('profit_loss', existing_note.get('profit_loss', 0.0)),
                    'profit_loss_rate': note_data.get('profit_loss_rate', existing_note.get('profit_loss_rate', 0.0)),
                    'mood': note_data.get('mood', existing_note.get('mood', '')),
                    'lessons': note_data.get('lessons', existing_note.get('lessons', '')),
                    'next_plan': note_data.get('next_plan', existing_note.get('next_plan', '')),
                    'risk_level': note_data.get('risk_level', existing_note.get('risk_level', '中等')),
                    'updated_time': current_time,
                    'is_important': note_data.get('is_important', existing_note.get('is_important', False)),
                    'is_public': note_data.get('is_public', existing_note.get('is_public', False)),
                    'attachments': note_data.get('attachments', existing_note.get('attachments', [])),
                    'weather': note_data.get('weather', existing_note.get('weather', '')),
                    'market_sentiment': note_data.get('market_sentiment', existing_note.get('market_sentiment', '')),
                    'technical_indicators': note_data.get('technical_indicators', existing_note.get('technical_indicators', {})),
                    'fundamental_analysis': note_data.get('fundamental_analysis', existing_note.get('fundamental_analysis', '')),
                    'news_events': note_data.get('news_events', existing_note.get('news_events', [])),
                    'follow_up_date': note_data.get('follow_up_date', existing_note.get('follow_up_date', '')),
                    'status': note_data.get('status', existing_note.get('status', 'active'))
                })
                
                # 更新列表中的记录
                self.trade_notes[user_id][existing_index] = existing_note
                self._save_notes()

                return {
                    "success": True,
                    "msg": "交易笔记更新成功",
                    "note_id": existing_note['id'],
                    "note": existing_note,
                    "is_updated": True
                }
            else:
                # 创建新记录
                note_id = str(uuid.uuid4())
                
                note = {
                    'id': note_id,
                    'title': title,
                    'content': note_data.get('content', ''),
                    'category': note_data.get('category', '其他'),
                    'tags': note_data.get('tags', []),
                    'stock_code': stock_code,
                    'stock_name': note_data.get('stock_name', ''),
                    'trade_type': note_data.get('trade_type', ''),  # 买入/卖出/观察
                    'trade_price': note_data.get('trade_price', 0.0),
                    'trade_amount': note_data.get('trade_amount', 0),
                    'trade_reason': note_data.get('trade_reason', ''),
                    'trade_result': note_data.get('trade_result', ''),  # 盈利/亏损/持平
                    'profit_loss': note_data.get('profit_loss', 0.0),
                    'profit_loss_rate': note_data.get('profit_loss_rate', 0.0),
                    'mood': note_data.get('mood', ''),  # 心情：兴奋/沮丧/平静/紧张
                    'lessons': note_data.get('lessons', ''),  # 经验教训
                    'next_plan': note_data.get('next_plan', ''),  # 下次计划
                    'risk_level': note_data.get('risk_level', '中等'),  # 风险等级：低/中/高
                    'created_time': current_time,
                    'updated_time': current_time,
                    'is_important': note_data.get('is_important', False),
                    'is_public': note_data.get('is_public', False),  # 是否公开分享
                    'attachments': note_data.get('attachments', []),  # 附件（图片链接等）
                    'weather': note_data.get('weather', ''),  # 记录交易时的天气
                    'market_sentiment': note_data.get('market_sentiment', ''),  # 市场情绪
                    'technical_indicators': note_data.get('technical_indicators', {}),  # 技术指标
                    'fundamental_analysis': note_data.get('fundamental_analysis', ''),  # 基本面分析
                    'news_events': note_data.get('news_events', []),  # 相关新闻事件
                    'follow_up_date': note_data.get('follow_up_date', ''),  # 跟进日期
                    'status': note_data.get('status', 'active')  # 状态：active/archived/deleted
                }

                self.trade_notes[user_id].append(note)
                self._save_notes()

                return {
                    "success": True,
                    "msg": "交易笔记创建成功",
                    "note_id": note_id,
                    "note": note,
                    "is_updated": False
                }

        except Exception as e:
            return {
                "success": False,
                "msg": f"创建交易笔记失败: {str(e)}",
                "note_id": None
            }

    def get_trade_notes(self, user_id, filters=None, page=1, page_size=20):
        """
        获取用户的交易笔记列表
        :param user_id: 用户ID
        :param filters: 过滤条件
        :param page: 页码
        :param page_size: 每页数量
        :return: 笔记列表
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": True,
                    "msg": "暂无交易笔记",
                    "notes": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size
                }

            notes = self.trade_notes[user_id].copy()

            # 应用过滤条件
            if filters:
                if filters.get('category'):
                    notes = [n for n in notes if n.get('category') == filters['category']]
                
                if filters.get('stock_code'):
                    notes = [n for n in notes if n.get('stock_code') == filters['stock_code']]
                
                if filters.get('trade_type'):
                    notes = [n for n in notes if n.get('trade_type') == filters['trade_type']]
                
                if filters.get('trade_result'):
                    notes = [n for n in notes if n.get('trade_result') == filters['trade_result']]
                
                if filters.get('mood'):
                    notes = [n for n in notes if n.get('mood') == filters['mood']]
                
                if filters.get('is_important') is not None:
                    notes = [n for n in notes if n.get('is_important') == filters['is_important']]
                
                if filters.get('status'):
                    notes = [n for n in notes if n.get('status') == filters['status']]
                
                if filters.get('date_from'):
                    notes = [n for n in notes if n.get('created_time', '') >= filters['date_from']]
                
                if filters.get('date_to'):
                    notes = [n for n in notes if n.get('created_time', '') <= filters['date_to']]
                
                if filters.get('search_text'):
                    search_text = filters['search_text'].lower()
                    notes = [n for n in notes if 
                            search_text in n.get('title', '').lower() or
                            search_text in n.get('content', '').lower() or
                            search_text in n.get('stock_name', '').lower() or
                            search_text in n.get('trade_reason', '').lower()]
                
                if filters.get('tags'):
                    # 支持标签过滤，只要笔记包含任一指定标签即可
                    filter_tags = filters['tags'] if isinstance(filters['tags'], list) else [filters['tags']]
                    def has_matching_tag(note):
                        note_tags = note.get('tags') or []
                        return any(tag in note_tags for tag in filter_tags)
                    notes = [n for n in notes if has_matching_tag(n)]

            # 按时间倒序排序
            notes.sort(key=lambda x: x.get('created_time', ''), reverse=True)

            # 分页
            total = len(notes)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_notes = notes[start_idx:end_idx]

            return {
                "success": True,
                "msg": "获取交易笔记成功",
                "notes": paginated_notes,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"获取交易笔记失败: {str(e)}",
                "notes": [],
                "total": 0
            }

    def get_trade_note(self, user_id, note_id):
        """
        获取单个交易笔记详情
        :param user_id: 用户ID
        :param note_id: 笔记ID
        :return: 笔记详情
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": False,
                    "msg": "用户不存在",
                    "note": None
                }

            for note in self.trade_notes[user_id]:
                if note.get('id') == note_id:
                    return {
                        "success": True,
                        "msg": "获取笔记详情成功",
                        "note": note
                    }

            return {
                "success": False,
                "msg": "笔记不存在",
                "note": None
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"获取笔记详情失败: {str(e)}",
                "note": None
            }

    def update_trade_note(self, user_id, note_id, update_data):
        """
        更新交易笔记
        :param user_id: 用户ID
        :param note_id: 笔记ID
        :param update_data: 更新数据
        :return: 更新结果
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": False,
                    "msg": "用户不存在"
                }

            for note in self.trade_notes[user_id]:
                if note.get('id') == note_id:
                    # 更新字段
                    for key, value in update_data.items():
                        if key in note:
                            note[key] = value
                    
                    # 更新修改时间
                    note['updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    self._save_notes()
                    
                    return {
                        "success": True,
                        "msg": "交易笔记更新成功",
                        "note": note
                    }

            return {
                "success": False,
                "msg": "笔记不存在"
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"更新交易笔记失败: {str(e)}"
            }

    def delete_trade_note(self, user_id, note_id):
        """
        删除交易笔记
        :param user_id: 用户ID
        :param note_id: 笔记ID
        :return: 删除结果
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": False,
                    "msg": "用户不存在"
                }

            for i, note in enumerate(self.trade_notes[user_id]):
                if note.get('id') == note_id:
                    deleted_note = self.trade_notes[user_id].pop(i)
                    self._save_notes()
                    
                    return {
                        "success": True,
                        "msg": "交易笔记删除成功",
                        "deleted_note": deleted_note
                    }

            return {
                "success": False,
                "msg": "笔记不存在"
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"删除交易笔记失败: {str(e)}"
            }

    def get_trade_note_statistics(self, user_id):
        """
        获取交易笔记统计信息
        :param user_id: 用户ID
        :return: 统计信息
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": True,
                    "msg": "暂无交易笔记",
                    "statistics": {
                        "total_notes": 0,
                        "total_profit": 0.0,
                        "total_loss": 0.0,
                        "win_rate": 0.0,
                        "category_stats": {},
                        "stock_stats": {},
                        "mood_stats": {},
                        "monthly_stats": {}
                    }
                }

            notes = self.trade_notes[user_id]
            active_notes = [n for n in notes if n.get('status') == 'active']

            # 基础统计
            total_notes = len(active_notes)
            total_profit = sum(n.get('profit_loss', 0) for n in active_notes if n.get('profit_loss', 0) > 0)
            total_loss = sum(n.get('profit_loss', 0) for n in active_notes if n.get('profit_loss', 0) < 0)
            
            # 胜率计算
            profitable_notes = [n for n in active_notes if n.get('profit_loss', 0) > 0]
            win_rate = len(profitable_notes) / len(active_notes) * 100 if active_notes else 0

            # 分类统计
            category_stats = {}
            for note in active_notes:
                category = note.get('category', '其他')
                if category not in category_stats:
                    category_stats[category] = {'count': 0, 'profit': 0.0}
                category_stats[category]['count'] += 1
                category_stats[category]['profit'] += note.get('profit_loss', 0)

            # 股票统计
            stock_stats = {}
            for note in active_notes:
                stock_code = note.get('stock_code', '')
                if stock_code:
                    if stock_code not in stock_stats:
                        stock_stats[stock_code] = {
                            'count': 0, 
                            'profit': 0.0, 
                            'stock_name': note.get('stock_name', '')
                        }
                    stock_stats[stock_code]['count'] += 1
                    stock_stats[stock_code]['profit'] += note.get('profit_loss', 0)

            # 心情统计
            mood_stats = {}
            for note in active_notes:
                mood = note.get('mood', '未知')
                if mood not in mood_stats:
                    mood_stats[mood] = {'count': 0, 'profit': 0.0}
                mood_stats[mood]['count'] += 1
                mood_stats[mood]['profit'] += note.get('profit_loss', 0)

            # 月度统计
            monthly_stats = {}
            for note in active_notes:
                created_time = note.get('created_time', '')
                if created_time:
                    month = created_time[:7]  # YYYY-MM
                    if month not in monthly_stats:
                        monthly_stats[month] = {'count': 0, 'profit': 0.0}
                    monthly_stats[month]['count'] += 1
                    monthly_stats[month]['profit'] += note.get('profit_loss', 0)

            return {
                "success": True,
                "msg": "获取统计信息成功",
                "statistics": {
                    "total_notes": total_notes,
                    "total_profit": round(total_profit, 2),
                    "total_loss": round(total_loss, 2),
                    "net_profit": round(total_profit + total_loss, 2),
                    "win_rate": round(win_rate, 2),
                    "category_stats": category_stats,
                    "stock_stats": stock_stats,
                    "mood_stats": mood_stats,
                    "monthly_stats": monthly_stats
                }
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"获取统计信息失败: {str(e)}",
                "statistics": {}
            }

    def get_trade_note_categories(self, user_id):
        """
        获取用户笔记分类列表
        :param user_id: 用户ID
        :return: 分类列表
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": True,
                    "msg": "暂无分类",
                    "categories": []
                }

            categories = set()
            for note in self.trade_notes[user_id]:
                if note.get('status') == 'active':
                    categories.add(note.get('category', '其他'))

            return {
                "success": True,
                "msg": "获取分类成功",
                "categories": list(categories)
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"获取分类失败: {str(e)}",
                "categories": []
            }

    def get_trade_note_tags(self, user_id):
        """
        获取用户笔记标签列表
        :param user_id: 用户ID
        :return: 标签列表
        """
        try:
            if user_id not in self.trade_notes:
                return {
                    "success": True,
                    "msg": "暂无标签",
                    "tags": []
                }

            all_tags = []
            for note in self.trade_notes[user_id]:
                if note.get('status') == 'active':
                    all_tags.extend(note.get('tags', []))

            # 统计标签使用次数
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            return {
                "success": True,
                "msg": "获取标签成功",
                "tags": [{"tag": tag, "count": count} for tag, count in tag_counts.items()]
            }

        except Exception as e:
            return {
                "success": False,
                "msg": f"获取标签失败: {str(e)}",
                "tags": []
            }

    def init_user_account(self, user_id, force_init=False):
        if not force_init and user_id in self.user_accounts:
            return {"success": False, "msg": "初始化失败，已有账户", "account": self.user_accounts[user_id]}
        self.user_accounts[user_id] = {
            "user_id": user_id,
            "cash": 1_000_000.0,
            "positions": {},
        }
        self.order_history[user_id] = []
        self._save()
        return {"success": True, "msg": "初始化成功", "account": self.user_accounts[user_id]}

    def query_account(self, user_id):
        account = self.user_accounts.get(user_id)
        if not account:
            return {"success": False, "msg": "未找到账户", "account": None}
        # 计算总持仓盈亏和个股盈亏（基于快照现价和成本差价*数量）
        positions = account.get('positions', {})
        symbols = list(positions.keys())
        total_pnl = 0.0
        positions_pnl = {}
        total_market_value = 0.0
        positions_pnl_ratio = {}
        total_cost = 0.0
        positions_days = {}  # 新增：持仓天数字典
        if symbols:
            try:
                print(f"[UserTradeService] batch_market_snapshot symbols: {symbols}")
                from quant import batch_market_snapshot
                snap = batch_market_snapshot(symbols)
                print(f"[UserTradeService] batch_market_snapshot result: {snap}")
                def normalize_symbol(s):
                    if '.' in s:
                        code, market = s.split('.')
                        market = market.upper()
                        # 处理板块代码：保持原有格式
                        if code.startswith('LIST') or code.startswith('BK'):
                            return f"{market}.{code}"
                        elif market == 'HK' and code.isdigit():
                            return f"{market}.{code.zfill(5)}"
                        elif market == 'US':
                            return f"US.{code.upper()}"
                        else:
                            return f"{market}.{code}"
                    else:
                        return s
                # 新增：获取order_history
                order_history = self.order_history.get(user_id, [])
                now_date = datetime.now().date()
                for sym, pos in positions.items():
                    snap_data = snap.get(sym)
                    if not snap_data:
                        snap_data = snap.get(normalize_symbol(sym))
                    if not snap_data:
                        snap_data = {}
                    price = snap_data.get('current_price')
                    if price is None or price == '':
                        price = snap_data.get('last_price')
                    if price is None or price == '':
                        price = snap_data.get('prev_close_price')
                    if price is None or price == '':
                        price = 0.0
                    price = float(price)
                    cost = float(pos.get('cost', 0.0))
                    amount = int(pos.get('amount', 0))
                    print(f"[UserTradeService] symbol={sym}, price={price}, cost={cost}, amount={amount}")
                    # 卖出手续费（假设全部卖出时才产生）
                    sell_fee = price * amount * 0.0003 if amount > 0 else 0.0
                    pnl = (price - cost) * amount - sell_fee
                    positions_pnl[sym] = round(pnl, 2)
                    total_market_value += price * amount
                    total_cost += cost * amount
                    # 个股盈亏率
                    if cost * amount > 0:
                        positions_pnl_ratio[sym] = round(pnl / (cost * amount), 4)
                    else:
                        positions_pnl_ratio[sym] = None
                    # 计算持仓天数
                    min_buy_time = None
                    for order in order_history:
                        if order.get('symbol') == sym and order.get('side') == 'buy' and order.get('status') == 'filled':
                            order_time = order.get('created_at')
                            if order_time:
                                order_date = datetime.fromtimestamp(order_time).date()
                                if min_buy_time is None or order_date < min_buy_time:
                                    min_buy_time = order_date
                    if min_buy_time:
                        days = (now_date - min_buy_time).days + 1  # 持仓当天算一天
                        positions_days[sym] = days
                    else:
                        positions_days[sym] = None
            except Exception as e:
                print(f"[UserTradeService] Exception: {e}")
                positions_pnl = {sym: 0.0 for sym in symbols}
                positions_pnl_ratio = {sym: None for sym in symbols}
                total_market_value = 0.0
                total_cost = 0.0
                positions_days = {sym: None for sym in symbols}
        cash = float(account.get('cash', 0.0))
        initial_cash = 1000000.0
        total_asset = cash + total_market_value
        total_pnl = total_asset - initial_cash
        total_pnl_ratio = round(total_pnl / initial_cash, 4)
        return {
            "success": True,
            "msg": "查询成功",
            "account": account,
            "total_pnl": round(total_pnl, 2),
            "positions_pnl": positions_pnl,
            "total_pnl_ratio": total_pnl_ratio,
            "positions_pnl_ratio": positions_pnl_ratio,
            "total_asset": round(total_asset, 2),
            "initial_cash": initial_cash,
            "positions_days": positions_days  # 新增：返回持仓天数字典
        }

    def query_orders(self, user_id):
        return self.order_history.get(user_id, [])

    def query_orders_by_symbol(self, user_id, symbol=None):
        """
        查询用户的历史订单，可选按股票代码过滤
        :param user_id: 用户ID
        :param symbol: 股票代码（如'00700.HK'），可选
        :return: 订单列表
        """
        orders = self.order_history.get(user_id, [])
        if symbol:
            return [order for order in orders if order.get('symbol') == symbol]
        return orders

    def order(self, user_id, symbol, price, amount, side, order_reason=None, order_reason_time=None):
        account = self.user_accounts.get(user_id)
        if not account:
            return {"success": False, "msg": "未找到账户", "account": account}
        try:
            price = float(price)
            amount = int(amount)
        except Exception:
            return {"success": False, "msg": "价格和数量格式错误", "account": account}
        if price <= 0 or amount <= 0 or not symbol or side not in ('buy', 'sell'):
            return {"success": False, "msg": "参数错误", "account": account}
        fee_rate = 0.0003
        order_id = str(uuid.uuid4())
        now = int(time.time())
        order = {
            "order_id": order_id,
            "user_id": user_id,
            "symbol": symbol,
            "price": price,
            "amount": amount,
            "side": side,
            "status": "filled",
            "created_at": now,
            "fee": 0.0,
            "order_reason": order_reason,
            "order_reason_time": order_reason_time
        }
        self.order_history.setdefault(user_id, [])
        account.setdefault('positions', {})
        if side == 'buy':
            cost = price * amount
            fee = round(cost * fee_rate, 2)
            total_cost = cost + fee
            if account.get('cash', 0) < total_cost or account.get('cash', 0) < 0:
                order['status'] = 'rejected'
                order['msg'] = '资金不足'
                self.order_history[user_id].append(order)
                self._save()
                return {"success": False, "msg": "资金不足", "account": account}
            pos = account['positions'].get(symbol, {"amount": 0, "cost": 0.0})
            total_amount = pos["amount"] + amount
            new_cost = (pos["cost"] * pos["amount"] + price * amount) / total_amount if total_amount > 0 else price
            account['positions'][symbol] = {"amount": total_amount, "cost": new_cost}
            account['cash'] = round(account.get('cash', 0) - total_cost, 2)
            order['fee'] = fee
            self.order_history[user_id].append(order)
            self._save()
            return {"success": True, "msg": f"买入{amount}股成功，手续费{fee}", "account": account, "order_id": order_id}
        elif side == 'sell':
            pos = account['positions'].get(symbol, {"amount": 0, "cost": 0.0})
            if pos["amount"] < amount or pos["amount"] <= 0:
                order['status'] = 'rejected'
                order['msg'] = '持仓不足，无法卖出'
                self.order_history[user_id].append(order)
                self._save()
                return {"success": False, "msg": "持仓不足，无法卖出", "account": account}
            fee = round(price * amount * fee_rate, 2)
            pos["amount"] -= amount
            account['cash'] = round(account.get('cash', 0) + price * amount - fee, 2)
            if pos["amount"] == 0:
                del account['positions'][symbol]
            else:
                account['positions'][symbol] = pos
            order['fee'] = fee
            self.order_history[user_id].append(order)
            self._save()
            return {"success": True, "msg": f"卖出{amount}股成功，手续费{fee}", "account": account, "order_id": order_id}
        else:
            order['status'] = 'rejected'
            order['msg'] = 'side参数需为buy或sell'
            self.order_history[user_id].append(order)
            self._save()
            return {"success": False, "msg": "side参数需为buy或sell", "account": account}

    def cancel_order(self, user_id, order_id):
        orders = self.order_history.get(user_id, [])
        for order in orders:
            if order['order_id'] == order_id:
                if order['status'] == 'filled':
                    return {"success": False, "msg": "订单已成交，无法撤单"}
                if order['status'] == 'cancelled':
                    return {"success": False, "msg": "订单已撤销"}
                order['status'] = 'cancelled'
                self._save()
                return {"success": True, "msg": "撤单成功"}
        return {"success": False, "msg": "未找到订单"}

# 单例
user_trade_service = UserTradeService() 
