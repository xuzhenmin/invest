from flask import Flask, jsonify, request, session
from flask_cors import CORS
from futu import OpenQuoteContext, RET_OK, KLType, AuType, PeriodType # 添加 PeriodType
from futu.common.constant import OptionType, SecurityType # 从正确的路径导入 OptionType 和 SecurityType
import pandas as pd
from datetime import datetime, timedelta
import logging
import traceback
import akshare as ak
import numpy as np
import requests
import json
import os
from dotenv import load_dotenv
try:
    import talib
except ImportError:
    talib = None
import sys
sys.path.append(os.path.dirname(__file__))
import threading
import time

# 强制导入quant.py相关方法，确保batch_market_snapshot可用
from quant import get_stock_list, get_stock_capital_flow, get_stock_financials, quant_get_stock_kline, get_stock_news, batch_market_snapshot, get_hk_minute_data, analyze_fundamental, load_latest_smart_monitor_signals, load_all_smart_monitor_signals, get_order_book, get_rt_ticker

try:
    from quant import get_stock_list, get_stock_capital_flow, get_stock_financials, quant_get_stock_kline, get_stock_news, batch_market_snapshot, get_hk_minute_data
except ImportError:
    get_stock_list = None
    get_stock_capital_flow = None
    get_stock_financials = None
    quant_get_stock_kline = None
    get_stock_news = None

from service.stock_service import get_stock_data as svc_get_stock_data
from service.user_trade_service import user_trade_service
from service.quant_trading import get_stock_diagnosis, get_batch_diagnosis, get_user_trade_history
from service.position_manager import update_user_positions, get_user_positions, get_user_position_details
from service.storage.data_service import data_service

try:
    from service.simple_scheduler import start_simple_scheduler
    SCHEDULER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"定时任务模块导入失败: {str(e)}")
    SCHEDULER_AVAILABLE = False

# 配置日志
from utils.logger_config import setup_logging, get_logger

# 设置日志配置
setup_logging()
logger = get_logger('app')

# 加载 .env 文件中的环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
logger.info(f"Loading .env file from: {env_path}")
load_dotenv(dotenv_path=env_path, override=True)

# 验证环境变量是否正确加载
deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
if not deepseek_api_key:
    logger.error("DEEPSEEK_API_KEY not found in environment variables")
else:
    masked_key = deepseek_api_key[:4] + '*' * (len(deepseek_api_key) - 8) + deepseek_api_key[-4:]
    logger.info(f"Successfully loaded DEEPSEEK_API_KEY: {masked_key}")

app = Flask(__name__)
# 配置 CORS，允许所有来源
CORS(app, resources={r"/*": {"origins": "*"}})

try:
    from service.limit_up_routes import limit_up_bp
    app.register_blueprint(limit_up_bp)
    logger.info("✅ limit_up 蓝图注册成功")
except Exception as _e:
    logger.warning(f"limit_up 蓝图注册失败: {_e}")

try:
    from service.content_ops.routes import content_bp
    app.register_blueprint(content_bp)
    logger.info("✅ content_ops 蓝图注册成功")
except Exception as _e:
    logger.warning(f"content_ops 蓝图注册失败: {_e}")

# 初始化 Futu API
try:
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    logger.info("Successfully connected to Futu API")
except Exception as e:
    logger.error(f"Failed to connect to Futu API: {str(e)}")
    logger.error(traceback.format_exc())
    quote_ctx = None

# 股票代码映射
STOCK_NAMES = {
    'HK.00700': '腾讯控股',
    'HK.09988': '阿里巴巴',
    'HK.03690': '美团'
}

# 期权类型映射
option_type_map = {
    'CALL': OptionType.CALL, # 对应整数值 1
    'PUT': OptionType.PUT   # 对应整数值 2
}

# 证券类型映射 (Futu SecurityType)
sec_type_map = {
    'DRVT': SecurityType.DRVT    # 对应整数值 8
}

# 简单内存存储，后续可换为数据库
user_watchlist_store = {}

import json
import threading
import os

user_config_file = os.path.join(os.path.dirname(__file__), 'user_watchlist_store.json')
user_config_lock = threading.Lock()

def load_user_config():
    if not os.path.exists(user_config_file):
        return {}
    with user_config_lock:
        with open(user_config_file, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}

def save_user_config(data):
    with user_config_lock:
        with open(user_config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

import json
import threading
import os

monitor_config_file = os.path.join(os.path.dirname(__file__), 'user_monitor_config.json')
monitor_config_lock = threading.Lock()

def load_monitor_config():
    if not os.path.exists(monitor_config_file):
        return {}
    with monitor_config_lock:
        with open(monitor_config_file, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}

def save_monitor_config(data):
    with monitor_config_lock:
        with open(monitor_config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

import json
import threading
import os

monitor_status_file = os.path.join(os.path.dirname(__file__), 'user_monitor_status.json')
monitor_status_lock = threading.Lock()

def load_monitor_status():
    if not os.path.exists(monitor_status_file):
        return {}
    with monitor_status_lock:
        with open(monitor_status_file, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}

def save_monitor_status(data):
    with monitor_status_lock:
        with open(monitor_status_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

import json
import threading
import os

strategy_log_file = os.path.join(os.path.dirname(__file__), 'user_strategy_exec_log.json')
strategy_log_lock = threading.Lock()

def load_strategy_log():
    if not os.path.exists(strategy_log_file):
        return {}
    with strategy_log_lock:
        with open(strategy_log_file, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}

def save_strategy_log(data):
    with strategy_log_lock:
        with open(strategy_log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/api/kline', methods=['GET'])
def get_kline():
    try:
        symbol = request.args.get('symbol', 'HK.00700')
        kline_data = get_kline_data(symbol)
        if not kline_data:
            return jsonify({'error': '未找到K线数据'}), 404
            return jsonify(kline_data)
    except Exception as e:
        error_msg = f"Error in get_kline: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol, as_dict=False):
    try:
        data = svc_get_stock_data(symbol, as_dict, batch_market_snapshot)
        if as_dict:
            return data
        return jsonify(data)
    except Exception as e:
        error_msg = f"Error in get_stock_data: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        if as_dict:
            return {'error': error_msg}
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/<symbol>/kline')
def get_stock_kline(symbol):
    try:
        # 自动补全 start/end 参数，取近两年
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        kline_data = quant_get_stock_kline(symbol, start_date, end_date)
        if not kline_data is None and hasattr(kline_data, 'empty') and kline_data.empty:
            return jsonify({'error': '未找到K线数据'}), 404
        # DataFrame 转 list
        if hasattr(kline_data, 'to_dict'):
            kline_list = kline_data.fillna('').to_dict(orient='records')
        else:
            kline_list = kline_data
        return jsonify(kline_list)
    except Exception as e:
        error_msg = f"Error in get_stock_kline: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/test_connection', methods=['GET'])
def test_connection():
    try:
        if quote_ctx is None:
            error_msg = "Futu API connection failed"
            logger.error(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
        
        # 测试获取市场快照
        ret, data = quote_ctx.get_market_snapshot(['HK.00700'])
        logger.info(f"Test connection - ret: {ret}, data shape: {data.shape if ret == RET_OK else 'N/A'}")
        
        if ret == RET_OK:
            response_data = {
                'status': 'success',
                'message': 'Successfully connected to Futu API',
                'data': data.to_dict('records')
            }
            logger.info(f"Test connection response: {response_data}")
            return jsonify(response_data)
        else:
            error_msg = f"Failed to get market snapshot: {data}"
            logger.error(error_msg)
            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 500
    except Exception as e:
        error_msg = f"Error testing connection: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500

# Helper to safely convert to int
def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

# Helper to safely convert to float
def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

# Helper to safely convert to bool
def safe_bool(value, default=False):
    if pd.isna(value):
        return default
    return bool(value)

@app.route('/api/stock/<symbol>/option_chain')
def get_option_chain_data(symbol):
    try:
        if quote_ctx is None:
            return jsonify({'error': 'Futu API connection failed'}), 500

        # 解析股票代码和市场
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return jsonify({'error': 'Invalid stock code format. Expected format: CODE.MARKET (e.g., 00700.HK)'}), 400
        
        stock_code = code_parts[0]
        market = code_parts[1].upper()
        
        # 检查是否为港股市场
        if market != 'HK':
            return jsonify({
                'optionChain': [],
                'message': '当前仅支持港股市场的期权链数据'
            }), 200

        # 获取期权链数据
        # start=None, end=None 默认获取当前日期到未来30天的期权链
        ret, data = quote_ctx.get_option_chain(code=f'{market}.{stock_code}', start=None, end=None)

        logger.info(f"get_option_chain for {symbol}: ret={ret}, data.empty={data.empty if isinstance(data, pd.DataFrame) else 'N/A'}, data_columns={data.columns.tolist() if isinstance(data, pd.DataFrame) and not data.empty else 'N/A'}")

        if ret != RET_OK:
            # 对于期权链获取失败的情况，返回空数组而不是错误
            logger.warning(f"Failed to get option chain data from Futu API: {data}")
            return jsonify({
                'optionChain': [],
                'message': '暂不支持该股票的期权链数据'
            }), 200

        if not isinstance(data, pd.DataFrame) or data.empty:
            logger.info(f"Option chain data for {symbol} is empty after Futu API call.")
            return jsonify({
                'optionChain': [],
                'message': '暂无期权链数据'
            }), 200

        option_chain_result = []
        grouped_by_strike_time = data.groupby('strike_time')

        for strike_time_str, time_group in grouped_by_strike_time:
            options_for_this_strike_time = []
            
            # Calculate strike_timestamp for this group from strike_time_str
            current_strike_timestamp = 0
            try:
                # Convert YYYY-MM-DD string to datetime object, then to Unix timestamp (seconds since epoch)
                dt_object = datetime.strptime(strike_time_str, '%Y-%m-%d')
                current_strike_timestamp = int(dt_object.timestamp())
            except ValueError:
                logger.error(f"Could not parse strike_time_str: {strike_time_str} to datetime. Defaulting strikeTimestamp to 0.")
                current_strike_timestamp = 0 # Default if parsing fails

            grouped_by_strike_price = time_group.groupby('strike_price')

            for strike_price, price_group in grouped_by_strike_price:
                call_info = None
                put_info = None

                for _, row in price_group.iterrows():
                    # 从完整的期权代码中解析市场
                    full_option_code = row.get('code', '')
                    option_market = full_option_code.split('.')[0] if '.' in full_option_code else ''
                    option_code_only = full_option_code.split('.')[1] if '.' in full_option_code else full_option_code

                    # 从 owner_code (例如 'HK.00700') 解析 owner market 和 code
                    full_owner_code = row.get('stock_owner', '')
                    owner_market = full_owner_code.split('.')[0] if '.' in full_owner_code else ''
                    owner_code_only = full_owner_code.split('.')[1] if '.' in full_owner_code else full_owner_code

                    option_basic = {
                        "security": {
                            "market": option_market,
                            "code": option_code_only # 使用解析后的期权代码
                        },
                        "id": str(safe_int(row.get('stock_id'))), # 使用 stock_id 作为 ID
                        "lotSize": safe_int(row.get('lot_size')),
                        "secType": sec_type_map.get(row.get('stock_type'), 0), # 使用映射获取 secType
                        "name": row.get('name', ''),
                        "listTime": row.get('list_time', ''),
                        "delisting": safe_bool(row.get('delisting'))
                    }
                    option_ex_data = {
                        "type": option_type_map.get(row.get('option_type'), 0), # 使用映射获取 option_type
                        "owner": {
                            "market": owner_market, # 使用解析后的 owner market
                            "code": owner_code_only # 使用解析后的 owner code
                        },
                        "strikeTime": row.get('strike_time', ''),
                        "strikePrice": safe_float(row.get('strike_price')),
                        "suspend": safe_bool(row.get('suspension')),
                        "market": option_market, # 使用解析后的期权市场
                        "strikeTimestamp": current_strike_timestamp, # Use the derived timestamp here
                        "expirationCycle": safe_int(row.get('expiration_cycle')),
                        "optionStandardType": safe_int(row.get('option_standard_type')),
                        "optionSettlementMode": safe_int(row.get('option_settlement_mode')),
                    }

                    # 确保比较时使用枚举值
                    # 直接使用 option_type_map 获取的类型，无需再次转换
                    option_type_val = option_type_map.get(row.get('option_type'), -1)
                    
                    logger.debug(f"Processing row: {row.to_dict()}")
                    logger.debug(f"Constructed option_basic: {option_basic}")
                    logger.debug(f"Constructed option_ex_data: {option_ex_data}")

                    if option_type_val == OptionType.CALL:
                        call_info = {
                            "basic": option_basic,
                            "optionExData": option_ex_data
                        }
                    elif option_type_val == OptionType.PUT:
                        put_info = {
                            "basic": option_basic,
                            "optionExData": option_ex_data
                        }
                
                options_for_this_strike_time.append({
                    "call": call_info,
                    "put": put_info
                })
            
            option_chain_result.append({
                "strikeTime": strike_time_str,
                "option": options_for_this_strike_time,
                "strikeTimestamp": current_strike_timestamp # Use the derived timestamp here
            })
        
        return jsonify({"optionChain": option_chain_result})

    except Exception as e:
        error_msg = f"Error in get_option_chain_data: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/<symbol>/capital_flow')
def get_capital_flow(symbol):
    try:
        if quote_ctx is None:
            return jsonify({'error': 'Futu API connection failed'}), 500

        # 使用 parse_stock_code 拆分 symbol
        stock_code, market = parse_stock_code(symbol)
        if not stock_code or not market:
            return jsonify({'error': f'无效的股票代码格式: {symbol}'}), 400

        # 获取历史资金流向数据（最近一年）
        ret, historical_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.DAY,
            start=None,  # 默认获取最近一年数据
            end=None
        )

        if ret != RET_OK:
            error_msg = f"Failed to get historical capital flow data: {historical_data}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500

        # 获取当日资金流向数据
        ret, intraday_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.INTRADAY
        )

        if ret != RET_OK:
            error_msg = f"Failed to get intraday capital flow data: {intraday_data}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500

        # 处理历史资金流向数据
        historical_flow = []
        if not historical_data.empty:
            for _, row in historical_data.iterrows():
                # 日期只保留年月日
                date_str = str(row['capital_flow_item_time'])
                date_only = date_str.split(' ')[0] if ' ' in date_str else date_str
                historical_flow.append({
                    'date': date_only,
                    'in_flow': float(row['in_flow']),
                    'main_in_flow': float(row['main_in_flow']),
                    'super_in_flow': float(row['super_in_flow']),
                    'big_in_flow': float(row['big_in_flow']),
                    'mid_in_flow': float(row['mid_in_flow']),
                    'sml_in_flow': float(row['sml_in_flow'])
                })

        # 处理当日资金流向数据
        intraday_flow = []
        if not intraday_data.empty:
            for _, row in intraday_data.iterrows():
                # 时间只保留年月日
                time_str = str(row['capital_flow_item_time'])
                date_only = time_str.split(' ')[0] if ' ' in time_str else time_str
                intraday_flow.append({
                    'time': date_only,
                    'in_flow': float(row['in_flow']),
                    'super_in_flow': float(row['super_in_flow']),
                    'big_in_flow': float(row['big_in_flow']),
                    'mid_in_flow': float(row['mid_in_flow']),
                    'sml_in_flow': float(row['sml_in_flow'])
                })

        return jsonify({
            'historical': historical_flow,
            'intraday': intraday_flow
        })

    except Exception as e:
        error_msg = f"Error in get_capital_flow: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/<symbol>/capital_distribution')
def get_capital_distribution(symbol):
    try:
        if quote_ctx is None:
            return jsonify({'error': 'Futu API connection failed'}), 500

        # 获取资金分布数据
        ret, data = quote_ctx.get_capital_distribution(f'HK.{symbol}')

        if ret != RET_OK:
            error_msg = f"Failed to get capital distribution data: {data}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500

        # 打印列名以便调试
        logger.info(f"Capital distribution columns: {data.columns.tolist() if not data.empty else 'Empty DataFrame'}")

        # 处理资金分布数据
        distribution = []
        if not data.empty:
            for _, row in data.iterrows():
                distribution.append({
                    'update_time': row['update_time'],
                    'capital_in': {
                        'super': float(row['capital_in_super']),
                        'big': float(row['capital_in_big']),
                        'mid': float(row['capital_in_mid']),
                        'small': float(row['capital_in_small'])
                    },
                    'capital_out': {
                        'super': float(row['capital_out_super']),
                        'big': float(row['capital_out_big']),
                        'mid': float(row['capital_out_mid']),
                        'small': float(row['capital_out_small'])
                    }
                })

        return jsonify({'distribution': distribution})

    except Exception as e:
        error_msg = f"Error in get_capital_distribution: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

def parse_stock_code(symbol):
    """
    Parse stock code and market from symbol string.
    Returns tuple of (stock_code, market) or (None, None) if invalid format.
    """
    try:
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return None, None
        
        stock_code = code_parts[0]
        market = code_parts[1].upper()
        
        # Validate market
        if market not in ['SH', 'SZ', 'HK', 'US']:
            return None, None
            
        return stock_code, market
    except Exception as e:
        logger.error(f"Error parsing stock code: {str(e)}")
        return None, None

def get_kline_data(symbol):
    """
    Get K-line data for a given stock symbol.
    Returns a list of dictionaries containing K-line data or None if failed.
    优化：FUTU额度不足或K线数据为空时自动兜底用akshare查询A股K线。
    """
    try:
        if quote_ctx is None:
            logger.error("Futu API connection failed")
            return None

        stock_code, market = parse_stock_code(symbol)
        logger.info(f"[KLINE] symbol: {symbol}, stock_code: {stock_code}, market: {market}")
        if not stock_code or not market:
            logger.error(f"Invalid stock symbol format: {symbol}")
            return None

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

        try:
            ret, data, page_req_key = quote_ctx.request_history_kline(
                code=f'{market}.{stock_code}',
                start=start_date,
                end=end_date,
                ktype=KLType.K_DAY,
                autype=AuType.QFQ,
                max_count=1000
            )
            logger.info(f"[KLINE] Futu返回 ret: {ret}, data类型: {type(data)}, data是否DataFrame: {isinstance(data, pd.DataFrame)}, data是否为空: {getattr(data, 'empty', 'N/A')}, data内容预览: {str(data)[:300]}")
            if ret != RET_OK or not isinstance(data, pd.DataFrame) or data.empty:
                logger.warning(f"[KLINE] Futu数据无效，准备走akshare兜底。ret: {ret}, data类型: {type(data)}, data.empty: {getattr(data, 'empty', 'N/A')}")
                raise Exception(f"FUTU K线查询失败或数据为空: {data}")
        except Exception as futu_err:
            logger.warning(f"[KLINE] FUTU K线查询失败，尝试用akshare兜底: {futu_err}")
            if market in ['SH', 'SZ']:
                try:
                    logger.info(f"[KLINE] akshare兜底查询: symbol={symbol}, stock_code={stock_code}, start={start_date}, end={end_date}")
                    ak_data = ak_get_kline_data(symbol, start_date, end_date)
                    logger.info(f"[KLINE] akshare兜底返回: {type(ak_data)}, 长度: {len(ak_data) if ak_data else 0}")
                    return ak_data
                except Exception as ak_err:
                    logger.error(f"[KLINE] akshare A股K线兜底失败: {ak_err}")
            else:
                logger.warning(f"[KLINE] 非A股市场({market})，不走akshare兜底。")
            return None

        # 走到这里说明FUTU成功
        data = data.sort_values('time_key')
        # Calculate technical indicators
        data['EMA5'] = data['close'].ewm(span=5, adjust=False).mean()
        data['EMA10'] = data['close'].ewm(span=10, adjust=False).mean()
        data['EMA20'] = data['close'].ewm(span=20, adjust=False).mean()
        data['EMA60'] = data['close'].ewm(span=60, adjust=False).mean()
        data['EMA12'] = data['close'].ewm(span=12, adjust=False).mean()
        data['EMA26'] = data['close'].ewm(span=26, adjust=False).mean()
        data['DIF'] = data['EMA12'] - data['EMA26']
        data['DEA'] = data['DIF'].ewm(span=9, adjust=False).mean()
        data['MACD'] = 2 * (data['DIF'] - data['DEA'])
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        kline_data = []
        for _, row in data.iterrows():
            kline_data.append({
                'time': row['time_key'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
                'EMA5': float(row['EMA5']) if pd.notna(row['EMA5']) else None,
                'EMA10': float(row['EMA10']) if pd.notna(row['EMA10']) else None,
                'EMA20': float(row['EMA20']) if pd.notna(row['EMA20']) else None,
                'EMA60': float(row['EMA60']) if pd.notna(row['EMA60']) else None,
                'MACD': float(row['MACD']) if pd.notna(row['MACD']) else None,
                'RSI': float(row['RSI']) if pd.notna(row['RSI']) else None
            })
        return kline_data
    except Exception as e:
        logger.error(f"Failed to get kline data: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error(f"[KLINE] get_kline_data最终返回None，symbol={symbol}")
        return None

def get_capital_flow_data(symbol):
    """
    Get capital flow data for a given stock symbol (last 6 months).
    Returns a dictionary containing capital flow data or None if failed.
    """
    try:
        if quote_ctx is None:
            logger.error("Futu API connection failed")
            return None

        # Parse stock code and market
        stock_code, market = parse_stock_code(symbol)
        if not stock_code or not market:
            logger.error(f"Invalid stock symbol format: {symbol}")
            return None

        # Get historical capital flow data (last 6 months - 180 days)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        logger.info(f"获取资金流向数据: symbol={symbol}, start_date={start_date}, end_date={end_date}")
        
        ret, historical_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.DAY,
            start=start_date,  # 180 days ago
            end=end_date
        )
        
        logger.info(f"历史资金流向数据获取结果: ret={ret}, data_type={type(historical_data)}, data_empty={getattr(historical_data, 'empty', 'N/A')}")

        if ret != RET_OK:
            logger.error(f"Failed to get historical capital flow data: {historical_data}")
            return None

        # Get intraday capital flow data
        ret, intraday_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.INTRADAY
        )

        if ret != RET_OK:
            logger.error(f"Failed to get intraday capital flow data: {intraday_data}")
            return None

        # Process historical capital flow data
        historical_flow = []
        if not historical_data.empty:
            for _, row in historical_data.iterrows():
                historical_flow.append({
                    'date': row['capital_flow_item_time'],
                    'in_flow': float(row['in_flow']),
                    'main_in_flow': float(row['main_in_flow']),
                    'super_in_flow': float(row['super_in_flow']),
                    'big_in_flow': float(row['big_in_flow']),
                    'mid_in_flow': float(row['mid_in_flow']),
                    'sml_in_flow': float(row['sml_in_flow'])
                })

        # Process intraday capital flow data
        intraday_flow = []
        if not intraday_data.empty:
            for _, row in intraday_data.iterrows():
                intraday_flow.append({
                    'time': row['capital_flow_item_time'],
                    'in_flow': float(row['in_flow']),
                    'super_in_flow': float(row['super_in_flow']),
                    'big_in_flow': float(row['big_in_flow']),
                    'mid_in_flow': float(row['mid_in_flow']),
                    'sml_in_flow': float(row['sml_in_flow'])
                })

        # Get capital distribution data
        ret, distribution_data = quote_ctx.get_capital_distribution(f'{market}.{stock_code}')
        
        distribution = []
        if ret == RET_OK and not distribution_data.empty:
            for _, row in distribution_data.iterrows():
                distribution.append({
                    'update_time': row['update_time'],
                    'capital_in': {
                        'super': float(row['capital_in_super']),
                        'big': float(row['capital_in_big']),
                        'mid': float(row['capital_in_mid']),
                        'small': float(row['capital_in_small'])
                    },
                    'capital_out': {
                        'super': float(row['capital_out_super']),
                        'big': float(row['capital_out_big']),
                        'mid': float(row['capital_out_mid']),
                        'small': float(row['capital_out_small'])
                    }
                })

        return {
            'historical': historical_flow,
            'intraday': intraday_flow,
            'distribution': distribution
        }

    except Exception as e:
        logger.error(f"Error in get_capital_flow_data: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def analyze_capital_flow(capital_flow_data):
    """
    Analyze capital flow data.
    Returns a dictionary containing capital flow analysis results.
    """
    try:
        if not capital_flow_data:
            return {
                '30d_trend': '暂无资金流向数据',
                'main_capital': '暂无主力资金数据',
                'strength_assessment': '暂无资金实力评估'
            }

        historical_data = capital_flow_data.get('historical', [])
        if not historical_data:
            return {
                '30d_trend': '暂无历史资金流向数据',
                'main_capital': '暂无主力资金数据',
                'strength_assessment': '暂无资金实力评估'
            }

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Get last 30 days data
        last_30d = df.tail(30)

        # Analyze 30-day trend
        total_inflow_30d = last_30d['in_flow'].sum()
        avg_daily_inflow = total_inflow_30d / len(last_30d)
        
        if total_inflow_30d > 0:
            trend_30d = f'近30日累计净流入{total_inflow_30d:.2f}亿元，日均净流入{avg_daily_inflow:.2f}亿元'
        else:
            trend_30d = f'近30日累计净流出{abs(total_inflow_30d):.2f}亿元，日均净流出{abs(avg_daily_inflow):.2f}亿元'

        # Analyze main capital
        main_inflow_30d = last_30d['main_in_flow'].sum()
        super_inflow_30d = last_30d['super_in_flow'].sum()
        big_inflow_30d = last_30d['big_in_flow'].sum()

        main_capital_analysis = []
        if main_inflow_30d > 0:
            main_capital_analysis.append(f'主力资金近30日净流入{main_inflow_30d:.2f}亿元')
        else:
            main_capital_analysis.append(f'主力资金近30日净流出{abs(main_inflow_30d):.2f}亿元')

        if super_inflow_30d > 0:
            main_capital_analysis.append(f'超大单净流入{super_inflow_30d:.2f}亿元')
        else:
            main_capital_analysis.append(f'超大单净流出{abs(super_inflow_30d):.2f}亿元')

        if big_inflow_30d > 0:
            main_capital_analysis.append(f'大单净流入{big_inflow_30d:.2f}亿元')
        else:
            main_capital_analysis.append(f'大单净流出{abs(big_inflow_30d):.2f}亿元')

        # Analyze recent trend (last 5 days)
        last_5d = df.tail(5)
        recent_trend = last_5d['in_flow'].sum()
        if recent_trend > 0:
            main_capital_analysis.append(f'近5日净流入{recent_trend:.2f}亿元，资金活跃度较高')
        else:
            main_capital_analysis.append(f'近5日净流出{abs(recent_trend):.2f}亿元，资金活跃度较低')

        # Assess capital strength
        strength_assessment = []
        
        # Calculate capital strength score
        strength_score = 0
        
        # Score based on 30-day total inflow
        if total_inflow_30d > 0:
            strength_score += 40
            strength_assessment.append('近30日资金持续流入，资金实力较强')
        elif total_inflow_30d > -1000:  # Small outflow
            strength_score += 20
            strength_assessment.append('近30日资金小幅流出，资金实力一般')
        else:
            strength_assessment.append('近30日资金大幅流出，资金实力较弱')

        # Score based on main capital
        if main_inflow_30d > 0:
            strength_score += 30
            strength_assessment.append('主力资金持续流入，主力资金实力较强')
        elif main_inflow_30d > -500:  # Small outflow
            strength_score += 15
            strength_assessment.append('主力资金小幅流出，主力资金实力一般')
        else:
            strength_assessment.append('主力资金大幅流出，主力资金实力较弱')

        # Score based on recent trend
        if recent_trend > 0:
            strength_score += 30
            strength_assessment.append('近期资金活跃度较高，短期资金实力较强')
        elif recent_trend > -200:  # Small outflow
            strength_score += 15
            strength_assessment.append('近期资金活跃度一般，短期资金实力一般')
        else:
            strength_assessment.append('近期资金活跃度较低，短期资金实力较弱')

        # Add overall assessment
        if strength_score >= 80:
            strength_assessment.append('综合评估：资金实力雄厚，有能力推动股价上涨')
        elif strength_score >= 50:
            strength_assessment.append('综合评估：资金实力一般，可能维持震荡')
        else:
            strength_assessment.append('综合评估：资金实力较弱，可能面临调整')

        return {
            '30d_trend': trend_30d,
            'main_capital': '；'.join(main_capital_analysis),
            'strength_assessment': '；'.join(strength_assessment)
        }

    except Exception as e:
        logger.error(f"Error in analyze_capital_flow: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            '30d_trend': '资金流向分析出错',
            'main_capital': '资金流向分析出错',
            'strength_assessment': '资金流向分析出错'
        }

def generate_investment_advice(kline_data, capital_flow_data):
    """
    Generate investment advice based on technical and capital flow analysis.
    Returns a string containing investment advice.
    """
    try:
        if not kline_data or not capital_flow_data:
            return '数据不足，无法给出投资建议'

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(kline_data)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time')

        # Get latest data
        latest_data = df.iloc[-1]
        prev_data = df.iloc[-2]

        # Get capital flow data
        historical_flow = capital_flow_data.get('historical', [])
        if historical_flow:
            latest_flow = historical_flow[-1]
            prev_flow = historical_flow[-2] if len(historical_flow) > 1 else None
        else:
            latest_flow = None
            prev_flow = None

        advice_points = []

        # Technical analysis based advice
        if latest_data['close'] > latest_data['EMA5'] and latest_data['close'] > latest_data['EMA20']:
            advice_points.append('当前价格位于短期和中期均线之上，技术面偏强')
        elif latest_data['close'] < latest_data['EMA5'] and latest_data['close'] < latest_data['EMA20']:
            advice_points.append('当前价格位于短期和中期均线之下，技术面偏弱')

        # Trend analysis
        if latest_data['EMA5'] > latest_data['EMA20'] and prev_data['EMA5'] <= prev_data['EMA20']:
            advice_points.append('短期均线上穿中期均线，可考虑逢低布局')
        elif latest_data['EMA5'] < latest_data['EMA20'] and prev_data['EMA5'] >= prev_data['EMA20']:
            advice_points.append('短期均线下穿中期均线，建议观望为主')

        # Capital flow based advice
        if latest_flow and prev_flow:
            if latest_flow['in_flow'] > 0 and latest_flow['in_flow'] > prev_flow['in_flow']:
                advice_points.append('资金持续流入且加速，可考虑适当加仓')
            elif latest_flow['in_flow'] < 0 and latest_flow['in_flow'] < prev_flow['in_flow']:
                advice_points.append('资金持续流出且加速，建议控制仓位')

        # RSI based advice
        if latest_data['RSI'] > 70:
            advice_points.append('RSI处于超买区域，注意回调风险')
        elif latest_data['RSI'] < 30:
            advice_points.append('RSI处于超卖区域，可考虑逢低布局')

        # MACD based advice
        if latest_data['MACD'] > 0 and prev_data['MACD'] <= 0:
            advice_points.append('MACD金叉，可考虑逢低布局')
        elif latest_data['MACD'] < 0 and prev_data['MACD'] >= 0:
            advice_points.append('MACD死叉，建议观望为主')

        # Combine all advice points
        if advice_points:
            return '；'.join(advice_points)
        else:
            return '暂无明确投资建议，建议观望为主'

    except Exception as e:
        logger.error(f"Error in generate_investment_advice: {str(e)}")
        logger.error(traceback.format_exc())
        return '生成投资建议时出错'

def generate_risk_warning(kline_data, capital_flow_data):
    """
    Generate risk warnings based on technical and capital flow analysis.
    Returns a string containing risk warnings.
    """
    try:
        if not kline_data or not capital_flow_data:
            return '数据不足，无法给出风险提示'

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(kline_data)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time')

        # Get latest data
        latest_data = df.iloc[-1]
        prev_data = df.iloc[-2]

        # Get capital flow data
        historical_flow = capital_flow_data.get('historical', [])
        if historical_flow:
            latest_flow = historical_flow[-1]
            prev_flow = historical_flow[-2] if len(historical_flow) > 1 else None
        else:
            latest_flow = None
            prev_flow = None

        risk_points = []

        # Technical risk warnings
        if latest_data['close'] < latest_data['EMA5'] and latest_data['close'] < latest_data['EMA20']:
            risk_points.append('价格位于短期和中期均线之下，存在继续下跌风险')

        if latest_data['RSI'] > 80:
            risk_points.append('RSI处于严重超买区域，存在大幅回调风险')
        elif latest_data['RSI'] < 20:
            risk_points.append('RSI处于严重超卖区域，存在继续下跌风险')

        if latest_data['MACD'] < 0 and prev_data['MACD'] >= 0:
            risk_points.append('MACD死叉，存在下跌风险')

        # Capital flow risk warnings
        if latest_flow and prev_flow:
            if latest_flow['in_flow'] < 0 and latest_flow['in_flow'] < prev_flow['in_flow']:
                risk_points.append('资金持续流出且加速，存在继续下跌风险')
            
            if latest_flow['main_in_flow'] < 0 and latest_flow['main_in_flow'] < prev_flow['main_in_flow']:
                risk_points.append('主力资金持续流出且加速，存在较大下跌风险')

        # Volatility risk warning
        recent_volatility = df['close'].pct_change().std() * 100
        if recent_volatility > 5:  # 5% volatility threshold
            risk_points.append(f'近期波动率较大（{recent_volatility:.1f}%），存在较大波动风险')

        # Combine all risk points
        if risk_points:
            return '；'.join(risk_points)
        else:
            return '暂无明确风险提示，但仍需注意市场风险'

    except Exception as e:
        logger.error(f"Error in generate_risk_warning: {str(e)}")
        logger.error(traceback.format_exc())
        return '生成风险提示时出错'

def analyze_technical(kline_data):
    """
    Analyze technical indicators from K-line data.
    Returns a dictionary containing technical analysis results.
    """
    try:
        if not kline_data or len(kline_data) < 60:  # 需要至少60天的数据进行分析
            return {
                'ema_crosses': '数据不足，无法进行技术分析',
                'ema_trends': '数据不足，无法进行技术分析',
                'price_ema_relation': '数据不足，无法进行技术分析',
                'trend_judgment': '数据不足，无法进行技术分析'
            }

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(kline_data)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time')

        # Get latest data
        latest_data = df.iloc[-1]
        prev_data = df.iloc[-2]

        # Analyze EMA crosses
        ema_crosses = []
        
        # Short-term crosses (EMA5 and EMA10)
        if latest_data['EMA5'] > latest_data['EMA10'] and prev_data['EMA5'] <= prev_data['EMA10']:
            ema_crosses.append('EMA5上穿EMA10，形成短期金叉，预示短期看涨')
        elif latest_data['EMA5'] < latest_data['EMA10'] and prev_data['EMA5'] >= prev_data['EMA10']:
            ema_crosses.append('EMA5下穿EMA10，形成短期死叉，预示短期看跌')

        # Medium-term crosses (EMA10 and EMA20)
        if latest_data['EMA10'] > latest_data['EMA20'] and prev_data['EMA10'] <= prev_data['EMA20']:
            ema_crosses.append('EMA10上穿EMA20，形成中期金叉，预示中期看涨')
        elif latest_data['EMA10'] < latest_data['EMA20'] and prev_data['EMA10'] >= prev_data['EMA20']:
            ema_crosses.append('EMA10下穿EMA20，形成中期死叉，预示中期看跌')

        # Long-term crosses (EMA20 and EMA60)
        if latest_data['EMA20'] > latest_data['EMA60'] and prev_data['EMA20'] <= prev_data['EMA60']:
            ema_crosses.append('EMA20上穿EMA60，形成长期金叉，预示长期看涨')
        elif latest_data['EMA20'] < latest_data['EMA60'] and prev_data['EMA20'] >= prev_data['EMA60']:
            ema_crosses.append('EMA20下穿EMA60，形成长期死叉，预示长期看跌')

        # Analyze EMA trends
        ema_trends = []
        
        # Short-term trend (last 5 days)
        short_term_trend = df['EMA5'].tail(5).pct_change().mean()
        if short_term_trend > 0.001:  # 0.1% threshold
            ema_trends.append('短期均线（EMA5）呈上升趋势，短期看涨')
        elif short_term_trend < -0.001:
            ema_trends.append('短期均线（EMA5）呈下降趋势，短期看跌')

        # Medium-term trend (last 10 days)
        medium_term_trend = df['EMA20'].tail(10).pct_change().mean()
        if medium_term_trend > 0.001:
            ema_trends.append('中期均线（EMA20）呈上升趋势，中期看涨')
        elif medium_term_trend < -0.001:
            ema_trends.append('中期均线（EMA20）呈下降趋势，中期看跌')

        # Long-term trend (last 20 days)
        long_term_trend = df['EMA60'].tail(20).pct_change().mean()
        if long_term_trend > 0.001:
            ema_trends.append('长期均线（EMA60）呈上升趋势，长期看涨')
        elif long_term_trend < -0.001:
            ema_trends.append('长期均线（EMA60）呈下降趋势，长期看跌')

        # Analyze price and EMA relationship
        price_ema_relation = []
        
        # Current price vs EMAs
        if latest_data['close'] > latest_data['EMA5']:
            price_ema_relation.append('当前价格位于EMA5之上，短期支撑较强')
        else:
            price_ema_relation.append('当前价格位于EMA5之下，短期压力较大')

        if latest_data['close'] > latest_data['EMA20']:
            price_ema_relation.append('当前价格位于EMA20之上，中期支撑较强')
        else:
            price_ema_relation.append('当前价格位于EMA20之下，中期压力较大')

        if latest_data['close'] > latest_data['EMA60']:
            price_ema_relation.append('当前价格位于EMA60之上，长期支撑较强')
        else:
            price_ema_relation.append('当前价格位于EMA60之下，长期压力较大')

        # EMA alignment
        if latest_data['EMA5'] > latest_data['EMA20'] > latest_data['EMA60']:
            price_ema_relation.append('均线呈多头排列，整体趋势向上')
        elif latest_data['EMA5'] < latest_data['EMA20'] < latest_data['EMA60']:
            price_ema_relation.append('均线呈空头排列，整体趋势向下')

        # Overall trend judgment
        trend_judgment = []
        
        # Short-term trend
        if short_term_trend > 0.001 and latest_data['close'] > latest_data['EMA5']:
            trend_judgment.append('短期趋势向上，可考虑逢低布局')
        elif short_term_trend < -0.001 and latest_data['close'] < latest_data['EMA5']:
            trend_judgment.append('短期趋势向下，建议观望为主')

        # Medium-term trend
        if medium_term_trend > 0.001 and latest_data['close'] > latest_data['EMA20']:
            trend_judgment.append('中期趋势向上，可考虑中线布局')
        elif medium_term_trend < -0.001 and latest_data['close'] < latest_data['EMA20']:
            trend_judgment.append('中期趋势向下，建议谨慎操作')

        # Long-term trend
        if long_term_trend > 0.001 and latest_data['close'] > latest_data['EMA60']:
            trend_judgment.append('长期趋势向上，可考虑长线布局')
        elif long_term_trend < -0.001 and latest_data['close'] < latest_data['EMA60']:
            trend_judgment.append('长期趋势向下，建议等待企稳')

        return {
            'ema_crosses': '；'.join(ema_crosses) if ema_crosses else '暂无均线交叉信号',
            'ema_trends': '；'.join(ema_trends) if ema_trends else '暂无明确均线趋势',
            'price_ema_relation': '；'.join(price_ema_relation) if price_ema_relation else '暂无明确价格与均线关系',
            'trend_judgment': '；'.join(trend_judgment) if trend_judgment else '暂无明确趋势判断'
        }

    except Exception as e:
        logger.error(f"Error in analyze_technical: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'ema_crosses': '技术分析出错',
            'ema_trends': '技术分析出错',
            'price_ema_relation': '技术分析出错',
            'trend_judgment': '技术分析出错'
        }

def analyze_capital_distribution(capital_flow_data):
    """
    Analyze capital distribution data.
    Returns a dictionary containing capital distribution analysis results.
    """
    try:
        if not capital_flow_data:
            return {
                'main_capital_distribution': '暂无资金分布数据',
                'retail_capital_distribution': '暂无资金分布数据',
                'capital_structure': '暂无资金分布数据'
            }

        distribution_data = capital_flow_data.get('distribution', [])
        if not distribution_data:
            return {
                'main_capital_distribution': '暂无资金分布数据',
                'retail_capital_distribution': '暂无资金分布数据',
                'capital_structure': '暂无资金分布数据'
            }

        # Get latest distribution data
        latest_dist = distribution_data[-1]

        # Analyze main capital distribution
        main_capital_points = []
        
        # Calculate main capital (super + big) inflow
        main_inflow = latest_dist['capital_in']['super'] + latest_dist['capital_in']['big']
        main_outflow = latest_dist['capital_out']['super'] + latest_dist['capital_out']['big']
        main_net = main_inflow - main_outflow

        if main_net > 0:
            main_capital_points.append(f'主力资金（超大单+大单）净流入{main_net:.2f}亿元')
        else:
            main_capital_points.append(f'主力资金（超大单+大单）净流出{abs(main_net):.2f}亿元')

        # Analyze super capital
        super_inflow = latest_dist['capital_in']['super']
        super_outflow = latest_dist['capital_out']['super']
        super_net = super_inflow - super_outflow

        if super_net > 0:
            main_capital_points.append(f'超大单净流入{super_net:.2f}亿元')
        else:
            main_capital_points.append(f'超大单净流出{abs(super_net):.2f}亿元')

        # Analyze big capital
        big_inflow = latest_dist['capital_in']['big']
        big_outflow = latest_dist['capital_out']['big']
        big_net = big_inflow - big_outflow

        if big_net > 0:
            main_capital_points.append(f'大单净流入{big_net:.2f}亿元')
        else:
            main_capital_points.append(f'大单净流出{abs(big_net):.2f}亿元')

        # Analyze retail capital distribution
        retail_capital_points = []
        
        # Calculate retail capital (mid + small) inflow
        retail_inflow = latest_dist['capital_in']['mid'] + latest_dist['capital_in']['small']
        retail_outflow = latest_dist['capital_out']['mid'] + latest_dist['capital_out']['small']
        retail_net = retail_inflow - retail_outflow

        if retail_net > 0:
            retail_capital_points.append(f'散户资金（中单+小单）净流入{retail_net:.2f}亿元')
        else:
            retail_capital_points.append(f'散户资金（中单+小单）净流出{abs(retail_net):.2f}亿元')

        # Analyze mid capital
        mid_inflow = latest_dist['capital_in']['mid']
        mid_outflow = latest_dist['capital_out']['mid']
        mid_net = mid_inflow - mid_outflow

        if mid_net > 0:
            retail_capital_points.append(f'中单净流入{mid_net:.2f}亿元')
        else:
            retail_capital_points.append(f'中单净流出{abs(mid_net):.2f}亿元')

        # Analyze small capital
        small_inflow = latest_dist['capital_in']['small']
        small_outflow = latest_dist['capital_out']['small']
        small_net = small_inflow - small_outflow

        if small_net > 0:
            retail_capital_points.append(f'小单净流入{small_net:.2f}亿元')
        else:
            retail_capital_points.append(f'小单净流出{abs(small_net):.2f}亿元')

        # Analyze capital structure
        capital_structure_points = []
        
        # Calculate total inflow and outflow
        total_inflow = main_inflow + retail_inflow
        total_outflow = main_outflow + retail_outflow
        total_net = total_inflow - total_outflow

        if total_net > 0:
            capital_structure_points.append(f'总体资金净流入{total_net:.2f}亿元')
        else:
            capital_structure_points.append(f'总体资金净流出{abs(total_net):.2f}亿元')

        # Calculate main capital ratio
        main_ratio = (main_inflow + main_outflow) / (total_inflow + total_outflow) * 100
        retail_ratio = (retail_inflow + retail_outflow) / (total_inflow + total_outflow) * 100

        capital_structure_points.append(f'主力资金占比{main_ratio:.1f}%，散户资金占比{retail_ratio:.1f}%')

        # Analyze capital structure trend
        if main_net > 0 and retail_net < 0:
            capital_structure_points.append('主力资金流入，散户资金流出，市场结构良好')
        elif main_net < 0 and retail_net > 0:
            capital_structure_points.append('主力资金流出，散户资金流入，需警惕风险')
        elif main_net > 0 and retail_net > 0:
            capital_structure_points.append('主力资金和散户资金同步流入，市场情绪较好')
        elif main_net < 0 and retail_net < 0:
            capital_structure_points.append('主力资金和散户资金同步流出，市场情绪较差')

        return {
            'main_capital_distribution': '；'.join(main_capital_points) if main_capital_points else '暂无主力资金分布数据',
            'retail_capital_distribution': '；'.join(retail_capital_points) if retail_capital_points else '暂无散户资金分布数据',
            'capital_structure': '；'.join(capital_structure_points) if capital_structure_points else '暂无资金结构数据'
        }

    except Exception as e:
        logger.error(f"Error in analyze_capital_distribution: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'main_capital_distribution': '资金分布分析出错',
            'retail_capital_distribution': '资金分布分析出错',
            'capital_structure': '资金分布分析出错'
        }

def calculate_technical_score(technical_analysis):
    """
    Calculate technical analysis score based on various technical indicators.
    Returns a dictionary containing score and evaluation.
    """
    try:
        score = 0
        max_score = 100
        evaluation_points = []

        # 1. 均线趋势评分 (30分)
        if '均线多头排列' in technical_analysis['ema_trends']:
            score += 30
            evaluation_points.append('均线多头排列，趋势良好')
        elif '均线空头排列' in technical_analysis['ema_trends']:
            score += 10
            evaluation_points.append('均线空头排列，趋势较弱')
        else:
            score += 20
            evaluation_points.append('均线趋势中性')

        # 2. 价格与均线关系评分 (30分)
        if '价格位于所有均线之上' in technical_analysis['price_ema_relation']:
            score += 30
            evaluation_points.append('价格位于所有均线之上，强势特征明显')
        elif '价格位于所有均线之下' in technical_analysis['price_ema_relation']:
            score += 10
            evaluation_points.append('价格位于所有均线之下，弱势特征明显')
        else:
            score += 20
            evaluation_points.append('价格与均线关系中性')

        # 3. 趋势判断评分 (20分)
        if '强势上涨' in technical_analysis['trend_judgment']:
            score += 20
            evaluation_points.append('强势上涨趋势')
        elif '强势下跌' in technical_analysis['trend_judgment']:
            score += 5
            evaluation_points.append('强势下跌趋势')
        else:
            score += 12
            evaluation_points.append('趋势中性')

        # 4. 均线交叉信号评分 (20分)
        if '金叉' in technical_analysis['ema_crosses']:
            score += 20
            evaluation_points.append('出现金叉信号，看涨')
        elif '死叉' in technical_analysis['ema_crosses']:
            score += 5
            evaluation_points.append('出现死叉信号，看跌')
        else:
            score += 10
            evaluation_points.append('无明显交叉信号')

        # 计算最终得分和评级
        final_score = round(score / max_score * 100, 1)
        
        if final_score >= 80:
            rating = 'A'
            rating_desc = '优秀'
        elif final_score >= 70:
            rating = 'B'
            rating_desc = '良好'
        elif final_score >= 60:
            rating = 'C'
            rating_desc = '一般'
        elif final_score >= 50:
            rating = 'D'
            rating_desc = '较差'
        else:
            rating = 'E'
            rating_desc = '差'

        return {
            'score': final_score,
            'rating': rating,
            'rating_desc': rating_desc,
            'evaluation': '；'.join(evaluation_points) if evaluation_points else '暂无评分说明'
        }

    except Exception as e:
        logger.error(f"Error in calculate_technical_score: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'score': 0,
            'rating': 'E',
            'rating_desc': '评分计算出错',
            'evaluation': '评分计算出错'
        }

def calculate_capital_score(capital_flow_analysis):
    """
    Calculate capital flow score based on capital flow analysis results.
    Returns a dictionary containing score and evaluation.
    """
    try:
        score = 0
        max_score = 100
        evaluation_points = []

        # 主力资金评分 (60分)
        if '净流入' in capital_flow_analysis.get('main_capital', ''):
            score += 60
            evaluation_points.append('主力资金持续净流入')
        elif '净流出' in capital_flow_analysis.get('main_capital', ''):
            score += 20
            evaluation_points.append('主力资金持续净流出')
        else:
            score += 40
            evaluation_points.append('主力资金流向中性')

        # 资金实力评分 (40分)
        if '资金实力雄厚' in capital_flow_analysis.get('strength_assessment', ''):
            score += 40
            evaluation_points.append('资金实力雄厚')
        elif '资金实力较弱' in capital_flow_analysis.get('strength_assessment', ''):
            score += 10
            evaluation_points.append('资金实力较弱')
        else:
            score += 25
            evaluation_points.append('资金实力一般')

        # 计算最终得分和评级
        final_score = round(score / max_score * 100, 1)
        
        if final_score >= 80:
            rating = 'A'
            rating_desc = '优秀'
        elif final_score >= 70:
            rating = 'B'
            rating_desc = '良好'
        elif final_score >= 60:
            rating = 'C'
            rating_desc = '一般'
        elif final_score >= 50:
            rating = 'D'
            rating_desc = '较差'
        else:
            rating = 'E'
            rating_desc = '差'

        return {
            'score': final_score,
            'rating': rating,
            'rating_desc': rating_desc,
            'evaluation': '；'.join(evaluation_points) if evaluation_points else '暂无评分说明'
        }

    except Exception as e:
        logger.error(f"Error in calculate_capital_score: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'score': 0,
            'rating': 'E',
            'rating_desc': '评分计算出错',
            'evaluation': '评分计算出错'
        }

def get_score_grade(score):
    """
    根据分数返回评级（A/B/C/D/F）。
    """
    try:
        if isinstance(score, dict):
            score = score.get('score', 0)
        if score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'
    except Exception as e:
        logger.error(f"Error in get_score_grade: {str(e)}")
        return 'F'

def calculate_overall_score(diagnosis_result):
    """
    Calculate overall score based on various analysis results.
    Returns a dictionary containing score and evaluation.
    """
    try:
        score = 0
        max_score = 0
        evaluation_points = []

        # 1. 技术分析评分 (40分)
        max_score += 40
        tech_score = 0
        tech_points = []
        technical_analysis = diagnosis_result.get('technical_analysis', {})

        # 均线趋势评分 (15分)
        if '均线多头排列' in technical_analysis.get('ema_trends', ''):
            tech_score += 15
            tech_points.append('均线多头排列，趋势良好')
        elif '均线空头排列' in technical_analysis.get('ema_trends', ''):
            tech_score += 5
            tech_points.append('均线空头排列，趋势较弱')
        else:
            tech_score += 10
            tech_points.append('均线趋势中性')

        # 价格与均线关系评分 (15分)
        if '价格位于所有均线之上' in technical_analysis.get('price_ema_relation', ''):
            tech_score += 15
            tech_points.append('价格位于所有均线之上，强势特征明显')
        elif '价格位于所有均线之下' in technical_analysis.get('price_ema_relation', ''):
            tech_score += 5
            tech_points.append('价格位于所有均线之下，弱势特征明显')
        else:
            tech_score += 10
            tech_points.append('价格与均线关系中性')

        # 趋势判断评分 (10分)
        if '强势上涨' in technical_analysis.get('trend_judgment', ''):
            tech_score += 10
            tech_points.append('强势上涨趋势')
        elif '强势下跌' in technical_analysis.get('trend_judgment', ''):
            tech_score += 2
            tech_points.append('强势下跌趋势')
        else:
            tech_score += 6
            tech_points.append('趋势中性')

        score += tech_score
        if tech_points:
            evaluation_points.append(f'技术分析得分：{tech_score}/40，' + '；'.join(tech_points))

        # 2. 资金流向评分 (30分)
        max_score += 30
        capital_score = 0
        capital_points = []
        capital_flow_analysis = diagnosis_result.get('capital_flow_analysis', {})

        # 主力资金评分 (15分)
        if '净流入' in capital_flow_analysis.get('main_capital', ''):
            capital_score += 15
            capital_points.append('主力资金持续净流入')
        elif '净流出' in capital_flow_analysis.get('main_capital', ''):
            capital_score += 5
            capital_points.append('主力资金持续净流出')
        else:
            capital_score += 10
            capital_points.append('主力资金流向中性')

        # 资金实力评分 (15分)
        if '资金实力雄厚' in capital_flow_analysis.get('strength_assessment', ''):
            capital_score += 15
            capital_points.append('资金实力雄厚')
        elif '资金实力较弱' in capital_flow_analysis.get('strength_assessment', ''):
            capital_score += 5
            capital_points.append('资金实力较弱')
        else:
            capital_score += 10
            capital_points.append('资金实力一般')

        score += capital_score
        if capital_points:
            evaluation_points.append(f'资金流向得分：{capital_score}/30，' + '；'.join(capital_points))

        # 3. 资金分布评分 (20分)
        max_score += 20
        distribution_score = 0
        distribution_points = []
        capital_distribution_analysis = diagnosis_result.get('capital_distribution_analysis', {})

        # 资金结构评分 (10分)
        if '主力资金占比' in capital_distribution_analysis.get('capital_structure', ''):
            try:
                main_ratio = float(capital_distribution_analysis.get('capital_structure', '').split('主力资金占比')[1].split('%')[0])
                if main_ratio > 60:
                    distribution_score += 10
                    distribution_points.append('主力资金占比高，市场结构良好')
                elif main_ratio > 40:
                    distribution_score += 7
                    distribution_points.append('主力资金占比适中')
                else:
                    distribution_score += 4
                    distribution_points.append('主力资金占比偏低')
            except Exception:
                distribution_score += 4
                distribution_points.append('主力资金占比信息解析失败')

        # 资金结构趋势评分 (10分)
        if '市场结构良好' in capital_distribution_analysis.get('capital_structure', ''):
            distribution_score += 10
            distribution_points.append('资金结构趋势良好')
        elif '需警惕风险' in capital_distribution_analysis.get('capital_structure', ''):
            distribution_score += 3
            distribution_points.append('资金结构存在风险')
        else:
            distribution_score += 6
            distribution_points.append('资金结构趋势中性')

        score += distribution_score
        if distribution_points:
            evaluation_points.append(f'资金分布得分：{distribution_score}/20，' + '；'.join(distribution_points))

        # 4. 新闻舆情评分 (10分)
        max_score += 10
        news_score = 0
        news_points = []
        news_analysis = diagnosis_result.get('news_analysis', [])
        if news_analysis:
            positive_count = 0
            negative_count = 0
            total_count = len(news_analysis)

            for news in news_analysis:
                if news.get('sentiment') == 'positive':
                    positive_count += 1
                elif news.get('sentiment') == 'negative':
                    negative_count += 1

            if total_count > 0:
                positive_ratio = positive_count / total_count
                negative_ratio = negative_count / total_count

                if positive_ratio > 0.6:
                    news_score += 10
                    news_points.append('新闻舆情非常正面')
                elif positive_ratio > 0.4:
                    news_score += 7
                    news_points.append('新闻舆情偏正面')
                elif negative_ratio > 0.6:
                    news_score += 2
                    news_points.append('新闻舆情非常负面')
                elif negative_ratio > 0.4:
                    news_score += 4
                    news_points.append('新闻舆情偏负面')
                else:
                    news_score += 6
                    news_points.append('新闻舆情中性')

        score += news_score
        if news_points:
            evaluation_points.append(f'新闻舆情得分：{news_score}/10，' + '；'.join(news_points))

        # 计算最终得分和评级
        final_score = round(score / max_score * 100, 1)
        
        if final_score >= 80:
            rating = 'A'
            rating_desc = '优秀'
        elif final_score >= 70:
            rating = 'B'
            rating_desc = '良好'
        elif final_score >= 60:
            rating = 'C'
            rating_desc = '一般'
        elif final_score >= 50:
            rating = 'D'
            rating_desc = '较差'
        else:
            rating = 'E'
            rating_desc = '差'

        return {
            'score': final_score,
            'rating': rating,
            'rating_desc': rating_desc,
            'evaluation': '；'.join(evaluation_points) if evaluation_points else '暂无评分说明'
        }

    except Exception as e:
        logger.error(f"Error in calculate_overall_score: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'score': 0,
            'rating': 'E',
            'rating_desc': '评分计算出错',
            'evaluation': '评分计算出错'
        }

@app.route('/api/stock/<symbol>/diagnose', methods=['POST'])
def diagnose_stock(symbol):
    try:
        # 解析股票代码和市场
        stock_code, market = parse_stock_code(symbol)
        if not stock_code or not market:
            return jsonify({'error': '无效的股票代码格式'}), 400

        # 获取K线数据
        kline_data = get_kline_data(symbol)
        # 获取资金流向数据
        capital_flow_data = get_capital_flow_data(symbol)
        logger.info(f"资金流向数据获取结果: {type(capital_flow_data)}, 数据长度: {len(capital_flow_data) if capital_flow_data else 'None'}")
        if capital_flow_data:
            logger.info(f"资金流向数据结构: historical={len(capital_flow_data.get('historical', []))}, intraday={len(capital_flow_data.get('intraday', []))}, distribution={len(capital_flow_data.get('distribution', []))}")
        else:
            logger.warning(f"资金流向数据获取失败，symbol={symbol}")
        # 获取新闻数据（只取最新10条，拼接标题+内容）
        news_list = []
        try:
            news_resp = get_stock_news(symbol)
            if hasattr(news_resp, 'json'):
                news_json = news_resp.json
                if callable(news_json):
                    news_json = news_json()
                news_list = news_json.get('news', [])
            elif isinstance(news_resp, dict):
                news_list = news_resp.get('news', [])
        except Exception as e:
            logger.error(f"获取新闻失败: {str(e)}")
        news_text = '\n\n'.join([f"标题: {n.get('title','')}\n内容: {n.get('content','')}" for n in news_list[:10]])

        # 构建大模型prompt
        kline_json = json.dumps(kline_data[-30:], ensure_ascii=False, indent=2) if kline_data and len(kline_data) >= 30 else '无足够K线数据'
        capital_json = json.dumps(capital_flow_data, ensure_ascii=False, indent=2) if capital_flow_data else '无资金流向数据'
        user_prompt = f"""
        你是一名资深金融分析师，请结合以下个股行情走势、技术指标、资金面和最新资讯，为投资者生成一份全面的诊断报告：

        【行情与技术指标】
        股票代码：{symbol}
        近30日K线与EMA数据（JSON）：
        {kline_json}

        【资金面数据】
        近半年资金流向（JSON）：
        {capital_json}

        【新闻资讯】
        {news_text}

        【分析要求】
        1. 先解读行情走势和技术面。
        2. 再解读资金面。
        3. 再解读新闻资讯及其对个股的潜在影响。
        4. 最后给出投资建议和风险提示。
        5. 输出分层清晰、适合 markdown 展示的内容。
        """
        messages = [
            {'role': 'system', 'content': '你是一名专业的金融分析师，擅长从海量信息中提炼核心观点，并为投资者提供有价值的决策参考。'},
            {'role': 'user', 'content': user_prompt.strip()}
        ]
        logger.info(f"DEEPSEEK DIAGNOSIS Prompt:\n{user_prompt}")
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {os.getenv("DEEPSEEK_API_KEY")}'
        }
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json={
                'model': 'deepseek-chat',
                'messages': messages,
                'temperature': 0.5,
                'max_tokens': 1500
            }
        )
        logger.info(f"DEEPSEEK DIAGNOSIS Response - Status Code: {response.status_code}")
        logger.info(f"DEEPSEEK DIAGNOSIS Response - Text: {response.text}")
        if response.status_code != 200:
            raise Exception(f'DEEPSEEK API 调用失败: {response.text}')
        result = response.json()
        diagnosis_markdown = result['choices'][0]['message']['content']

        # 原有结构化分析
        diagnosis_result = {
            'symbol': symbol,
            'technical_analysis': analyze_technical(kline_data),
            'capital_flow_analysis': analyze_capital_flow(capital_flow_data) if capital_flow_data else None,
            'capital_distribution_analysis': analyze_capital_distribution(capital_flow_data) if capital_flow_data else None,
            'investment_advice': generate_investment_advice(kline_data, capital_flow_data),
            'risk_warning': generate_risk_warning(kline_data, capital_flow_data),
            'news': news_list,
            'charts_data': {
                'technical': {
                    'dates': [item['time'] for item in kline_data],
                    'prices': [item['close'] for item in kline_data],
                    'ema5': [item['EMA5'] for item in kline_data],
                    'ema10': [item['EMA10'] for item in kline_data],
                    'ema20': [item['EMA20'] for item in kline_data],
                    'ema60': [item['EMA60'] for item in kline_data]
                }
            },
            'diagnosis_markdown': diagnosis_markdown
        }
        if capital_flow_data:
            diagnosis_result['charts_data']['capital_flow'] = {
                'historical': [
                    {
                        'date': item['date'],
                        'in_flow': item['in_flow']
                    }
                    for item in capital_flow_data['historical']
                ]
            }
        diagnosis_result['overall_score'] = calculate_overall_score(diagnosis_result)
        diagnosis_result['technical_score'] = calculate_technical_score(diagnosis_result['technical_analysis'])
        diagnosis_result['capital_score'] = calculate_capital_score(diagnosis_result['capital_flow_analysis'])
        diagnosis_result['score'] = {
            'grade': get_score_grade(diagnosis_result['overall_score']),
            'technical_grade': get_score_grade(diagnosis_result['technical_score']),
            'capital_grade': get_score_grade(diagnosis_result['capital_score'])
        }
        return jsonify(diagnosis_result)
    except Exception as e:
        logger.error(f"诊断失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'诊断失败: {str(e)}'}), 500

def analyze_with_deepseek(data):
    """
    使用DEEPSEEK分析股票数据
    只处理简单的参数验证和调用业务服务
    """
    try:
        # 调用业务服务进行DeepSeek分析
        from service.stock_service import analyze_with_deepseek_service
        result = analyze_with_deepseek_service(data)
        
        return result
        
    except Exception as e:
        logger.error(f"DEEPSEEK分析错误: {str(e)}")
        logger.error(traceback.format_exc())
        # 发生错误时返回默认评分
        return {
            'technical_analysis': {'error': str(e)},
            'capital_flow_analysis': {'error': str(e)},
            'capital_distribution_analysis': {'error': str(e)},
            'score': {
                'total_score': 50,
                'grade': 'C',
                'technical_score': 50,
                'technical_grade': 'C',
                'capital_score': 50,
                'capital_grade': 'C'
            },
            'investment_advice': '分析过程出现错误，请稍后重试',
            'risk_warning': '请注意投资风险'
        }

@app.route('/api/stock/<symbol>/news')
def get_stock_news(symbol):
    """
    获取股票新闻接口
    只处理简单的参数验证和调用业务服务
    """
    try:
        # 解析股票代码和市场
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return jsonify({'error': '股票代码格式错误'}), 400
            
        # 调用业务服务获取新闻数据
        from service.stock_service import get_stock_news_data
        result = get_stock_news_data(symbol)
        
        # 处理返回结果
        if 'error' in result:
            return jsonify({'error': result['error']}), result.get('status', 500)
        
        return jsonify({
            'news': result['news'],
            'total': result['total']
        })
        
    except Exception as e:
        logger.error(f"获取新闻失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'获取新闻失败: {str(e)}'}), 500

@app.route('/api/news/summary', methods=['POST'])
def news_summary():
    try:
        # 1. 获取 symbol（前端传递，或默认）
        req_data = request.get_json(force=True) if request.is_json else {}
        symbol = req_data.get('symbol', '00700.HK')  # 默认腾讯控股

        # 2. 获取个股近30日K线和EMA数据
        kline_data = get_kline_data(symbol)
        if not kline_data or len(kline_data) < 30:
            kline_json = '无足够K线数据'
        else:
            # 只取最近30日
            kline_json = json.dumps(kline_data[-30:], ensure_ascii=False, indent=2)

        # 3. 获取最新资讯
        news_df = ak.stock_info_global_futu()
        news_list = []
        for _, row in news_df.head(10).iterrows(): # 取最新的10条
            news_list.append(f"标题: {row['标题']}\n内容: {row['内容']}")
        news_text = "\n\n".join(news_list)

        # 4. 构建 prompt
        user_prompt = f"""
        你是一名资深金融分析师，请结合以下个股行情走势、技术指标和最新资讯，为投资者提供专业解读和建议：

        【个股行情与技术指标】
        股票代码：{symbol}
        近30日K线与EMA数据（JSON）：
        {kline_json}

        【最新资讯】
        {news_text}

        【分析要求】
        1. 先简要解读该股近期行情走势和技术面（如趋势、支撑压力、均线形态等）。
        2. 再总结资讯要点及其对该股的潜在影响。
        3. 最后给出投资建议。
        4. 语言风格专业、分层清晰，适合 markdown 展示。
        """

        messages = [
            {'role': 'system', 'content': '你是一名专业的金融分析师，擅长从海量信息中提炼核心观点，并为投资者提供有价值的决策参考。'},
            {'role': 'user', 'content': user_prompt.strip()}
        ]

        logger.info(f"DEEPSEEK News Summary Prompt:\n{user_prompt}")

        # 5. 调用 DEEPSEEK API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {os.getenv("DEEPSEEK_API_KEY")}'
        }
        
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json={
                'model': 'deepseek-chat',
                'messages': messages,
                'temperature': 0.5,
                'max_tokens': 1000
            }
        )
        
        logger.info(f"DEEPSEEK News Summary Response - Status Code: {response.status_code}")
        logger.info(f"DEEPSEEK News Summary Response - Text: {response.text}")

        if response.status_code != 200:
            raise Exception(f'DEEPSEEK API 调用失败: {response.text}')
            
        result = response.json()
        summary = result['choices'][0]['message']['content']
        
        return jsonify({'summary': summary})

    except Exception as e:
        logger.error(f"资讯总结失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'资讯总结失败: {str(e)}'}), 500

def ak_get_kline_data(symbol, start_date, end_date):
    """
    用 akshare 查询A股、港股、美股K线（日线），返回与 get_kline_data 兼容的列表格式
    symbol: 形如 '000001.SZ', '00700.HK', 'AAPL.US'
    start_date, end_date: 'YYYY-MM-DD'
    """
    try:
        if symbol.endswith('.SZ') or symbol.endswith('.SH'):
            # A股
            stock_code = symbol.split('.')[0]
            ak_start_date = start_date.replace('-', '')
            ak_end_date = end_date.replace('-', '')
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=ak_start_date, end_date=ak_end_date, adjust="qfq")
            logger.info(f"[AKSHARE] 查询A股K线: symbol={symbol}, stock_code={stock_code}, start={ak_start_date}, end={ak_end_date}, 返回行数: {0 if df is None else len(df)}")
            if df is not None and not df.empty:
                logger.info(f"[AKSHARE] A股K线数据示例: {df.head(1).to_dict()}")
            if df is None or df.empty:
                return []
            df = df.rename(columns={
                '日期': 'time_key',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume'
            })
        elif symbol.endswith('.HK'):
            # 港股
            stock_code = symbol.split('.')[0]
            df = ak.stock_hk_daily(symbol=stock_code)
            logger.info(f"[AKSHARE] 查询港股K线: symbol={symbol}, stock_code={stock_code}, start={start_date}, end={end_date}, 返回行数: {0 if df is None else len(df)}")
            if df is not None and not df.empty:
                logger.info(f"[AKSHARE] 港股K线数据示例: {df.head(1).to_dict()}")
            if df is None or df.empty:
                return []
            df = df.rename(columns={
                '日期': 'time_key',
                '开盘价': 'open',
                '收盘价': 'close',
                '最高价': 'high',
                '最低价': 'low',
                '成交量': 'volume'
            })
            df = df[(df['time_key'] >= start_date) & (df['time_key'] <= end_date)]
        elif symbol.endswith('.US'):
            # 美股
            stock_code = symbol.split('.')[0]
            df = ak.stock_us_daily(symbol=stock_code)
            logger.info(f"[AKSHARE] 查询美股K线: symbol={symbol}, stock_code={stock_code}, start={start_date}, end={end_date}, 返回行数: {0 if df is None else len(df)}")
            if df is not None and not df.empty:
                logger.info(f"[AKSHARE] 美股K线数据示例: {df.head(1).to_dict()}")
            if df is None or df.empty:
                return []
            df = df.rename(columns={
                '日期': 'time_key',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume'
            })
            df = df[(df['time_key'] >= start_date) & (df['time_key'] <= end_date)]
        else:
            logger.error(f"ak_get_kline_data: 不支持的symbol格式: {symbol}")
            return []

        # 统一日期格式为 'YYYY-MM-DD' 字符串，以兼容前端
        df['time_key'] = pd.to_datetime(df['time_key']).dt.date.astype(str)

        df = df.sort_values('time_key')
        logger.info(f"[AKSHARE] K线数据排序后总行数: {len(df)}")
        df['EMA5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA60'] = df['close'].ewm(span=60, adjust=False).mean()
        df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = df['EMA12'] - df['EMA26']
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        kline_data = []
        for _, row in df.iterrows():
            kline_data.append({
                'time': row['time_key'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
                'EMA5': float(row['EMA5']) if pd.notna(row['EMA5']) else None,
                'EMA10': float(row['EMA10']) if pd.notna(row['EMA10']) else None,
                'EMA20': float(row['EMA20']) if pd.notna(row['EMA20']) else None,
                'EMA60': float(row['EMA60']) if pd.notna(row['EMA60']) else None,
                'MACD': float(row['MACD']) if pd.notna(row['MACD']) else None,
                'RSI': float(row['RSI']) if pd.notna(row['RSI']) else None
            })
        logger.info(f"[AKSHARE] kline_data最终返回长度: {len(kline_data)}")
        if kline_data:
            logger.info(f"[AKSHARE] kline_data首条: {kline_data[0]}")
        return kline_data
    except Exception as e:
        import traceback
        logger.error(f"ak_get_kline_data error: {e}\n{traceback.format_exc()}")
        return []

@app.route('/quant/stock_list')
def quant_stock_list_flask():
    print("进入 quant_stock_list_flask")
    market = request.args.get('market', '').upper()
    try:
        logger.info("调用 get_stock_list 前, market=%s", market)
        data = get_stock_list(market)
        logger.info("调用 get_stock_list 后, data type=%s", type(data))
        print("data type:", type(data))
        print("data repr:", repr(data))
        if data is None:
            return jsonify({'error': 'get_stock_list 返回 None'}), 500
        return jsonify(data.fillna('').to_dict(orient='records'))
    except Exception as e:
        logger.error("except: %s", traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/kline')
def quant_kline_flask():
    symbol = request.args.get('symbol', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    try:
        from quant import quant_get_stock_kline
        data = quant_get_stock_kline(symbol, start, end)
        if isinstance(data, pd.DataFrame):
            return jsonify(data.fillna('').to_dict(orient='records'))
        else:
            return jsonify({'error': 'quant_get_stock_kline 未返回 DataFrame', 'type': str(type(data))}), 500
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/capital_flow')
def quant_capital_flow_flask():
    symbol = request.args.get('symbol', '')
    try:
        if not get_stock_capital_flow:
            return jsonify({'error': 'quant.py未集成'}), 500
        data = get_stock_capital_flow(symbol)
        return jsonify(data.fillna('').to_dict(orient='records'))
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/news')
def quant_news_flask():
    symbol = request.args.get('symbol', '')
    try:
        if not get_stock_news:
            return jsonify({'error': 'quant.py未集成'}), 500
        data = get_stock_news(symbol)
        from flask import Response
        if isinstance(data, Response):
            return data
        if isinstance(data, pd.DataFrame):
            return jsonify(data.fillna('').to_dict(orient='records'))
        else:
            return jsonify({'error': 'get_stock_news 未返回 DataFrame', 'type': str(type(data))}), 500
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        import logging
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/financials')
def quant_financials_flask():
    symbol = request.args.get('symbol', '')
    try:
        if not get_stock_financials:
            return jsonify({'error': 'quant.py未集成'}), 500
        data = get_stock_financials(symbol)
        return jsonify(data.fillna('').to_dict(orient='records'))
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/analyze')
def quant_analyze_flask():
    symbol = request.args.get('symbol', '')
    try:
        from quant import analyze_stock
        result = analyze_stock(symbol)
        return jsonify(result)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/elliott_wave')
def quant_elliott_wave_flask():
    symbol = request.args.get('symbol', '')
    try:
        from quant import analyze_elliott_wave
        result = analyze_elliott_wave(symbol)
        return jsonify(result)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    if request.method == 'GET':
        user_id = request.args.get('userId', '')
        all_data = load_user_config()
        data = all_data.get(user_id, {
            'userId': user_id,
            'stocks': [],
            'frequency': '5min',
            'rules': [],
            'alerts': []
        })
        return jsonify(data)
    elif request.method == 'POST':
        data = request.get_json(force=True)
        user_id = data.get('userId', '')
        if not user_id:
            return jsonify({'error': 'userId必填'}), 400
        all_data = load_user_config()
        all_data[user_id] = data
        save_user_config(all_data)
        return jsonify({'status': 'ok', 'msg': '设置已保存'})

@app.route('/watchlist/save/monitor', methods=['POST'])
def save_monitor():
    data = request.get_json(force=True)
    user_id = data.get('userId', '')
    if not user_id:
        return jsonify({'error': 'userId必填'}), 400
    
    # 保存监控配置到文件
    all_data = load_monitor_config()
    all_data[user_id] = data
    save_monitor_config(all_data)
    
    # 从监控配置中提取量化股票列表和量化开启状态
    try:
        # 获取监控的股票列表
        quant_stocks = data.get('stocks', [])
        
        # 获取量化交易开启状态
        quant_enabled = data.get('quant_trading_enabled', False)
        
        # 调用数据服务更新用户量化设置
        success = data_service.update_user_quant_settings(
            user_id=user_id,
            quant_enabled=quant_enabled,
            quant_stocks=quant_stocks if quant_stocks else None
        )
        
        if success:
            logger.info(f"用户 {user_id} 的量化设置已更新：quant_enabled={quant_enabled}, quant_stocks={quant_stocks}")
        else:
            logger.warning(f"用户 {user_id} 的量化设置更新失败")
            
    except Exception as e:
        logger.error(f"更新用户量化设置时出错: {str(e)}")
        # 不返回错误，因为监控配置保存成功
    
    return jsonify({'status': 'ok', 'msg': '监控配置已保存'})

@app.route('/watchlist/query/monitor', methods=['GET'])
def query_monitor():
    user_id = request.args.get('userId', '')
    all_data = load_monitor_config()
    data = all_data.get(user_id, {})
    return jsonify(data)

@app.route("/watchlist/<rule>/execute", methods=["POST"])
def execute_watchlist_rule(rule):
    """
    执行观察列表规则
    只处理简单的参数验证和调用业务服务
    """
    try:
        data = request.get_json(force=True)
        user_id = data.get("userId", "")
        if not user_id:
            return jsonify({"error": "userId必填"}), 400
            
        # 调用业务服务执行观察列表规则
        from service.stock_service import execute_watchlist_rule_service
        result = execute_watchlist_rule_service(rule, user_id)
        
        # 处理返回结果
        if "error" in result:
            return jsonify({"error": result["error"]}), result.get("status", 500)
        
        return jsonify({"results": result["results"]})
        
    except Exception as e:
        logger.error(f"执行观察列表规则错误: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
@app.route('/watchlist/last_result', methods=['GET'])
def get_last_result():
    user_id = request.args.get('userId', '')
    if not user_id:
        return {'error': 'userId必填'}, 400
    today = datetime.now().strftime('%Y-%m-%d')
    strategy_log = load_strategy_log()
    user_log = strategy_log.get(today, {}).get(user_id, [])
    if not user_log:
        return {'results': []}
    # 取最新一组 results
    latest = user_log[0]
    return {'results': latest.get('results', [])}

@app.route('/api/stock/batch', methods=['GET', 'POST'])
def get_stock_data_batch():
    try:
        # 支持GET参数和POST JSON
        if request.method == 'POST':
            if request.is_json:
                symbols = request.json.get('symbols', [])
                if isinstance(symbols, str):
                    symbols = [s.strip() for s in symbols.split(',') if s.strip()]
            else:
                return jsonify({'error': 'POST需传递JSON格式，包含symbols字段'}), 400
        else:
            symbols = request.args.get('symbols', '')
            symbols = [s.strip() for s in symbols.split(',') if s.strip()]
        if not symbols or not isinstance(symbols, list):
            return jsonify({'error': '请提供symbols参数，如600519.SH,00700.HK'}), 400
        logger.info(f"[get_stock_data_batch] 批量查询快照 symbols={symbols}")
        result = batch_market_snapshot(symbols)
        data = {}
        for symbol in symbols:
            code_parts = symbol.split('.')
            if len(code_parts) == 2:
                code, market = code_parts[0], code_parts[1].upper()
                # 正确的代码格式转换
                if market == 'HK' and code.isdigit():
                    norm_symbol = f"{market}.{code.zfill(5)}"
                else:
                    norm_symbol = f"{market}.{code}"
            else:
                norm_symbol = symbol
            
            stock_data = None
            if symbol in result:
                stock_data = result[symbol]
            elif norm_symbol in result:
                stock_data = result[norm_symbol]
            if not stock_data:
                data[symbol] = {'error': '未找到股票数据'}
                continue
            data[symbol] = {
                'code': symbol,
                'name': stock_data.get('name'),
                'current_price': float(stock_data.get('last_price', 0)),
                'open_price': float(stock_data.get('open_price', 0)),
                'high_price': float(stock_data.get('high_price', 0)),
                'low_price': float(stock_data.get('low_price', 0)),
                'pre_close': float(stock_data.get('prev_close_price', 0)),
                'volume': int(stock_data.get('volume', 0)),
                'turnover': float(stock_data.get('turnover', 0)),
                'update_time': stock_data.get('update_time')
            }
        return jsonify(data)
    except Exception as e:
        error_msg = f"Error in get_stock_data_batch: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/<symbol>/minute')
def get_stock_minute(symbol):
    """
    查询分时数据，支持A股、港股、美股。返回格式：[{time, price, volume}]
    """
    try:
        import akshare as ak
        import pandas as pd
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return jsonify({'error': 'Invalid stock code format. Expected format: CODE.MARKET (e.g., 00700.HK)'}), 400
        stock_code = code_parts[0]
        market = code_parts[1].upper()
        data = []
        if market in ['SH', 'SZ']:
            # 优先用东方财富接口
            try:
                # 东方财富接口需要无前缀代码和market_code
                market_code = '1' if market == 'SH' or stock_code.startswith('6') else '0'
                df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1')
                if not df.empty:
                    df = df.rename(columns={'时间': 'time', '收盘': 'price', '成交量': 'volume'})
                    data = df[['time', 'price', 'volume']].fillna('').to_dict(orient='records')
            except Exception as e:
                # 降级用新浪接口（需sh/sz前缀）
                try:
                    sina_code = ('sh' if market == 'SH' or stock_code.startswith('6') else 'sz') + stock_code
                    df = ak.stock_zh_a_minute(symbol=sina_code, period='1')
                    if not df.empty:
                        # 新浪接口字段：day, open, high, low, close, volume
                        df = df.rename(columns={'day': 'time', 'close': 'price', 'volume': 'volume'})
                        data = df[['time', 'price', 'volume']].fillna('').to_dict(orient='records')
                except Exception as e2:
                    data = []
        elif market == 'HK':
            try:
                from quant import get_hk_minute_data
                data = get_hk_minute_data(symbol, quote_ctx)
            except Exception as e:
                data = []
        elif market == 'US':
            # 美股分时（akshare暂不支持1m，返回空）
            data = []
        else:
            data = []
        return jsonify(data)
    except Exception as e:
        import traceback
        error_msg = f"Error in get_stock_minute: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/minute/batch', methods=['POST'])
def get_stock_minute_batch():
    """批量查询分时数据，供 MinuteChartPanel 使用。POST body: {"codes": ["000001.SZ", ...]}"""
    try:
        codes = (request.json or {}).get('codes', [])
        results = {}
        for symbol in codes:
            try:
                code_parts = symbol.split('.')
                if len(code_parts) != 2:
                    results[symbol] = []
                    continue
                stock_code, market = code_parts[0], code_parts[1].upper()
                data = []
                if market in ['SH', 'SZ']:
                    try:
                        df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1')
                        if not df.empty:
                            df = df.rename(columns={'时间': 'time', '收盘': 'price', '成交量': 'volume'})
                            data = df[['time', 'price', 'volume']].fillna('').to_dict(orient='records')
                    except Exception:
                        try:
                            prefix = 'sh' if market == 'SH' or stock_code.startswith('6') else 'sz'
                            df = ak.stock_zh_a_minute(symbol=prefix + stock_code, period='1')
                            if not df.empty:
                                df = df.rename(columns={'day': 'time', 'close': 'price', 'volume': 'volume'})
                                data = df[['time', 'price', 'volume']].fillna('').to_dict(orient='records')
                        except Exception:
                            data = []
                elif market == 'HK':
                    try:
                        from quant import get_hk_minute_data
                        data = get_hk_minute_data(symbol, quote_ctx)
                    except Exception:
                        data = []
                results[symbol] = data
            except Exception:
                results[symbol] = []
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/<symbol>/financials')
def get_stock_financials_api(symbol):
    try:
        if not get_stock_financials:
            return jsonify({'error': 'quant.py未集成'}), 500
        data = get_stock_financials(symbol)
        if data is None or (hasattr(data, 'empty') and data.empty):
            return jsonify({'error': '未找到财务数据'}), 404
        return jsonify(data.fillna('').to_dict(orient='records'))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/stock/<symbol>/fundamental')
def get_stock_fundamental(symbol):
    try:
        result = analyze_fundamental(symbol)
        return jsonify(result)
    except Exception as e:
        import traceback
        logger.error(f"/api/stock/<symbol>/fundamental error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/smart_monitor_signals')
def quant_smart_monitor_signals():
    try:
        data = load_latest_smart_monitor_signals()
        return jsonify({'signals': data})
    except Exception as e:
        import traceback
        logger.error(f"[quant_smart_monitor_signals] {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/quant/smart_monitor_signals_by_stock', methods=['POST'])
def quant_smart_monitor_signals_by_stock():
    try:
        data = request.get_json(force=True)
        logger.info(f"[smart_monitor_signals_by_stock] 入参: {data}")
        symbols = data.get('symbols', [])
        limit = int(data.get('limit', 5))
        # 1. 先执行盯盘分析，写入最新数据
        try:
            from quant import smart_watchlist_monitor
            smart_watchlist_monitor(symbols)
        except Exception as e:
            logger.error(f"smart_watchlist_monitor error: {e}")
        # 2. 加载全部历史数据
        all_signals = load_all_smart_monitor_signals()
        # 3. 聚合每个标的的所有事件，只保留time和signal字段，去重并合并同日同signal
        from collections import defaultdict
        import datetime
        result = {}
        for symbol in symbols:
            # 收集所有事件
            raw_events = []
            for time_key in sorted(all_signals.keys(), reverse=True):
                for event in all_signals[time_key]:
                    if event.get('stock') == symbol:
                        raw_events.append({
                            'time': event.get('time'),
                            'signal': event.get('signal'),
                            'signal_type': event.get('signal_type') if 'signal_type' in event else None,
                            'value': event.get('value') if 'value' in event else None
                        })
            # 1. 按 time+signal 去重
            seen = set()
            deduped = []
            for ev in raw_events:
                key = (ev['time'], ev['signal'])
                if key not in seen:
                    deduped.append(ev)
                    seen.add(key)
            # 2. 按日期+signal 合并，计数，保留最新time
            merged = {}
            for ev in deduped:
                # 取日期部分
                import datetime
                try:
                    dt = datetime.datetime.strptime(ev['time'], '%Y-%m-%d %H:%M:%S')
                except Exception:
                    try:
                        dt = datetime.datetime.strptime(ev['time'], '%Y-%m-%d')
                    except Exception:
                        continue
                day = dt.strftime('%Y-%m-%d')
                sig = ev['signal']
                key = (day, sig)
                if key not in merged:
                    merged[key] = {'time': ev['time'], 'signal': sig, 'signal_type': ev.get('signal_type'), 'value': ev.get('value'), 'count': 1}
                else:
                    # 保留最新time
                    if ev['time'] > merged[key]['time']:
                        merged[key]['time'] = ev['time']
                    merged[key]['count'] += 1
            # 3. 生成最终事件列表，按time倒序
            merged_events = []
            for (day, sig), v in merged.items():
                signal_text = v['signal']
                if v['count'] > 1:
                    if 'x' in signal_text and signal_text.endswith(')'):
                        # 避免重复叠加
                        signal_text = signal_text.rsplit('x', 1)[0].rstrip()
                    signal_text = f"{signal_text} x{v['count']}"
                merged_events.append({
                    'time': v['time'],
                    'signal': signal_text,
                    'signal_type': v.get('signal_type'),
                    'value': v.get('value')
                })
            merged_events = sorted(merged_events, key=lambda x: x['time'], reverse=True)
            result[symbol] = merged_events
        logger.info(f"[smart_monitor_signals_by_stock] 返回: { {k: len(v) for k,v in result.items()} }")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in quant_smart_monitor_signals_by_stock: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/quant/capital_distribution')
def quant_capital_distribution_flask():
    symbol = request.args.get('symbol', '')
    try:
        from quant import get_capital_distribution
        data = get_capital_distribution(symbol)
        # 转为dict以便jsonify
        if hasattr(data, 'to_dict'):
            return jsonify(data.to_dict(orient='records'))
        else:
            return jsonify(data)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/stock/<symbol>/order_book', methods=['GET'])
def get_order_book_api(symbol):
    """
    查询个股实时摆盘（Futu/OpenD接口）。
    GET /api/stock/<symbol>/order_book?num=10
    """
    try:
        num = int(request.args.get('num', 10))
        data = get_order_book(symbol, num=num)
        return jsonify({'code': 0, 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'error': str(e)})

@app.route('/api/stock/<symbol>/rt_ticker', methods=['GET'])
def get_rt_ticker_api(symbol):
    """
    查询个股实时逐笔（Futu/OpenD接口）。
    GET /api/stock/<symbol>/rt_ticker?num=500
    """
    try:
        num = int(request.args.get('num', 500))
        data = get_rt_ticker(symbol, num=num)
        # DataFrame 转 dict
        if hasattr(data, 'to_dict'):
            data = data.to_dict(orient='records')
        return jsonify({'code': 0, 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'error': str(e)})

@app.route('/api/trade/init', methods=['POST'])
def api_trade_init():
    data = request.json or {}
    user_id = data.get('user_id')
    force = data.get('force') == 666 or data.get('force') == '666'
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id'}), 400
    result = user_trade_service.init_user_account(user_id, force_init=force)
    return jsonify(result)

@app.route('/api/trade/query', methods=['GET'])
def api_trade_query():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id'}), 400
    result = user_trade_service.query_account(user_id)
    return jsonify(result)

@app.route('/api/trade/order', methods=['POST'])
def api_trade_order():
    data = request.get_json()
    user_id = data.get('user_id')
    symbol = data.get('symbol')
    price = data.get('price')
    amount = data.get('amount')
    side = data.get('side')
    order_reason = data.get('order_reason')
    order_reason_time = data.get('order_reason_time')
    if not user_id or not symbol or price is None or amount is None or not side:
        return jsonify({'success': False, 'msg': '缺少参数'}), 400
    result = user_trade_service.order(user_id, symbol, price, amount, side, order_reason, order_reason_time)
    return jsonify(result)

@app.route('/api/trade/orders', methods=['GET'])
def api_trade_orders():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id'}), 400
    orders = user_trade_service.query_orders(user_id)
    return jsonify({'success': True, 'orders': orders})

@app.route('/api/trade/cancel', methods=['POST'])
def api_trade_cancel():
    data = request.json or {}
    user_id = data.get('user_id')
    order_id = data.get('order_id')
    if not all([user_id, order_id]):
        return jsonify({'success': False, 'msg': '参数不全'}), 400
    result = user_trade_service.cancel_order(user_id, order_id)
    return jsonify(result)

@app.route('/api/trade/market_state', methods=['GET'])
def api_trade_market_state():
    """
    查询指定市场的交易状态
    GET /api/trade/market_state?market=SH
    """
    market = request.args.get('market')
    if not market:
        return jsonify({'success': False, 'msg': '缺少market参数'}), 400
    
    result = user_trade_service.get_market_state(market)
    return jsonify(result)

@app.route('/api/trade/ipo_list', methods=['GET'])
def api_trade_ipo_list():
    """
    查询指定市场的IPO信息
    GET /api/trade/ipo_list?market=SH
    """
    market = request.args.get('market')
    if not market:
        return jsonify({'success': False, 'msg': '缺少market参数'}), 400

    result = user_trade_service.get_ipo_list(market)
    return jsonify(result)

@app.route('/api/trade/trading_days', methods=['GET'])
def api_trade_trading_days():
    """
    查询指定市场或指定标的的交易日历
    GET /api/trade/trading_days?market=HK&start=2024-01-01&end=2024-01-31
    GET /api/trade/trading_days?code=HK.00700&start=2024-01-01&end=2024-01-31
    """
    market = request.args.get('market')
    code = request.args.get('code')
    start = request.args.get('start')
    end = request.args.get('end')
    
    # 至少需要提供市场或股票代码之一
    if not market and not code:
        return jsonify({'success': False, 'msg': '缺少market或code参数'}), 400

    result = user_trade_service.get_trading_days(market=market, start=start, end=end, code=code)
    return jsonify(result)

# ==================== 交易笔记API接口 ====================

@app.route('/api/trade/notes', methods=['POST'])
def api_create_trade_note():
    """
    创建交易笔记
    POST /api/trade/notes
    """
    data = request.get_json()
    user_id = data.get('user_id')
    note_data = data.get('note_data', {})
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.create_trade_note(user_id, note_data)
    return jsonify(result)

@app.route('/api/trade/notes', methods=['GET'])
def api_get_trade_notes():
    """
    获取交易笔记列表
    GET /api/trade/notes?user_id=123&page=1&page_size=20&category=技术分析&search_text=腾讯
    """
    user_id = request.args.get('user_id')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    
    # 构建过滤条件
    filters = {}
    for key in ['category', 'stock_code', 'trade_type', 'trade_result', 'mood', 'status', 'search_text', 'date_from', 'date_to']:
        value = request.args.get(key)
        if value:
            filters[key] = value
    
    # 处理布尔值参数
    is_important = request.args.get('is_important')
    if is_important is not None:
        filters['is_important'] = is_important.lower() == 'true'
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.get_trade_notes(user_id, filters, page, page_size)
    return jsonify(result)

@app.route('/api/trade/notes/<note_id>', methods=['GET'])
def api_get_trade_note(note_id):
    """
    获取单个交易笔记详情
    GET /api/trade/notes/note_id?user_id=123
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.get_trade_note(user_id, note_id)
    return jsonify(result)

@app.route('/api/trade/notes/<note_id>', methods=['PUT'])
def api_update_trade_note(note_id):
    """
    更新交易笔记
    PUT /api/trade/notes/note_id
    """
    data = request.get_json()
    user_id = data.get('user_id')
    update_data = data.get('update_data', {})
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.update_trade_note(user_id, note_id, update_data)
    return jsonify(result)

@app.route('/api/trade/notes/<note_id>', methods=['DELETE'])
def api_delete_trade_note(note_id):
    """
    删除交易笔记
    DELETE /api/trade/notes/note_id?user_id=123
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.delete_trade_note(user_id, note_id)
    return jsonify(result)

@app.route('/api/trade/notes/statistics', methods=['GET'])
def api_get_trade_note_statistics():
    """
    获取交易笔记统计信息
    GET /api/trade/notes/statistics?user_id=123
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.get_trade_note_statistics(user_id)
    return jsonify(result)

@app.route('/api/trade/notes/categories', methods=['GET'])
def api_get_trade_note_categories():
    """
    获取交易笔记分类列表
    GET /api/trade/notes/categories?user_id=123
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.get_trade_note_categories(user_id)
    return jsonify(result)

@app.route('/api/trade/notes/tags', methods=['GET'])
def api_get_trade_note_tags():
    """
    获取交易笔记标签列表
    GET /api/trade/notes/tags?user_id=123
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.get_trade_note_tags(user_id)
    return jsonify(result)

@app.route('/api/trade/orders_by_symbol', methods=['GET'])
def api_trade_orders_by_symbol():
    """
    查询用户历史订单，支持按股票代码过滤
    GET /api/trade/orders_by_symbol?user_id=xxx&symbol=00700.HK
    """
    user_id = request.args.get('user_id')
    symbol = request.args.get('symbol')
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400
    orders = user_trade_service.query_orders_by_symbol(user_id, symbol)
    return jsonify({'success': True, 'orders': orders})

@app.route('/share/note/<note_id>', methods=['GET'])
def api_share_note(note_id):
    """
    查询分享的笔记详情（公开接口，不需要user_id验证）
    GET /share/note/note_id?user_id=123
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'msg': '缺少user_id参数'}), 400

    result = user_trade_service.get_trade_note(user_id, note_id)
    return jsonify(result)

@app.route('/api/plates/<market>', methods=['GET'])
def api_get_plate_list(market):
    """
    获取板块列表
    GET /api/plates/HK?plate_class=CONCEPT
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        from futu import Market, Plate
        
        # 解析市场参数
        market_map = {
            'HK': Market.HK,
            'US': Market.US,
            'SH': Market.SH,
            'SZ': Market.SZ
        }
        
        if market not in market_map:
            return jsonify({'error': '不支持的市场类型'}), 400
        
        futu_market = market_map[market]
        
        # 解析板块分类参数
        plate_class = request.args.get('plate_class', 'CONCEPT')
        plate_map = {
            'CONCEPT': Plate.CONCEPT,
            'INDUSTRY': Plate.INDUSTRY,
            'REGION': Plate.REGION,
            'OTHER': Plate.OTHER
        }
        
        if plate_class not in plate_map:
            return jsonify({'error': '不支持的板块分类'}), 400
        
        futu_plate_class = plate_map[plate_class]
        
        # 获取板块列表
        client = FutuClient()
        plates = client.get_plate_list(futu_market, futu_plate_class)
        client.close()
        
        return jsonify({
            'success': True,
            'market': market,
            'plate_class': plate_class,
            'plates': plates,
            'count': len(plates)
        })
        
    except Exception as e:
        logger.error(f"获取板块列表失败: {str(e)}")
        return jsonify({'error': f'获取板块列表失败: {str(e)}'}), 500

@app.route('/api/plates/<market>/all', methods=['GET'])
def api_get_all_plate_lists(market):
    """
    获取指定市场的所有板块分类
    GET /api/plates/HK/all
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        from futu import Market
        
        # 解析市场参数
        market_map = {
            'HK': Market.HK,
            'US': Market.US,
            'SH': Market.SH,
            'SZ': Market.SZ
        }
        
        if market not in market_map:
            return jsonify({'error': '不支持的市场类型'}), 400
        
        futu_market = market_map[market]
        
        # 获取所有板块分类
        client = FutuClient()
        all_plates = client.get_all_plate_lists(futu_market)
        client.close()
        
        return jsonify({
            'success': True,
            'market': market,
            'plate_lists': all_plates
        })
        
    except Exception as e:
        logger.error(f"获取所有板块列表失败: {str(e)}")
        return jsonify({'error': f'获取所有板块列表失败: {str(e)}'}), 500

@app.route('/api/plates/<market>/search', methods=['GET'])
def api_search_plate(market):
    """
    搜索板块
    GET /api/plates/HK/search?plate_class=CONCEPT&keyword=科技
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        from futu import Market, Plate
        
        # 解析市场参数
        market_map = {
            'HK': Market.HK,
            'US': Market.US,
            'SH': Market.SH,
            'SZ': Market.SZ
        }
        
        if market not in market_map:
            return jsonify({'error': '不支持的市场类型'}), 400
        
        futu_market = market_map[market]
        
        # 解析参数
        plate_class = request.args.get('plate_class', 'CONCEPT')
        keyword = request.args.get('keyword', '')
        
        if not keyword:
            return jsonify({'error': '缺少搜索关键词'}), 400
        
        plate_map = {
            'CONCEPT': Plate.CONCEPT,
            'INDUSTRY': Plate.INDUSTRY,
            'REGION': Plate.REGION,
            'OTHER': Plate.OTHER
        }
        
        if plate_class not in plate_map:
            return jsonify({'error': '不支持的板块分类'}), 400
        
        futu_plate_class = plate_map[plate_class]
        
        # 搜索板块
        client = FutuClient()
        matched_plates = client.search_plate_by_name(futu_market, futu_plate_class, keyword)
        client.close()
        
        return jsonify({
            'success': True,
            'market': market,
            'plate_class': plate_class,
            'keyword': keyword,
            'plates': matched_plates,
            'count': len(matched_plates)
        })
        
    except Exception as e:
        logger.error(f"搜索板块失败: {str(e)}")
        return jsonify({'error': f'搜索板块失败: {str(e)}'}), 500

@app.route('/api/stocks/plates', methods=['GET'])
def api_get_stocks_plates():
    """
    获取股票所属板块信息
    GET /api/stocks/plates?codes=HK.00700,HK.09988&plate_type=CONCEPT
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        from futu import Plate
        
        # 解析股票代码列表
        codes_param = request.args.get('codes', '')
        if not codes_param:
            return jsonify({'error': '缺少股票代码参数'}), 400
        
        codes = [code.strip() for code in codes_param.split(',') if code.strip()]
        if not codes:
            return jsonify({'error': '股票代码列表为空'}), 400
        
        # 解析板块类型过滤参数
        plate_type_param = request.args.get('plate_type', '')
        plate_type = None
        if plate_type_param:
            plate_map = {
                'CONCEPT': Plate.CONCEPT,
                'INDUSTRY': Plate.INDUSTRY,
                'REGION': Plate.REGION,
                'OTHER': Plate.OTHER
            }
            if plate_type_param not in plate_map:
                return jsonify({'error': '不支持的板块类型'}), 400
            plate_type = plate_map[plate_type_param]
        
        # 获取股票所属板块信息
        client = FutuClient()
        if plate_type:
            stocks_plates = client.get_stocks_plates_by_type(codes, plate_type)
        else:
            stocks_plates = client.get_owner_plate(codes)
        client.close()
        
        return jsonify({
            'success': True,
            'codes': codes,
            'plate_type': plate_type_param if plate_type_param else 'ALL',
            'stocks': stocks_plates,
            'count': len(stocks_plates)
        })
        
    except Exception as e:
        logger.error(f"获取股票所属板块失败: {str(e)}")
        return jsonify({'error': f'获取股票所属板块失败: {str(e)}'}), 500

@app.route('/api/stocks/<symbol>/plates', methods=['GET'])
def api_get_stock_plates(symbol):
    """
    获取单个股票的所属板块信息
    GET /api/stocks/HK.00700/plates
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        
        # 获取单个股票的所属板块信息
        client = FutuClient()
        stock_plates = client.get_stock_plates(symbol)
        client.close()
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'stock': stock_plates
        })
        
    except Exception as e:
        logger.error(f"获取股票{symbol}所属板块失败: {str(e)}")
        return jsonify({'error': f'获取股票所属板块失败: {str(e)}'}), 500

@app.route('/api/plate/ranking/<market>/<plate_class>', methods=['GET'])
def api_get_plate_ranking(market, plate_class):
    """
    获取板块行情排名
    GET /api/plate/ranking/HK/CONCEPT
    GET /api/plate/ranking/HK/CONCEPT?date=20240812
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        from service.stock_service import get_plate_ranking, get_plate_ranking_history
        
        # 获取日期参数
        date = request.args.get('date')
        
        # 如果指定了日期，查询历史数据
        if date:
            logger.info(f"查询{market}市场{plate_class}板块{date}的历史排名数据")
            result = get_plate_ranking_history(market, plate_class, date)
            
            if result['success']:
                # 转换历史数据格式，使其与实时数据格式一致
                history_data = result['data']
                return jsonify({
                    'success': True,
                    'market': market,
                    'plate_class': plate_class,
                    'date': date,
                    'total_count': history_data.get('total_count', 0),
                    'valid_count': len(history_data.get('rankings', [])),
                    'rankings': history_data.get('rankings', []),
                    'update_time': history_data.get('update_time', ''),
                    'is_history': True
                })
            else:
                return jsonify(result), 404
        else:
            # 查询实时数据
            logger.info(f"查询{market}市场{plate_class}板块的实时排名数据")
            
            # 初始化FutuClient
            client = FutuClient()
            
            # 获取板块排名
            result = get_plate_ranking(market, plate_class, client, batch_market_snapshot)
            
            # 关闭连接
            client.close()
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"获取板块排名失败: {str(e)}")
        return jsonify({'error': f'获取板块排名失败: {str(e)}'}), 500

@app.route('/api/plate/ranking/all', methods=['GET'])
def api_get_all_plate_rankings():
    """
    获取所有市场的板块排名
    GET /api/plate/ranking/all
    """
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'core'))
        from futu_client import FutuClient
        from service.stock_service import get_all_markets_plate_rankings
        
        # 初始化FutuClient
        client = FutuClient()
        
        # 获取所有市场板块排名
        result = get_all_markets_plate_rankings(client, batch_market_snapshot)
        
        # 关闭连接
        client.close()
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"获取所有市场板块排名失败: {str(e)}")
        return jsonify({'error': f'获取所有市场板块排名失败: {str(e)}'}), 500

@app.route('/api/plate/ranking/history/<market>/<plate_class>', methods=['GET'])
def api_get_plate_ranking_history(market, plate_class):
    """
    获取历史板块排名数据
    GET /api/plate/ranking/history/HK/CONCEPT?date=20240812
    """
    try:
        from service.stock_service import get_plate_ranking_history
        
        # 获取日期参数
        date = request.args.get('date')
        
        # 获取历史数据
        result = get_plate_ranking_history(market, plate_class, date)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"获取历史板块排名失败: {str(e)}")
        return jsonify({'error': f'获取历史板块排名失败: {str(e)}'}), 500

@app.route('/api/quant/diagnosis/<symbol>', methods=['GET'])
def get_stock_diagnosis_endpoint(symbol):
    """
    获取个股诊断分析
    
    Args:
        symbol: 股票代码，如000001.SZ
        
    Returns:
        完整的个股诊断分析结果，包含16个结构化字段
    """
    try:
        if not symbol:
            return jsonify({'error': '股票代码不能为空'}), 400
        
        # 调用个股诊断服务
        result = get_stock_diagnosis(symbol)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"个股诊断失败 {symbol}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/quant/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'quant_diagnosis',
        'version': '1.0.0'
    })

# 新增：查询诊断报告的接口
from service.quant_trading import query_diagnosis_reports, get_all_diagnosis_reports

@app.route('/api/quant/diagnosis/query', methods=['GET'])
def query_diagnosis_reports_api():
    """
    查询诊断报告接口
    
    Args:
        symbols: 股票代码，支持单个或多个（逗号分隔）
        date: 查询日期（格式：YYYY-MM-DD），未指定时返回最新数据
        
    Returns:
        诊断报告查询结果
        未指定日期时返回最新数据，指定日期时返回该日期数据
    """
    try:
        symbols = request.args.get('symbols')
        date = request.args.get('date')
        
        if not symbols:
            return jsonify({'error': 'symbols参数不能为空'}), 400
        
        # 处理symbols参数，支持逗号分隔的多个股票
        symbol_list = [s.strip() for s in symbols.split(',')]
        
        # 调用查询方法
        result = query_diagnosis_reports(symbol_list, date)
        
        # 检查是否有错误
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify({
            'success': True,
            'data': result,
            'query_params': {
                'symbols': symbol_list,
                'date': result.get('date', date)  # 使用实际查询的日期
            }
        })
        
    except Exception as e:
        logger.error(f"查询诊断报告失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/quant/execute', methods=['GET', 'POST'])
def execute_quant_trading():
    """
    执行当日量化交易策略
    
    GET /api/quant/execute?user_id=123&symbols=000001,000002
    POST /api/quant/execute {"user_id": "123", "symbols": ["000001", "000002"]}
    """
    try:
        from service.quant_trading import execute_daily_quant_trading
        
        # 解析用户ID参数（必填）
        user_id = None
        if request.method == 'POST':
            if request.is_json:
                user_id = request.json.get('user_id')
                if not user_id:
                    return jsonify({'success': False, 'error': '用户ID不能为空'}), 400
                symbols = request.json.get('symbols', [])
                if isinstance(symbols, str):
                    symbols = [s.strip() for s in symbols.split(',') if s.strip()]
            else:
                return jsonify({'success': False, 'error': 'POST需传递JSON格式，包含user_id字段'}), 400
        else:
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'success': False, 'error': '用户ID不能为空'}), 400
            symbols_str = request.args.get('symbols', '')
            symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]
        
        # 执行量化交易
        logger.info(f"[execute_quant_trading] 用户{user_id}开始执行量化交易 symbols={symbols}")
        result = execute_daily_quant_trading(user_id, symbols if symbols else None)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result,
                'user_id': user_id,
                'message': f'用户{user_id}量化交易执行完成 - 买入: {len(result.get("buy_executions", []))}, 卖出: {len(result.get("sell_executions", []))}',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'user_id': user_id,
                'error': result.get('error', '执行失败'),
                'timestamp': datetime.now().isoformat()
            }), 400
            
    except Exception as e:
        logger.error(f"执行量化交易失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/quant/orders/active', methods=['GET'])
def get_active_quant_orders():
    """
    获取活跃量化订单
    GET /api/quant/orders/active?user_id=123
    """
    try:
        from service.quant_trading import get_active_quant_orders
        
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '用户ID不能为空'}), 400
        
        orders = get_active_quant_orders(user_id)
        return jsonify({
            'success': True,
            'data': orders,
            'user_id': user_id,
            'count': len(orders),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取活跃订单失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/quant/account', methods=['GET'])
def get_quant_account_info():
    """
    获取量化交易账户信息
    GET /api/quant/account?user_id=123
    """
    try:
        from service.quant_trading import get_quant_account_summary
        
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '用户ID不能为空'}), 400
        
        summary = get_quant_account_summary(user_id)
        return jsonify({
            'success': True,
            'data': summary,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取账户信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/quant/predictions/history/<symbol>', methods=['GET'])
def get_stock_predictions_history(symbol):
    """
    获取指定股票的历史预测数据
    GET /api/quant/predictions/history/<symbol>
    
    参数:
        symbol: 股票代码，如 300059.SZ
        days: 查询天数，默认30天（可选参数）
        start_date: 开始日期，格式YYYY-MM-DD（可选参数）
        end_date: 结束日期，格式YYYY-MM-DD（可选参数）
        
    返回:
        {
            "success": true,
            "data": {
                "2024-11-01": {预测数据},
                "2024-10-31": {预测数据},
                ...
            },
            "symbol": "300059.SZ",
            "total_count": 30,
            "date_range": {"start": "2024-10-02", "end": "2024-11-01"}
        }
    """
    try:
        from service.quant_trading import query_diagnosis_reports
        from datetime import datetime, timedelta
        from flask import request
        
        # 获取查询参数
        days = request.args.get('days', type=int, default=30)
        start_date = request.args.get('start_date', type=str)
        end_date = request.args.get('end_date', type=str)
        
        # 计算日期范围
        if start_date and end_date:
            # 使用指定的日期范围
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "日期格式错误，请使用YYYY-MM-DD格式",
                    "symbol": symbol
                }), 400
        else:
            # 使用天数计算日期范围
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)
            start_date = start_dt.strftime('%Y-%m-%d')
            end_date = end_dt.strftime('%Y-%m-%d')
        
        # 获取所有相关日期的诊断数据
        all_data = {}
        current_dt = start_dt
        
        while current_dt <= end_dt:
            date_str = current_dt.strftime('%Y-%m-%d')
            result = query_diagnosis_reports(symbol, date=date_str)
            
            if "error" not in result and symbol in result.get("results", {}):
                diagnosis_data = result["results"][symbol]
                if "diagnosis" in diagnosis_data:
                    all_data[date_str] = diagnosis_data["diagnosis"]
            
            current_dt += timedelta(days=1)
        
        # 构建返回结果
        if all_data:
            sorted_dates = sorted(all_data.keys())
            formatted_result = {
                "success": True,
                "data": all_data,
                "symbol": symbol,
                "total_count": len(all_data),
                "date_range": {
                    "start": sorted_dates[0] if sorted_dates else start_date,
                    "end": sorted_dates[-1] if sorted_dates else end_date
                },
                "query_params": {
                    "days": days,
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
            return jsonify(formatted_result)
        else:
            return jsonify({
                "success": False,
                "error": f"在指定日期范围内未找到{symbol}的诊断数据",
                "symbol": symbol,
                "date_range": {"start": start_date, "end": end_date}
            }), 404
            
    except Exception as e:
        logger.error(f"获取股票预测历史数据接口异常: {symbol}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'symbol': symbol,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/quant/user/trades', methods=['GET'])
def get_user_trades():
    """
    获取用户历史交易记录
    GET /api/quant/user/trades?user_id=123[&symbol=AAPL&start_date=2024-01-01&end_date=2024-12-31]
    
    参数:
        user_id: 必需参数，用户ID
        symbol: 可选参数，股票代码
        start_date: 可选参数，开始日期(YYYY-MM-DD)
        end_date: 可选参数，结束日期(YYYY-MM-DD)
    
    返回:
        用户历史交易记录数据
    """
    try:
        user_id = request.args.get('user_id')
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': '用户ID不能为空',
                'message': '请提供user_id参数'
            }), 400
        
        # 调用服务层获取用户交易历史
        result = get_user_trade_history(user_id, symbol, start_date, end_date)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"获取用户交易历史接口异常: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取用户交易历史失败',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/quant/positions/update', methods=['GET'])
def update_user_positions_endpoint():
    """
    更新用户持仓信息
    GET /api/quant/positions/update
    
    请求参数:
    - user_id: 用户ID (必填)
    - initial_cash: 初始资金 (可选, 默认100万)
    
    返回:
    - success: 是否成功
    - message: 操作结果描述
    - positions: 更新后的持仓信息
    - total_trades: 总交易次数
    - total_value: 持仓总市值
    """
    try:
        user_id = request.args.get('user_id')
        initial_cash = request.args.get('initial_cash')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id参数不能为空'
            }), 400
        
        # 转换initial_cash为float类型
        if initial_cash:
            try:
                initial_cash = float(initial_cash)
            except (ValueError, TypeError):
                initial_cash = 1000000.0
        else:
            initial_cash = 1000000.0
        
        # 调用position_manager更新持仓
        result = update_user_positions(user_id, initial_cash)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': result.get('message', '持仓信息更新成功'),
                'positions': result.get('positions', {}),
                'total_trades': result.get('total_trades', 0),
                'total_value': result.get('total_value', 0),
                'current_cash': result.get('current_cash', initial_cash),
                'last_update': result.get('last_update', datetime.now().isoformat())
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '更新持仓信息失败')
            }), 500
            
    except Exception as e:
        logger.error(f"更新用户持仓信息失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'更新用户持仓信息失败: {str(e)}'
        }), 500

@app.route('/api/quant/positions', methods=['GET'])
def get_user_positions_endpoint():
    """
    获取用户当前持仓信息
    GET /api/quant/positions
    
    请求参数:
    - user_id: 用户ID (必填)
    
    返回:
    - success: 是否成功
    - positions: 当前持仓信息
    - total_value: 持仓总市值
    - current_cash: 当前现金余额
    - total_trades: 总交易次数
    - last_update: 最后更新时间
    """
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id参数不能为空'
            }), 400
        
        # 调用position_manager获取持仓
        result = get_user_positions(user_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'positions': result.get('positions', {}),
                'total_value': result.get('total_value', 0),
                'current_cash': result.get('current_cash', 1000000.0),
                'total_trades': result.get('total_trades', 0),
                'last_update': result.get('last_update', '')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '获取持仓信息失败')
            }), 500
            
    except Exception as e:
        logger.error(f"获取用户持仓信息失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'获取用户持仓信息失败: {str(e)}'
        }), 500

@app.route('/api/quant/health', methods=['GET'])
def quant_health_check():
    """
    量化交易服务健康检查
    GET /api/quant/health
    """
    return jsonify({
        'success': True,
        'message': '量化交易服务运行正常',
        'timestamp': datetime.now().isoformat(),
        'endpoints': [
            'GET/POST /api/quant/execute?user_id=123[&symbols=000001,000002]',
            'GET /api/quant/orders/active?user_id=123',
            'POST /api/quant/orders/clear {"user_id": "123"}',
            'GET /api/quant/account?user_id=123',
            'GET /api/quant/predictions/history/<symbol>',
            'GET /api/quant/predictions/history',
            'GET /api/quant/user/trades?user_id=123[&symbol=AAPL&start_date=2024-01-01&end_date=2024-12-31]',
            'GET /api/quant/positions/update?user_id=123',
            'GET /api/quant/positions?user_id=123',
            'GET /api/quant/health'
        ],
        'note': '所有接口都需要提供user_id参数'
    })

# 服务启动时自动启动定时任务（使用极简调度器）
def start_scheduler():
    """启动极简定时任务"""
    if not SCHEDULER_AVAILABLE:
        logger.warning("定时任务模块不可用，跳过自动启动")
        return
    
    try:
        success = start_simple_scheduler()
        if success:
            logger.info("✅ 极简定时任务已随服务自动启动")
        else:
            logger.info("极简定时任务已在运行中")
    except Exception as e:
        logger.error(f"❌ 启动极简定时任务失败: {str(e)}")

@app.route('/api/quant/positions/details', methods=['GET'])
def get_position_details_endpoint():
    """
    获取用户持仓明细信息
    GET /api/quant/positions/details
    
    请求参数:
    - user_id: 用户ID (必填)
    - symbol: 股票代码 (可选)
    - status: 持仓状态 ('active', 'partial_sold', 'closed', 'cancelled') (可选)
    - active_only: 是否只返回活跃持仓 (可选, 默认true)
    
    返回:
    - success: 是否成功
    - position_details: 持仓明细列表
    - summary: 汇总统计信息
    - user_id: 用户ID
    - query_params: 查询参数
    """
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id参数不能为空'
            }), 400
        
        # 获取可选参数
        symbol = request.args.get('symbol')
        status = request.args.get('status')
        active_only = request.args.get('active_only', 'true').lower() != 'false'
        
        # 调用position_manager获取持仓明细
        result = get_user_position_details(
            user_id=user_id,
            symbol=symbol,
            status=status,
            active_only=active_only
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'position_details': result.get('position_details', []),
                'summary': result.get('summary', {}),
                'user_id': result.get('user_id', user_id),
                'query_params': result.get('query_params', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '获取持仓明细失败')
            }), 500
            
    except Exception as e:
        logger.error(f"获取用户持仓明细失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'获取用户持仓明细失败: {str(e)}'
        }), 500

@app.route('/api/quant/positions/recalculate', methods=['GET'])
def recalculate_positions_endpoint():
    """
    重算用户所有持仓信息
    GET /api/quant/positions/recalculate
    
    请求参数:
    - user_id: 用户ID (必填)
    - initial_cash: 初始资金 (可选，单位：元)
    
    返回:
    - success: 是否成功
    - message: 操作结果描述
    - positions: 重新计算后的持仓信息
    - total_trades: 总交易次数
    - total_value: 持仓总市值
    - current_cash: 当前现金
    - user_id: 用户ID
    """
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id参数不能为空'
            }), 400
        
        # 获取可选参数
        initial_cash_str = request.args.get('initial_cash')
        initial_cash = None
        if initial_cash_str:
            try:
                initial_cash = float(initial_cash_str)
                if initial_cash <= 0:
                    return jsonify({
                        'success': False,
                        'error': 'initial_cash必须大于0'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'initial_cash格式错误，请输入数字'
                }), 400
        
        # 调用recalculate_user_positions重算持仓
        from service.position_manager import recalculate_user_positions
        result = recalculate_user_positions(user_id=user_id, initial_cash=initial_cash)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': result.get('message', '持仓重算成功'),
                'positions': result.get('positions', {}),
                'total_trades': result.get('total_trades', 0),
                'total_value': result.get('total_value', 0),
                'current_cash': result.get('current_cash', 0),
                'user_id': result.get('user_id', user_id),
                'last_update': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '持仓重算失败')
            }), 500
            
    except Exception as e:
        logger.error(f"重算用户持仓失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'重算用户持仓失败: {str(e)}'
        }), 500

@app.route('/api/quant/trades/<int:record_id>', methods=['GET'])
def delete_trade_record_endpoint(record_id):
    """
    根据ID删除交易记录
    DELETE /api/quant/trades/<record_id>
    
    路径参数:
    - record_id: 交易记录ID (必填)
    
    返回:
    - success: 是否成功
    - message: 操作结果描述
    - deleted_id: 被删除的记录ID
    - deleted_count: 删除的记录数量
    """
    try:
        # 调用data_service删除交易记录
        from service.storage.data_service import data_service
        success = data_service.delete_trade_record_by_id(record_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'交易记录 {record_id} 删除成功',
                'deleted_id': record_id,
                'deleted_count': 1
            })
        else:
            return jsonify({
                'success': False,
                'error': f'未找到ID为 {record_id} 的交易记录'
            }), 404
            
    except Exception as e:
        logger.error(f"删除交易记录失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'删除交易记录失败: {str(e)}'
        }), 500

# 在服务启动时自动启动定时任务
start_scheduler()

if __name__ == '__main__':
    from datetime import datetime
    print("🚀 启动服务...")
    print("📡 服务地址: http://localhost:5001")
    print("📊 量化交易接口：")
    print("  GET/POST  http://localhost:5001/api/quant/execute?user_id=123[&symbols=000001,000002]")
    print("  GET       http://localhost:5001/api/quant/orders/active?user_id=123")
    print("  GET       http://localhost:5001/api/quant/account?user_id=123")
    print("  GET       http://localhost:5001/api/quant/user/trades?user_id=123[&symbol=AAPL&start_date=2024-01-01&end_date=2024-12-31]")
    print("  GET       http://localhost:5001/api/quant/user/trades/summary?user_id=123")
    print("  GET       http://localhost:5001/api/quant/positions/update?user_id=123")
    print("  GET       http://localhost:5001/api/quant/positions?user_id=123")
    print("  GET       http://localhost:5001/api/quant/positions/details?user_id=123[&symbol=000001.SZ&status=active&active_only=true]")
    print("  GET       http://localhost:5001/api/quant/positions/recalculate?user_id=123[&initial_cash=1000000]")
    print("  GET    http://localhost:5001/api/quant/trades/123 (删除单条交易记录)")
    print("  GET       http://localhost:5001/api/quant/health")
    print("⏰ 定时任务：周一到周五执行一次")
    app.run(host='0.0.0.0', port=5001, debug=True)
