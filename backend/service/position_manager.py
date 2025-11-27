"""
交易持仓管理器
负责基于历史成交记录计算和更新用户持仓信息
"""

import logging
import json
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from .storage.data_service import data_service
from .storage.query_service import query_service
from .storage.models import Position, PositionDetail, PositionStatus

logger = logging.getLogger(__name__)


class PositionManager:
    """持仓管理器 - 基于历史成交记录计算用户持仓"""
        
    def ensure_user_exists(self, user_id: str) -> bool:
        """
        确保用户存在并初始化资金数据
        
        检查逻辑：
        1. 用户不存在 -> 创建用户并初始化资金（默认100万）
        2. 用户存在但资金数据为None -> 初始化资金（默认100万）
        3. 用户存在但资金数据为0或负数 -> 初始化资金（默认100万）
        4. 用户存在且资金数据正常 -> 跳过初始化
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 用户是否已存在或成功创建/初始化
        """
        try:
            logger.info(f"🔍 [USER_CHECK] 开始检查用户 {user_id} 的资金状态...")
            
            # 检查用户是否存在
            user_info = query_service.get_user_info(user_id)
            
            if user_info is not None:
                logger.info(f"✅ [USER_CHECK] 用户 {user_id} 已存在")
                
                # 获取当前资金数据
                current_cash = user_info.get('current_cash')
                initial_cash_db = user_info.get('initial_cash')
                
                # 判断是否需要初始化资金数据
                need_init = False
                init_reason = ""
                
                # 检查资金数据是否存在
                if current_cash is None or initial_cash_db is None:
                    need_init = True
                    init_reason = "缺少资金数据"
                
                # 检查资金数据是否为0
                elif float(current_cash) <= 0 or float(initial_cash_db) <= 0:
                    need_init = True
                    init_reason = "资金数据为0或负数"
                
                if need_init:
                    logger.warning(f"⚠️ [USER_CHECK] 用户 {user_id} {init_reason}，正在初始化资金...")
                    logger.info(f"📊 [USER_CHECK] 当前资金状态: 初始资金={initial_cash_db}, 当前现金={current_cash}")
                    self._initialize_user_info(user_id)
                    logger.info(f"✅ [USER_CHECK] 用户 {user_id} 资金初始化完成")
                else:
                    logger.info(f"💰 [USER_CHECK] 用户 {user_id} 资金数据正常: 初始资金={float(initial_cash_db):,.2f}, 当前现金={float(current_cash):,.2f}")
                
                return True
            else:
                logger.info(f"⚠️ [USER_CHECK] 用户 {user_id} 不存在，正在创建新用户并初始化资金...")
                self._initialize_user_info(user_id)
                logger.info(f"✅ [USER_CHECK] 用户 {user_id} 创建完成")
                return True
                
        except Exception as e:
            logger.error(f"❌ [USER_CHECK] 检查/创建用户 {user_id} 失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def update_positions_from_history(self, user_id: str = None) -> Dict[str, Any]:
        """
        基于历史成交记录更新用户持仓信息和持仓明细
        
        Args:
            user_id: 用户ID，如果提供则使用该ID，否则使用实例的user_id
            
        Returns:
            Dict: 更新结果，包含持仓信息和统计
        """
        try:
            target_user_id = user_id
            logger.info(f"🚀 [POSITION_UPDATE] 开始为用户 {target_user_id} 更新持仓信息和持仓明细...")
            
            # 0. 确保用户存在并初始化资金数据
            logger.info(f"📋 [POSITION_UPDATE] 步骤0: 确保用户 {target_user_id} 存在并初始化资金数据...")
            user_exists = self.ensure_user_exists(target_user_id)
            if not user_exists:
                logger.error(f"❌ [POSITION_UPDATE] 用户 {target_user_id} 初始化失败")
                return {
                    "success": False,
                    "error": "用户初始化失败",
                    "positions": {},
                    "total_trades": 0,
                    "total_value": 0,
                    "total_cost": 0,
                    "user_id": target_user_id
                }
            logger.info(f"✅ [POSITION_UPDATE] 用户 {target_user_id} 初始化完成")
            
            # 1. 从数据库加载历史成交记录
            logger.info(f"📋 [POSITION_UPDATE] 步骤1: 从数据库加载历史成交记录...")
            trade_history = self._load_trade_history_from_database(target_user_id)
            logger.info(f"📊 [POSITION_UPDATE] 历史成交记录加载完成: 共 {len(trade_history)} 条记录")
            
            if not trade_history:
                logger.warning(f"⚠️ [POSITION_UPDATE] 用户 {target_user_id} 没有历史成交记录")
                logger.info(f"🧹 [POSITION_UPDATE] 清空数据库中的持仓信息和持仓明细...")
                # 清空数据库中的持仓信息和持仓明细
                self._clear_user_positions(target_user_id)
                self._clear_user_position_details(target_user_id)
                logger.info(f"✅ [POSITION_UPDATE] 清空完成")
                return {
                    "success": True,
                    "message": "没有历史成交记录，已初始化用户信息",
                    "positions": {},
                    "total_trades": 0,
                    "total_value": 0,
                    "total_cost": 0,
                    "user_id": target_user_id
                }
            
            # 打印前5条交易记录用于调试
            logger.info(f"📋 [POSITION_UPDATE] 交易记录预览:")
            for i, trade in enumerate(trade_history[:5]):
                logger.info(f"  交易 {i+1}: {trade.get('action')} {trade.get('quantity')}股 {trade.get('symbol')} @ {trade.get('price')}元, 时间: {trade.get('timestamp')}")
            
            # 2. 基于成交记录计算持仓
            logger.info(f"📋 [POSITION_UPDATE] 步骤2: 基于成交记录计算持仓...")
            positions_result = self._calculate_positions_from_trades(trade_history, target_user_id)
            logger.info(f"📊 [POSITION_UPDATE] 持仓计算完成: 共 {len(positions_result['positions'])} 个持仓")
            
            # 打印持仓详情
            for symbol, pos in positions_result['positions'].items():
                logger.info(f"  持仓: {symbol} - 数量: {pos['quantity']}股, 成本价: {pos['avg_price']:.2f}, 总成本: {pos['total_cost']:.2f}")
            
            # 3. 保存更新后的持仓信息到数据库
            logger.info(f"📋 [POSITION_UPDATE] 步骤3: 保存持仓信息到数据库...")
            self._save_positions_to_database(positions_result, target_user_id)
            logger.info(f"✅ [POSITION_UPDATE] 持仓信息保存完成")
            
            # 4. 同步更新持仓明细
            logger.info(f"📋 [POSITION_UPDATE] 步骤4: 同步更新持仓明细...")
            self._update_position_details_from_trades(trade_history, target_user_id)
            
            # 5. 基于持仓信息更新用户资金数据
            logger.info(f"📋 [POSITION_UPDATE] 步骤5: 基于持仓信息更新用户资金数据...")
            self._update_user_account_info(target_user_id, positions_result)
            
            logger.info(f"🎉 [POSITION_UPDATE] 用户 {target_user_id} 持仓更新完成: 共 {len(positions_result['positions'])} 个持仓, 总交易 {positions_result['total_trades']} 次, 当前现金: {positions_result['current_cash']:.2f}, 总持仓价值: {positions_result['total_value']:.2f}")
            
            return {
                "success": True,
                "message": "持仓信息和持仓明细更新成功",
                "user_id": target_user_id,
                **positions_result
            }
            
        except Exception as e:
            logger.error(f"❌ [POSITION_UPDATE] 更新用户 {target_user_id if 'target_user_id' in locals() else self.user_id} 持仓信息失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "positions": {},
                "total_trades": 0,
                "total_value": 0,
                "total_cost": 0,
                "user_id": target_user_id if 'target_user_id' in locals() else self.user_id
            }
    
    def _load_trade_history_from_database(self, user_id: str) -> List[Dict[str, Any]]:
        """
        从数据库加载历史成交记录
        
        Args:
            user_id: 用户ID
            
        Returns:
            List: 历史成交记录列表
        """
        try:
            # 从数据库查询指定用户的所有交易记录
            trade_history = query_service.get_trade_records(user_id=user_id)
            
            # 按时间排序（从早到晚）
            trade_history.sort(key=lambda x: x.get('timestamp', ''))
            
            logger.info(f"从数据库加载用户 {user_id} 历史成交记录完成: 共 {len(trade_history)} 条记录")
            return trade_history
            
        except Exception as e:
            logger.error(f"从数据库加载用户 {user_id} 历史成交记录失败: {str(e)}")
            return []
    
    def _calculate_positions_from_trades(self, trade_history: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """
        基于历史成交记录计算当前持仓
        
        Args:
            trade_history: 历史成交记录列表
            user_id: 用户ID，用于获取用户特定的初始资金和手续费率
            
        Returns:
            Dict: 持仓计算结果
        """
        try:
            # 从数据库获取用户初始资金和手续费率
            user_info = query_service.get_user_info(user_id)
            if user_info:
                user_initial_cash = user_info.get('initial_cash', 1000000.0)
                user_fee_rate = user_info.get('fee_rate', 0.0003)
            else:
                user_initial_cash = 1000000.0
                user_fee_rate = 0.0003
            
            positions = {}
            current_cash = user_initial_cash
            total_trades = len(trade_history)
            
            for trade in trade_history:
                symbol = trade.get('symbol')
                action = trade.get('action')
                price = trade.get('price', 0)
                quantity = trade.get('quantity', 0)
                total_amount = price * quantity
                
                if action == 'buy':
                    # 买入操作
                    fee = total_amount * user_fee_rate
                    total_cost = total_amount + fee
                    
                    if symbol in positions:
                        # 已有持仓，计算加权平均成本
                        old_position = positions[symbol]
                        old_total_cost = old_position['quantity'] * old_position['avg_price']
                        new_total_cost = old_total_cost + total_cost
                        new_quantity = old_position['quantity'] + quantity
                        new_avg_price = new_total_cost / new_quantity if new_quantity > 0 else 0
                        
                        positions[symbol] = {
                            'symbol': symbol,
                            'quantity': new_quantity,
                            'avg_price': new_avg_price,
                            'total_cost': new_total_cost,
                            'last_update': trade.get('timestamp', datetime.now().isoformat())
                        }
                    else:
                        # 新建持仓
                        avg_price = price + (fee / quantity) if quantity > 0 else 0
                        positions[symbol] = {
                            'symbol': symbol,
                            'quantity': quantity,
                            'avg_price': avg_price,
                            'total_cost': total_cost,
                            'last_update': trade.get('timestamp', datetime.now().isoformat())
                        }
                    
                    # 扣减现金
                    current_cash -= total_cost
                    
                elif action == 'sell':
                    # 卖出操作
                    if symbol in positions:
                        fee = total_amount * user_fee_rate
                        net_amount = total_amount - fee
                        
                        old_position = positions[symbol]
                        sell_quantity = min(quantity, old_position['quantity'])
                        
                        if sell_quantity >= old_position['quantity']:
                            # 清仓
                            del positions[symbol]
                        else:
                            # 部分卖出，成本价不变
                            remaining_quantity = old_position['quantity'] - sell_quantity
                            remaining_cost = remaining_quantity * old_position['avg_price']
                            
                            positions[symbol] = {
                                'symbol': symbol,
                                'quantity': remaining_quantity,
                                'avg_price': old_position['avg_price'],
                                'total_cost': remaining_cost,
                                'last_update': trade.get('timestamp', datetime.now().isoformat())
                            }
                        
                        # 增加现金
                        current_cash += net_amount
            
            # 计算持仓总市值
            total_value = sum(pos['total_cost'] for pos in positions.values())
            
            return {
                "positions": positions,
                "total_trades": total_trades,
                "current_cash": current_cash,
                "total_value": total_value,
                "total_cost": total_value,
                "last_update": datetime.now().isoformat(),
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"❌ [CALCULATE_POSITIONS] 计算用户 {user_id} 持仓信息失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "positions": {},
                "total_trades": 0,
                "current_cash": 1000000.0,
                "total_value": 0,
                "total_cost": 0,
                "last_update": datetime.now().isoformat(),
                "user_id": user_id
            }
    
    def _save_positions_to_database(self, positions_data: Dict[str, Any], user_id: str):
        """
        保存持仓信息到数据库
        
        Args:
            positions_data: 持仓数据
            user_id: 用户ID
        """
        try:
            # 1. 先清空该用户的现有持仓
            self._clear_user_positions(user_id)
            
            # 2. 构建持仓对象列表并保存到数据库
            positions = positions_data.get('positions', {})
            position_objects = []
            
            for symbol, pos_data in positions.items():
                position = Position(
                    user_id=user_id,
                    symbol=symbol,
                    name=pos_data.get('name', symbol),  # 如果没有名称，使用代码
                    quantity=pos_data['quantity'],
                    avg_price=pos_data['avg_price'],
                    total_cost=pos_data['total_cost'],
                    market_value=pos_data['total_cost'],  # 初始市值等于成本
                    floating_pnl=0.0,  # 初始浮动盈亏为0
                    floating_pnl_ratio=0.0,  # 初始浮动盈亏率为0
                    last_price=pos_data['avg_price']  # 初始最新价格等于平均成本
                )
                position_objects.append(position)
            
            # 3. 批量保存到数据库
            if position_objects:
                data_service.batch_save_positions(position_objects)
            
            logger.info(f"用户 {user_id} 持仓信息已保存到数据库: 共 {len(position_objects)} 个持仓")
            
        except Exception as e:
            logger.error(f"保存用户 {user_id} 持仓信息到数据库失败: {str(e)}")
    
    def _create_position_detail_from_trade(self, trade: Dict[str, Any], 
                                         diagnosis_data: Dict[str, Any] = None,
                                         user_id: str = None) -> PositionDetail:
        """
        从交易记录创建持仓明细
        
        Args:
            trade: 交易记录
            diagnosis_data: 诊断数据
            user_id: 用户ID，如果提供则使用该ID，否则使用实例的user_id
            
        Returns:
            PositionDetail: 持仓明细对象
        """
        target_user_id = user_id or self.user_id
        return PositionDetail(
            user_id=target_user_id,
            symbol=trade.get('symbol'),
            name=trade.get('name', trade.get('symbol')),
            original_quantity=trade.get('quantity', 0),
            remaining_quantity=trade.get('quantity', 0),
            buy_price=trade.get('price', 0.0),
            total_cost=trade.get('total_cost', 0.0),
            buy_date=trade.get('trade_date', datetime.now()),
            buy_order_id=trade.get('order_id', ''),
            diagnosis_data=diagnosis_data or trade.get('signal_data', {}),
            target_price=diagnosis_data.get('target_price') if diagnosis_data else None,
            stop_loss=diagnosis_data.get('stop_loss') if diagnosis_data else None,
            support=diagnosis_data.get('support') if diagnosis_data else None,
            resistance=diagnosis_data.get('resistance') if diagnosis_data else None,
            sell_price=diagnosis_data.get('sell_price') if diagnosis_data else None,
            max_drawdown=diagnosis_data.get('max_drawdown') if diagnosis_data else None,
            status=PositionStatus.ACTIVE.value,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def _update_position_details_from_trades(self, trade_history: List[Dict[str, Any]], user_id: str = None):
        """
        基于交易历史更新持仓明细
        
        Args:
            trade_history: 交易历史
            user_id: 用户ID，如果提供则使用该ID，否则使用实例的user_id
        """
        try:
            target_user_id = user_id or self.user_id
            logger.info(f"=== 开始更新用户 {target_user_id} 的持仓明细 ===")
            
            # 1. 清空指定用户的现有持仓明细
            logger.info(f"步骤1: 清空用户 {target_user_id} 的现有持仓明细")
            self._clear_user_position_details(target_user_id)
            
            # 2. 获取所有交易记录（包括买入和卖出）
            all_trades = trade_history
            logger.info(f"步骤2: 获取交易记录完成，共 {len(all_trades)} 条记录")
            
            if not all_trades:
                logger.warning(f"用户 {target_user_id} 没有任何交易记录")
                return
            
            # 3. 按股票代码分组处理交易
            trades_by_symbol = {}
            for trade in all_trades:
                symbol = trade.get('symbol')
                if symbol not in trades_by_symbol:
                    trades_by_symbol[symbol] = []
                trades_by_symbol[symbol].append(trade)
            
            logger.info(f"步骤3: 按股票代码分组完成，共 {len(trades_by_symbol)} 只股票有交易记录")
            for symbol, trades in trades_by_symbol.items():
                logger.debug(f"  股票 {symbol}: {len(trades)} 条交易记录")
            
            # 4. 为每个股票处理持仓明细
            position_details = []
            total_processed_trades = 0
            
            for symbol, symbol_trades in trades_by_symbol.items():
                logger.info(f"=== 处理股票 {symbol} 的交易记录 ===")
                
                # 按时间排序交易记录
                symbol_trades.sort(key=lambda x: x.get('timestamp', ''))
                logger.info(f"股票 {symbol}: 共 {len(symbol_trades)} 条交易记录，按时间排序完成")
                
                # 打印所有交易记录详情
                for i, trade in enumerate(symbol_trades):
                    logger.debug(f"  交易 {i+1}: {trade.get('action')} {trade.get('quantity')}股 @ {trade.get('price')}元, 时间: {trade.get('timestamp')}")
                
                # 使用FIFO方法处理买入卖出匹配
                all_buy_records = []  # 存储所有买入记录，包括已完全卖出的
                buy_queue = []  # 用于FIFO匹配的买入队列
                
                for trade in symbol_trades:
                    action = trade.get('action')
                    quantity = trade.get('quantity', 0)
                    price = trade.get('price', 0)
                    timestamp = trade.get('timestamp', '')
                    
                    logger.info(f"处理交易: {action} {quantity}股 @ {price}元, 时间: {timestamp}")
                    
                    if action == 'buy':
                        # 买入交易：创建买入记录并添加到两个队列
                        buy_item = {
                            'trade': trade,
                            'remaining_quantity': quantity,
                            'sell_records': []  # 存储与该买入记录相关的卖出记录
                        }
                        buy_queue.append(buy_item)
                        all_buy_records.append(buy_item)  # 添加到所有买入记录列表
                        logger.info(f"  买入交易加入队列: {quantity}股, 队列长度: {len(buy_queue)}, 总买入记录: {len(all_buy_records)}")
                        
                    elif action == 'sell':
                        # 卖出交易：匹配之前的买入记录，并记录卖出信息
                        sell_quantity = quantity
                        sell_price = price
                        sell_date = trade.get('trade_date', datetime.now())
                        sell_order_id = trade.get('order_id', '')
                        
                        logger.info(f"  开始处理卖出: {sell_quantity}股 @ {sell_price}元, 当前买入队列: {len(buy_queue)} 条记录")
                        
                        # 处理卖出匹配
                        remaining_sell_quantity = sell_quantity
                        matched_count = 0
                        
                        while remaining_sell_quantity > 0 and buy_queue:
                            buy_item = buy_queue[0]
                            buy_trade = buy_item['trade']
                            available_buy_quantity = buy_item['remaining_quantity']
                            
                            # 计算本次匹配的卖出数量
                            matched_quantity = min(remaining_sell_quantity, available_buy_quantity)
                            
                            logger.info(f"    匹配卖出: {matched_quantity}股 (卖出剩余: {remaining_sell_quantity}, 买入可用: {available_buy_quantity})")
                            
                            # 创建卖出记录
                            sell_record = {
                                'sell_quantity': matched_quantity,
                                'sell_price': sell_price,
                                'sell_date': sell_date.isoformat() if hasattr(sell_date, 'isoformat') else str(sell_date),
                                'sell_order_id': sell_order_id,
                                'original_buy_order_id': buy_trade.get('order_id', ''),
                                'original_buy_price': buy_trade.get('price', 0.0),
                                'original_buy_date': buy_trade.get('trade_date', '').isoformat() if hasattr(buy_trade.get('trade_date', ''), 'isoformat') else str(buy_trade.get('trade_date', ''))
                            }
                            
                            # 将卖出记录添加到对应的买入记录中
                            buy_item['sell_records'].append(sell_record)
                            
                            # 更新买入记录的剩余数量
                            buy_item['remaining_quantity'] -= matched_quantity
                            
                            # 如果买入记录已完全卖出，从匹配队列中移除，但保留在所有记录中
                            if buy_item['remaining_quantity'] <= 0:
                                removed_item = buy_queue.pop(0)
                                logger.info(f"    买入记录已完全卖出，从匹配队列移除但保留记录: {removed_item['trade'].get('quantity')}股, 卖出记录: {len(removed_item['sell_records'])}条")
                            else:
                                logger.info(f"    买入记录剩余: {buy_item['remaining_quantity']}股, 卖出记录: {len(buy_item['sell_records'])}条")
                            
                            # 更新剩余卖出数量
                            remaining_sell_quantity -= matched_quantity
                            matched_count += 1
                        
                        if remaining_sell_quantity > 0:
                            logger.warning(f"  警告: 卖出数量 {sell_quantity}股 超过可用买入数量，剩余 {remaining_sell_quantity}股 无法匹配")
                        
                        logger.info(f"  卖出处理完成: 共匹配 {matched_count} 次，剩余卖出: {remaining_sell_quantity}股")
                
                # 5. 为所有买入记录创建持仓明细（包括已完全卖出的记录）
                logger.info(f"股票 {symbol}: 处理完成后，总买入记录 {len(all_buy_records)} 条记录")
                
                for i, buy_item in enumerate(all_buy_records):
                    buy_trade = buy_item['trade']
                    remaining_quantity = buy_item['remaining_quantity']
                    original_quantity = buy_trade.get('quantity', 0)
                    
                    logger.info(f"  处理买入记录 {i+1}: 原始 {original_quantity}股, 剩余 {remaining_quantity}股")
                    
                    # 获取对应的诊断数据
                    diagnosis_data = None
                    latest_diagnosis = query_service.get_latest_diagnosis(symbol)
                    if latest_diagnosis:
                        diagnosis_data = {
                            'target_price': latest_diagnosis.get('target_price'),
                            'stop_loss': latest_diagnosis.get('stop_loss'),
                            'support': latest_diagnosis.get('support'),
                            'resistance': latest_diagnosis.get('resistance'),
                            'sell_price': latest_diagnosis.get('sell_price'),
                            'max_drawdown': latest_diagnosis.get('max_drawdown'),
                            **(buy_trade.get('signal_data', {}))
                        }
                    
                    # 计算已卖出数量和卖出总额
                    sell_records = buy_item['sell_records']
                    total_sold_quantity = sum(record['sell_quantity'] for record in sell_records)
                    total_sold_amount = sum(record['sell_quantity'] * record['sell_price'] for record in sell_records)
                    
                    # 确定持仓状态
                    sold_quantity = original_quantity - remaining_quantity
                    if sold_quantity == 0:
                        status = PositionStatus.ACTIVE.value
                    elif sold_quantity > 0 and remaining_quantity > 0:
                        status = PositionStatus.PARTIAL_SOLD.value
                    else:
                        status = PositionStatus.CLOSED.value
                    
                    # 创建持仓明细，保留所有记录包括已完全卖出的
                    position_detail = PositionDetail(
                        user_id=target_user_id,
                        symbol=buy_trade.get('symbol'),
                        name=buy_trade.get('name', buy_trade.get('symbol')),
                        original_quantity=original_quantity,
                        remaining_quantity=remaining_quantity,
                        buy_price=buy_trade.get('price', 0.0),
                        total_cost=buy_trade.get('total_cost', 0.0),
                        buy_date=buy_trade.get('trade_date', datetime.now()),
                        buy_order_id=buy_trade.get('order_id', ''),
                        diagnosis_data=diagnosis_data or buy_trade.get('signal_data', {}),
                        target_price=diagnosis_data.get('target_price') if diagnosis_data else None,
                        stop_loss=diagnosis_data.get('stop_loss') if diagnosis_data else None,
                        support=diagnosis_data.get('support') if diagnosis_data else None,
                        resistance=diagnosis_data.get('resistance') if diagnosis_data else None,
                        sell_price=diagnosis_data.get('sell_price') if diagnosis_data else None,
                        max_drawdown=diagnosis_data.get('max_drawdown') if diagnosis_data else None,
                        status=status,
                        sell_records=sell_records,  # 存储卖出记录
                        closed_date=datetime.now() if status == PositionStatus.CLOSED.value else None,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    position_details.append(position_detail)
                    
                    logger.info(f"    创建持仓明细: {symbol} {remaining_quantity}股 (原始 {original_quantity}股, 已卖出 {total_sold_quantity}股, 卖出总额: {total_sold_amount:.2f}元, 卖出记录: {len(sell_records)}条, 状态: {status})")
                
                total_processed_trades += len(symbol_trades)
            
            # 6. 批量保存持仓明细
            logger.info(f"=== 准备保存持仓明细 ===")
            logger.info(f"总共需要保存的持仓明细记录: {len(position_details)} 条")
            
            if position_details:
                data_service.batch_save_position_details(position_details)
                logger.info(f"✅ 用户 {target_user_id} 持仓明细已保存到数据库: 共 {len(position_details)} 条记录")
            else:
                logger.info(f"ℹ️ 用户 {target_user_id} 没有需要保存的持仓明细")
            
            logger.info(f"=== 用户 {target_user_id} 持仓明细更新完成 ===")
            
        except Exception as e:
            logger.error(f"❌ 更新用户 {user_id or self.user_id} 持仓明细失败: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _clear_user_position_details(self, user_id: str):
        """
        清空指定用户的所有持仓明细
        
        Args:
            user_id: 用户ID
        """
        try:
            query = "DELETE FROM position_details WHERE user_id = ?"
            from .storage.database_manager import db_manager
            db_manager.execute_update(query, (user_id,))
            logger.info(f"已清空用户 {user_id} 的持仓明细")
        except Exception as e:
            logger.error(f"清空用户 {user_id} 持仓明细失败: {str(e)}")
    
    def _clear_user_positions(self, user_id: str):
        """
        清空指定用户的所有持仓信息
        
        Args:
            user_id: 用户ID
        """
        try:
            query = "DELETE FROM positions WHERE user_id = ?"
            from .storage.database_manager import db_manager
            db_manager.execute_update(query, (user_id,))
            logger.info(f"已清空用户 {user_id} 的持仓信息")
        except Exception as e:
            logger.error(f"清空用户 {user_id} 持仓信息失败: {str(e)}")
    
    def _initialize_user_info(self, user_id: str):
        """
        初始化用户信息（当用户没有历史成交记录时）
        
        Args:
            user_id: 用户ID
        """
        try:
            from .storage.models import UserInfo
            
            # 获取用户的初始资金配置
            initial_cash = 1000000.0
            
            # 创建用户信息对象
            user_info = UserInfo(
                user_id=user_id,
                username=user_id,  # 默认使用user_id作为用户名
                initial_cash=initial_cash,
                current_cash=initial_cash,
                total_assets=initial_cash,
                total_profit=0.0,
                total_profit_ratio=0.0,
                trade_count=0,
                fee_rate=0.0003,
                status="active"
            )
            
            # 使用data_service保存用户信息到数据库
            data_service.save_user_info(user_info)
            
            logger.info(f"已初始化用户 {user_id} 的信息到数据库: 初始资金 {initial_cash}")
            
        except Exception as e:
            logger.error(f"初始化用户 {user_id} 信息失败: {str(e)}")
    
    def get_current_positions(self, user_id: str) -> Dict[str, Any]:
        """
        获取当前持仓信息（从数据库查询）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 当前持仓信息
        """
        try:
            # 从数据库获取用户信息
            user_info = query_service.get_user_info(user_id)
            if not user_info:
                logger.warning(f"用户 {user_id} 不存在")
                return {
                    "success": False,
                    "error": "用户不存在",
                    "positions": {},
                    "total_value": 0,
                    "current_cash": 0,
                    "total_trades": 0
                }
            
            # 从数据库查询当前用户的持仓信息
            positions = query_service.get_positions(user_id=user_id)
            
            if not positions:
                logger.info(f"用户 {user_id} 当前没有持仓")
                return {
                    "success": True,
                    "message": "当前没有持仓",
                    "positions": {},
                    "total_value": 0,
                    "current_cash": user_info.get('current_cash', 0),
                    "total_trades": user_info.get('trade_count', 0),
                    "last_update": datetime.now().isoformat()
                }
            
            # 计算总持仓市值和总成本
            total_value = sum(pos['market_value'] for pos in positions)
            total_cost = sum(pos['total_cost'] for pos in positions)
            
            # 构建持仓字典
            positions_dict = {}
            for pos in positions:
                symbol = pos['symbol']
                positions_dict[symbol] = {
                    'symbol': symbol,
                    'quantity': pos['quantity'],
                    'avg_price': pos['avg_price'],
                    'total_cost': pos['total_cost'],
                    'market_value': pos['market_value'],
                    'floating_pnl': pos['floating_pnl'],
                    'floating_pnl_ratio': pos['floating_pnl_ratio'],
                    'last_price': pos['last_price'],
                    'last_update': pos['updated_at']
                }
            
            return {
                "success": True,
                "positions": positions_dict,
                "total_value": total_value,
                "total_cost": total_cost,
                "current_cash": user_info.get('current_cash'),
                "total_trades": user_info.get('trade_count', 0),
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"从数据库获取当前持仓信息失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "positions": {},
                "total_value": 0,
                "current_cash": 0,
                "total_trades": 0
            }
    
    def get_position_details(self, user_id: str, symbol: str = None, status: str = None, 
                           active_only: bool = True) -> Dict[str, Any]:
        """
        获取持仓明细记录
        
        Args:
            user_id: 用户ID
            symbol: 股票代码，如果为None则获取所有股票的持仓明细
            status: 持仓状态 ('active', 'partial_sold', 'closed', 'cancelled')
            active_only: 是否只返回活跃持仓（remaining_quantity > 0）
            
        Returns:
            Dict: 持仓明细信息，包含详细记录和汇总统计
        """
        try:
            # 调用query_service的get_position_details方法
            position_details = query_service.get_position_details(
                user_id=user_id,
                symbol=symbol,
                status=status,
                active_only=active_only
            )
            
            if not position_details:
                logger.info(f"用户 {user_id} 没有持仓明细记录")
                return {
                    "success": True,
                    "message": "没有持仓明细记录",
                    "position_details": [],
                    "summary": {},
                    "user_id": user_id
                }
            
            # 获取汇总信息
            summary = query_service.get_position_detail_summary(
                user_id=user_id,
                symbol=symbol
            )
            
            logger.info(f"用户 {user_id} 持仓明细查询完成: 共 {len(position_details)} 条记录")
            
            return {
                "success": True,
                "position_details": position_details,
                "summary": summary,
                "user_id": user_id,
                "query_params": {
                    "symbol": symbol,
                    "status": status,
                    "active_only": active_only
                }
            }
            
        except Exception as e:
            logger.error(f"获取持仓明细失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "position_details": [],
                "summary": {},
                "user_id": user_id
            }
    
    def get_position_detail_by_id(self, position_id: int) -> Dict[str, Any]:
        """
        根据ID获取单个持仓明细记录
        
        Args:
            position_id: 持仓明细ID
            
        Returns:
            Dict: 单个持仓明细信息
        """
        try:
            # 调用query_service的get_position_detail_by_id方法
            position_detail = query_service.get_position_detail_by_id(position_id)
            
            if not position_detail:
                return {
                    "success": False,
                    "error": "未找到指定的持仓明细记录",
                    "position_detail": None
                }
            
            return {
                "success": True,
                "position_detail": position_detail
            }
            
        except Exception as e:
            logger.error(f"获取持仓明细记录失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "position_detail": None
            }
    
    def get_position_detail_by_order_id(self, buy_order_id: str) -> Dict[str, Any]:
        """
        根据买入订单ID获取持仓明细记录
        
        Args:
            buy_order_id: 买入订单ID
            
        Returns:
            Dict: 持仓明细信息
        """
        try:
            # 调用query_service的get_position_detail_by_order_id方法
            position_detail = query_service.get_position_detail_by_order_id(buy_order_id)
            
            if not position_detail:
                return {
                    "success": False,
                    "error": "未找到指定订单的持仓明细记录",
                    "position_detail": None
                }
            
            return {
                "success": True,
                "position_detail": position_detail
            }
            
        except Exception as e:
            logger.error(f"根据订单ID获取持仓明细失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "position_detail": None
            }
    
    def _update_user_account_info(self, user_id: str, positions_result: Dict[str, Any]):
        """
        基于持仓信息更新用户资金数据
        
        Args:
            user_id: 用户ID
            positions_result: 持仓计算结果，包含positions、current_cash、total_value等信息
        """
        try:
            logger.info(f"💰 [UPDATE_USER_ACCOUNT] 开始更新用户 {user_id} 的资金数据...")
            
            # 从positions_result获取数据
            positions = positions_result.get('positions', {})
            current_cash = positions_result.get('current_cash', 0.0)
            total_value = positions_result.get('total_value', 0.0)
            total_trades = positions_result.get('total_trades', 0)
            
            # 计算总资产
            total_assets = current_cash + total_value
            
            # 从数据库获取用户初始资金
            user_info = query_service.get_user_info(user_id)
            if user_info:
                initial_cash = user_info.get('initial_cash', 1000000.0)
            else:
                initial_cash = 1000000.0
                logger.warning(f"用户 {user_id} 信息不存在，使用默认初始资金: {initial_cash}")
            
            # 计算总盈亏
            total_profit = total_assets - initial_cash
            
            # 计算盈亏率
            total_profit_ratio = 0.0
            if initial_cash > 0:
                total_profit_ratio = (total_profit / initial_cash) * 100
            
            logger.info(f"💰 [UPDATE_USER_ACCOUNT] 用户资金数据计算完成:")
            logger.info(f"  初始资金: {initial_cash:,.2f}")
            logger.info(f"  当前现金: {current_cash:,.2f}")
            logger.info(f"  持仓市值: {total_value:,.2f}")
            logger.info(f"  总资产: {total_assets:,.2f}")
            logger.info(f"  总盈亏: {total_profit:,.2f}")
            logger.info(f"  盈亏率: {total_profit_ratio:.2f}%")
            logger.info(f"  交易次数: {total_trades}")
            
            # 更新用户账户信息到数据库
            success = data_service.update_user_account(
                user_id=user_id,
                current_cash=current_cash,
                total_assets=total_assets,
                total_profit=total_profit,
                total_profit_ratio=total_profit_ratio,
                trade_count=total_trades
            )
            
            if success:
                logger.info(f"✅ [UPDATE_USER_ACCOUNT] 用户 {user_id} 资金数据更新成功")
            else:
                logger.error(f"❌ [UPDATE_USER_ACCOUNT] 用户 {user_id} 资金数据更新失败")
                
        except Exception as e:
            logger.error(f"❌ [UPDATE_USER_ACCOUNT] 更新用户 {user_id} 资金数据失败: {str(e)}")
            logger.error(traceback.format_exc())
    
    def recalculate_all_positions(self, user_id: str, initial_cash: float = None) -> Dict[str, Any]:
        """
        重新计算所有持仓（用于数据修复）
        
        Args:
            user_id: 用户ID
            initial_cash: 初始资金，如果提供则覆盖默认值
            
        Returns:
            Dict: 重新计算结果
        """
        if initial_cash is not None:
            # 更新用户初始资金
            data_service.update_user_account(user_id, initial_cash=initial_cash)
        
        return self.update_positions_from_history(user_id)


def update_user_positions(user_id: str, initial_cash: float = None) -> Dict[str, Any]:
    """
    更新用户持仓信息的便捷函数
    
    Args:
        user_id: 用户ID
        initial_cash: 初始资金（可选）
        
    Returns:
        Dict: 更新结果
    """
    manager = PositionManager()
    if initial_cash is not None:
        data_service.update_user_account(user_id, initial_cash=initial_cash)
    
    return manager.update_positions_from_history(user_id)


def get_user_positions(user_id: str) -> Dict[str, Any]:
    """
    获取用户当前持仓信息的便捷函数
    
    Args:
        user_id: 用户ID
        
    Returns:
        Dict: 当前持仓信息
    """
    manager = PositionManager()
    return manager.get_current_positions(user_id)


def get_user_position_details(user_id: str, symbol: str = None, status: str = None, 
                            active_only: bool = True) -> Dict[str, Any]:
    """
    获取用户持仓明细的便捷函数
    
    Args:
        user_id: 用户ID
        symbol: 股票代码，如果为None则获取所有股票的持仓明细
        status: 持仓状态 ('active', 'partial_sold', 'closed', 'cancelled')
        active_only: 是否只返回活跃持仓（remaining_quantity > 0）
        
    Returns:
        Dict: 持仓明细信息
    """
    manager = PositionManager()
    return manager.get_position_details(user_id, symbol=symbol, status=status, active_only=active_only)


def get_position_detail_by_id(user_id: str, position_id: int) -> Dict[str, Any]:
    """
    根据ID获取单个持仓明细记录的便捷函数
    
    Args:
        user_id: 用户ID
        position_id: 持仓明细ID
        
    Returns:
        Dict: 单个持仓明细信息
    """
    manager = PositionManager()
    return manager.get_position_detail_by_id(position_id)


def get_position_detail_by_order_id(user_id: str, buy_order_id: str) -> Dict[str, Any]:
    """
    根据买入订单ID获取持仓明细记录的便捷函数
    
    Args:
        user_id: 用户ID
        buy_order_id: 买入订单ID
        
    Returns:
        Dict: 持仓明细信息
    """
    manager = PositionManager()
    return manager.get_position_detail_by_order_id(buy_order_id)


def recalculate_user_positions(user_id: str, initial_cash: float = None) -> Dict[str, Any]:
    """
    重新计算用户所有持仓的便捷函数
    
    Args:
        user_id: 用户ID
        initial_cash: 初始资金（可选）
        
    Returns:
        Dict: 重新计算结果
    """
    manager = PositionManager()
    return manager.recalculate_all_positions(user_id, initial_cash)
