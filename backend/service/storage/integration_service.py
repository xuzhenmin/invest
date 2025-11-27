"""
数据库集成示例
展示如何在现有交易系统中集成SQLite数据库功能
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from . import data_service, query_service
from .models import TradeRecord, Position, MarketData, TradeFailure, DiagnosisReport

class TradingDatabaseIntegration:
    """交易数据库集成类"""
    
    @staticmethod
    def record_trade_execution(trade_data: Dict[str, Any]) -> int:
        """记录交易执行
        
        Args:
            trade_data: 交易数据字典，必须包含：
                - user_id: 用户ID
                - symbol: 股票代码
                - name: 股票名称
                - action: 交易动作 ('buy' 或 'sell')
                - price: 成交价格
                - quantity: 成交数量
                - total_cost: 总成本（含费用）
                - order_id: 订单ID（可选）
                - signal_data: 信号数据（可选）
            
        Returns:
            交易记录ID
        """
        trade_record = TradeRecord(
            user_id=trade_data['user_id'],
            symbol=trade_data['symbol'],
            name=trade_data['name'],
            action=trade_data['action'],
            timestamp=datetime.now(),
            trade_date=datetime.now(),
            price=trade_data['price'],
            quantity=trade_data['quantity'],
            total_cost=trade_data['total_cost'],
            order_id=trade_data.get('order_id'),
            signal_data=trade_data.get('signal_data')
        )
        
        return data_service.save_trade_record(trade_record)
    
    @staticmethod
    def update_position_after_trade(user_id: str, symbol: str, trade_data: Dict[str, Any]) -> bool:
        """交易后更新持仓
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            trade_data: 交易数据，必须包含：
                - name: 股票名称
                - action: 交易动作 ('buy' 或 'sell')
                - price: 成交价格
                - quantity: 成交数量
                - total_cost: 总成本（含费用）
            
        Returns:
            是否更新成功
        """
        # 获取当前持仓
        current_positions = query_service.get_positions(user_id=user_id, symbol=symbol)
        
        if not current_positions:
            # 新建持仓
            if trade_data['action'] == 'buy':
                position = Position(
                    user_id=user_id,
                    symbol=symbol,
                    name=trade_data['name'],
                    quantity=trade_data['quantity'],
                    avg_price=trade_data['price'],
                    total_cost=trade_data['total_cost'],
                    market_value=trade_data['price'] * trade_data['quantity'],
                    floating_pnl=0,
                    floating_pnl_ratio=0,
                    last_price=trade_data['price']
                )
                data_service.save_position(position)
                return True
        else:
            # 更新现有持仓
            pos = current_positions[0]
            current_quantity = pos['quantity']
            avg_price = pos['avg_price']
            
            if trade_data['action'] == 'buy':
                # 买入：更新持仓
                new_quantity = current_quantity + trade_data['quantity']
                new_total_cost = pos['total_cost'] + trade_data['total_cost']
                new_avg_price = new_total_cost / new_quantity
                
                position = Position(
                    user_id=user_id,
                    symbol=symbol,
                    name=trade_data['name'],
                    quantity=new_quantity,
                    avg_price=new_avg_price,
                    total_cost=new_total_cost,
                    market_value=trade_data['price'] * new_quantity,
                    floating_pnl=(trade_data['price'] - new_avg_price) * new_quantity,
                    floating_pnl_ratio=((trade_data['price'] - new_avg_price) / new_avg_price * 100),
                    last_price=trade_data['price']
                )
                data_service.save_position(position)
                return True
            
            elif trade_data['action'] == 'sell':
                # 卖出：减少持仓
                new_quantity = max(0, current_quantity - trade_data['quantity'])
                if new_quantity > 0:
                    # 卖出部分，保持平均成本不变
                    new_total_cost = avg_price * new_quantity
                    position = Position(
                        user_id=user_id,
                        symbol=symbol,
                        name=trade_data['name'],
                        quantity=new_quantity,
                        avg_price=avg_price,
                        total_cost=new_total_cost,
                        market_value=trade_data['price'] * new_quantity,
                        floating_pnl=(trade_data['price'] - avg_price) * new_quantity,
                        floating_pnl_ratio=((trade_data['price'] - avg_price) / avg_price * 100),
                        last_price=trade_data['price']
                    )
                    data_service.save_position(position)
                else:
                    # 清仓
                    position = Position(
                        user_id=user_id,
                        symbol=symbol,
                        name=trade_data['name'],
                        quantity=0,
                        avg_price=0,
                        total_cost=0,
                        market_value=0,
                        floating_pnl=0,
                        floating_pnl_ratio=0,
                        last_price=trade_data['price']
                    )
                    data_service.save_position(position)
                return True
        
        return False
    
    @staticmethod
    def save_market_price(symbol: str, price_data: Dict[str, Any]) -> int:
        """保存市场价格数据
        
        Args:
            symbol: 股票代码
            price_data: 价格数据，包含：
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - volume: 成交量
                - turnover: 成交额（可选）
                - date: 交易日期（可选）
            
        Returns:
            数据记录ID
        """
        market_data = MarketData(
            stock_code=symbol,
            trade_date=price_data.get('date', datetime.now().date()),
            open_price=price_data['open'],
            high_price=price_data['high'],
            low_price=price_data['low'],
            close_price=price_data['close'],
            volume=price_data['volume'],
            turnover=price_data.get('turnover', 0)
        )
        
        # 保存市场数据
        record_id = data_service.save_market_data(market_data)
        
        # 更新所有用户的持仓价格
        # 注意：这里需要遍历所有用户，实际应用中可能需要优化
        positions = query_service.get_positions(symbol=symbol)
        for position in positions:
            data_service.update_position_price(
                position['user_id'], 
                symbol, 
                price_data['close']
            )
        
        return record_id
    
    @staticmethod
    def get_portfolio_summary(user_id: str = None) -> Dict[str, Any]:
        """获取投资组合汇总
        
        Args:
            user_id: 用户ID，如果为None则获取所有用户的投资组合
            
        Returns:
            投资组合汇总信息
        """
        positions = query_service.get_positions(user_id=user_id)
        summary = query_service.get_position_summary(user_id=user_id)
        
        # 获取持仓股票的最新价格
        for position in positions:
            latest_price = query_service.get_latest_price(position['symbol'])
            if latest_price:
                position['latest_price'] = latest_price
                position['latest_market_value'] = latest_price * position['quantity']
                position['latest_floating_pnl'] = (latest_price - position['avg_price']) * position['quantity']
        
        return {
            'positions': positions,
            'summary': summary,
            'total_positions': len(positions)
        }
    
    @staticmethod
    def get_trading_history(user_id: str = None, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """获取交易历史
        
        Args:
            user_id: 用户ID，如果为None则获取所有用户的交易历史
            symbol: 股票代码，None表示获取全部
            days: 查询天数
            
        Returns:
            交易历史信息
        """
        start_date = datetime.now() - timedelta(days=days)
        
        trades = query_service.get_trade_records(
            user_id=user_id,
            symbol=symbol,
            start_date=start_date
        )
        
        if symbol:
            performance = query_service.get_stock_performance(symbol, days)
            return {
                'trades': trades,
                'performance': performance
            }
        else:
            # 获取所有交易汇总
            summary = query_service.get_trade_summary(user_id=user_id)
            return {
                'trades': trades,
                'summary': summary
            }
    
    @staticmethod
    def record_trade_failure(failure_data: Dict[str, Any]) -> int:
        """记录交易失败
        
        Args:
            failure_data: 失败数据字典，必须包含：
                - user_id: 用户ID
                - symbol: 股票代码
                - name: 股票名称
                - action: 交易动作 ('buy' 或 'sell')
                - reason: 失败原因
                - signal_data: 信号数据（可选）
                - details: 失败详情（可选）
            
        Returns:
            失败记录ID
        """
        trade_failure = TradeFailure(
            user_id=failure_data['user_id'],
            symbol=failure_data['symbol'],
            name=failure_data['name'],
            action=failure_data['action'],
            reason=failure_data['reason'],
            timestamp=datetime.now(),
            trade_date=datetime.now(),
            signal_data=failure_data.get('signal_data'),
            details=failure_data.get('details')
        )
        
        return data_service.save_trade_failure(trade_failure)
    
    @staticmethod
    def save_diagnosis_report(diagnosis_data: Dict[str, Any]) -> int:
        """保存诊断报告
        
        Args:
            diagnosis_data: 诊断数据字典，必须包含：
                - symbol: 股票代码
                - name: 股票名称
                - current_price: 当前价格
                - overall_score: 综合评分
                - fundamental_score: 基本面评分
                - technical_score: 技术面评分
                - capital_score: 资金面评分
                - valuation_score: 估值评分
                - risk_level: 风险等级
                - recommendation: 投资建议
                - target_price: 目标价格（可选）
                - stop_loss: 止损价格（可选）
                - support: 支撑位（可选）
                - resistance: 阻力位（可选）
                - buy_price: 买入价格（可选）
                - sell_price: 卖出价格（可选）
                - investment_reason: 投资理由
                - key_indicators: 关键指标列表（可选）
                - risk_warnings: 风险提示列表（可选）
            
        Returns:
            诊断报告ID
        """
        diagnosis_report = DiagnosisReport(
            symbol=diagnosis_data['symbol'],
            name=diagnosis_data['name'],
            current_price=diagnosis_data['current_price'],
            overall_score=diagnosis_data['overall_score'],
            fundamental_score=diagnosis_data['fundamental_score'],
            technical_score=diagnosis_data['technical_score'],
            capital_score=diagnosis_data['capital_score'],
            valuation_score=diagnosis_data['valuation_score'],
            risk_level=diagnosis_data['risk_level'],
            recommendation=diagnosis_data['recommendation'],
            target_price=diagnosis_data.get('target_price'),
            stop_loss=diagnosis_data.get('stop_loss'),
            support=diagnosis_data.get('support'),
            resistance=diagnosis_data.get('resistance'),
            buy_price=diagnosis_data.get('buy_price'),
            sell_price=diagnosis_data.get('sell_price'),
            investment_reason=diagnosis_data['investment_reason'],
            key_indicators=diagnosis_data.get('key_indicators'),
            risk_warnings=diagnosis_data.get('risk_warnings'),
            timestamp=datetime.now()
        )
        
        return data_service.save_diagnosis_report(diagnosis_report)

# 集成服务类已更新完成，移除了模拟代码
