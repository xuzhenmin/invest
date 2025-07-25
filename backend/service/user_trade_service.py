import time
import uuid
import json
import os
import threading

class UserTradeService:
    """
    用户交易服务，包括账户初始化、持仓、下单、订单历史、撤单、手续费等功能。
    所有数据持久化到本地文件。
    """
    DATA_FILE = 'user_trade_data.json'
    _lock = threading.Lock()

    def __init__(self):
        self.user_accounts = {}
        self.order_history = {}
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
                        if market == 'HK' and code.isdigit():
                            return f"{market}.{code.zfill(5)}"
                        elif market == 'US':
                            return f"US.{code.upper()}"
                        else:
                            return f"{market}.{code}"
                    else:
                        return s
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
            except Exception as e:
                print(f"[UserTradeService] Exception: {e}")
                positions_pnl = {sym: 0.0 for sym in symbols}
                positions_pnl_ratio = {sym: None for sym in symbols}
                total_market_value = 0.0
                total_cost = 0.0
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
            "initial_cash": initial_cash
        }

    def query_orders(self, user_id):
        return self.order_history.get(user_id, [])

    def order(self, user_id, symbol, price, amount, side):
        account = self.user_accounts.get(user_id)
        if not account:
            return {"success": False, "msg": "未找到账户", "account": None}
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
