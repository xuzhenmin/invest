from flask import Flask, jsonify, request
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
import talib  # 使用 ta-lib 替代 ta

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
def get_stock_data(symbol):
    try:
        # 解析股票代码和市场
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return jsonify({'error': 'Invalid stock code format. Expected format: CODE.MARKET (e.g., 00700.HK)'}), 400
        
        stock_code = code_parts[0]
        market = code_parts[1].upper()
        
        # 获取实时行情
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, data = quote_ctx.get_market_snapshot([f'{market}.{stock_code}'])
        quote_ctx.close()
        
        if ret != RET_OK:
            error_msg = f"Failed to get market snapshot: {data}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
            
        if data.empty:
            return jsonify({'error': '未找到股票数据'}), 404
            
        stock_data = data.iloc[0]
        return jsonify({
            'code': symbol,
            'name': stock_data['name'],
            'current_price': float(stock_data['last_price']),
            'open_price': float(stock_data['open_price']),
            'high_price': float(stock_data['high_price']),
            'low_price': float(stock_data['low_price']),
            'pre_close': float(stock_data['prev_close_price']),
            'volume': int(stock_data['volume']),
            'turnover': float(stock_data['turnover']),
            'update_time': stock_data['update_time']
        })
    except Exception as e:
        error_msg = f"Error in get_stock_data: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@app.route('/api/stock/<symbol>/kline')
def get_stock_kline(symbol):
    try:
        kline_data = get_kline_data(symbol)
        if not kline_data:
            return jsonify({'error': '未找到K线数据'}), 404
        return jsonify(kline_data)
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

        # 获取历史资金流向数据（最近一年）
        ret, historical_data = quote_ctx.get_capital_flow(
            stock_code=f'HK.{symbol}',
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
            stock_code=f'HK.{symbol}',
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
                historical_flow.append({
                    'date': row['capital_flow_item_time'],
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
                intraday_flow.append({
                    'time': row['capital_flow_item_time'],
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
        if market not in ['SH', 'SZ', 'HK']:
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
    Get capital flow data for a given stock symbol.
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

        # Get historical capital flow data (last year)
        ret, historical_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.DAY,
            start=None,  # Default to last year
            end=None
        )

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
        近30日资金流向（JSON）：
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

SYSTEM_PROMPT_TEMPLATE = """
作为一只专注于港股的量化交易AI，你的任务是根据提供的股票数据，给出专业的诊断分析报告。
请严格按照以下JSON格式输出所有分析结果，不要包含任何多余的文本或Markdown围栏（如```json```）。确保JSON的完整性和正确性。
分析结果必须包含以下所有字段：
{
  "technical_analysis": {
    "ema_crosses": "详细描述各EMA交叉情况及其对短期、中期、长期趋势的影响，例如：EMA5上穿EMA10形成金叉，预示短期看涨；EMA20下穿EMA60形成死叉，可能预示长期趋势转弱。", // EMA交叉情况
    "ema_trends": "详细描述各EMA线的近期走势及其对股价的指示作用，例如：EMA5、EMA10、EMA20均呈现多头排列，且向上发散，表明市场处于强势上涨趋势。", // 各EMA趋势
    "price_ema_relation": "详细描述当前价格与各EMA线的相对位置，以及这些EMA线如何形成支撑或压力，例如：当前价格站稳EMA5之上，EMA5对股价形成短期支撑，而EMA60则构成长期压力位。", // 价格与EMA的关系
    "trend_judgment": "详细的趋势判断，例如：短期震荡整理，中期趋势向上，长期维持牛市格局。"
  },
  "capital_flow_analysis": {
    "30d_trend": "详细描述近30日资金的净流入/流出情况及其波动特征，例如：近30日累计净流入达到X亿元，资金活跃度较高，但近期波动有所增加。", // 近30日资金流向趋势
    "main_capital": "详细描述主力资金的流向和强度，以及其对股价的潜在影响，例如：主力资金连续X日净流入，大单买入强度较高，显示主力资金看好后市，有望推动股价上涨。", // 主力资金动向
    "strength_assessment": "对资金实力进行评估，例如：资金实力雄厚，有能力推动股价上涨。"
  },
  "capital_distribution_analysis": {
    "main_capital_distribution": "详细描述主力资金的分布情况，例如：超级大户和大户资金占比约45%，近期呈现净流入状态。",
    "retail_capital_distribution": "详细描述散户资金的分布情况，例如：散户资金占比约55%，近期流出压力较大，活跃度下降。",
    "capital_structure": "对资金结构进行概括性描述，例如：主力资金与散户资金均较活跃，但近期散户资金流出明显。"
  },
  "investment_advice": "基于以上分析给出的投资建议，例如：短期建议观望等待趋势明朗，中长期可逢低布局，关注500元附近的支撑位。",
  "risk_warning": "风险提示，例如：需警惕技术面短期调整风险，以及资金面主力资金持续流出的潜在风险。",
  "overall_score": 0, // 综合评分，0-100
  "technical_score": 0, // 技术面评分，0-100
  "capital_score": 0, // 资金面评分，0-100
  "score": {
    "total_score": 0, // 综合评分，0-100
    "grade": "A/B/C/D/F", // 综合评级
    "technical_score": 0, // 技术面评分，0-100
    "technical_grade": "A/B/C/D/F", // 技术面评级
    "capital_score": 0, // 资金面评分，0-100
    "capital_grade": "A/B/C/D/F" // 资金面评级
  }
}
"""

def analyze_with_deepseek(data):
    """
    使用DEEPSEEK分析股票数据
    """
    try:
        # 提取相关数据用于构建提示
        technical_data = data.get('technical_indicators', {})
        capital_flow_data = data.get('capital_flow', {})

        # 将相关数据转换为JSON字符串，以便嵌入到提示中
        technical_json = json.dumps(technical_data, indent=2, ensure_ascii=False)
        capital_flow_json = json.dumps(capital_flow_data, indent=2, ensure_ascii=False)

        # 构建用户提示
        user_prompt = f"""
        请对股票 {data['symbol']} 进行全面的技术分析和资金面分析。以下是相关数据：

        **技术指标数据 (最近30天):**
        ```json
        {technical_json}
        ```

        **资金流向和分布数据:**
        ```json
        {capital_flow_json}
        ```

        请根据以上数据，严格按照系统提示的JSON格式返回分析结果。特别注意：
        1. 必须返回具体的数值评分（0-100的整数）
        2. 必须返回具体的评级（A/B/C/D/F）
        3. 所有评分和评级必须基于数据客观计算得出
        """
        
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT_TEMPLATE.strip()},
            {'role': 'user', 'content': user_prompt.strip()}
        ]

        # 打印大模型输入日志
        logger.info(f"DEEPSEEK Request - Messages: {json.dumps(messages, indent=2, ensure_ascii=False)}")

        # 调用DEEPSEEK API
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
                'temperature': 0.7,
                'max_tokens': 2000
            }
        )
        
        # 打印大模型原始输出日志
        logger.info(f"DEEPSEEK Response - Status Code: {response.status_code}")
        logger.info(f"DEEPSEEK Response - Text: {response.text}")

        if response.status_code != 200:
            raise Exception(f'DEEPSEEK API调用失败: {response.text}')
            
        result = response.json()
        analysis_text = result['choices'][0]['message']['content']
        
        # 移除Markdown代码块围栏，确保是纯JSON
        if analysis_text.startswith('```json') and analysis_text.endswith('```'):
            analysis_text = analysis_text[7:-3].strip()
        
        # 再次尝试移除可能存在的其他Markdown代码块围栏
        analysis_text = analysis_text.replace('```json', '').replace('```', '').strip()

        # 解析返回的JSON文本
        try:
            analysis_data = json.loads(analysis_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from DEEPSEEK API: {analysis_text}")
            # 如果返回的不是有效的JSON，设置默认评分
            analysis_data = {
                'technical_analysis': analysis_text, 
                'capital_flow_analysis': '无法解析资金流向分析',
                'capital_distribution_analysis': '无法解析资金分布分析',
                'score': {
                    'total_score': 50,
                    'grade': 'C',
                    'technical_score': 50,
                    'technical_grade': 'C',
                    'capital_score': 50,
                    'capital_grade': 'C'
                },
                'investment_advice': '请参考技术分析结果',
                'risk_warning': '请注意投资风险'
            }
        
        # 确保score字段存在且包含所有必要的子字段
        if 'score' not in analysis_data:
            analysis_data['score'] = {}
        
        # 设置默认评分和评级
        default_scores = {
            'total_score': 50,
            'grade': 'C',
            'technical_score': 50,
            'technical_grade': 'C',
            'capital_score': 50,
            'capital_grade': 'C'
        }
        
        # 确保所有评分字段都存在且为有效数值
        for key, default_value in default_scores.items():
            if key not in analysis_data['score'] or not isinstance(analysis_data['score'][key], (int, float)):
                analysis_data['score'][key] = default_value
                logger.warning(f"Missing or invalid score field: {key}, using default value: {default_value}")
        
        # 添加图表数据
        analysis_data['charts_data'] = {
            'technical': {
                'dates': data['technical_indicators']['dates'],
                'prices': data['technical_indicators']['prices'],
                'ema5': data['technical_indicators']['ema']['ema5'],
                'ema10': data['technical_indicators']['ema']['ema10'],
                'ema20': data['technical_indicators']['ema']['ema20'],
                'ema60': data['technical_indicators']['ema']['ema60']
            },
            'capital_flow': data['capital_flow'],
            'capital_distribution': data['capital_flow']['distribution']
        }
        
        # 验证返回的JSON结构，确保所有预期字段都存在
        expected_fields = [
            'technical_analysis',
            'capital_flow_analysis',
            'capital_distribution_analysis',
            'score',
            'investment_advice',
            'risk_warning'
        ]
        
        for field in expected_fields:
            if field not in analysis_data:
                logger.warning(f"DEEPSEEK response missing expected field: {field}. Filling with default value.")
                if field == 'score':
                    analysis_data[field] = default_scores
                else:
                    analysis_data[field] = {} if 'analysis' in field else ""

        # 针对嵌套的分析字段，也做一次结构验证和填充
        nested_analysis_fields = {
            'technical_analysis': ['ema_crosses', 'ema_trends', 'price_ema_relation', 'trend_judgment'],
            'capital_flow_analysis': ['30d_trend', 'main_capital', 'strength_assessment'],
            'capital_distribution_analysis': ['main_capital_distribution', 'retail_capital_distribution', 'capital_structure']
        }

        for main_field, sub_fields in nested_analysis_fields.items():
            if main_field in analysis_data and isinstance(analysis_data[main_field], dict):
                for sub_field in sub_fields:
                    if sub_field not in analysis_data[main_field]:
                        logger.warning(f"DEEPSEEK response missing nested field: {main_field}.{sub_field}. Filling with default value.")
                        analysis_data[main_field][sub_field] = ""

        return analysis_data
        
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
    try:
        # 解析股票代码和市场
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return jsonify({'error': '股票代码格式错误'}), 400
            
        stock_code = code_parts[0]
        market = code_parts[1].upper()
        
        news_list = []
        
        # 检查是否为A股市场
        if market == 'SH' or market == 'SZ':
            try:
                # 获取A股新闻
                # 1. 获取公司公告
                try:
                    logger.info(f"正在获取A股公司公告，股票代码: {stock_code}")
                    stock_code_6 = stock_code.split('.')[0] if '.' in stock_code else stock_code
                    try:
                        notice_df = ak.stock_notice_report(symbol=stock_code_6)
                    except KeyError:
                        logger.warning(f"akshare公告接口不支持该股票: {stock_code_6}")
                        notice_df = pd.DataFrame()
                    logger.info(f"A股公司公告返回数据列名: {notice_df.columns.tolist() if not notice_df.empty else 'Empty DataFrame'}")
                    logger.info(f"A股公司公告返回数据示例: {notice_df.head(1).to_dict('records') if not notice_df.empty else 'No data'}")
                    
                    if not notice_df.empty:
                        for _, row in notice_df.iterrows():
                            news_list.append({
                                'title': row['公告标题'] if '公告标题' in row else row['title'],
                                'content': row['公告内容'] if '公告内容' in row else row['content'],
                                'publish_time': str(row['公告日期'] if '公告日期' in row else row['date']),
                                'source': '公司公告',
                                'url': row['公告链接'] if '公告链接' in row else row['url'] if 'url' in row else None
                            })
                except Exception as e:
                    logger.warning(f"获取A股公司公告失败: {str(e)}")
                    logger.error(traceback.format_exc())
                
                # 2. 获取公司新闻
                try:
                    logger.info(f"正在获取A股公司新闻，股票代码: {stock_code}")
                    news_df = ak.stock_news_em(symbol=stock_code)
                    logger.info(f"A股公司新闻返回数据列名: {news_df.columns.tolist() if not news_df.empty else 'Empty DataFrame'}")
                    logger.info(f"A股公司新闻返回数据示例: {news_df.head(1).to_dict('records') if not news_df.empty else 'No data'}")
                    
                    if not news_df.empty:
                        for _, row in news_df.iterrows():
                            news_list.append({
                                'title': row['title'] if 'title' in row else row['新闻标题'],
                                'content': row['content'] if 'content' in row else row['新闻内容'],
                                'publish_time': str(row['time'] if 'time' in row else row['发布时间']),
                                'source': row['source'] if 'source' in row else row['来源'] if '来源' in row else '东方财富网',
                                'url': row['url'] if 'url' in row else row['链接'] if '链接' in row else None
                            })
                except Exception as e:
                    logger.warning(f"获取A股公司新闻失败: {str(e)}")
                    logger.error(traceback.format_exc())
                
                # 3. 获取行业新闻
                try:
                    logger.info(f"正在获取A股行业信息，股票代码: {stock_code}")
                    stock_info = ak.stock_individual_info_em(symbol=stock_code)
                    logger.info(f"A股行业信息返回数据列名: {stock_info.columns.tolist() if not stock_info.empty else 'Empty DataFrame'}")
                    logger.info(f"A股行业信息返回数据示例: {stock_info.head(1).to_dict('records') if not stock_info.empty else 'No data'}")
                    
                    if not stock_info.empty and '所属行业' in stock_info.columns:
                        industry = stock_info['所属行业'].iloc[0]
                        logger.info(f"获取到行业: {industry}")
                        
                        industry_news = ak.stock_news_industry(symbol=industry)
                        logger.info(f"行业新闻返回数据列名: {industry_news.columns.tolist() if not industry_news.empty else 'Empty DataFrame'}")
                        logger.info(f"行业新闻返回数据示例: {industry_news.head(1).to_dict('records') if not industry_news.empty else 'No data'}")
                        
                        if not industry_news.empty:
                            for _, row in industry_news.iterrows():
                                news_list.append({
                                    'title': row['title'] if 'title' in row else row['新闻标题'],
                                    'content': row['content'] if 'content' in row else row['新闻内容'],
                                    'publish_time': str(row['time'] if 'time' in row else row['发布时间']),
                                    'source': '行业新闻',
                                    'url': row['url'] if 'url' in row else row['链接']
                                })
                except Exception as e:
                    logger.warning(f"获取A股行业新闻失败: {str(e)}")
                    logger.error(traceback.format_exc())
                
            except Exception as e:
                logger.error(f"获取A股新闻失败: {str(e)}")
                logger.error(traceback.format_exc())
                return jsonify({'error': f'获取A股新闻失败: {str(e)}'}), 500
        
        # 港股市场
        elif market == 'HK':
            try:
                # 获取港股新闻
                try:
                    # 使用 stock_hk_news_em 接口获取港股新闻
                    news_df = ak.stock_hk_news_em(symbol=stock_code)
                    if not news_df.empty:
                        for _, row in news_df.iterrows():
                            news_list.append({
                                'title': row['title'] if 'title' in row else row['新闻标题'],
                                'content': row['content'] if 'content' in row else row['新闻内容'],
                                'publish_time': str(row['time'] if 'time' in row else row['发布时间']),
                                'source': row['source'] if 'source' in row else row['来源'],
                                'url': row['url'] if 'url' in row else row['链接']
                            })
                except Exception as e:
                    logger.warning(f"获取港股新闻失败: {str(e)}")
                
                # 获取港股公告
                try:
                    # 使用 stock_hk_report_em 接口获取港股公告
                    notice_df = ak.stock_hk_report_em(symbol=stock_code)
                    if not notice_df.empty:
                        for _, row in notice_df.iterrows():
                            news_list.append({
                                'title': row['title'] if 'title' in row else row['公告标题'],
                                'content': row['content'] if 'content' in row else row['公告内容'],
                                'publish_time': str(row['time'] if 'time' in row else row['公告日期']),
                                'source': '公司公告',
                                'url': row['url'] if 'url' in row else row['公告链接'] if '公告链接' in row else None
                            })
                except Exception as e:
                    logger.warning(f"获取港股公告失败: {str(e)}")
                
                # 获取行业新闻
                try:
                    # 获取港股所属行业
                    stock_info = ak.stock_hk_spot_em()
                    if not stock_info.empty:
                        stock_row = stock_info[stock_info['代码'] == stock_code]
                        if not stock_row.empty and '所属行业' in stock_row.columns:
                            industry = stock_row['所属行业'].iloc[0]
                            # 获取行业新闻
                            industry_news = ak.stock_news_industry(symbol=industry)
                            if not industry_news.empty:
                                for _, row in industry_news.iterrows():
                                    news_list.append({
                                        'title': row['title'] if 'title' in row else row['新闻标题'],
                                        'content': row['content'] if 'content' in row else row['新闻内容'],
                                        'publish_time': str(row['time'] if 'time' in row else row['发布时间']),
                                        'source': '行业新闻',
                                        'url': row['url'] if 'url' in row else row['链接']
                                    })
                except Exception as e:
                    logger.warning(f"获取港股行业新闻失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"获取港股新闻失败: {str(e)}")
                return jsonify({'error': f'获取港股新闻失败: {str(e)}'}), 500
        
        else:
            return jsonify({'error': '不支持的市场类型'}), 400
        
        # 按发布时间排序
        news_list.sort(key=lambda x: x['publish_time'], reverse=True)
        
        # 限制返回最新的50条新闻
        news_list = news_list[:50]
        
        return jsonify({
            'news': news_list,
            'total': len(news_list)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True) 
