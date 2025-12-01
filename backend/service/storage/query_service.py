"""
查询服务层
提供各种查询功能
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from .database_manager import db_manager
from .models import StockInfo, TradeRecord, Position, StrategySignal, MarketData, TradeFailure, DiagnosisReport, UserInfo

class QueryService:
    """查询服务类"""
    
    # Stock Info 查询
    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票基本信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票信息字典
        """
        query = "SELECT * FROM stock_info WHERE code = ?"
        result = db_manager.execute_query(query, (stock_code,))
        return result[0] if result else None
    
    def get_all_stocks(self, market: str = None) -> List[Dict[str, Any]]:
        """获取所有股票信息
        
        Args:
            market: 市场代码，如'HK', 'SH', 'SZ'
            
        Returns:
            股票信息列表
        """
        if market:
            query = "SELECT * FROM stock_info WHERE market = ? ORDER BY code"
            return db_manager.execute_query(query, (market,))
        else:
            query = "SELECT * FROM stock_info ORDER BY code"
            return db_manager.execute_query(query)
    
    def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索股票
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的股票列表
        """
        query = """
        SELECT * FROM stock_info 
        WHERE code LIKE ? OR name LIKE ?
        ORDER BY code
        """
        pattern = f"%{keyword}%"
        return db_manager.execute_query(query, (pattern, pattern))
    
    # Trade Record 查询
    def get_trade_records(self, user_id: str = None,
                         symbol: str = None, 
                         start_date: datetime = None, 
                         end_date: datetime = None,
                         action: str = None) -> List[Dict[str, Any]]:
        """获取交易记录
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            action: 交易动作 ('buy' 或 'sell')
            
        Returns:
            交易记录列表
        """
        query = "SELECT * FROM trade_records WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        query += " ORDER BY timestamp DESC"
        
        results = db_manager.execute_query(query, tuple(params))
        # 解析JSON信号数据
        for result in results:
            if result.get('signal_data'):
                try:
                    result['signal_data'] = json.loads(result['signal_data'])
                except:
                    result['signal_data'] = {}
        
        return results
    
    def get_trade_summary(self, user_id: str = None, symbol: str = None) -> Dict[str, Any]:
        """获取交易汇总信息
        
        Args:
            user_id: 用户ID
            symbol: 股票代码，如果为None则获取全部汇总
            
        Returns:
            交易汇总信息
        """
        base_query = "FROM trade_records WHERE 1=1"
        params = []
        
        if user_id:
            base_query += " AND user_id = ?"
            params.append(user_id)
        
        if symbol:
            base_query += " AND symbol = ?"
            params.append(symbol)
        
        # 总交易次数
        count_query = f"SELECT COUNT(*) as total_trades {base_query}"
        total_trades = db_manager.execute_query(count_query, tuple(params))[0]['total_trades']
        
        # 总买入金额
        buy_query = f"SELECT SUM(total_cost) as total_buy FROM trade_records WHERE action = 'buy'"
        if user_id:
            buy_query += " AND user_id = ?"
            buy_params = [user_id]
        else:
            buy_params = []
        
        if symbol:
            buy_query += " AND symbol = ?"
            buy_params.append(symbol)
        
        buy_result = db_manager.execute_query(buy_query, tuple(buy_params))
        total_buy = buy_result[0]['total_buy'] or 0
        
        # 总卖出金额
        sell_query = f"SELECT SUM(total_cost) as total_sell FROM trade_records WHERE action = 'sell'"
        if user_id:
            sell_query += " AND user_id = ?"
            sell_params = [user_id]
        else:
            sell_params = []
        
        if symbol:
            sell_query += " AND symbol = ?"
            sell_params.append(symbol)
        
        sell_result = db_manager.execute_query(sell_query, tuple(sell_params))
        total_sell = sell_result[0]['total_sell'] or 0
        
        return {
            'total_trades': total_trades,
            'total_buy': total_buy,
            'total_sell': total_sell,
            'net_investment': total_buy - total_sell
        }
    
    # Position 查询
    def get_positions(self, user_id: str = None, symbol: str = None) -> List[Dict[str, Any]]:
        """获取持仓信息
        
        Args:
            user_id: 用户ID
            symbol: 股票代码，如果为None则获取所有持仓
            
        Returns:
            持仓信息列表
        """
        query = "SELECT * FROM positions WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        else:
            query += " AND quantity > 0"
        
        query += " ORDER BY market_value DESC"
        return db_manager.execute_query(query, tuple(params))
    
    def get_position_summary(self, user_id: str = None) -> Dict[str, Any]:
        """获取持仓汇总信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            持仓汇总信息
        """
        query = """
        SELECT 
            COUNT(*) as total_positions,
            SUM(quantity) as total_shares,
            SUM(market_value) as total_market_value,
            SUM(total_cost) as total_cost_value,
            SUM(floating_pnl) as total_floating_pnl,
            CASE 
                WHEN SUM(total_cost) > 0 THEN SUM(floating_pnl) / SUM(total_cost) * 100
                ELSE 0
            END as total_floating_pnl_ratio
        FROM positions 
        WHERE quantity > 0
        """
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        result = db_manager.execute_query(query, tuple(params))
        return result[0] if result else {}
    
    # Strategy Signal 查询
    def get_strategy_signals(self, strategy_name: str = None,
                           stock_code: str = None,
                           start_date: datetime = None,
                           end_date: datetime = None,
                           executed: bool = None) -> List[Dict[str, Any]]:
        """获取策略信号
        
        Args:
            strategy_name: 策略名称
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            executed: 是否已执行
            
        Returns:
            策略信号列表
        """
        query = "SELECT * FROM strategy_signals WHERE 1=1"
        params = []
        
        if strategy_name:
            query += " AND strategy_name = ?"
            params.append(strategy_name)
        
        if stock_code:
            query += " AND stock_code = ?"
            params.append(stock_code)
        
        if start_date:
            query += " AND signal_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND signal_date <= ?"
            params.append(end_date)
        
        if executed is not None:
            query += " AND executed = ?"
            params.append(executed)
        
        query += " ORDER BY signal_date DESC"
        
        results = db_manager.execute_query(query, tuple(params))
        # 解析JSON参数
        for result in results:
            if result.get('parameters'):
                try:
                    result['parameters'] = json.loads(result['parameters'])
                except:
                    result['parameters'] = {}
        
        return results
    
    def get_unexecuted_signals(self) -> List[Dict[str, Any]]:
        """获取未执行的策略信号
        
        Returns:
            未执行的策略信号列表
        """
        return self.get_strategy_signals(executed=False)
    
    # Market Data 查询
    def get_market_data(self, stock_code: str, 
                       start_date: datetime = None,
                       end_date: datetime = None,
                       limit: int = None) -> List[Dict[str, Any]]:
        """获取市场数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制返回记录数
            
        Returns:
            市场数据列表
        """
        query = "SELECT * FROM market_data WHERE stock_code = ?"
        params = [stock_code]
        
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY trade_date DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return db_manager.execute_query(query, tuple(params))
    
    def get_latest_price(self, stock_code: str) -> Optional[float]:
        """获取股票最新价格
        
        Args:
            stock_code: 股票代码
            
        Returns:
            最新价格
        """
        query = """
        SELECT close_price FROM market_data 
        WHERE stock_code = ? 
        ORDER BY trade_date DESC 
        LIMIT 1
        """
        result = db_manager.execute_query(query, (stock_code,))
        return result[0]['close_price'] if result else None
    
    # Trade Notes 查询
    def get_trade_notes(self, stock_code: str = None,
                       start_date: datetime = None,
                       end_date: datetime = None,
                       tags: List[str] = None) -> List[Dict[str, Any]]:
        """获取交易笔记
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            tags: 标签列表
            
        Returns:
            交易笔记列表
        """
        query = "SELECT * FROM trade_notes WHERE 1=1"
        params = []
        
        if stock_code:
            query += " AND stock_code = ?"
            params.append(stock_code)
        
        if start_date:
            query += " AND note_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND note_date <= ?"
            params.append(end_date)
        
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            query += " AND (" + " OR ".join(tag_conditions) + ")"
        
        query += " ORDER BY note_date DESC"
        
        return db_manager.execute_query(query, tuple(params))
    
    # 统计查询
    def get_daily_pnl(self, date: datetime = None) -> List[Dict[str, Any]]:
        """获取每日盈亏统计
        
        Args:
            date: 日期，如果为None则获取最近30天
            
        Returns:
            每日盈亏统计
        """
        if date is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        query = """
        SELECT 
            DATE(trade_date) as trade_day,
            SUM(CASE WHEN direction = 'buy' THEN -amount ELSE amount END) as daily_pnl,
            COUNT(*) as trade_count
        FROM trade_records 
        WHERE status = 'executed' 
        AND trade_date >= ? AND trade_date <= ?
        GROUP BY DATE(trade_date)
        ORDER BY trade_day DESC
        """
        return db_manager.execute_query(query, (start_date, end_date))
    
    # Trade Failure 查询
    def get_trade_failures(self, user_id: str = None,
                          symbol: str = None,
                          reason: str = None,
                          start_date: datetime = None,
                          end_date: datetime = None) -> List[Dict[str, Any]]:
        """获取交易失败记录
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            reason: 失败原因
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            交易失败记录列表
        """
        query = "SELECT * FROM trade_failures WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if reason:
            query += " AND reason = ?"
            params.append(reason)
        
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        results = db_manager.execute_query(query, tuple(params))
        # 解析JSON数据
        for result in results:
            if result.get('signal_data'):
                try:
                    result['signal_data'] = json.loads(result['signal_data'])
                except:
                    result['signal_data'] = {}
            
            if result.get('details'):
                try:
                    result['details'] = json.loads(result['details'])
                except:
                    result['details'] = {}
        
        return results
    
    def get_failure_summary(self, user_id: str = None) -> Dict[str, Any]:
        """获取失败记录汇总信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            失败记录汇总信息
        """
        base_query = "FROM trade_failures WHERE 1=1"
        params = []
        
        if user_id:
            base_query += " AND user_id = ?"
            params.append(user_id)
        
        # 总失败次数
        count_query = f"SELECT COUNT(*) as total_failures {base_query}"
        total_failures = db_manager.execute_query(count_query, tuple(params))[0]['total_failures']
        
        # 按原因统计
        reason_query = f"SELECT reason, COUNT(*) as count {base_query} GROUP BY reason ORDER BY count DESC"
        reason_stats = db_manager.execute_query(reason_query, tuple(params))
        
        # 按股票统计
        symbol_query = f"SELECT symbol, name, COUNT(*) as count {base_query} GROUP BY symbol, name ORDER BY count DESC"
        symbol_stats = db_manager.execute_query(symbol_query, tuple(params))
        
        return {
            'total_failures': total_failures,
            'reason_stats': reason_stats,
            'symbol_stats': symbol_stats
        }
    
    # Diagnosis Report 查询
    def get_diagnosis_reports(self, symbol: str = None,
                            date: datetime = None,
                            recommendation: str = None,
                            risk_level: str = None) -> List[Dict[str, Any]]:
        """获取诊断报告
        
        Args:
            symbol: 股票代码
            date: 诊断日期
            recommendation: 投资建议
            risk_level: 风险等级
            
        Returns:
            诊断报告列表
        """
        query = "SELECT * FROM diagnosis_reports WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if date:
            query += " AND date = ?"
            params.append(date)
        
        if recommendation:
            query += " AND recommendation = ?"
            params.append(recommendation)
        
        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level)
        
        query += " ORDER BY date DESC, timestamp DESC"
        
        results = db_manager.execute_query(query, tuple(params))
        # 解析JSON数据
        for result in results:
            if result.get('key_indicators'):
                try:
                    result['key_indicators'] = json.loads(result['key_indicators'])
                except:
                    result['key_indicators'] = []
            
            if result.get('risk_warnings'):
                try:
                    result['risk_warnings'] = json.loads(result['risk_warnings'])
                except:
                    result['risk_warnings'] = []
        
        return results
    
    def get_latest_diagnosis(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取最新诊断报告
        
        Args:
            symbol: 股票代码
            
        Returns:
            最新诊断报告
        """
        query = """
        SELECT * FROM diagnosis_reports 
        WHERE symbol = ? 
        ORDER BY date DESC, timestamp DESC 
        LIMIT 1
        """
        results = db_manager.execute_query(query, (symbol,))
        if results:
            result = results[0]
            # 解析JSON数据
            if result.get('key_indicators'):
                try:
                    result['key_indicators'] = json.loads(result['key_indicators'])
                except:
                    result['key_indicators'] = []
            
            if result.get('risk_warnings'):
                try:
                    result['risk_warnings'] = json.loads(result['risk_warnings'])
                except:
                    result['risk_warnings'] = []
            return result
        return None
    
    def get_diagnosis_reports_by_date_range(self, symbol: str,
                                          start_date: datetime = None,
                                          end_date: datetime = None,
                                          limit: int = None) -> List[Dict[str, Any]]:
        """按照股票代码和时间范围查询诊断报告
        
        Args:
            symbol: 股票代码
            start_date: 开始日期（包含）
            end_date: 结束日期（包含）
            limit: 限制返回记录数，最新的优先
            
        Returns:
            诊断报告列表，按日期降序排列
        """
        query = "SELECT * FROM diagnosis_reports WHERE symbol = ?"
        params = [symbol]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date.strftime('%Y-%m-%d') if isinstance(start_date, datetime) else str(start_date))
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date.strftime('%Y-%m-%d') if isinstance(end_date, datetime) else str(end_date))
        
        query += " ORDER BY date DESC, timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = db_manager.execute_query(query, tuple(params))
        
        # 解析JSON数据
        for result in results:
            if result.get('key_indicators'):
                try:
                    result['key_indicators'] = json.loads(result['key_indicators'])
                except:
                    result['key_indicators'] = []
            
            if result.get('risk_warnings'):
                try:
                    result['risk_warnings'] = json.loads(result['risk_warnings'])
                except:
                    result['risk_warnings'] = []
        
        return results
    
    def get_stock_performance(self, symbol: str, 
                            days: int = 30) -> Dict[str, Any]:
        """获取股票表现统计
        
        Args:
            symbol: 股票代码
            days: 统计天数
            
        Returns:
            股票表现统计
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 交易记录
        trades = self.get_trade_records(symbol=symbol, start_date=start_date, end_date=end_date)
        
        # 计算盈亏
        total_buy = sum(t['total_cost'] for t in trades if t['action'] == 'buy')
        total_sell = sum(t['total_cost'] for t in trades if t['action'] == 'sell')
        
        # 当前持仓
        position = self.get_positions(symbol=symbol)
        current_position = position[0] if position else None
        
        # 诊断报告
        diagnosis = self.get_latest_diagnosis(symbol)
        
        return {
            'symbol': symbol,
            'total_trades': len(trades),
            'total_buy': total_buy,
            'total_sell': total_sell,
            'net_investment': total_buy - total_sell,
            'current_position': current_position,
            'latest_diagnosis': diagnosis,
            'recent_trades': trades[:10]  # 最近10笔交易
        }
    
    # Position Detail 查询
    def get_position_details(self, user_id: str = None, symbol: str = None, 
                           status: str = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """获取持仓明细记录
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            status: 持仓状态 ('active', 'partial_sold', 'closed', 'cancelled')
            active_only: 是否只返回活跃持仓（remaining_quantity > 0）
            
        Returns:
            持仓明细列表
        """
        query = "SELECT * FROM position_details WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        elif active_only:
            query += " AND remaining_quantity > 0"
        
        query += " ORDER BY buy_date DESC"
        
        results = db_manager.execute_query(query, tuple(params))
        # 解析JSON数据
        for result in results:
            if result.get('diagnosis_data'):
                try:
                    result['diagnosis_data'] = json.loads(result['diagnosis_data'])
                except:
                    result['diagnosis_data'] = {}
            
            if result.get('sell_records'):
                try:
                    result['sell_records'] = json.loads(result['sell_records'])
                except:
                    result['sell_records'] = {}
        
        return results
    
    def get_position_detail_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取持仓明细记录
        
        Args:
            position_id: 持仓明细ID
            
        Returns:
            持仓明细信息
        """
        query = "SELECT * FROM position_details WHERE id = ?"
        results = db_manager.execute_query(query, (position_id,))
        
        if results:
            result = results[0]
            # 解析JSON数据
            if result.get('diagnosis_data'):
                try:
                    result['diagnosis_data'] = json.loads(result['diagnosis_data'])
                except:
                    result['diagnosis_data'] = {}
            
            if result.get('sell_records'):
                try:
                    result['sell_records'] = json.loads(result['sell_records'])
                except:
                    result['sell_records'] = {}
            return result
        return None
    
    def get_position_detail_by_order_id(self, buy_order_id: str) -> Optional[Dict[str, Any]]:
        """根据买入订单ID获取持仓明细记录
        
        Args:
            buy_order_id: 买入订单ID
            
        Returns:
            持仓明细信息
        """
        query = "SELECT * FROM position_details WHERE buy_order_id = ?"
        results = db_manager.execute_query(query, (buy_order_id,))
        
        if results:
            result = results[0]
            # 解析JSON数据
            if result.get('diagnosis_data'):
                try:
                    result['diagnosis_data'] = json.loads(result['diagnosis_data'])
                except:
                    result['diagnosis_data'] = {}
            
            if result.get('sell_records'):
                try:
                    result['sell_records'] = json.loads(result['sell_records'])
                except:
                    result['sell_records'] = {}
            return result
        return None
    
    def get_position_detail_summary(self, user_id: str = None, symbol: str = None) -> Dict[str, Any]:
        """获取持仓明细汇总信息
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            
        Returns:
            持仓明细汇总信息
        """
        base_query = "FROM position_details WHERE 1=1"
        params = []
        
        if user_id:
            base_query += " AND user_id = ?"
            params.append(user_id)
        
        if symbol:
            base_query += " AND symbol = ?"
            params.append(symbol)
        
        # 总持仓记录数
        count_query = f"SELECT COUNT(*) as total_positions {base_query}"
        total_positions = db_manager.execute_query(count_query, tuple(params))[0]['total_positions']
        
        # 活跃持仓数
        active_query = f"SELECT COUNT(*) as active_positions {base_query} AND status = 'active'"
        active_positions = db_manager.execute_query(active_query, tuple(params))[0]['active_positions']
        
        # 部分卖出数
        partial_query = f"SELECT COUNT(*) as partial_positions {base_query} AND status = 'partial_sold'"
        partial_positions = db_manager.execute_query(partial_query, tuple(params))[0]['partial_positions']
        
        # 已清仓数
        closed_query = f"SELECT COUNT(*) as closed_positions {base_query} AND status = 'closed'"
        closed_positions = db_manager.execute_query(closed_query, tuple(params))[0]['closed_positions']
        
        # 总持仓数量
        quantity_query = f"SELECT SUM(remaining_quantity) as total_remaining, SUM(original_quantity) as total_original {base_query}"
        quantity_result = db_manager.execute_query(quantity_query, tuple(params))
        total_remaining = quantity_result[0]['total_remaining'] or 0
        total_original = quantity_result[0]['total_original'] or 0
        
        # 总成本
        cost_query = f"SELECT SUM(total_cost) as total_cost {base_query}"
        total_cost = db_manager.execute_query(cost_query, tuple(params))[0]['total_cost'] or 0
        
        return {
            'total_positions': total_positions,
            'active_positions': active_positions,
            'partial_positions': partial_positions,
            'closed_positions': closed_positions,
            'total_remaining_quantity': total_remaining,
            'total_original_quantity': total_original,
            'total_cost': total_cost
        }
    
    def get_position_details_by_date_range(self, user_id: str = None,
                                         start_date: datetime = None,
                                         end_date: datetime = None,
                                         status: str = None) -> List[Dict[str, Any]]:
        """按照时间范围查询持仓明细
        
        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            status: 持仓状态
            
        Returns:
            持仓明细列表
        """
        query = "SELECT * FROM position_details WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if start_date:
            query += " AND buy_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND buy_date <= ?"
            params.append(end_date)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY buy_date DESC"
        
        results = db_manager.execute_query(query, tuple(params))
        # 解析JSON数据
        for result in results:
            if result.get('diagnosis_data'):
                try:
                    result['diagnosis_data'] = json.loads(result['diagnosis_data'])
                except:
                    result['diagnosis_data'] = {}
            
            if result.get('sell_records'):
                try:
                    result['sell_records'] = json.loads(result['sell_records'])
                except:
                    result['sell_records'] = {}
        
        return results
    
    # User Info 查询
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户信息字典
        """
        query = "SELECT * FROM user_info WHERE user_id = ?"
        results = db_manager.execute_query(query, (user_id,))
        
        if results:
            result = results[0]
            # 解析JSON数据
            if result.get('quant_stocks'):
                try:
                    result['quant_stocks'] = json.loads(result['quant_stocks'])
                except:
                    result['quant_stocks'] = {}
            return result
        return None
    
    def get_all_users_with_quant_enabled(self) -> List[Dict[str, Any]]:
        """获取所有开启量化交易的用户信息
        
        Returns:
            开启量化交易的用户列表
        """
        query = "SELECT * FROM user_info WHERE quant_enabled = 1"
        results = db_manager.execute_query(query)
        
        # 解析JSON数据
        for result in results:
            if result.get('quant_stocks'):
                try:
                    result['quant_stocks'] = json.loads(result['quant_stocks'])
                except:
                    result['quant_stocks'] = {}
        
        return results
# 全局查询服务实例
query_service = QueryService()
