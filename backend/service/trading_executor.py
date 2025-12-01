"""
量化交易执行器
负责处理交易模拟、账户管理和交易记录
"""

import logging
import json
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

# 导入持仓管理器
from .position_manager import PositionManager
# 导入查询服务
from .storage.query_service import query_service
# 导入数据服务
from .storage.data_service import data_service

logger = logging.getLogger(__name__)

class QuantTradingSimulator:
    """量化交易模拟器 - 模拟交易账户和交易操作"""

    def buy_stock(self, user_id: str, symbol: str, price: float, quantity: int,
                  signal_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        买入股票方法
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            price: 买入价格
            quantity: 买入数量
            signal_data: 信号数据，包含支撑位/压力位等信息
            
        Returns:
            Dict: 交易结果
        """
        try:
            logger.info(f"开始买入股票: {symbol}, 价格: {price}, 数量: {quantity}, 用户: {user_id}")
            
            # 1. 参数验证和买入条件判断
            if price <= 0:
                error_msg = "买入价格必须大于0"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="buy",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"price": price, "quantity": quantity}
                )
                return {"success": False, "error": error_msg}
            
            if quantity <= 0:
                error_msg = "买入数量必须大于0"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="buy",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"price": price, "quantity": quantity}
                )
                return {"success": False, "error": error_msg}
            
            if not symbol or not isinstance(symbol, str):
                error_msg = "股票代码无效"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=str(symbol) if symbol else "unknown",
                    action="buy",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"price": price, "quantity": quantity}
                )
                return {"success": False, "error": error_msg}
            
            # 2. 获取用户账户信息
            user_info = self._get_user_account_info(user_id)
            current_cash = float(user_info.get('current_cash'))
            fee_rate = float(user_info.get('fee_rate'))
            
            # 3. 买入条件判断：诊断报告评分检查
            if signal_data:
                overall_score = signal_data.get('overall_score', 0)
                if overall_score < 55:
                    error_msg = f"诊断报告评分{overall_score}分低于55分，不满足买入条件"
                    self._save_unmet_condition(
                        user_id=user_id,
                        symbol=symbol,
                        action="buy",
                        reason=error_msg,
                        signal_data=signal_data,
                        details={"overall_score": overall_score, "min_required_score": 55}
                    )
                    return {"success": False, "error": error_msg}
            
            # 4. 买入条件判断：建议买入价是否在当日价格区间内
            if signal_data:
                buy_price = signal_data.get('buy_price', price)
                day_low = signal_data.get('day_low', 0)
                day_high = signal_data.get('day_high', 0)
                
                # 检查建议买入价是否在当日价格区间内
                if not (day_low <= buy_price <= day_high):
                    error_msg = f"建议买入价{buy_price}不在当日价格区间[{day_low}, {day_high}]内"
                    self._save_unmet_condition(
                        user_id=user_id,
                        symbol=symbol,
                        action="buy",
                        reason=error_msg,
                        signal_data=signal_data,
                        details={"buy_price": buy_price, "day_low": day_low, "day_high": day_high}
                    )
                    return {"success": False, "error": error_msg}
            
            # 5. 一天一只股票只能买一次的限制
            if self.has_bought_today(user_id, symbol):
                error_msg = f"今天已经买入过{symbol}"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="buy",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"symbol": symbol, "date": datetime.now().strftime('%Y-%m-%d')}
                )
                return {"success": False, "error": error_msg}
            
            # 6. 资金检查
            total_amount = price * quantity
            fee = total_amount * fee_rate
            total_cost = total_amount + fee
            
            if total_cost > current_cash:
                error_msg = f"资金不足，需要{total_cost:,.2f}，可用{current_cash:,.2f}"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="buy",
                    reason="资金不足",
                    signal_data=signal_data,
                    details={
                        "required_amount": total_cost,
                        "available_cash": current_cash,
                        "shortage": total_cost - current_cash,
                        "price": price,
                        "quantity": quantity
                    }
                )
                return {"success": False, "error": error_msg}
            
            # 6. 获取当前持仓
            positions_data = query_service.get_positions(user_id=user_id, symbol=symbol)
            current_position = positions_data[0] if positions_data else None
            
            # 7. 订单创建
            trade_records = query_service.get_trade_records(user_id=user_id)
            trade_count = len(trade_records)
            order_id = f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}{trade_count:04d}"
            
            # 8. 计算新的持仓
            if current_position:
                # 已有持仓，计算加权平均成本
                old_quantity = float(current_position.get('quantity', 0))
                old_avg_price = float(current_position.get('avg_price', 0))
                old_total = old_quantity * old_avg_price
                new_total = total_amount
                new_quantity = old_quantity + quantity
                new_avg_price = (old_total + new_total) / new_quantity if new_quantity > 0 else price
                new_total_cost = new_quantity * new_avg_price
            else:
                # 新建持仓
                new_quantity = quantity
                new_avg_price = price
                new_total_cost = total_amount
            
            # 9. 更新资金
            new_cash = current_cash - total_cost
            
            # 10. 创建交易记录
            from .storage.models import TradeRecord
            
            trade_record = TradeRecord(
                user_id=user_id,
                symbol=symbol,
                name=signal_data.get('name', symbol) if signal_data else symbol,
                action='buy',
                price=price,
                quantity=quantity,
                total_cost=total_cost,
                order_id=order_id,
                timestamp=datetime.now(),
                trade_date=datetime.now(),
                signal_data=signal_data
            )
            
            # 11. 保存交易记录到数据库
            record_id = data_service.save_trade_record(trade_record)
            
            # 12. 更新持仓信息
            position_data = {
                'user_id': user_id,
                'symbol': symbol,
                'quantity': new_quantity,
                'avg_price': new_avg_price,
                'total_cost': new_total_cost,
                'market_value': new_quantity * price,
                'floating_pnl': new_quantity * price - new_total_cost
            }
            
            # 13. 更新用户资金
            data_service.update_user_account(
                user_id=user_id,
                current_cash=new_cash,
                trade_count_increment=1
            )
            
            # 14. 更新账户总价值
            self._update_account_value(user_id)
            
            logger.info(f"买入成功: {symbol} {quantity}股 @ {price}, 订单号: {order_id}")
            
            # 创建返回用的交易记录字典
            trade_record_dict = {
                'order_id': order_id,
                'user_id': user_id,
                'symbol': symbol,
                'name': signal_data.get('name', symbol) if signal_data else symbol,
                'action': 'buy',
                'price': price,
                'quantity': quantity,
                'total_amount': total_amount,
                'fee': fee,
                'total_cost': total_cost,
                'timestamp': datetime.now().isoformat(),
                'cash_after': new_cash,
                'signal_timestamp': signal_data.get('timestamp') if signal_data else None,
                'support': signal_data.get('support') if signal_data else None,
                'resistance': signal_data.get('resistance') if signal_data else None,
                'target_price': signal_data.get('target_price') if signal_data else None,
                'stop_loss': signal_data.get('stop_loss') if signal_data else None,
                'buy_price': signal_data.get('buy_price') if signal_data else None,
                'sell_price': signal_data.get('sell_price') if signal_data else None,
                'recommendation': signal_data.get('recommendation') if signal_data else None,
                'overall_score': signal_data.get('overall_score') if signal_data else None
            }
            
            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "total_cost": total_cost,
                "fee": fee,
                "cash_remaining": new_cash,
                "position": position_data,
                "trade_record": trade_record_dict
            }
            
        except Exception as e:
            logger.error(f"买入股票失败: {symbol}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _is_a_stock(self, symbol: str) -> bool:
        """
        判断是否为A股
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 如果是A股返回True，否则返回False
        """
        # A股代码规则：6位数字，沪市以6开头，深市以0或3开头
        if not symbol:
            return False
            
        # 处理带后缀的格式，如 000001.SZ, 600000.SH
        if '.' in symbol:
            code_part = symbol.split('.')[0]
        else:
            code_part = symbol
            
        # 检查是否为6位数字
        if not code_part.isdigit() or len(code_part) != 6:
            return False
            
        # 检查A股代码规则
        first_digit = code_part[0]
        return first_digit in ['0', '3', '6']
    
    def _is_hk_stock(self, symbol: str) -> bool:
        """
        判断是否为港股
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 如果是港股返回True，否则返回False
        """
        # 港股代码规则：通常是4-5位数字，或者带.HK后缀
        if not symbol:
            return False
            
        # 处理带后缀的格式，如 00700.HK
        if '.HK' in symbol.upper():
            return True
            
        # 处理纯数字格式，港股通常是4-5位数字
        code_part = symbol.split('.')[0] if '.' in symbol else symbol
        if code_part.isdigit() and 4 <= len(code_part) <= 5:
            # 港股代码范围：00001-09999
            try:
                code_num = int(code_part)
                return 1 <= code_num <= 99999
            except ValueError:
                return False
                
        return False
    
    def _has_bought_today(self, user_id: str, symbol: str) -> bool:
        """
        检查今天是否已经买入过指定股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 如果今天已经买入过则返回True，否则返回False
        """
        today_buys = self.get_today_trades(user_id=user_id, symbol=symbol, action='buy')
        return len(today_buys) > 0
    
    def sell_stock(self, user_id: str, symbol: str, price: float, quantity: int, 
                   signal_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        卖出股票方法
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            price: 卖出价格
            quantity: 卖出数量
            signal_data: 信号数据，包含支撑位/压力位等信息
            
        Returns:
            Dict: 交易结果
        """
        try:
            logger.info(f"开始卖出股票: {symbol}, 价格: {price}, 数量: {quantity}, 用户: {user_id}")
            
            # 1. 参数验证
            if price <= 0:
                error_msg = "卖出价格必须大于0"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="sell",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"price": price, "quantity": quantity}
                )
                return {"success": False, "error": error_msg}
            
            if quantity <= 0:
                error_msg = "卖出数量必须大于0"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="sell",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"price": price, "quantity": quantity}
                )
                return {"success": False, "error": error_msg}
            
            if not symbol or not isinstance(symbol, str):
                error_msg = "股票代码无效"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=str(symbol) if symbol else "unknown",
                    action="sell",
                    reason=error_msg,
                    signal_data=signal_data,
                    details={"price": price, "quantity": quantity}
                )
                return {"success": False, "error": error_msg}
            
            # 2. 获取用户账户信息
            user_info = self._get_user_account_info(user_id)
            fee_rate = float(user_info.get('fee_rate'))
            
            # 3. 获取当前持仓
            positions_data = query_service.get_positions(user_id=user_id, symbol=symbol)
            if not positions_data:
                error_msg = f"未持有{symbol}股票"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="sell",
                    reason="未持有股票",
                    signal_data=signal_data,
                    details={
                        "price": price,
                        "quantity": quantity,
                        "current_holdings": []
                    }
                )
                return {"success": False, "error": error_msg}
            
            current_position = positions_data[0]
            current_quantity = float(current_position.get('quantity', 0))
            avg_cost = float(current_position.get('avg_price', 0))
            
            if current_quantity < quantity:
                error_msg = f"持仓不足，持有{current_quantity}股，尝试卖出{quantity}股"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="sell",
                    reason="持仓不足",
                    signal_data=signal_data,
                    details={
                        "price": price,
                        "requested_quantity": quantity,
                        "available_quantity": current_quantity,
                        "shortage": quantity - current_quantity
                    }
                )
                return {
                    "success": False, 
                    "error": error_msg
                }
            
            # 4. 当日买入限制判断
            if self._is_a_stock(symbol) and self._has_bought_today(user_id, symbol):
                error_msg = f"A股当日买入的股票不能卖出：{symbol}"
                self._save_unmet_condition(
                    user_id=user_id,
                    symbol=symbol,
                    action="sell",
                    reason="A股当日买入限制",
                    signal_data=signal_data,
                    details={
                        "price": price,
                        "quantity": quantity,
                        "symbol": symbol,
                        "market_type": "A股",
                        "restriction": "当日买入不能卖出"
                    }
                )
                return {"success": False, "error": error_msg}
            
            # 港股当日买入可以卖出，不做限制
            if self._is_hk_stock(symbol) and self._has_bought_today(user_id, symbol):
                logger.info(f"港股当日买入可以卖出：{symbol}")
            
            # 5. 卖出条件判断：基于持仓止盈止损点位
            if signal_data:
                target_price = signal_data.get('target_price', 0)
                stop_loss = signal_data.get('stop_loss', 0)
                day_low = signal_data.get('day_low', 0)
                day_high = signal_data.get('day_high', 0)
                current_price = signal_data.get('current_price', price)
                
                # 检查是否触发止盈或止损
                should_sell = False
                sell_reason = None
                
                if target_price > 0 and day_low <= target_price <= day_high:
                    should_sell = True
                    sell_reason = f"触发止盈价{target_price}"
                elif stop_loss > 0 and day_low <= stop_loss <= day_high:
                    should_sell = True
                    sell_reason = f"触发止损价{stop_loss}"
                elif current_price >= target_price > 0:
                    should_sell = True
                    sell_reason = f"当前价{current_price}达到止盈价{target_price}"
                elif current_price <= stop_loss > 0:
                    should_sell = True
                    sell_reason = f"当前价{current_price}触及止损价{stop_loss}"
                
                # 新增：基于整体诊断评分强制卖出
                # overall_score = signal_data.get('overall_score', 0)
                # if overall_score < 45:
                #     should_sell = True
                #     sell_reason = f"整体诊断评分过低({overall_score}分)，触发强制卖出"
                #     logger.info(f"[sell_stock] 股票{symbol}评分{overall_score}低于45分，强制卖出")
                
                if not should_sell:
                    error_msg = f"未触发止盈止损条件，止盈价{target_price}，止损价{stop_loss}，当前价{current_price}"
                    self._save_unmet_condition(
                        user_id=user_id,
                        symbol=symbol,
                        action="sell",
                        reason=error_msg,
                        signal_data=signal_data,
                        details={
                            "target_price": target_price,
                            "stop_loss": stop_loss,
                            "current_price": current_price,
                            "day_low": day_low,
                            "day_high": day_high,
                            "overall_score": overall_score
                        }
                    )
                    return {"success": False, "error": error_msg}
            
            # 6. 订单创建
            trade_records = query_service.get_trade_records(user_id=user_id)
            trade_count = len(trade_records)
            order_id = f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}{trade_count:04d}"
            
            # 7. 计算交易金额和费用
            total_amount = price * quantity
            fee = total_amount * fee_rate
            net_amount = total_amount - fee
            
            # 8. 计算盈亏
            profit_loss = (price - avg_cost) * quantity
            
            # 9. 计算新的持仓
            remaining_quantity = current_quantity - quantity
            if remaining_quantity <= 0:
                # 清仓
                remaining_quantity = 0
                new_avg_price = 0
                new_total_cost = 0
            else:
                # 部分卖出，成本不变
                new_avg_price = avg_cost
                new_total_cost = remaining_quantity * avg_cost
            
            # 10. 获取当前资金并更新
            new_cash = float(user_info.get('current_cash', 1000000.0)) + net_amount
            
            # 11. 创建交易记录
            from .storage.models import TradeRecord
            
            trade_record = TradeRecord(
                user_id=user_id,
                symbol=symbol,
                name=signal_data.get('name', symbol) if signal_data else symbol,
                action='sell',
                price=price,
                quantity=quantity,
                total_cost=net_amount,  # 卖出时total_cost为净收入
                order_id=order_id,
                timestamp=datetime.now(),
                trade_date=datetime.now(),
                signal_data=signal_data
            )
            
            # 12. 保存交易记录到数据库
            record_id = data_service.save_trade_record(trade_record)
            
            # 13. 更新持仓信息
            if remaining_quantity > 0:
                position_data = {
                    'user_id': user_id,
                    'symbol': symbol,
                    'quantity': remaining_quantity,
                    'avg_price': new_avg_price,
                    'total_cost': new_total_cost,
                    'market_value': remaining_quantity * price,
                    'floating_pnl': remaining_quantity * price - new_total_cost
                }
                # 更新持仓
                # 这里需要实现更新持仓的逻辑
            else:
                # 删除持仓
                # 这里需要实现删除持仓的逻辑
                pass
            
            # 14. 更新用户资金
            data_service.update_user_account(
                user_id=user_id,
                current_cash=new_cash,
                trade_count_increment=1
            )
            
            # 15. 更新账户总价值
            self._update_account_value(user_id)
            
            logger.info(f"卖出成功: {symbol} {quantity}股 @ {price}, 盈亏: {profit_loss:,.2f}, 订单号: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "net_amount": net_amount,
                "fee": fee,
                "profit": profit_loss,
                "cash_remaining": new_cash,
                "position": {
                    'quantity': remaining_quantity,
                    'avg_price': new_avg_price,
                    'total_cost': new_total_cost,
                    'market_value': remaining_quantity * price,
                    'profit_loss': remaining_quantity * price - new_total_cost
                } if remaining_quantity > 0 else None,
                "trade_record": trade_record
            }
            
        except Exception as e:
            logger.error(f"卖出股票失败: {symbol}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _get_user_account_info(self, user_id: str) -> Dict[str, Any]:
        """从数据库获取用户账户信息"""
        try:
            user_info = query_service.get_user_info(user_id)
            if not user_info:
                # 如果用户不存在，创建默认用户
                default_user = {
                    'user_id': user_id,
                    'initial_cash': 1000000.0,
                    'current_cash': 1000000.0,
                    'total_assets': 1000000.0,
                    'total_profit': 0.0,
                    'total_profit_ratio': 0.0,
                    'trade_count': 0,
                    'fee_rate': 0.0003
                }
                return default_user
            
            return user_info
        except Exception as e:
            logger.error(f"获取用户账户信息失败: {str(e)}")
            return {
                'user_id': user_id,
                'initial_cash': 1000000.0,
                'current_cash': 1000000.0,
                'total_assets': 1000000.0,
                'total_profit': 0.0,
                'total_profit_ratio': 0.0,
                'trade_count': 0,
                'fee_rate': 0.0003
            }
    
    def _update_account_value(self, user_id: str):
        """更新账户总价值到数据库"""
        try:
            # 获取当前持仓信息
            positions_data = query_service.get_positions(user_id=user_id)
            
            # 计算持仓总市值
            positions_value = 0
            for pos in positions_data:
                market_value = float(pos.get('market_value', 0))
                positions_value += market_value
            
            # 获取用户账户信息
            user_info = self._get_user_account_info(user_id)
            current_cash = float(user_info.get('current_cash', 1000000.0))
            initial_cash = float(user_info.get('initial_cash', 1000000.0))
            
            # 计算总资产和盈亏
            total_assets = current_cash + positions_value
            total_profit = total_assets - initial_cash
            total_profit_ratio = (total_profit / initial_cash * 100) if initial_cash > 0 else 0
            
            # 更新数据库中的用户账户信息
            success = data_service.update_user_account(
                user_id=user_id,
                current_cash=current_cash,
                total_assets=total_assets,
                total_profit=total_profit,
                total_profit_ratio=total_profit_ratio
            )
            
            if success:
                logger.debug(f"账户信息已更新到数据库 - 用户: {user_id}, 总价值: {total_assets:,.2f}, 总盈亏: {total_profit:,.2f}")
            else:
                logger.warning(f"更新账户信息到数据库失败 - 用户: {user_id}")
            
        except Exception as e:
            logger.error(f"更新账户价值失败: {str(e)}")
    
    def get_account_summary(self, user_id: str) -> Dict[str, Any]:
        """获取账户概览，从数据库实时获取数据"""
        try:
            logger.info(f"[ACCOUNT_SUMMARY] 开始获取用户 {user_id} 的账户概览")
            
            # 从数据库获取用户账户信息
            user_info = self._get_user_account_info(user_id)
            logger.info(f"[ACCOUNT_SUMMARY] 用户账户信息: user_info={user_info}")
            
            # 检查用户初始金额是否为0，如果是则初始化用户
            initial_cash = float(user_info.get('initial_cash', 0))
            if initial_cash <= 0:
                logger.warning(f"[ACCOUNT_SUMMARY] 用户 {user_id} 初始金额为 {initial_cash}，正在初始化用户资金...")
                from .position_manager import PositionManager
                position_manager = PositionManager()
                success = position_manager.ensure_user_exists(user_id)
                if success:
                    logger.info(f"[ACCOUNT_SUMMARY] 用户 {user_id} 资金初始化完成")
                    # 重新获取用户信息
                    user_info = self._get_user_account_info(user_id)
                    logger.info(f"[ACCOUNT_SUMMARY] 更新后的用户账户信息: user_info={user_info}")
                else:
                    logger.error(f"[ACCOUNT_SUMMARY] 用户 {user_id} 资金初始化失败")
            
            # 从数据库获取持仓信息
            positions_data = query_service.get_positions(user_id=user_id)
            logger.info(f"[ACCOUNT_SUMMARY] 持仓信息: 共 {len(positions_data)} 个持仓")
            
            # 打印详细持仓信息
            for pos in positions_data:
                symbol = pos.get('symbol', '未知')
                quantity = float(pos.get('quantity', 0))
                avg_price = float(pos.get('avg_price', 0))
                total_cost = float(pos.get('total_cost', 0))
                market_value = float(pos.get('market_value', total_cost))
                logger.info(f"[ACCOUNT_SUMMARY] 持仓详情: {symbol} - 数量={quantity}, 成本价={avg_price:.2f}, 总成本={total_cost:,.2f}, 市值={market_value:,.2f}")
            
            # 获取历史K线数据用于计算每日盈亏
            kline_data_cache = {}
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # 获取股票代码列表
            symbols = [pos['symbol'] for pos in positions_data]
            logger.info(f"[ACCOUNT_SUMMARY] 需要获取行情的股票: {symbols}")
            
            # 统一获取实时数据和使用区间查询获取所有股票的K线数据
            market_data = self._get_unified_market_data(symbols, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            kline_data_cache = market_data['kline_data']
            realtime_data = market_data['realtime_data']
            stock_names = market_data['stock_names']
            
            logger.info(f"[ACCOUNT_SUMMARY] 行情数据获取完成: 实时数据{len(realtime_data)}条, K线数据{len(kline_data_cache)}条")

            # 使用传入的实时数据更新持仓
            positions_with_realtime = self._update_positions_with_realtime_prices(positions_data, realtime_data, stock_names)
            logger.info(f"[ACCOUNT_SUMMARY] 实时价格更新完成: 更新{positions_with_realtime}持仓")

            # 计算基于实时价格的总市值
            realtime_positions_value = sum(pos['current_value'] for pos in positions_with_realtime.values())
            realtime_account_value = float(user_info.get('current_cash', 1000000.0)) + realtime_positions_value
            realtime_total_profit = realtime_account_value - float(user_info.get('initial_cash', 1000000.0))
            
            logger.info(f"[ACCOUNT_SUMMARY] 账户价值计算: 持仓市值={realtime_positions_value:,.2f}, 账户总值={realtime_account_value:,.2f}, 总盈亏={realtime_total_profit:,.2f}")
            
            # 计算每日盈亏详情（使用传入的K线数据）
            daily_profit_details = self._calculate_daily_profit_details(user_id, kline_data_cache)
            logger.info(f"[ACCOUNT_SUMMARY] 每日盈亏详情: 共{len(daily_profit_details)}天数据")
            
            # 计算持仓天数
            positions_with_hold_days = self._calculate_hold_days(user_id, positions_with_realtime)
            logger.info(f"[ACCOUNT_SUMMARY] 持仓天数计算完成: 共{len(positions_with_hold_days)}个持仓有天数信息")
            
            # 获取交易记录数量
            trade_records = query_service.get_trade_records(user_id=user_id)
            trade_count = len(trade_records)
            logger.info(f"[ACCOUNT_SUMMARY] 交易记录: 共{trade_count}条记录")
            
            # 构建返回结果
            result = {
                "initial_cash": float(user_info.get('initial_cash', 1000000.0)),
                "current_cash": float(user_info.get('current_cash', 1000000.0)),
                "account_value": realtime_account_value,
                "total_profit": realtime_total_profit,
                "profit_rate": (realtime_total_profit / float(user_info.get('initial_cash', 1000000.0)) * 100) if float(user_info.get('initial_cash', 1000000.0)) > 0 else 0,
                "trade_count": trade_count,
                "positions": positions_with_hold_days,
                "positions_count": len(positions_with_hold_days),
                "positions_value": realtime_positions_value,
                "positions_cost": sum(pos['total_cost'] for pos in positions_with_hold_days.values()),
                "daily_profit_details": daily_profit_details,
                "daily_profit_rates": {date: details['profit_rate'] for date, details in daily_profit_details.items()},
                "last_update": datetime.now().isoformat()
            }
            
            logger.info(f"[ACCOUNT_SUMMARY] 账户概览完成: 用户{user_id}, 账户总值={result['account_value']:,.2f}, 持仓数量={result['positions_count']}, 总盈亏={result['total_profit']:,.2f}")
            return result
        except Exception as e:
            logger.error(f"获取账户概览失败: {str(e)}")
            # 返回默认账户信息
            return {
                "initial_cash": 1000000.0,
                "current_cash": 1000000.0,
                "account_value": 1000000.0,
                "total_profit": 0,
                "profit_rate": 0,
                "trade_count": 0,
                "positions": {},
                "positions_count": 0,
                "positions_value": 0,
                "positions_cost": 0,
                "daily_profit_details": {},
                "daily_profit_rates": {},
                "last_update": datetime.now().isoformat()
            }
    
    def get_position_data(self, user_id: str, symbol: str) -> Dict[str, Any]:
        """
        获取持仓对应的买入信号数据
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            
        Returns:
            Dict: 包含止盈止损等信息的持仓数据
        """
        try:
            # 从交易记录中获取该股票的最新买入记录
            trade_records = query_service.get_trade_records(user_id=user_id, symbol=symbol, action='buy')
            for trade in reversed(trade_records):
                return trade.get('signal_data', {})
            
            return {}
            
        except Exception as e:
            logger.error(f"获取持仓数据失败 {symbol}: {str(e)}")
            return {}
    
    def get_today_trades(self, user_id: str, symbol: str = None, action: str = None) -> List[Dict[str, Any]]:
        """
        获取今天的交易记录
        
        Args:
            user_id: 用户ID
            symbol: 股票代码，如果为None则返回所有股票
            action: 交易动作(buy/sell)，如果为None则返回所有动作
            
        Returns:
            List: 今天的交易记录列表
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 从数据库获取今日交易记录
            trade_records = query_service.get_trade_records(user_id=user_id)
            
            # 过滤今日交易
            today_trades = []
            for trade in trade_records:
                trade_date = trade.get('timestamp', '')[:10] if trade.get('timestamp') else ''
                if trade_date == today:
                    today_trades.append(trade)
            
            # 根据条件过滤
            filtered_trades = today_trades
            if symbol:
                filtered_trades = [t for t in filtered_trades if t.get('symbol') == symbol]
            if action:
                filtered_trades = [t for t in filtered_trades if t.get('action') == action]
            
            return filtered_trades
            
        except Exception as e:
            logger.error(f"获取今日交易记录失败: {str(e)}")
            return []
    
    def has_bought_today(self, user_id: str, symbol: str) -> bool:
        """
        检查今天是否已经买入过指定股票
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            
        Returns:
            bool: 如果今天已经买入过则返回True，否则返回False
        """
        today_buys = self.get_today_trades(user_id=user_id, symbol=symbol, action='buy')
        return len(today_buys) > 0
    
    def _calculate_hold_days(self, user_id: str, positions: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算持仓天数，考虑中间清仓的情况
        
        Args:
            user_id: 用户ID
            positions: 当前持仓信息
            
        Returns:
            Dict: 包含持仓天数的持仓信息
        """
        try:
            positions_with_days = {}
            
            if not positions:
                return positions
            
            # 从数据库获取当前用户的所有交易记录
            all_trades = query_service.get_trade_records(user_id=user_id)
            
            if not all_trades:
                # 如果没有交易记录，使用当前日期作为买入日期
                for symbol, position in positions.items():
                    position_with_days = position.copy()
                    position_with_days['hold_days'] = 1  # 默认1天
                    positions_with_days[symbol] = position_with_days
                return positions_with_days
            
            # 按时间排序交易记录（从早到晚）
            all_trades.sort(key=lambda x: x.get('timestamp', ''))
            
            # 为每个持仓计算持仓天数
            for symbol, position in positions.items():
                position_with_days = position.copy()
                
                # 获取该股票的所有交易记录
                symbol_trades = [trade for trade in all_trades if trade.get('symbol') == symbol]
                
                if not symbol_trades:
                    # 如果没有该股票的交易记录，使用当前日期
                    position_with_days['hold_days'] = 1
                else:
                    # 找到最后一次买入的时间
                    last_buy_time = None
                    current_quantity = 0
                    
                    # 从后往前遍历，找到导致当前持仓的最后一次买入
                    for trade in reversed(symbol_trades):
                        action = trade.get('action')
                        quantity = trade.get('quantity', 0)
                        
                        if action == 'buy':
                            current_quantity += quantity
                            if current_quantity >= position['quantity']:
                                last_buy_time = trade.get('timestamp')
                                break
                        elif action == 'sell':
                            current_quantity -= quantity
                    
                    if last_buy_time:
                        # 计算持仓天数
                        try:
                            buy_date = datetime.fromisoformat(last_buy_time.replace('Z', '+00:00'))
                            current_date = datetime.now()
                            hold_days = (current_date - buy_date).days
                            position_with_days['hold_days'] = max(hold_days, 1)
                        except (ValueError, TypeError):
                            # 如果日期格式有问题，使用默认1天
                            position_with_days['hold_days'] = 1
                    else:
                        # 如果找不到买入记录，使用当前日期
                        position_with_days['hold_days'] = 1
                
                positions_with_days[symbol] = position_with_days
            
            logger.info(f"从数据库计算持仓天数完成，共{len(positions_with_days)}个持仓")
            return positions_with_days
            
        except Exception as e:
            logger.error(f"从数据库计算持仓天数失败: {str(e)}")
            # 出错时使用默认1天
            positions_with_days = {}
            for symbol, position in positions.items():
                position_with_days = position.copy()
                position_with_days['hold_days'] = 1
                positions_with_days[symbol] = position_with_days
            return positions_with_days
    
    
    def _calculate_daily_profit_details(self, user_id: str, kline_data_cache: Dict[str, Dict[str, float]] = None) -> Dict[str, Dict[str, float]]:
        """计算每日盈亏详情，使用数据库中的成交记录，不再读取文件"""
        try:
            daily_details = {}
            
            # 使用传入的K线数据缓存，如果没有则使用成本价
            kline_cache = kline_data_cache or {}
            
            # 从数据库获取当前用户的所有交易记录
            all_trades = query_service.get_trade_records(user_id=user_id)
            
            if not all_trades:
                return daily_details
            
            # 获取用户初始资金
            user_info = self._get_user_account_info(user_id)
            initial_cash = float(user_info.get('initial_cash', 1000000.0))
            
            # 按日期分组交易记录
            trades_by_date = {}
            for trade in all_trades:
                # 从timestamp中提取日期
                trade_date = trade.get('timestamp', '')[:10] if trade.get('timestamp') else ''
                if trade_date:
                    if trade_date not in trades_by_date:
                        trades_by_date[trade_date] = []
                    trades_by_date[trade_date].append(trade)
            
            # 按日期排序
            sorted_dates = sorted(trades_by_date.keys())
            
            # 计算每日盈亏详情，使用缓存的K线数据
            current_positions = {}  # 记录每日收盘时的持仓
            current_value = initial_cash
            
            for date_str in sorted_dates:
                orders = trades_by_date[date_str]
                
                # 处理当日交易，更新持仓
                for order in orders:
                    symbol = order.get('symbol')
                    action = order.get('action')
                    quantity = order.get('quantity', 0)
                    price = order.get('price', 0)
                    
                    if action == 'buy':
                        if symbol not in current_positions:
                            current_positions[symbol] = {'quantity': 0, 'cost': 0}
                        current_positions[symbol]['quantity'] += quantity
                        current_positions[symbol]['cost'] += price * quantity
                    elif action == 'sell':
                        if symbol in current_positions:
                            sell_quantity = min(quantity, current_positions[symbol]['quantity'])
                            if current_positions[symbol]['quantity'] > 0:
                                avg_cost = current_positions[symbol]['cost'] / current_positions[symbol]['quantity']
                                current_positions[symbol]['quantity'] -= sell_quantity
                                current_positions[symbol]['cost'] -= avg_cost * sell_quantity
                                if current_positions[symbol]['quantity'] == 0:
                                    del current_positions[symbol]
                
                # 使用缓存的K线数据计算持仓市值
                daily_market_value = 0
                for symbol, pos in current_positions.items():
                    # 根据当前kline_cache格式：{股票代码: {日期: 收盘价}}
                    symbol_klines = kline_cache.get(symbol, {})
                    close_price = symbol_klines.get(date_str)
                    if close_price is not None:
                        daily_market_value += pos['quantity'] * close_price
                    else:
                        # 使用持仓成本作为近似
                        daily_market_value += pos['quantity'] * (pos['cost'] / pos['quantity'] if pos['quantity'] > 0 else 0)
                
                # 计算当日账户总值（现金 + 持仓市值）
                total_invested = sum(pos['cost'] for pos in current_positions.values())
                cash = initial_cash - total_invested + daily_market_value
                
                # 计算当日盈亏金额和盈亏率
                daily_profit_amount = cash - initial_cash
                daily_profit_rate = 0
                if initial_cash > 0:
                    daily_profit_rate = (daily_profit_amount / initial_cash) * 100
                
                daily_details[date_str] = {
                    'profit_amount': round(daily_profit_amount, 2),
                    'profit_rate': round(daily_profit_rate, 4)
                }
            
            # 添加最近7天的数据（如果有的话）
            if daily_details:
                # 按日期倒序排序，取最近7天
                sorted_dates = sorted(daily_details.keys(), reverse=True)
                recent_details = {date: daily_details[date] for date in sorted_dates[:7]}
                return recent_details
            
            return daily_details
            
        except Exception as e:
            logger.error(f"计算每日盈亏详情失败: {str(e)}")
            return {}
    
    def _get_unified_market_data(self, symbols: List[str], st_date: str = None,ed_date: str = None) -> Dict[str, Any]:
        """统一获取市场数据的方法"""
        try:
            import sys
            import os
            from typing import List
            
            from quant import batch_market_snapshot, quant_get_stock_kline
            
            result = {
                'realtime_data': {},
                'kline_data': {},
                'stock_names': {},
                'lot_size': {}  # 添加每手股数信息
            }
            
            if not symbols:
                return result
            
            # 获取实时行情和股票名称
            realtime_data = batch_market_snapshot(symbols)
            if realtime_data:
                for symbol, data in realtime_data.items():
                    # 转换股票代码格式
                    original_symbol = symbol
                    if '.' in symbol and len(symbol.split('.')) == 2:
                        market, code = symbol.split('.')
                        original_symbol = f"{code}.{market}"
                    
                    result['realtime_data'][original_symbol] = data.get('last_price', 0)
                    result['stock_names'][original_symbol] = data.get('name', original_symbol)
                    result['lot_size'][original_symbol] = data.get('lot_size', 100)  # 获取每手股数，默认100
            
            # 获取历史K线数据
            logger.info(f"开始获取历史K线数据，参数: start={st_date}, end={ed_date}, symbols={symbols}")
            for symbol in symbols:
                try:
                    kline_data = quant_get_stock_kline(symbol, start=st_date, end=ed_date)
 
                    if kline_data is not None:
                        import pandas as pd
                        # 存储完整的时序数据
                        time_series_data = {}
                        
                        if isinstance(kline_data, pd.DataFrame) and not kline_data.empty:
                            # DataFrame格式，按日期存储收盘价
                            for idx, row in kline_data.iterrows():
                                # 优先使用time_key字段，如果没有则使用索引
                                if 'time_key' in row:
                                    date_str = str(row['time_key'])[:10]
                                else:
                                    date_str = str(idx)[:10] if hasattr(idx, 'strftime') else str(idx)
                                time_series_data[date_str] = float(row['close'])
                        elif isinstance(kline_data, list) and len(kline_data) > 0:
                            # 列表格式，按日期存储收盘价
                            for item in kline_data:
                                if isinstance(item, dict) and 'time_key' in item and 'close' in item:
                                    date_str = str(item['time_key'])[:10]
                                    time_series_data[date_str] = float(item['close'])
                                elif isinstance(item, dict) and 'date' in item and 'close' in item:
                                    # 兼容其他接口的date字段
                                    date_str = str(item['date'])[:10]
                                    time_series_data[date_str] = float(item['close'])
                                elif isinstance(item, dict) and 'close' in item:
                                    # 如果没有日期，使用索引
                                    time_series_data[str(len(time_series_data))] = float(item['close'])
                        
                        result['kline_data'][symbol] = time_series_data
                        logger.debug(f"获取{symbol}的时序K线数据成功: {len(time_series_data)}条记录")
                    else:
                        result['kline_data'][symbol] = {}
                    
                except Exception as e:
                    logger.warning(f"获取{symbol}在{st_date}到{ed_date}的K线数据失败: {str(e)}")
                    result['kline_data'][symbol] = {}
                
            
            return result
            
        except Exception as e:
            logger.error(f"统一获取市场数据失败: {str(e)}")
            return {'realtime_data': {}, 'kline_data': {}, 'stock_names': {}}

    def _update_positions_with_realtime_prices(self, positions_data: List[Dict[str, Any]], realtime_data: Dict[str, float], stock_names: Dict[str, str] = None) -> Dict[str, Any]:
        """使用传入的实时价格更新持仓信息
        
        Args:
            positions_data: 用户持仓信息列表
            realtime_data: 实时价格数据
            stock_names: 股票名称映射
            
        Returns:
            Dict: 更新后的持仓信息
        """
        try:
            if not positions_data:
                return {}
            
            updated_positions = {}
            stock_names = stock_names or {}
            
            # 将positions_data转换为字典格式，按symbol分组
            positions_dict = {}
            for pos in positions_data:
                symbol = pos.get('symbol')
                if symbol:
                    positions_dict[symbol] = pos
            
            for symbol, position in positions_dict.items():
                # 获取实时价格，默认使用成本价
                realtime_price = realtime_data.get(symbol, float(position.get('avg_price', 0)))
                stock_name = stock_names.get(symbol, symbol)
                
                # 获取总成本，兼容 total_cost 和 total_value 两种格式
                total_cost = float(position.get('total_cost', position.get('total_value', 0)))
                quantity = float(position.get('quantity', 0))
                
                # 更新持仓信息
                current_value = quantity * realtime_price
                profit_loss = current_value - total_cost
                profit_rate = (profit_loss / total_cost) * 100 if total_cost > 0 else 0
                
                updated_positions[symbol] = {
                    'symbol': symbol,
                    'name': stock_name,
                    'quantity': quantity,
                    'avg_price': float(position.get('avg_price', 0)),
                    'current_price': realtime_price,
                    'total_cost': total_cost,
                    'total_value': current_value,
                    'current_value': current_value,
                    'profit_loss': profit_loss,
                    'profit_rate': profit_rate
                }
            
            return updated_positions
            
        except Exception as e:
            logger.error(f"更新实时股价失败: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return self.positions
    
    def _save_executed_trade(self, user_id: str, trade_record: Dict[str, Any]):
        """保存已执行的交易记录到数据库"""
        try:
            logger.info(f"[SAVE_TRADE_DB] 开始保存交易记录到数据库: {trade_record}")
            
            # 导入TradeRecord模型
            from .storage.models import TradeRecord
            
            # 获取用户费率信息
            user_info = self._get_user_account_info(user_id)
            fee_rate = float(user_info.get('fee_rate', 0.0003))
            
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                get_attr = trade_record.get
            else:
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            # 构建交易记录对象
            trade_obj = TradeRecord(
                user_id=user_id,
                symbol=get_attr('symbol'),
                name=get_attr('name', get_attr('symbol')),
                action=get_attr('action'),
                timestamp=get_attr('timestamp') or datetime.now(),
                trade_date=datetime.now(),
                price=get_attr('price', 0),
                quantity=get_attr('quantity', 0),
                total_cost=get_attr('total_cost') or (get_attr('price', 0) * get_attr('quantity', 0) * (1 + fee_rate)),
                order_id=get_attr('order_id'),
                signal_data=self._build_signal_data(trade_record)
            )
            
            # 使用data_service保存到数据库
            record_id = data_service.save_trade_record(trade_obj)
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                order_id = trade_record.get('order_id')
            else:
                order_id = getattr(trade_record, 'order_id', None)
            logger.info(f"[SAVE_TRADE_DB] 交易记录保存成功到数据库: ID={record_id}, 订单={order_id}")
            
        except Exception as e:
            logger.error(f"[SAVE_TRADE_DB] 保存交易记录到数据库失败: {str(e)}", exc_info=True)
            logger.error(f"[SAVE_TRADE_DB] 失败的交易记录: {trade_record}")
    
    def _build_signal_data(self, trade_record) -> Dict[str, Any]:
        """构建信号数据结构"""
        try:
            logger.debug(f"[BUILD_SIGNAL] 开始构建信号数据: {trade_record}")
            
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                # 字典格式
                get_attr = trade_record.get
            else:
                # 对象格式
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            # 获取信号数据中的价格信息，提供合理的默认值
            signal_data = {
                'symbol': get_attr('symbol'),
                'name': get_attr('name'),
                'buy_price': get_attr('buy_price') or (get_attr('price', 0) * 0.98 if get_attr('price') else None),
                'sell_price': get_attr('sell_price') or (get_attr('price', 0) * 1.02 if get_attr('price') else None),
                'stop_loss': get_attr('stop_loss') or (get_attr('price', 0) * 0.95 if get_attr('price') else None),
                'support': get_attr('support') or (get_attr('price', 0) * 0.98 if get_attr('price') else None),
                'resistance': get_attr('resistance') or (get_attr('price', 0) * 1.02 if get_attr('price') else None),
                'overall_score': get_attr('overall_score') or 0,
                'timestamp': get_attr('signal_timestamp') or get_attr('timestamp'),
                'recommendation': get_attr('recommendation') or 'hold'
            }
            
            # 确保所有价格字段都有值
            if not signal_data['buy_price'] and signal_data['price']:
                signal_data['buy_price'] = round(signal_data['price'] * 0.98, 2)
            if not signal_data['sell_price'] and signal_data['price']:
                signal_data['sell_price'] = round(signal_data['price'] * 1.02, 2)
            if not signal_data['stop_loss'] and signal_data['price']:
                signal_data['stop_loss'] = round(signal_data['price'] * 0.95, 2)
            if not signal_data['support'] and signal_data['price']:
                signal_data['support'] = round(signal_data['price'] * 0.98, 2)
            if not signal_data['resistance'] and signal_data['price']:
                signal_data['resistance'] = round(signal_data['price'] * 1.02, 2)
            
            logger.debug(f"[BUILD_SIGNAL] 信号数据构建完成: {signal_data}")
            return signal_data
            
        except Exception as e:
            logger.error(f"[BUILD_SIGNAL] 构建信号数据异常: {str(e)}", exc_info=True)
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                get_attr = trade_record.get
            else:
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            return {
                'symbol': get_attr('symbol'),
                'name': get_attr('symbol'),
                'buy_price': None,
                'sell_price': None,
                'stop_loss': None,
                'support': None,
                'resistance': None,
                'overall_score': 0,
                'timestamp': get_attr('timestamp'),
                'recommendation': 'hold'
            }
    
    def _build_buy_reason(self, trade_record) -> Dict[str, Any]:
        """构建买入原因分析"""
        try:
            logger.debug(f"[BUILD_BUY_REASON] 开始构建买入原因: {trade_record}")
            
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                get_attr = trade_record.get
            else:
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            current_price = get_attr('price', 0) or 0
            suggested_price = get_attr('buy_price', current_price) or current_price
            
            # 安全计算价格偏离度
            price_deviation = 0
            if suggested_price > 0:
                price_deviation = abs(current_price - suggested_price) / suggested_price * 100
            
            buy_reason = {
                'type': '基于诊断信号买入',
                'price_analysis': {
                    'current_price': current_price,
                    'suggested_buy_price': suggested_price,
                    'price_deviation': round(price_deviation, 2),
                    'price_tolerance': 2.0,
                    'price_status': '在合理范围内' if price_deviation <= 2.0 else '偏离建议价'
                },
                'market_analysis': {
                    'high_price': get_attr('resistance', current_price * 1.05),
                    'low_price': get_attr('support', current_price * 0.95),
                    'price_range': f"{get_attr('support', current_price * 0.95):.2f}-{get_attr('resistance', current_price * 1.05):.2f}",
                    'buy_price_in_range': True,
                    'current_price_in_range': True
                },
                'signal_analysis': {
                    'overall_score': get_attr('overall_score') or 0,
                    'signal_strength': '强' if (get_attr('overall_score') or 0) >= 80 else '中等' if (get_attr('overall_score') or 0) >= 60 else '弱',
                    'diagnosis_timestamp': get_attr('signal_timestamp') or get_attr('timestamp'),
                    'key_factors': [
                        f"支撑位: ¥{get_attr('support', 'N/A')}",
                        f"压力位: ¥{get_attr('resistance', 'N/A')}",
                        f"建议买入价: ¥{get_attr('buy_price', 'N/A')}",
                        f"建议卖出价: ¥{get_attr('sell_price', 'N/A')}",
                        f"止损价: ¥{get_attr('stop_loss', 'N/A')}"
                    ]
                },
                'allocation_analysis': {
                    'available_cash': get_attr('cash_after', 1000000.0),
                    'allocation_ratio': min(10.0, (get_attr('price', 0) * get_attr('quantity', 0) / max(get_attr('cash_after', 1000000.0), 1) * 100)),
                    'allocation_amount': get_attr('price', 0) * get_attr('quantity', 0),
                    'quantity_calculated': get_attr('quantity', 0),
                    'risk_level': '激进' if (get_attr('overall_score') or 0) >= 80 else '稳健' if (get_attr('overall_score') or 0) >= 60 else '保守'
                }
            }
            
            logger.debug(f"[BUILD_BUY_REASON] 买入原因构建完成: {buy_reason}")
            return buy_reason
            
        except Exception as e:
            logger.error(f"[BUILD_BUY_REASON] 构建买入原因异常: {str(e)}", exc_info=True)
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                get_attr = trade_record.get
            else:
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            return {
                'type': '基于诊断信号买入',
                'price_analysis': {'current_price': get_attr('price', 0), 'error': str(e)},
                'signal_analysis': {'overall_score': 0, 'error': str(e)}
            }
    
    def _build_sell_reason(self, trade_record) -> Dict[str, Any]:
        """构建卖出原因分析"""
        try:
            logger.debug(f"[BUILD_SELL_REASON] 开始构建卖出原因: {trade_record}")
            
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                get_attr = trade_record.get
            else:
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            current_price = get_attr('price', 0) or 0
            suggested_price = get_attr('sell_price', current_price) or current_price
            
            # 安全计算价格偏离度
            price_deviation = 0
            if suggested_price > 0:
                price_deviation = abs(current_price - suggested_price) / suggested_price * 100
            
            # 安全计算盈亏率
            avg_cost = trade_record.get('avg_cost', 0) or 0
            profit_rate = 0
            if avg_cost > 0:
                profit_rate = (current_price - avg_cost) / avg_cost * 100
            
            sell_reason = {
                'type': '基于诊断信号卖出',
                'price_analysis': {
                    'current_price': current_price,
                    'suggested_sell_price': suggested_price,
                    'price_deviation': round(price_deviation, 2),
                    'price_tolerance': 2.0,
                    'price_status': '在合理范围内' if price_deviation <= 2.0 else '偏离建议价'
                },
                'market_analysis': {
                    'high_price': get_attr('resistance', current_price * 1.05),
                    'low_price': get_attr('support', current_price * 0.95),
                    'price_range': f"{get_attr('support', current_price * 0.95):.2f}-{get_attr('resistance', current_price * 1.05):.2f}",
                    'sell_price_in_range': True,
                    'current_price_in_range': True
                },
                'signal_analysis': {
                    'overall_score': get_attr('overall_score') or 0,
                    'signal_strength': '强' if (get_attr('overall_score') or 0) >= 80 else '中等' if (get_attr('overall_score') or 0) >= 60 else '弱',
                    'diagnosis_timestamp': get_attr('signal_timestamp') or get_attr('timestamp'),
                    'key_factors': [
                        f"支撑位: ¥{get_attr('support', 'N/A')}",
                        f"压力位: ¥{get_attr('resistance', 'N/A')}",
                        f"建议买入价: ¥{get_attr('buy_price', 'N/A')}",
                        f"建议卖出价: ¥{get_attr('sell_price', 'N/A')}",
                        f"止损价: ¥{get_attr('stop_loss', 'N/A')}"
                    ]
                },
                'profit_analysis': {
                    'avg_cost': avg_cost,
                    'current_price': current_price,
                    'profit_loss': get_attr('profit_loss', 0) or 0,
                    'profit_rate': round(profit_rate, 2),
                    'profit_status': '盈利' if (get_attr('profit_loss', 0) or 0) > 0 else '亏损' if (get_attr('profit_loss', 0) or 0) < 0 else '持平'
                }
            }
            
            logger.debug(f"[BUILD_SELL_REASON] 卖出原因构建完成: {sell_reason}")
            return sell_reason
            
        except Exception as e:
            logger.error(f"[BUILD_SELL_REASON] 构建卖出原因异常: {str(e)}", exc_info=True)
            # 处理不同类型的输入
            if hasattr(trade_record, 'get'):
                get_attr = trade_record.get
            else:
                get_attr = lambda key, default=None: getattr(trade_record, key, default)
            
            return {
                'type': '基于诊断信号卖出',
                'price_analysis': {'current_price': get_attr('price', 0), 'error': str(e)},
                'signal_analysis': {'overall_score': 0, 'error': str(e)}
            }
    
    def _calculate_buy_quantity(self, overall_score: float, current_price: float, available_cash: float, symbol: str, lot_size: int = 100) -> int:
        """
        计算基于评分和可用资金的动态买入数量
        
        Args:
            overall_score: 股票整体评分 (0-100)
            current_price: 当前股票价格
            available_cash: 可用资金
            symbol: 股票代码
            lot_size: 每手股数，默认100股
            
        Returns:
            int: 计算后的买入数量（向下取整到lot_size的倍数）
        """
        try:
            # 参数配置
            max_single_position_ratio = 0.20  # 单只股票最大仓位比例20%
            min_buy_amount = 1000.0  # 最小买入金额1000元
            max_buy_amount = 50000.0  # 最大单笔买入金额50000元
            
            # 安全校验
            if current_price <= 0:
                logger.warning(f"[_calculate_buy_quantity] 股票价格无效: {symbol} 价格{current_price}")
                return 0
            
            if available_cash < min_buy_amount:
                logger.info(f"[_calculate_buy_quantity] 可用资金不足: {symbol} 可用{available_cash:.2f} < 最小{min_buy_amount}")
                return 0
            
            # 评分系数：使用平方关系，评分影响更显著
            # 评分100分 -> 系数1.0，评分50分 -> 系数0.25，评分20分 -> 系数0.04
            score = max(0, min(overall_score, 100))  # 确保评分在0-100范围内
            score_factor = (score / 100.0) ** 2
            
            # 资金系数：使用可用资金的10%，但有上下限
            cash_factor = min(available_cash * 0.10, max_buy_amount)
            
            # 目标买入金额
            target_amount = cash_factor * score_factor
            
            # 实际买入金额：考虑单只股票最大仓位限制和最小买入金额
            max_allowed_amount = available_cash * max_single_position_ratio
            actual_amount = max(
                min(target_amount, max_allowed_amount, available_cash),
                min_buy_amount
            )
            
            # 计算买入数量（向下取整到lot_size的倍数）
            raw_quantity = actual_amount / current_price
            quantity = max(int(raw_quantity / lot_size) * lot_size, lot_size)  # 最小lot_size股
            
            # 最终校验：确保不超过可用资金
            total_cost = quantity * current_price
            if total_cost > available_cash:
                # 如果超出资金，重新计算最大可买数量
                max_quantity = int(available_cash / current_price / lot_size) * lot_size
                quantity = max(max_quantity, 0)
            
            logger.info(f"[_calculate_buy_quantity] 买入数量计算: {symbol} "
                       f"评分{score:.1f} -> 系数{score_factor:.3f}, "
                       f"目标金额{target_amount:.2f}, "
                       f"实际金额{quantity * current_price:.2f}, "
                       f"数量{quantity}股, 每手{lot_size}股")
            
            return quantity
            
        except Exception as e:
            logger.error(f"[_calculate_buy_quantity] 计算买入数量失败: {symbol} 错误{str(e)}")
            return lot_size  # 出错时返回默认每手股数

    def _save_unmet_condition(self, user_id: str, symbol: str, action: str, reason: str, signal_data: Dict[str, Any] = None, details: Dict[str, Any] = None):
        """保存未成功交易的记录到数据库
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            action: 交易动作 (buy/sell)
            reason: 未执行原因
            signal_data: 信号数据
            details: 详细信息
        """
        try:
            logger.info(f"[SAVE_FAILURE_DB] 开始保存失败交易记录到数据库: {symbol} - {action} - {reason}")
            
            # 导入TradeFailure模型
            from .storage.models import TradeFailure
            
            # 构建交易失败记录对象
            failure_obj = TradeFailure(
                user_id=user_id,
                symbol=symbol,
                name=signal_data.get('name', symbol) if signal_data else symbol,
                action=action,
                reason=reason,
                timestamp=datetime.now(),
                trade_date=datetime.now(),
                signal_data=signal_data,
                details=details
            )
            
            # 使用data_service保存到数据库
            record_id = data_service.save_trade_failure(failure_obj)
            logger.info(f"[SAVE_FAILURE_DB] 失败交易记录保存成功到数据库: ID={record_id}, 股票={symbol}, 原因={reason}")
            
        except Exception as e:
            logger.error(f"[SAVE_FAILURE_DB] 保存失败交易记录到数据库失败: {str(e)}", exc_info=True)
           
    def _load_trade_history_from_database(self, user_id: str):
        """从数据库加载交易历史"""
        trades = query_service.get_trade_records(user_id=user_id)
        
        self.trade_history = trades
        self.trade_count = len(trades)
        
        logger.info(f"从数据库加载交易历史完成 - 用户: {user_id}, 共{len(self.trade_history)}条记录")


# 便捷函数
def get_user_unmet_conditions(user_id: str, symbol: str = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    根据用户ID查询该ID下全部未成功交易的记录
    
    Args:
        user_id: 用户ID
        symbol: 股票代码（可选，指定则只查询该股票的记录）
        start_date: 开始日期（格式：YYYY-MM-DD，可选）
        end_date: 结束日期（格式：YYYY-MM-DD，可选）
        
    Returns:
        Dict: 包含用户未成功交易记录的数据
    """
    try:
        if not user_id:
            return {"success": False, "error": "用户ID不能为空", "data": []}
        
        # 使用query_service从数据库查询交易失败记录
        start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        all_unmet = query_service.get_trade_failures(
            user_id=user_id,
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt
        )
        
        # 添加日期信息（从timestamp中提取）
        for record in all_unmet:
            if 'timestamp' in record and record['timestamp']:
                try:
                    trade_date = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                    record['trade_date'] = trade_date.strftime('%Y-%m-%d')
                except:
                    record['trade_date'] = record.get('trade_date', '')
        
        # 按时间排序（最新的在前）
        all_unmet.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # 统计信息
        total_unmet = len(all_unmet)
        buy_unmet = [r for r in all_unmet if r.get('action') == 'buy']
        sell_unmet = [r for r in all_unmet if r.get('action') == 'sell']
        
        # 获取交易的股票列表
        traded_symbols = list(set([r.get('symbol') for r in all_unmet if r.get('symbol')]))
        
        # 获取交易日期范围
        trade_dates = [r.get('trade_date') for r in all_unmet if r.get('trade_date')]
        date_range = {
            "start": min(trade_dates) if trade_dates else None,
            "end": max(trade_dates) if trade_dates else None
        }
        
        logger.info(f"成功获取用户{user_id}的未成功交易记录: 共{total_unmet}条")
        
        return {
            "success": True,
            "user_id": user_id,
            "data": all_unmet,
            "total_unmet": total_unmet,
            "buy_unmet": len(buy_unmet),
            "sell_unmet": len(sell_unmet),
            "traded_symbols": traded_symbols,
            "date_range": date_range,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "message": f"成功获取用户{user_id}的未成功交易记录"
        }
        
    except Exception as e:
        logger.error(f"获取用户{user_id}未成功交易记录失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "data": []
        }


def get_user_trade_history(user_id: str, symbol: str = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    根据用户ID查询该ID下全部的历史交易记录
    
    Args:
        user_id: 用户ID
        symbol: 股票代码（可选，指定则只查询该股票的交易记录）
        start_date: 开始日期（格式：YYYY-MM-DD，可选）
        end_date: 结束日期（格式：YYYY-MM-DD，可选）
        
    Returns:
        Dict: 包含用户历史交易记录的数据
    """
    try:
        if not user_id:
            return {"success": False, "error": "用户ID不能为空", "data": []}
        
        # 使用query_service从数据库查询交易记录
        start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        all_trades = query_service.get_trade_records(
            user_id=user_id,
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt
        )
        
        # 添加日期信息（从timestamp中提取）
        for trade in all_trades:
            if 'timestamp' in trade and trade['timestamp']:
                try:
                    trade_date = datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00'))
                    trade['trade_date'] = trade_date.strftime('%Y-%m-%d')
                except:
                    trade['trade_date'] = trade.get('trade_date', '')
        
        # 按时间排序（最新的在前）
        all_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # 统计信息
        total_trades = len(all_trades)
        buy_trades = [t for t in all_trades if t.get('action') == 'buy']
        sell_trades = [t for t in all_trades if t.get('action') == 'sell']
        
        # 计算总盈亏
        total_profit = 0.0
        for trade in all_trades:
            if trade.get('action') == 'sell' and 'profit_loss' in trade:
                total_profit += float(trade.get('profit_loss', 0))
        
        # 获取交易的股票列表
        traded_symbols = list(set([t.get('symbol') for t in all_trades if t.get('symbol')]))
        
        # 获取交易日期范围
        trade_dates = [t.get('trade_date') for t in all_trades if t.get('trade_date')]
        date_range = {
            "start": min(trade_dates) if trade_dates else None,
            "end": max(trade_dates) if trade_dates else None
        }
        
        logger.info(f"成功获取用户{user_id}的历史交易记录: 共{total_trades}条交易")
        
        return {
            "success": True,
            "user_id": user_id,
            "data": all_trades,
            "total_trades": total_trades,
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_profit": round(total_profit, 2),
            "traded_symbols": traded_symbols,
            "date_range": date_range,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "message": f"成功获取用户{user_id}的历史交易记录"
        }
        
    except Exception as e:
        logger.error(f"获取用户{user_id}历史交易记录失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "data": []
        }


def get_quant_account_summary(user_id: str) -> Dict[str, Any]:
    """
    获取量化交易账户概览
    
    Args:
        user_id: 用户ID
        
    Returns:
        Dict: 账户概览信息
    """
    try:
        simulator = QuantTradingSimulator()
        return simulator.get_account_summary(user_id)
    except Exception as e:
        logger.error(f"获取账户概览失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "获取账户信息失败"
        }

def _get_monitoring_stocks(user_id: str, symbols: List[str] = None) -> List[str]:
    """
    第一步：获取用户监控的股票列表
    
    根据用户ID从用户监控配置中获取股票列表，如果提供了symbols参数则直接使用
    
    Args:
        user_id: 用户ID
        symbols: 可选的股票代码列表，如果提供则直接使用
        
    Returns:
        List[str]: 最终确定的交易股票列表
    """
    if symbols is not None and len(symbols) > 0:
        logger.info(f"[_get_monitoring_stocks] 使用提供的股票列表: {symbols}")
        return symbols
    
    # 从用户监控配置中获取股票列表
    monitor_stocks = get_user_monitor_stocks(user_id)
    logger.info(f"[_get_monitoring_stocks] 从用户{user_id}的监控配置中获取股票列表: {monitor_stocks}")
    
    if not monitor_stocks:
        logger.warning(f"[_get_monitoring_stocks] 用户{user_id}未配置监控股票")
    
    return monitor_stocks


def _get_historical_diagnoses(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    第二步：获取并处理历史诊断报告
    
    使用query_service从数据库查询历史诊断报告，并保留每个股票今日之前最新的诊断报告
    
    Args:
        symbols: 股票代码列表
        
    Returns:
        Dict[str, Dict[str, Any]]: 以股票代码为键的历史诊断报告字典，
                                  每个股票只保留今日之前最新的诊断报告
    """
    from datetime import date
    from typing import Dict, List, Any
    
    if not symbols:
        return {}
    
    logger.info(f"[_get_historical_diagnoses] 开始从数据库批量查询诊断报告...")
    
    # 获取今日日期字符串
    today_str = date.today().strftime("%Y-%m-%d")
    
    # 使用query_service从数据库查询所有诊断报告
    all_diagnosis_reports = query_service.get_diagnosis_reports()
    
    # 按股票代码组织诊断报告，并过滤掉今天的报告
    diagnosis_by_symbol = {}
    
    for report in all_diagnosis_reports:
        symbol = report.get('symbol')
        date_str = report.get('date', '')
        
        # 跳过不在查询列表中的股票
        if symbol not in symbols:
            continue
            
        # 跳过今天的诊断报告
        if date_str == today_str:
            logger.debug(f"跳过今天的诊断报告: {symbol} - {date_str}")
            continue
            
        # 跳过异常结果（评分为0）
        if report.get('overall_score', 0) == 0:
            continue
            
        # 只保留每个股票最新的诊断报告
        if symbol not in diagnosis_by_symbol:
            diagnosis_by_symbol[symbol] = {
                "symbol": symbol,
                "date": date_str,
                "timestamp": report.get('timestamp', ''),
                "diagnosis": report
            }
            logger.debug(f"[_get_historical_diagnoses] 股票{symbol}使用最新诊断报告: "
                       f"日期={date_str}, "
                       f"评分={report.get('overall_score', 0)}")
        else:
            # 如果已有记录，比较日期，保留最新的
            existing_date = diagnosis_by_symbol[symbol]['date']
            if date_str > existing_date:
                diagnosis_by_symbol[symbol] = {
                    "symbol": symbol,
                    "date": date_str,
                    "timestamp": report.get('timestamp', ''),
                    "diagnosis": report
                }
                logger.debug(f"[_get_historical_diagnoses] 股票{symbol}更新为更新诊断报告: "
                           f"日期={date_str}, "
                           f"评分={report.get('overall_score', 0)}")
    
    logger.info(f"[_get_historical_diagnoses] 诊断报告处理完成: "
                f"共{len(symbols)}只股票，有效历史诊断{len(diagnosis_by_symbol)}个（今日之前最新）")
    
    return diagnosis_by_symbol


def _get_user_trade_history(user_id: str) -> List[Dict[str, Any]]:
    """
    第三步：获取用户历史成交记录
    
    使用query_service从数据库查询用户历史全部成交记录，用于后续判断当前用户持仓情况和买卖情况
    
    Args:
        user_id: 用户ID
        
    Returns:
        List[Dict[str, Any]]: 用户历史成交记录列表
    """
    logger.info(f"[_get_user_trade_history] 开始从数据库查询用户历史成交记录...")
    
    # 使用query_service从数据库查询交易记录
    all_trades = query_service.get_trade_records(user_id=user_id)
    
    logger.info(f"[_get_user_trade_history] 历史成交记录查询完成: 共{len(all_trades)}条记录")
    return all_trades


def _validate_market_data(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    第四步：验证行情数据
    
    批量查询最新行情信息，并判断是否当日行情，如果非当日行情，则跳过，并打印相关日志
    
    Args:
        symbols: 股票代码列表
        
    Returns:
        Dict[str, Dict[str, Any]]: 有效的当日行情数据
    """
    from datetime import date, datetime
    from typing import Dict, Any, List
    
    if not symbols:
        logger.warning("[_validate_market_data] 股票列表为空，跳过行情查询")
        return {}
    
    # 获取今日日期
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    
    logger.info(f"[_validate_market_data] 开始批量查询{len(symbols)}只股票的最新行情...")
    
    try:
        from quant import batch_market_snapshot
        
        # 批量查询所有股票的行情数据
        realtime_data = batch_market_snapshot(list(symbols))
        
        if not realtime_data:
            logger.warning("[_validate_market_data] 无法获取实时行情数据，返回空结果")
            return {}
        
        # 统计信息
        total_queried = len(realtime_data)
        valid_count = 0
        skipped_count = 0
        skipped_symbols = []
        
        valid_market_data = {}
        
        # 遍历并验证每个股票的行情数据
        for symbol, market_info in realtime_data.items():
            if not market_info:
                logger.warning(f"[_validate_market_data] 股票{symbol}行情数据为空，跳过")
                skipped_count += 1
                skipped_symbols.append(f"{symbol}(空数据)")
                continue
            
            # 获取行情日期
            market_date = str(market_info.get("update_time", "")).strip()
            
            # 验证日期格式和有效性
            if not market_date:
                logger.warning(f"[_validate_market_data] 股票{symbol}行情数据缺少日期信息，跳过")
                skipped_count += 1
                skipped_symbols.append(f"{symbol}(无日期)")
                continue
            
            # 检查是否为当日行情（只比较日期部分，忽略时间）
            market_date_str = str(market_date).split(' ')[0] if ' ' in str(market_date) else str(market_date)
            if market_date_str != today_str:
                logger.info(f"[_validate_market_data] 跳过非当日行情: {symbol} - "
                           f"行情日期: {market_date_str}, 期望日期: {today_str}")
                skipped_count += 1
                skipped_symbols.append(f"{symbol}({market_date_str})")
                continue
            
            # 验证行情数据完整性
            last_price = market_info.get("last_price")
            if last_price is None or float(last_price) <= 0:
                logger.warning(f"[_validate_market_data] 股票{symbol}行情数据价格无效: {last_price}，跳过")
                skipped_count += 1
                skipped_symbols.append(f"{symbol}(价格无效)")
                continue
            
            # 统一股票代码格式为 600031.SH 格式
            formatted_symbol = symbol
            if '.' in symbol:
                market, code = symbol.split('.')
                formatted_symbol = f"{code}.{market}"
            
            # 添加到有效数据
            valid_market_data[formatted_symbol] = market_info
            valid_count += 1
        
        # 汇总日志
        if skipped_count > 0:
            logger.info(f"[_validate_market_data] 行情数据验证结果: "
                       f"总查询{total_queried}只股票，" 
                       f"有效{valid_count}只，"
                       f"跳过{skipped_count}只")
            
            # 详细记录跳过的股票（限制数量避免日志过长）
            if len(skipped_symbols) <= 10:
                logger.debug(f"[_validate_market_data] 跳过的股票详情: {', '.join(skipped_symbols)}")
            else:
                logger.debug(f"[_validate_market_data] 跳过的股票详情: "
                           f"{', '.join(skipped_symbols[:10])}...等{len(skipped_symbols)}只")
        else:
            logger.info(f"[_validate_market_data] 行情数据验证完成: "
                       f"{valid_count}/{total_queried}只股票数据有效")
        
        return valid_market_data
        
    except ImportError as e:
        logger.error(f"[_validate_market_data] 导入行情查询模块失败: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"[_validate_market_data] 获取实时行情失败: {str(e)}")
        logger.exception("[_validate_market_data] 详细错误信息:")
        return {}


def _execute_trading_decisions(
    user_id: str,
    symbols: List[str],
    historical_diagnoses: Dict[str, Dict[str, Any]],
    valid_market_data: Dict[str, Dict[str, Any]],
    all_trades: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    第五步：执行交易决策
    
    遍历监控股票列表，调用buy_stock和sell_stock方法，
    入参是该股票的诊断报告/行情信息/成交记录
    
    Args:
        user_id: 用户ID
        symbols: 股票代码列表
        historical_diagnoses: 历史诊断报告
        valid_market_data: 有效的行情数据
        all_trades: 用户历史成交记录
        
    Returns:
        List[Dict[str, Any]]: 交易执行结果列表
    """
    simulator = QuantTradingSimulator()
    results = []
    
    logger.info(f"[_execute_trading_decisions] 开始遍历监控股票并执行交易...")

    # 获取持仓明细信息（用于详细分析）
    position_details = query_service.get_position_details(
        user_id=user_id, 
        status='active', 
        active_only=True
    )
    
    # 按股票代码分组持仓明细
    position_details_by_symbol = {}
    for detail in position_details:
        symbol = detail.get('symbol')
        if symbol:
            if symbol not in position_details_by_symbol:
                position_details_by_symbol[symbol] = []
            position_details_by_symbol[symbol].append(detail)
    
    for symbol in symbols:
        try:
            logger.info(f"[_execute_trading_decisions] 开始处理股票: {symbol}")
            
            # 获取该股票的诊断报告
            diagnosis_data = historical_diagnoses.get(symbol)
            logger.info(f"[_execute_trading_decisions] 股票{symbol}的诊断报告数据: {diagnosis_data is not None}")
            if not diagnosis_data:
                logger.info(f"[_execute_trading_decisions] 跳过无诊断报告的股票: {symbol}")
                continue
                
            # 提取实际的诊断内容
            diagnosis = diagnosis_data.get("diagnosis", {})
            logger.info(f"[_execute_trading_decisions] 股票{symbol}的诊断内容: {diagnosis}")
            if not diagnosis:
                logger.info(f"[_execute_trading_decisions] 跳过无诊断内容的股票: {symbol}")
                continue
                
            # 检查诊断报告的评分是否为0，如果为0则认为报告未成功生成
            overall_score = diagnosis.get("overall_score", 0)
            logger.info(f"[_execute_trading_decisions] 股票{symbol}的诊断评分: {overall_score}")
            if overall_score == 0:
                logger.info(f"[_execute_trading_decisions] 跳过评分0的股票: {symbol} - 诊断报告未成功生成")
                continue
            
            # 获取该股票的行情数据
            market_data = valid_market_data.get(symbol)
            logger.info(f"[_execute_trading_decisions] 股票{symbol}的行情数据: {market_data is not None}")
            if not market_data:
                logger.info(f"[_execute_trading_decisions] 跳过无行情数据的股票: {symbol}")
                continue
            
            # 获取该股票的历史成交记录
            symbol_trades = [trade for trade in all_trades if trade.get("symbol") == symbol]
            logger.info(f"[_execute_trading_decisions] 股票{symbol}的历史成交记录数量: {len(symbol_trades)}")
            
            # 构建交易参数
            current_price = float(market_data.get("last_price", 0))     
            
            # 1. 先处理卖出逻辑（基于持仓明细逐笔处理）
            symbol_position_details = position_details_by_symbol.get(symbol, [])
            logger.info(f"[_execute_trading_decisions] 股票{symbol}的持仓明细数量: {len(symbol_position_details)}")
            
            # 初始化卖出标志和数量
            should_sell = False
            sell_quantity = 0
            
            for position_detail in symbol_position_details:
                remaining_qty = float(position_detail.get('remaining_quantity', 0))
                logger.info(f"[_execute_trading_decisions] 股票{symbol}持仓明细 - 剩余数量: {remaining_qty}")
                if remaining_qty <= 0:
                    continue
                
                # 获取该笔持仓的买入价格和诊断数据
                buy_price = float(position_detail.get('buy_price', 0))
                diagnosis_data = position_detail.get('diagnosis_data', {})
                if isinstance(diagnosis_data, str):
                    try:
                        diagnosis_data = json.loads(diagnosis_data)
                    except:
                        diagnosis_data = {}
                
                # 基于该笔持仓的特定条件创建卖出信号
                profit_rate = (current_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
                sell_signal = {
                    "symbol": symbol,
                    "name": diagnosis_data.get("name", symbol),
                    "current_price": current_price,
                    "buy_price": buy_price,
                    "position_detail_id": position_detail.get('id'),
                    "original_quantity": float(position_detail.get('original_quantity', 0)),
                    "remaining_quantity": remaining_qty,
                    "target_price": diagnosis_data.get('target_price') ,
                    "stop_loss": diagnosis_data.get('stop_loss') ,
                    "sell_price": diagnosis_data.get('sell_price'),
                    "support": diagnosis_data.get('support') ,
                    "resistance": diagnosis_data.get('resistance') ,
                    "max_drawdown": diagnosis_data.get('max_drawdown'),
                    "overall_score": diagnosis_data.get("overall_score", 0),
                    "day_low": float(market_data.get("low_price", 0)),
                    "day_high": float(market_data.get("high_price", 0)),
                    "market_data": market_data,
                    "diagnosis": diagnosis_data,
                    "trade_history": symbol_trades,
                    "position_detail": position_detail,
                    "profit_rate": profit_rate
                }
                
                logger.info(f"[_execute_trading_decisions] 股票{symbol}卖出信号参数: 买入价{buy_price}, 当前价{current_price}, 盈亏率{profit_rate:.2f}%, 卖出价{sell_signal.get('sell_price')}, 止损价{sell_signal.get('stop_loss')}")
                
                # 基于持仓明细的卖出决策逻辑
                current_should_sell = False
                current_sell_quantity = remaining_qty
                execution_price = None  # 新增：记录实际执行价格
                sell_reason = None  # 新增：记录卖出原因

                logger.info(f"[_execute_trading_decisions] 股票{symbol}开始卖出决策检查...")
                
                # 1. 基于该笔持仓的卖出价卖出（止盈价）
                sell_price = sell_signal.get('sell_price', 0)
                logger.info(f"[_execute_trading_decisions] 股票{symbol}卖出价检查 - 设定卖出价: {sell_price}, 当前价: {current_price}, 条件满足: {sell_price > 0 and current_price >= sell_price}")
                if sell_price > 0 and current_price >= sell_price:
                    current_should_sell = True
                    execution_price = sell_price
                    sell_reason = f"达到预设卖出价{sell_price}"
                    logger.info(f"[_execute_trading_decisions] 达到卖出价卖出: {symbol} 执行价{execution_price} 当前价{current_price}")
                
                # 2. 基于该笔持仓的止损价卖出
                stop_loss = sell_signal.get('stop_loss', 0)
                logger.info(f"[_execute_trading_decisions] 股票{symbol}止损价检查 - 设定止损价: {stop_loss}, 当前价: {current_price}, 条件满足: {stop_loss > 0 and current_price <= stop_loss}")
                if stop_loss > 0 and current_price <= stop_loss:
                    current_should_sell = True
                    execution_price = stop_loss
                    sell_reason = f"触发止损价{stop_loss}"
                    logger.info(f"[_execute_trading_decisions] 触发止损卖出: {symbol} 执行价{execution_price} 当前价{current_price}")
                
                # 3. 基于整体诊断评分卖出
                # current_score = diagnosis.get("overall_score", 0)
                # logger.info(f"[_execute_trading_decisions] 股票{symbol}评分检查 - 当前评分: {current_score}, 阈值: 45, 条件满足: {current_score < 45}")
                # if current_score < 45:
                #     current_should_sell = True
                #     # 评分过低卖出时，使用卖出价作为执行价，如果没有则使用当前价
                #     execution_price = sell_signal.get('sell_price', 0) or current_price
                #     sell_reason = f"评分过低({current_score}分)"
                #     logger.info(f"[_execute_trading_decisions] 评分过低卖出: {symbol} 评分{current_score} 执行价{execution_price}")
                
                # 4. 基于最大回撤卖出
                max_drawdown = sell_signal.get('max_drawdown')
                if max_drawdown is None or max_drawdown == 0:
                    max_drawdown = 15  # 默认最大回撤为15%
                current_profit_rate = sell_signal.get('profit_rate', 0)
                logger.info(f"[_execute_trading_decisions] 股票{symbol}回撤检查 - 最大回撤: {max_drawdown}%, 当前盈亏: {current_profit_rate:.2f}%, 条件满足: {current_profit_rate < -max_drawdown}")
                if current_profit_rate < -max_drawdown:
                    current_should_sell = True
                    execution_price = current_price  # 回撤卖出时使用实时市场价作为执行价
                    sell_reason = f"触发最大回撤(当前{current_profit_rate:.2f}%, 阈值{max_drawdown}%)"
                    logger.info(f"[_execute_trading_decisions] 触发最大回撤卖出: {symbol} 执行价{execution_price} (实时市场价)")
                
                # 确保有执行价格
                if current_should_sell and execution_price is None:
                    execution_price = sell_signal.get('sell_price', 0) or current_price

                logger.info(f"[_execute_trading_decisions] 股票{symbol}卖出决策结果: {current_should_sell}, 卖出数量: {current_sell_quantity}, 执行价格: {execution_price}, 卖出原因: {sell_reason}")
                
                # 如果当前持仓应该卖出，更新全局卖出标志和数量
                if current_should_sell:
                    should_sell = True
                    sell_quantity = current_sell_quantity
                    
            if should_sell and sell_quantity > 0:
                logger.info(f"[_execute_trading_decisions] 股票{symbol}准备执行卖出 - 卖出数量: {sell_quantity}, 执行价格: {execution_price}")
                # 调用sell_stock方法，使用触发条件的价格而非实时市场价
                result = simulator.sell_stock(
                    user_id=user_id,
                    symbol=symbol,
                    price=execution_price,  # 使用触发条件的价格
                    quantity=sell_quantity,
                    signal_data={**sell_signal, "execution_price": execution_price, "sell_reason": sell_reason}
                )
                
                logger.info(f"[_execute_trading_decisions] 股票{symbol}卖出交易结果: {result}")
                if result.get("success"):
                    results.append(result)
                    logger.info(f"[_execute_trading_decisions] 基于持仓明细卖出成功: {symbol} {sell_quantity}股 (买入价{buy_price:.2f}, 卖出价{execution_price:.2f}, 盈亏{sell_signal.get('profit_rate'):.2f}%)")
                    
                else:
                    logger.info(f"[_execute_trading_decisions] 基于持仓明细卖出未执行: {symbol} - {result.get('error')}")
            
            # 2. 无论是否持仓，都考虑买入逻辑
            buy_price = diagnosis.get("buy_price", current_price)
            if buy_price <= 0:
                buy_price = current_price
            
            logger.info(f"[_execute_trading_decisions] 股票{symbol}买入逻辑 - 设定买入价: {buy_price}, 当前价: {current_price}")
            
            # 获取用户账户信息用于计算买入数量
            user_info = simulator._get_user_account_info(user_id)
            available_cash = float(user_info.get('current_cash', 1000000.0))
            
            # 计算买入数量（基于评分和可用资金的动态算法）
            lot_size = market_data.get('lot_size', 100)  # 获取每手股数
            quantity = simulator._calculate_buy_quantity(
                overall_score=diagnosis.get("overall_score", 50),
                current_price=current_price,
                available_cash=available_cash,
                symbol=symbol,
                lot_size=lot_size
            )
            
            logger.info(f"[_execute_trading_decisions] 股票{symbol}买入计算 - 可用资金: {available_cash}, 每手股数: {lot_size}, 计算买入数量: {quantity}")
            
            buy_signal = {
                "symbol": symbol,
                "name": diagnosis.get("name", symbol),
                "current_price": current_price,
                "buy_price": buy_price,
                "target_price": diagnosis.get("target_price", 0),
                "stop_loss": diagnosis.get("stop_loss", 0),
                "sell_price": diagnosis.get("sell_price", 0),
                "overall_score": diagnosis.get("overall_score", 0),
                "support": diagnosis.get("support", 0),
                "resistance": diagnosis.get("resistance", 0),
                "day_low": float(market_data.get("low_price", 0)),
                "day_high": float(market_data.get("high_price", 0)),
                "market_data": market_data,
                "diagnosis": diagnosis,
                "trade_history": symbol_trades
            }
            
            # 调用buy_stock方法
            logger.info(f"[_execute_trading_decisions] 股票{symbol}准备执行买入 - 买入数量: {quantity}, 买入价格: {buy_price}")
            result = simulator.buy_stock(
                user_id=user_id,
                symbol=symbol,
                price=buy_price,
                quantity=quantity,
                signal_data=buy_signal
            )
            
            if result.get("success"):
                results.append(result)
                logger.info(f"[_execute_trading_decisions] 买入交易成功: {symbol} {quantity}股")
            else:
                logger.info(f"[_execute_trading_decisions] 买入交易未执行: {symbol} - {result.get('error')}")
                    
        except Exception as e:
            logger.error(f"[_execute_trading_decisions] 处理股票{symbol}时发生错误: {str(e)}")
            continue
    
    logger.info(f"[_execute_trading_decisions] 交易执行完成: 总交易{len(results)}笔")
    return results


def execute_daily_quant_trading(user_id: str, symbols: List[str] = None) -> Dict[str, Any]:
    """
    执行每日量化交易（重构后的核心逻辑）
    
    将复杂的交易逻辑分解为五个清晰的步骤：
    1. 获取监控股票列表
    2. 获取并处理诊断报告
    3. 获取历史成交记录
    4. 验证行情数据
    5. 执行交易决策
    
    Args:
        user_id: 用户ID
        symbols: 股票代码列表（可选），如果未提供则从用户监控配置中获取
        
    Returns:
        Dict: 交易执行结果
    """
    try:
        simulator = QuantTradingSimulator()
        
        # 第1步：获取用户监控的股票列表
        symbols = _get_monitoring_stocks(user_id, symbols)
        if not symbols:
            return {
                "success": True,
                "results": [],
                "diagnosis_results": [],
                "trading_signals": [],
                "total_trades": 0,
                "buy_executions": [],
                "sell_executions": [],
                "message": "用户未配置监控股票"
            }
        
        logger.info(f"[execute_daily_quant_trading] 用户{user_id}开始执行量化交易，监控股票数量: {len(symbols)}")
        
        # 第2步：获取并处理诊断报告
        historical_diagnoses = _get_historical_diagnoses(symbols)
        #logger.info(f"获取的历史诊断报告: {json.dumps(historical_diagnoses, indent=2, ensure_ascii=False, default=str)}")
        if not historical_diagnoses:
            return {
                "success": True,
                "results": [],
                "diagnosis_results": [],
                "trading_signals": [],
                "total_trades": 0,
                "buy_executions": [],
                "sell_executions": [],
                "message": "没有有效的历史诊断报告"
            }
        
        valid_diagnoses = list(historical_diagnoses.values())
        
        # 第3步：获取用户历史成交记录
        all_trades = _get_user_trade_history(user_id)
        
        # 第4步：验证行情数据
        valid_market_data = _validate_market_data(historical_diagnoses.keys())
        if not valid_market_data:
            return {
                "success": True,
                "results": [],
                "diagnosis_results": valid_diagnoses,
                "trading_signals": [],
                "total_trades": 0,
                "buy_executions": [],
                "sell_executions": [],
                "message": "没有有效的当日行情数据"
            }
        
        logger.info("[execute_daily_quant_trading] 执行交易决策 start")
        # 第5步：执行交易决策
        results = _execute_trading_decisions(
            user_id=user_id,
            symbols=symbols,
            historical_diagnoses=historical_diagnoses,
            valid_market_data=valid_market_data,
            all_trades=all_trades
        )
        logger.info(f"[execute_daily_quant_trading] 执行交易决策 over ,result:{results}")
        
        # 第6步：更新持仓信息
        if results:
            try:
                from .position_manager import update_user_positions
                position_update_result = update_user_positions(user_id=user_id)
                if position_update_result.get("success"):
                    logger.info(f"[execute_daily_quant_trading] 持仓信息更新成功: {len(position_update_result.get('positions', {}))}个持仓")
                else:
                    logger.error(f"[execute_daily_quant_trading] 持仓信息更新失败: {position_update_result.get('error', '未知错误')}")
            except Exception as e:
                logger.error(f"[execute_daily_quant_trading] 更新持仓信息时发生异常: {str(e)}")
        
        # 统计结果
        def get_trade_action(trade_record):
            if hasattr(trade_record, 'action'):
                return str(trade_record.action)
            else:
                return str(trade_record.get('action', ''))
        
        buy_executions = [r for r in results if r.get("trade_record") and get_trade_action(r.get("trade_record")) == "buy"]
        sell_executions = [r for r in results if r.get("trade_record") and get_trade_action(r.get("trade_record")) == "sell"]
        
        logger.info(f"[execute_daily_quant_trading] 交易执行完成: 总交易{len(results)}笔，买入{len(buy_executions)}笔，卖出{len(sell_executions)}笔")
        
        return {
            "success": True,
            "results": results,
            "diagnosis_results": valid_diagnoses,
            "total_trades": len(results),
            "buy_executions": buy_executions,
            "sell_executions": sell_executions,
            "message": f"交易执行完成: 总交易{len(results)}笔"
        }
        
    except Exception as e:
        logger.error(f"[execute_daily_quant_trading] 执行量化交易失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": [],
            "diagnosis_results": [],
            "trading_signals": [],
            "total_trades": 0,
            "buy_executions": [],
            "sell_executions": [],
            "message": f"执行量化交易失败: {str(e)}"
        }


def get_active_quant_orders(user_id: str) -> Dict[str, Any]:
    """
    获取活跃的量化交易订单（模拟，实际为返回最近的交易记录）
    
    Args:
        user_id: 用户ID
        
    Returns:
        Dict: 活跃订单信息
    """
    try:
        # 获取最近的交易记录作为活跃订单
        history = get_user_trade_history(user_id)
        recent_orders = history.get('data', [])[:10]  # 最近10条
        
        return {
            "success": True,
            "active_orders": recent_orders,
            "count": len(recent_orders)
        }
        
    except Exception as e:
        logger.error(f"获取活跃订单失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "active_orders": []
        }


def clear_active_quant_orders(user_id: str) -> Dict[str, Any]:
    """
    清除活跃的量化交易订单（模拟功能）
    
    Args:
        user_id: 用户ID
        
    Returns:
        Dict: 清除结果
    """
    try:
        return {
            "success": True,
            "message": "活跃订单已清除",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"清除活跃订单失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def buy_stock_with_signal(user_id: str, symbol: str, price: float, quantity: int, signal_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    根据信号买入股票
    
    Args:
        user_id: 用户ID
        symbol: 股票代码
        price: 买入价格
        quantity: 买入数量
        signal_data: 信号数据
        
    Returns:
        Dict: 买入结果
    """
    try:
        simulator = QuantTradingSimulator()
        return simulator.buy_stock(user_id, symbol, price, quantity, signal_data)
        
    except Exception as e:
        logger.error(f"买入股票失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def sell_stock_with_reason(user_id: str, symbol: str, price: float, quantity: int, reason: str = "手动卖出") -> Dict[str, Any]:
    """
    卖出股票（带卖出原因）
    
    Args:
        user_id: 用户ID
        symbol: 股票代码
        price: 卖出价格
        quantity: 卖出数量
        reason: 卖出原因
        
    Returns:
        Dict: 卖出结果
    """
    try:
        simulator = QuantTradingSimulator()
        signal_data = {"reason": reason}
        return simulator.sell_stock(user_id, symbol, price, quantity, signal_data)
        
    except Exception as e:
        logger.error(f"卖出股票失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def get_quant_trade_history(user_id: str, symbol: str = None, limit: int = 50) -> Dict[str, Any]:
    """
    获取量化交易历史（简化版）
    
    Args:
        user_id: 用户ID
        symbol: 股票代码（可选）
        limit: 返回记录数量限制
        
    Returns:
        Dict: 交易历史
    """
    try:
        history = get_user_trade_history(user_id, symbol)
        if history.get('success'):
            trades = history.get('data', [])[:limit]
            return {
                "success": True,
                "trades": trades,
                "count": len(trades)
            }
        else:
            return history
            
    except Exception as e:
        logger.error(f"获取交易历史失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "trades": []
        }


class QuantUserManager:
    """量化交易用户管理器"""
    
    def __init__(self):
        self.users = {}
    
    def get_user_simulator(self, user_id: str) -> QuantTradingSimulator:
        """获取用户的交易模拟器"""
        if user_id not in self.users:
            self.users[user_id] = QuantTradingSimulator()
        return self.users[user_id]
    
    def reset_user(self, user_id: str, initial_cash: float = 1000000.0):
        """重置用户账户"""
        if user_id in self.users:
            del self.users[user_id]
        self.users[user_id] = QuantTradingSimulator()


class QuantTradeExecutor:
    """量化交易执行器类"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.simulator = QuantTradingSimulator()
    
    def execute_trade(self, symbol: str, action: str, price: float, quantity: int, signal_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行交易"""
        if action == 'buy':
            return self.simulator.buy_stock(self.user_id, symbol, price, quantity, signal_data)
        elif action == 'sell':
            return self.simulator.sell_stock(self.user_id, symbol, price, quantity, signal_data)
        else:
            return {"success": False, "error": "无效的交易动作"}
    
    def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息"""
        return self.simulator.get_account_summary(self.user_id)


# 全局服务实例
quant_trading_simulator = QuantTradingSimulator()
quant_user_manager = QuantUserManager()


def get_user_monitor_stocks(user_id: str) -> List[str]:
    """
    基于用户ID查询用户的监控股票列表
    
    Args:
        user_id: 用户ID
        
    Returns:
        List[str]: 用户监控的股票代码列表
    """
    try:
        # 构建监控配置文件路径（在backend目录下）
        monitor_config_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'user_monitor_config.json'
        )
        
        if not os.path.exists(monitor_config_file):
            logger.warning(f"监控配置文件不存在: {monitor_config_file}")
            return []
        
        with open(monitor_config_file, 'r', encoding='utf-8') as f:
            try:
                all_monitor_config = json.load(f)
            except Exception as e:
                logger.error(f"加载监控配置失败: {str(e)}")
                return []
        
        # 获取指定用户的监控配置
        user_config = all_monitor_config.get(user_id, {})
        
        # 提取监控的股票列表
        monitor_stocks = []
        
        # 从stocks字段获取（如果有）
        if 'stocks' in user_config and isinstance(user_config['stocks'], list):
            monitor_stocks.extend(user_config['stocks'])
        
        # 从watchlist字段获取（如果有）
        if 'watchlist' in user_config and isinstance(user_config['watchlist'], list):
            monitor_stocks.extend(user_config['watchlist'])
        
        # 去重并返回
        unique_stocks = list(set(monitor_stocks))
        logger.info(f"用户{user_id}的监控股票列表: {unique_stocks}")
        
        return unique_stocks
        
    except Exception as e:
        logger.error(f"获取用户{user_id}监控股票列表失败: {str(e)}")
        return []
