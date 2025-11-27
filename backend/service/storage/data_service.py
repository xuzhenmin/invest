"""
数据服务层
提供数据的存储、更新和查询功能
"""

import json
from datetime import datetime
from typing import List, Optional, Any, Dict
from .database_manager import db_manager
from .models import (
    StockInfo, TradeRecord, Position, StrategySignal, 
    MarketData, TradeFailure, DiagnosisReport, PositionDetail, UserInfo,
    TABLE_DEFINITIONS, INDEX_DEFINITIONS
)

class DataService:
    """数据服务类"""
    
    def __init__(self):
        """初始化数据服务"""
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库表结构"""
        # 创建所有表
        for table_name, create_sql in TABLE_DEFINITIONS.items():
            db_manager.create_table(create_sql)
        
        # 创建索引
        for index_name, index_sql in INDEX_DEFINITIONS.items():
            db_manager.execute_update(index_sql)
    
    # Stock Info 相关操作
    def save_stock_info(self, stock_info: StockInfo) -> int:
        """保存股票基本信息
        
        Args:
            stock_info: 股票信息对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT OR REPLACE INTO stock_info (code, name, market, sector, industry, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            stock_info.code,
            stock_info.name,
            stock_info.market,
            stock_info.sector,
            stock_info.industry,
            datetime.now()
        )
        return db_manager.execute_update(query, params)
    
    def batch_save_stock_info(self, stock_list: List[StockInfo]) -> int:
        """批量保存股票信息
        
        Args:
            stock_list: 股票信息列表
            
        Returns:
            影响的行数
        """
        query = """
        INSERT OR REPLACE INTO stock_info (code, name, market, sector, industry, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (s.code, s.name, s.market, s.sector, s.industry, datetime.now())
            for s in stock_list
        ]
        return db_manager.execute_many(query, params_list)
    
    # Trade Record 相关操作
    def save_trade_record(self, trade_record: TradeRecord) -> int:
        """保存交易记录
        
        Args:
            trade_record: 交易记录对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT INTO trade_records (
            user_id, symbol, name, action, timestamp, trade_date, 
            price, quantity, total_cost, order_id, signal_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            trade_record.user_id,
            trade_record.symbol,
            trade_record.name,
            trade_record.action,
            trade_record.timestamp or datetime.now(),
            trade_record.trade_date or datetime.now(),
            trade_record.price,
            trade_record.quantity,
            trade_record.total_cost,
            trade_record.order_id,
            json.dumps(trade_record.signal_data) if trade_record.signal_data else None
        )
        return db_manager.execute_update(query, params)
    
    # Position 相关操作
    def save_position(self, position: Position) -> int:
        """保存持仓信息
        
        Args:
            position: 持仓信息对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT OR REPLACE INTO positions (
            user_id, symbol, name, quantity, avg_price,
            total_cost, market_value, floating_pnl, floating_pnl_ratio,
            last_price, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            position.user_id,
            position.symbol,
            position.name,
            position.quantity,
            position.avg_price,
            position.total_cost,
            position.market_value,
            position.floating_pnl,
            position.floating_pnl_ratio,
            position.last_price,
            datetime.now()
        )
        return db_manager.execute_update(query, params)
    
    def update_position_price(self, user_id: str, symbol: str, last_price: float) -> bool:
        """更新持仓股票最新价格
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            last_price: 最新价格
            
        Returns:
            是否更新成功
        """
        query = """
        UPDATE positions 
        SET last_price = ?, 
            market_value = quantity * ?,
            floating_pnl = (quantity * ?) - total_cost,
            floating_pnl_ratio = CASE 
                WHEN total_cost > 0 THEN ((quantity * ?) - total_cost) / total_cost * 100
                ELSE 0
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND symbol = ?
        """
        affected = db_manager.execute_update(query, (last_price, last_price, last_price, last_price, user_id, symbol))
        return affected > 0
    
    # Strategy Signal 相关操作
    def save_strategy_signal(self, signal: StrategySignal) -> int:
        """保存策略信号
        
        Args:
            signal: 策略信号对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT INTO strategy_signals (
            strategy_name, stock_code, signal_type, signal_strength,
            signal_date, parameters, executed
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            signal.strategy_name,
            signal.stock_code,
            signal.signal_type,
            signal.signal_strength,
            signal.signal_date or datetime.now(),
            json.dumps(signal.parameters) if signal.parameters else None,
            signal.executed
        )
        return db_manager.execute_update(query, params)
    
    def mark_signal_executed(self, signal_id: int) -> bool:
        """标记策略信号为已执行
        
        Args:
            signal_id: 信号ID
            
        Returns:
            是否更新成功
        """
        query = """
        UPDATE strategy_signals 
        SET executed = TRUE 
        WHERE id = ?
        """
        affected = db_manager.execute_update(query, (signal_id,))
        return affected > 0
    
    # Market Data 相关操作
    def save_market_data(self, market_data: MarketData) -> int:
        """保存市场数据
        
        Args:
            market_data: 市场数据对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT OR REPLACE INTO market_data (
            stock_code, trade_date, open_price, high_price, low_price,
            close_price, volume, turnover
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            market_data.stock_code,
            market_data.trade_date,
            market_data.open_price,
            market_data.high_price,
            market_data.low_price,
            market_data.close_price,
            market_data.volume,
            market_data.turnover
        )
        return db_manager.execute_update(query, params)
    
    def batch_save_market_data(self, data_list: List[MarketData]) -> int:
        """批量保存市场数据
        
        Args:
            data_list: 市场数据列表
            
        Returns:
            影响的行数
        """
        query = """
        INSERT OR REPLACE INTO market_data (
            stock_code, trade_date, open_price, high_price, low_price,
            close_price, volume, turnover
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (d.stock_code, d.trade_date, d.open_price, d.high_price, 
             d.low_price, d.close_price, d.volume, d.turnover)
            for d in data_list
        ]
        return db_manager.execute_many(query, params_list)
    
    def batch_save_positions(self, position_list: List[Position]) -> int:
        """批量保存持仓信息
        
        Args:
            position_list: 持仓信息列表
            
        Returns:
            影响的行数
        """
        query = """
        INSERT OR REPLACE INTO positions (
            user_id, symbol, name, quantity, avg_price, total_cost, market_value,
            floating_pnl, floating_pnl_ratio, last_price, updated_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (p.user_id, p.symbol, p.name, p.quantity, p.avg_price, p.total_cost,
             p.market_value, p.floating_pnl, p.floating_pnl_ratio, p.last_price,
             p.updated_at or datetime.now(), p.created_at or datetime.now())
            for p in position_list
        ]
        return db_manager.execute_many(query, params_list)
    
    # Trade Notes 相关操作
    # Trade Failure 相关操作
    def save_trade_failure(self, trade_failure: TradeFailure) -> int:
        """保存交易失败记录
        
        Args:
            trade_failure: 交易失败记录对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT INTO trade_failures (
            user_id, symbol, name, action, reason, timestamp, trade_date,
            signal_data, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            trade_failure.user_id,
            trade_failure.symbol,
            trade_failure.name,
            trade_failure.action,
            trade_failure.reason,
            trade_failure.timestamp or datetime.now(),
            trade_failure.trade_date or datetime.now(),
            json.dumps(trade_failure.signal_data) if trade_failure.signal_data else None,
            json.dumps(trade_failure.details) if trade_failure.details else None
        )
        return db_manager.execute_update(query, params)
    
    def batch_save_trade_failures(self, failure_list: List[TradeFailure]) -> int:
        """批量保存交易失败记录
        
        Args:
            failure_list: 交易失败记录列表
            
        Returns:
            影响的行数
        """
        query = """
        INSERT INTO trade_failures (
            user_id, symbol, name, action, reason, timestamp, trade_date,
            signal_data, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (f.user_id, f.symbol, f.name, f.action, f.reason, 
             f.timestamp or datetime.now(), f.trade_date or datetime.now(),
             json.dumps(f.signal_data) if f.signal_data else None,
             json.dumps(f.details) if f.details else None)
            for f in failure_list
        ]
        return db_manager.execute_many(query, params_list)
    
    # Diagnosis Report 相关操作
    def save_diagnosis_report(self, diagnosis_report: DiagnosisReport) -> int:
        """保存诊断报告
        
        Args:
            diagnosis_report: 诊断报告对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT OR REPLACE INTO diagnosis_reports (
            symbol, date, name, current_price, overall_score, fundamental_score,
            technical_score, capital_score, valuation_score, risk_level,
            recommendation, target_price, stop_loss, support, resistance,
            buy_price, sell_price, investment_reason, key_indicators, risk_warnings, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            diagnosis_report.symbol,
            diagnosis_report.date or datetime.now().date(),
            diagnosis_report.name,
            diagnosis_report.current_price,
            diagnosis_report.overall_score,
            diagnosis_report.fundamental_score,
            diagnosis_report.technical_score,
            diagnosis_report.capital_score,
            diagnosis_report.valuation_score,
            diagnosis_report.risk_level,
            diagnosis_report.recommendation,
            diagnosis_report.target_price,
            diagnosis_report.stop_loss,
            diagnosis_report.support,
            diagnosis_report.resistance,
            diagnosis_report.buy_price,
            diagnosis_report.sell_price,
            diagnosis_report.investment_reason,
            json.dumps(diagnosis_report.key_indicators) if diagnosis_report.key_indicators else None,
            json.dumps(diagnosis_report.risk_warnings) if diagnosis_report.risk_warnings else None,
            diagnosis_report.timestamp or datetime.now()
        )
        return db_manager.execute_update(query, params)
    
    def batch_save_diagnosis_reports(self, report_list: List[DiagnosisReport]) -> int:
        """批量保存诊断报告
        
        Args:
            report_list: 诊断报告列表
            
        Returns:
            影响的行数
        """
        query = """
        INSERT OR REPLACE INTO diagnosis_reports (
            symbol, date, name, current_price, overall_score, fundamental_score,
            technical_score, capital_score, valuation_score, risk_level,
            recommendation, target_price, stop_loss, support, resistance,
            buy_price, sell_price, investment_reason, key_indicators, risk_warnings, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (d.symbol, d.date or datetime.now().date(), d.name, d.current_price,
             d.overall_score, d.fundamental_score, d.technical_score, d.capital_score,
             d.valuation_score, d.risk_level, d.recommendation, d.target_price,
             d.stop_loss, d.support, d.resistance, d.buy_price, d.sell_price,
             d.investment_reason,
             json.dumps(d.key_indicators) if d.key_indicators else None,
             json.dumps(d.risk_warnings) if d.risk_warnings else None,
             d.timestamp or datetime.now())
            for d in report_list
        ]
        return db_manager.execute_many(query, params_list)
    
    def save_trade_note(self, stock_code: str, title: str, content: str, 
                       note_date: datetime = None, tags: List[str] = None) -> int:
        """保存交易笔记
        
        Args:
            stock_code: 股票代码
            title: 笔记标题
            content: 笔记内容
            note_date: 笔记日期
            tags: 标签列表
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT INTO trade_notes (stock_code, note_date, title, content, tags)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (
            stock_code,
            note_date or datetime.now(),
            title,
            content,
            ','.join(tags) if tags else None
        )
        return db_manager.execute_update(query, params)
    
    # Position Detail 相关操作
    def save_position_detail(self, position_detail: PositionDetail) -> int:
        """保存持仓明细记录
        
        Args:
            position_detail: 持仓明细对象
            
        Returns:
            插入的记录ID
        """
        query = """
        INSERT INTO position_details (
            user_id, symbol, name, original_quantity, remaining_quantity,
            buy_price, total_cost, buy_date, buy_order_id, diagnosis_data,
            target_price, stop_loss, support, resistance, sell_price, max_drawdown,
            status, sell_records, closed_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            position_detail.user_id,
            position_detail.symbol,
            position_detail.name,
            position_detail.original_quantity,
            position_detail.remaining_quantity,
            position_detail.buy_price,
            position_detail.total_cost,
            position_detail.buy_date or datetime.now(),
            position_detail.buy_order_id,
            json.dumps(position_detail.diagnosis_data) if position_detail.diagnosis_data else None,
            position_detail.target_price,
            position_detail.stop_loss,
            position_detail.support,
            position_detail.resistance,
            position_detail.sell_price,
            position_detail.max_drawdown,
            position_detail.status,
            json.dumps(position_detail.sell_records) if position_detail.sell_records else None,
            position_detail.closed_date,
            position_detail.created_at or datetime.now(),
            position_detail.updated_at or datetime.now()
        )
        return db_manager.execute_update(query, params)
    
    def batch_save_position_details(self, position_details: List[PositionDetail]) -> int:
        """批量保存持仓明细记录
        
        Args:
            position_details: 持仓明细对象列表
            
        Returns:
            影响的行数
        """
        query = """
        INSERT INTO position_details (
            user_id, symbol, name, original_quantity, remaining_quantity,
            buy_price, total_cost, buy_date, buy_order_id, diagnosis_data,
            target_price, stop_loss, support, resistance, sell_price, max_drawdown,
            status, sell_records, closed_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (d.user_id, d.symbol, d.name, d.original_quantity, d.remaining_quantity,
             d.buy_price, d.total_cost, d.buy_date or datetime.now(), d.buy_order_id,
             json.dumps(d.diagnosis_data) if d.diagnosis_data else None,
             d.target_price, d.stop_loss, d.support, d.resistance, d.sell_price,
             d.max_drawdown, d.status,
             json.dumps(d.sell_records) if d.sell_records else None,
             d.closed_date, d.created_at or datetime.now(), d.updated_at or datetime.now())
            for d in position_details
        ]
        return db_manager.execute_many(query, params_list)
    
    # Trade Record 删除操作
    def delete_trade_record_by_id(self, record_id: int) -> bool:
        """按ID删除交易记录
        
        Args:
            record_id: 交易记录ID
            
        Returns:
            是否删除成功
        """
        query = "DELETE FROM trade_records WHERE id = ?"
        affected = db_manager.execute_update(query, (record_id,))
        return affected > 0
    
    def delete_trade_records_by_user_id(self, user_id: str) -> int:
        """按用户ID删除所有交易记录
        
        Args:
            user_id: 用户ID
            
        Returns:
            删除的记录数量
        """
        query = "DELETE FROM trade_records WHERE user_id = ?"
        affected = db_manager.execute_update(query, (user_id,))
        return affected
    
    def delete_trade_records_by_symbol(self, user_id: str, symbol: str) -> int:
        """按用户ID和股票代码删除交易记录
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            
        Returns:
            删除的记录数量
        """
        query = "DELETE FROM trade_records WHERE user_id = ? AND symbol = ?"
        affected = db_manager.execute_update(query, (user_id, symbol))
        return affected
    
    def update_position_detail_status(self, position_id: int, status: str, 
                                    remaining_quantity: int = None,
                                    sell_records: Dict[str, Any] = None,
                                    closed_date: datetime = None) -> bool:
        """更新持仓明细状态
        
        Args:
            position_id: 持仓明细ID
            status: 新状态
            remaining_quantity: 剩余数量（可选）
            sell_records: 卖出记录（可选）
            closed_date: 清仓日期（可选）
            
        Returns:
            是否更新成功
        """
        query = """
        UPDATE position_details 
        SET status = ?, 
            updated_at = CURRENT_TIMESTAMP
        """
        params = [status]
        
        if remaining_quantity is not None:
            query += ", remaining_quantity = ?"
            params.append(remaining_quantity)
        
        if sell_records is not None:
            query += ", sell_records = ?"
            params.append(json.dumps(sell_records))
        
        if closed_date is not None:
            query += ", closed_date = ?"
            params.append(closed_date)
        
        query += " WHERE id = ?"
        params.append(position_id)
        
        affected = db_manager.execute_update(query, tuple(params))
        return affected > 0
    
    # User Info 相关操作
    def save_user_info(self, user_info: UserInfo) -> int:
        """保存用户信息（insert or update）
        
        如果用户已存在，则合并更新数据；如果不存在，则创建新用户
        
        Args:
            user_info: 用户信息对象
            
        Returns:
            影响的记录ID
        """
        try:
            # 首先检查用户是否存在
            check_query = "SELECT * FROM user_info WHERE user_id = ?"
            existing_user = db_manager.execute_query(check_query, (user_info.user_id,))
            
            if existing_user:
                # 用户已存在，合并更新数据
                existing_data = existing_user[0]
                
                # 合并数据：新数据优先，但保留旧数据中的非空值
                merged_data = {
                    'user_id': user_info.user_id,
                    'username': user_info.username or existing_data.get('username'),
                    'email': user_info.email or existing_data.get('email'),
                    'phone': user_info.phone or existing_data.get('phone'),
                    'initial_cash': user_info.initial_cash if user_info.initial_cash is not None else existing_data.get('initial_cash', 1000000.0),
                    'current_cash': user_info.current_cash if user_info.current_cash is not None else existing_data.get('current_cash', 1000000.0),
                    'total_assets': user_info.total_assets if user_info.total_assets is not None else existing_data.get('total_assets', 1000000.0),
                    'total_profit': user_info.total_profit if user_info.total_profit is not None else existing_data.get('total_profit', 0.0),
                    'total_profit_ratio': user_info.total_profit_ratio if user_info.total_profit_ratio is not None else existing_data.get('total_profit_ratio', 0.0),
                    'trade_count': user_info.trade_count if user_info.trade_count is not None else existing_data.get('trade_count', 0),
                    'fee_rate': user_info.fee_rate if user_info.fee_rate is not None else existing_data.get('fee_rate', 0.0003),
                    'status': user_info.status or existing_data.get('status', 'active'),
                    'quant_stocks': user_info.quant_stocks if user_info.quant_stocks is not None else json.loads(existing_data.get('quant_stocks', '[]') or '[]'),
                    'quant_enabled': user_info.quant_enabled if user_info.quant_enabled is not None else existing_data.get('quant_enabled', False),
                    'updated_at': datetime.now()
                }
                
                # 执行更新
                update_query = """
                UPDATE user_info SET
                    username = ?,
                    email = ?,
                    phone = ?,
                    initial_cash = ?,
                    current_cash = ?,
                    total_assets = ?,
                    total_profit = ?,
                    total_profit_ratio = ?,
                    trade_count = ?,
                    fee_rate = ?,
                    status = ?,
                    quant_stocks = ?,
                    quant_enabled = ?,
                    updated_at = ?
                WHERE user_id = ?
                """
                params = (
                    merged_data['username'],
                    merged_data['email'],
                    merged_data['phone'],
                    merged_data['initial_cash'],
                    merged_data['current_cash'],
                    merged_data['total_assets'],
                    merged_data['total_profit'],
                    merged_data['total_profit_ratio'],
                    merged_data['trade_count'],
                    merged_data['fee_rate'],
                    merged_data['status'],
                    json.dumps(merged_data['quant_stocks']),
                    merged_data['quant_enabled'],
                    merged_data['updated_at'],
                    user_info.user_id
                )
                
                affected = db_manager.execute_update(update_query, params)
                print(f"用户信息更新完成: 用户 {user_info.user_id}, 影响行数: {affected}")
                return affected
                
            else:
                # 用户不存在，创建新用户
                insert_query = """
                INSERT INTO user_info (
                    user_id, username, email, phone, initial_cash, current_cash,
                    total_assets, total_profit, total_profit_ratio, trade_count,
                    fee_rate, status, quant_stocks, quant_enabled, updated_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    user_info.user_id,
                    user_info.username or user_info.user_id,  # 默认用户名为user_id
                    user_info.email,
                    user_info.phone,
                    user_info.initial_cash or 1000000.0,
                    user_info.current_cash or 1000000.0,
                    user_info.total_assets or 1000000.0,
                    user_info.total_profit or 0.0,
                    user_info.total_profit_ratio or 0.0,
                    user_info.trade_count or 0,
                    user_info.fee_rate or 0.0003,
                    user_info.status or 'active',
                    json.dumps(user_info.quant_stocks) if user_info.quant_stocks else None,
                    user_info.quant_enabled or False,
                    datetime.now(),
                    datetime.now()
                )
                
                new_id = db_manager.execute_update(insert_query, params)
                print(f"新用户创建完成: 用户 {user_info.user_id}, 记录ID: {new_id}")
                return new_id
                
        except Exception as e:
            print(f"保存用户信息失败: {e}")
            return 0
    
    def update_user_account(self, user_id: str, **kwargs) -> bool:
        """更新用户账户信息（通用方法）
        
        Args:
            user_id: 用户ID
            **kwargs: 要更新的字段，支持：
                current_cash: 当前可用资金
                total_assets: 总资产
                total_profit: 总盈亏
                total_profit_ratio: 总盈亏比例
                trade_count: 交易次数（绝对值）
                trade_count_increment: 交易次数增量（相对值）
                initial_cash: 初始资金
                fee_rate: 手续费率
                
        Returns:
            是否更新成功
        """
        if not kwargs:
            return False
            
        query = "UPDATE user_info SET updated_at = CURRENT_TIMESTAMP"
        params = []
        
        # 处理交易次数增量
        if 'trade_count_increment' in kwargs:
            query += ", trade_count = trade_count + ?"
            params.append(kwargs['trade_count_increment'])
            del kwargs['trade_count_increment']
        
        # 处理其他字段
        valid_fields = {
            'current_cash', 'total_assets', 'total_profit', 
            'total_profit_ratio', 'trade_count', 'initial_cash', 'fee_rate'
        }
        
        for field, value in kwargs.items():
            if field in valid_fields:
                query += f", {field} = ?"
                params.append(value)
        
        query += " WHERE user_id = ?"
        params.append(user_id)
        
        affected = db_manager.execute_update(query, tuple(params))
        return affected > 0
    
    def update_user_quant_settings(self, user_id: str, quant_enabled: bool = None, 
                                 quant_stocks: List[str] = None) -> bool:
        """根据用户ID更新或插入用户量化股票列表和是否开启量化交易
        
        Args:
            user_id: 用户ID
            quant_enabled: 是否开启量化交易（可选），True为开启，False为关闭
            quant_stocks: 量化股票列表（可选），格式为股票代码列表：
                         ["300059.SZ", "300124.SZ", "000001.SZ"]
            
        Returns:
            是否操作成功
            
        Examples:
            # 只更新是否开启量化交易
            update_user_quant_settings("user123", quant_enabled=True)
            
            # 只更新量化股票列表
            update_user_quant_settings("user123", quant_stocks=["300059.SZ", "300124.SZ"])
            
            # 同时更新两者
            update_user_quant_settings("user123", quant_enabled=True, quant_stocks=["300059.SZ", "300124.SZ"])
            
            # 用户不存在时自动创建
            update_user_quant_settings("new_user", quant_enabled=True, quant_stocks=["300059.SZ"])
        """
        if quant_enabled is None and quant_stocks is None:
            return False
            
        # 检查用户是否存在
        check_query = "SELECT user_id FROM user_info WHERE user_id = ?"
        existing_user = db_manager.execute_query(check_query, (user_id,))
        
        if existing_user:
            # 用户存在，执行更新
            query = "UPDATE user_info SET updated_at = CURRENT_TIMESTAMP"
            params = []
            
            if quant_enabled is not None:
                query += ", quant_enabled = ?"
                params.append(quant_enabled)
            
            if quant_stocks is not None:
                query += ", quant_stocks = ?"
                params.append(json.dumps(quant_stocks))
            
            query += " WHERE user_id = ?"
            params.append(user_id)
            
            affected = db_manager.execute_update(query, tuple(params))
            return affected > 0
        else:
            # 用户不存在，执行插入
            query = """
            INSERT INTO user_info (
                user_id, username, email, phone, initial_cash, current_cash,
                total_assets, total_profit, total_profit_ratio, trade_count,
                fee_rate, status, quant_stocks, quant_enabled, updated_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                user_id,
                user_id,  # 默认用户名为user_id
                None,     # email
                None,     # phone
                0,        # initial_cash
                0,        # current_cash
                0,        # total_assets
                0,        # total_profit
                0,        # total_profit_ratio
                0,        # trade_count
                0.0003,   # 默认手续费率
                'active', # status
                json.dumps(quant_stocks) if quant_stocks is not None else None,
                quant_enabled if quant_enabled is not None else False,
                datetime.now(),
                datetime.now()
            )
            
            try:
                db_manager.execute_update(query, params)
                return True
            except Exception as e:
                print(f"插入用户信息失败: {e}")
                return False
    
    def increment_user_trade_count(self, user_id: str, increment: int = 1) -> bool:
        """增加用户交易次数
        
        Args:
            user_id: 用户ID
            increment: 增加的数量，默认为1
            
        Returns:
            是否更新成功
        """
        query = """
        UPDATE user_info 
        SET trade_count = trade_count + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """
        affected = db_manager.execute_update(query, (increment, user_id))
        return affected > 0

# 全局数据服务实例
data_service = DataService()
