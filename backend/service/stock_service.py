# backend/service/stock_service.py
"""
行情、K线、资金流、诊断等主要业务逻辑
"""
import logging
import pandas as pd
from datetime import datetime, timedelta
import json
import numpy as np
import traceback
from futu import RET_OK, KLType, AuType, PeriodType, Market, Plate
from futu.common.constant import OptionType, SecurityType
import akshare as ak
import os
import talib

logger = logging.getLogger(__name__)

# 迁移自 app.py
# 依赖注入: quote_ctx, batch_market_snapshot, get_stock_news, analyze_fundamental 等需在app.py中传入或全局导入

def get_plate_ranking(market, plate_class, futu_client, batch_market_snapshot):
    """
    获取板块行情排名
    
    Args:
        market: 市场标识，如 'HK', 'US', 'SH', 'SZ'
        plate_class: 板块分类，如 'CONCEPT', 'INDUSTRY', 'REGION', 'OTHER'
        futu_client: FutuClient实例
        batch_market_snapshot: 批量查询行情快照函数
        
    Returns:
        dict: 板块排名结果
    """
    try:
        logger.info(f"开始获取{market}市场{plate_class}板块排名")
        
        # 1. 查询市场下所有的板块
        market_map = {
            'HK': Market.HK,
            'US': Market.US,
            'SH': Market.SH,
            'SZ': Market.SZ
        }
        
        plate_map = {
            'CONCEPT': Plate.CONCEPT,
            'INDUSTRY': Plate.INDUSTRY,
            'REGION': Plate.REGION,
            'OTHER': Plate.OTHER
        }
        
        if market not in market_map:
            raise Exception(f"不支持的市场类型: {market}")
        
        if plate_class not in plate_map:
            raise Exception(f"不支持的板块分类: {plate_class}")
        
        futu_market = market_map[market]
        futu_plate_class = plate_map[plate_class]
        
        # 获取板块列表
        plates = futu_client.get_plate_list(futu_market, futu_plate_class)
        logger.info(f"获取到{len(plates)}个板块")
        
        if not plates:
            return {
                'success': False,
                'error': f'未获取到{market}市场{plate_class}板块数据'
            }
        
        # 2. 批量查询板块对应的行情快照
        plate_codes = [plate['code'] for plate in plates]
        logger.info(f"开始批量查询{len(plate_codes)}个板块的行情快照")
        
        # 使用专门的板块行情查询函数
        try:
            from quant import batch_plate_market_snapshot
            all_snapshots = batch_plate_market_snapshot(plate_codes)
            logger.info(f"板块行情查询完成: {len(all_snapshots)}个板块")
        except Exception as e:
            logger.error(f"板块行情查询失败: {e}")
            all_snapshots = {}
        
        # 3. 处理行情数据并计算涨跌幅
        plate_rankings = []
        
        for plate in plates:
            plate_code = plate['code']
            plate_name = plate['plate_name']
            
            # 直接使用原始代码查找行情数据
            if plate_code in all_snapshots:
                snapshot = all_snapshots[plate_code]
                
                try:
                    # 计算涨跌幅
                    current_price = float(snapshot.get('last_price', 0))
                    prev_close = float(snapshot.get('prev_close_price', 0))
                    
                    if prev_close > 0:
                        change_percent = ((current_price - prev_close) / prev_close) * 100
                    else:
                        change_percent = 0
                    
                    # 构建板块排名数据
                    plate_data = {
                        'plate_code': plate_code,
                        'plate_name': plate_name,
                        'current_price': current_price,
                        'prev_close': prev_close,
                        'change': current_price - prev_close,
                        'change_percent': round(change_percent, 2),
                        'volume': int(snapshot.get('volume', 0)),
                        'turnover': float(snapshot.get('turnover', 0)),
                        'update_time': snapshot.get('update_time', ''),
                        'market': market,
                        'plate_class': plate_class
                    }
                    
                    plate_rankings.append(plate_data)
                    
                except Exception as e:
                    logger.error(f"处理板块{plate_code}数据失败: {e}")
                    continue
            else:
                logger.warning(f"未获取到板块{plate_code}的行情数据")
                # 检查代码是否在查询列表中
                if plate_code in plate_codes:
                    logger.warning(f"  代码 {plate_code} 在查询列表中，但未返回数据")
                else:
                    logger.warning(f"  代码 {plate_code} 不在查询列表中")
        
        # 4. 按照涨跌幅排序
        plate_rankings.sort(key=lambda x: x['change_percent'], reverse=True)
        
        # 5. 记录到文件
        save_plate_ranking_to_file(market, plate_class, plate_rankings)
        
        # 6. 返回排序结果
        return {
            'success': True,
            'market': market,
            'plate_class': plate_class,
            'total_count': len(plates),
            'valid_count': len(plate_rankings),
            'rankings': plate_rankings,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"获取板块排名失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': f'获取板块排名失败: {str(e)}'
        }

def save_plate_ranking_to_file(market, plate_class, plate_rankings):
    """
    将板块排名数据保存到文件
    
    Args:
        market: 市场标识
        plate_class: 板块分类
        plate_rankings: 板块排名数据
    """
    try:
        # 创建数据目录
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'plate_rankings')
        os.makedirs(data_dir, exist_ok=True)
        
        # 生成文件名：按日期和板块类型命名
        today = datetime.now().strftime('%Y%m%d')
        filename = f"{market}_{plate_class}_{today}.json"
        filepath = os.path.join(data_dir, filename)
        
        # 构建保存数据
        save_data = {
            'market': market,
            'plate_class': plate_class,
            'date': today,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_count': len(plate_rankings),
            'rankings': plate_rankings
        }
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"板块排名数据已保存到: {filepath}")
        
    except Exception as e:
        logger.error(f"保存板块排名数据失败: {str(e)}")
        logger.error(traceback.format_exc())

def get_plate_ranking_history(market, plate_class, date=None):
    """
    获取历史板块排名数据
    
    Args:
        market: 市场标识
        plate_class: 板块分类
        date: 日期，格式为YYYYMMDD，如果为None则获取最新数据
        
    Returns:
        dict: 历史排名数据
    """
    try:
        # 构建数据目录路径
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'plate_rankings')
        
        if not os.path.exists(data_dir):
            return {
                'success': False,
                'error': '历史数据目录不存在'
            }
        
        # 如果未指定日期，获取最新数据
        if date is None:
            # 查找最新的文件
            files = [f for f in os.listdir(data_dir) 
                    if f.startswith(f"{market}_{plate_class}_") and f.endswith('.json')]
            
            if not files:
                return {
                    'success': False,
                    'error': f'未找到{market}市场{plate_class}板块的历史数据'
                }
            
            # 按文件名排序，获取最新的
            files.sort(reverse=True)
            filename = files[0]
            date = filename.split('_')[2].split('.')[0]
        else:
            filename = f"{market}_{plate_class}_{date}.json"
        
        filepath = os.path.join(data_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                'success': False,
                'error': f'未找到{date}的板块排名数据'
            }
        
        # 读取文件数据
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            'success': True,
            'data': data
        }
        
    except Exception as e:
        logger.error(f"获取历史板块排名数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': f'获取历史板块排名数据失败: {str(e)}'
        }

def get_all_markets_plate_rankings(futu_client, batch_market_snapshot):
    """
    获取所有市场的板块排名
    
    Args:
        futu_client: FutuClient实例
        batch_market_snapshot: 批量查询行情快照函数
        
    Returns:
        dict: 所有市场的板块排名结果
    """
    try:
        logger.info("开始获取所有市场的板块排名")
        
        # 定义市场和板块类型
        markets = ['HK', 'US', 'SH', 'SZ']
        plate_classes = ['CONCEPT', 'INDUSTRY']
        
        all_rankings = {}
        
        for market in markets:
            all_rankings[market] = {}
            
            for plate_class in plate_classes:
                try:
                    logger.info(f"获取{market}市场{plate_class}板块排名")
                    result = get_plate_ranking(market, plate_class, futu_client, batch_market_snapshot)
                    all_rankings[market][plate_class] = result
                    
                    if result['success']:
                        logger.info(f"{market}市场{plate_class}板块排名获取成功: {result['valid_count']}个板块")
                    else:
                        logger.error(f"{market}市场{plate_class}板块排名获取失败: {result.get('error', '未知错误')}")
                        
                except Exception as e:
                    logger.error(f"获取{market}市场{plate_class}板块排名异常: {e}")
                    all_rankings[market][plate_class] = {
                        'success': False,
                        'error': f'获取失败: {str(e)}'
                    }
        
        return {
            'success': True,
            'rankings': all_rankings,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"获取所有市场板块排名失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': f'获取所有市场板块排名失败: {str(e)}'
        }

# 1. K线数据

def get_kline_data(symbol, quote_ctx, batch_market_snapshot, get_stock_news, analyze_fundamental):
    try:
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            err = {'error': 'Invalid stock code format. Expected format: CODE.MARKET (e.g., 00700.HK)'}
            return err
        result = batch_market_snapshot([symbol])
        code, market = code_parts[0], code_parts[1].upper()
        norm_symbol = f"{market}.{code.zfill(5) if market=='HK' and code.isdigit() else code}"
        kline_data = None
        if symbol in result:
            kline_data = result[symbol]
        elif norm_symbol in result:
            kline_data = result[norm_symbol]
        elif len(result) == 1:
            kline_data = list(result.values())[0]
        if not kline_data:
            err = {'error': '未找到K线数据'}
            return err
        data = {
            'code': symbol,
            'name': kline_data.get('name'),
            'kline_data': kline_data.get('kline_data'),
            'update_time': kline_data.get('update_time'),
        }
        return data
    except Exception as e:
        return {'error': f'Error in get_kline_data: {str(e)}'}

# 2. 股票快照

def get_stock_data(symbol, as_dict, batch_market_snapshot):
    try:
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            err = {'error': 'Invalid stock code format. Expected format: CODE.MARKET (e.g., 00700.HK)'}
            if as_dict:
                return err
            return err
        result = batch_market_snapshot([symbol])
        code, market = code_parts[0], code_parts[1].upper()
        norm_symbol = f"{market}.{code.zfill(5) if market=='HK' and code.isdigit() else code}"
        stock_data = None
        if symbol in result:
            stock_data = result[symbol]
        elif norm_symbol in result:
            stock_data = result[norm_symbol]
        elif len(result) == 1:
            stock_data = list(result.values())[0]
        if not stock_data:
            err = {'error': '未找到股票数据'}
            if as_dict:
                return err
            return err
        data = {
            'code': symbol,
            'name': stock_data.get('name'),
            'current_price': float(stock_data.get('last_price', 0)),
            'open_price': float(stock_data.get('open_price', 0)),
            'high_price': float(stock_data.get('high_price', 0)),
            'low_price': float(stock_data.get('low_price', 0)),
            'pre_close': float(stock_data.get('prev_close_price', 0)),
            'volume': int(stock_data.get('volume', 0)),
            'turnover': float(stock_data.get('turnover', 0)),
            'update_time': stock_data.get('update_time'),
            'turnover_rate': stock_data.get('turnover_rate'),
            'amplitude': stock_data.get('amplitude'),
            'avg_price': stock_data.get('avg_price'),
            'volume_ratio': stock_data.get('volume_ratio'),
            'highest52weeks_price': stock_data.get('highest52weeks_price'),
            'lowest52weeks_price': stock_data.get('lowest52weeks_price'),
            'total_market_val': stock_data.get('total_market_val'),
            'circular_market_val': stock_data.get('circular_market_val'),
            'pe_ratio': stock_data.get('pe_ratio'),
            'pb_ratio': stock_data.get('pb_ratio'),
            'dividend_ttm': stock_data.get('dividend_ttm'),
            'dividend_ratio_ttm': stock_data.get('dividend_ratio_ttm'),
            'earning_per_share': stock_data.get('earning_per_share'),
        }
        return data
    except Exception as e:
        return {'error': f'Error in get_stock_data: {str(e)}'}

# 3. 资金流

def get_capital_flow_data(symbol, quote_ctx):
    try:
        from backend.app import parse_stock_code  # 确保依赖
        if quote_ctx is None:
            logger.error("Futu API connection failed")
            return None
        stock_code, market = parse_stock_code(symbol)
        if not stock_code or not market:
            logger.error(f"Invalid stock symbol format: {symbol}")
            return None
        ret, historical_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.DAY,
            start=None,
            end=None
        )
        if ret != RET_OK:
            logger.error(f"Failed to get historical capital flow data: {historical_data}")
            return None
        ret, intraday_data = quote_ctx.get_capital_flow(
            stock_code=f'{market}.{stock_code}',
            period_type=PeriodType.INTRADAY
        )
        if ret != RET_OK:
            logger.error(f"Failed to get intraday capital flow data: {intraday_data}")
            return None
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

# 4. 技术分析

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
        return {
            'main_capital_distribution': '；'.join(main_capital_points),
            'retail_capital_distribution': '；'.join(retail_capital_points),
            'capital_structure': '暂无资金分布数据'
        }
    except Exception as e:
        import traceback
        logger.error(f"Error in analyze_capital_distribution: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'main_capital_distribution': '资金分布分析出错',
            'retail_capital_distribution': '资金分布分析出错',
            'capital_structure': '资金分布分析出错'
        }

def calculate_technical_score(technical_analysis):
    """
    Calculate a technical score based on technical analysis results.
    Returns a dictionary containing the score and grade.
    """
    try:
        if not technical_analysis:
            return {'score': 0, 'grade': 'F'}

        # Define weights for different indicators
        ema_cross_weight = 0.3
        ema_trend_weight = 0.2
        price_ema_weight = 0.2
        trend_judgment_weight = 0.3

        # Initialize scores
        ema_cross_score = 0
        ema_trend_score = 0
        price_ema_score = 0
        trend_judgment_score = 0

        # Calculate scores based on technical analysis results
        if 'ema_crosses' in technical_analysis and technical_analysis['ema_crosses'] != '暂无均线交叉信号':
            if '短期金叉' in technical_analysis['ema_crosses']:
                ema_cross_score += 10
            if '中期金叉' in technical_analysis['ema_crosses']:
                ema_cross_score += 10
            if '长期金叉' in technical_analysis['ema_crosses']:
                ema_cross_score += 10
            if '短期死叉' in technical_analysis['ema_crosses']:
                ema_cross_score -= 5
            if '中期死叉' in technical_analysis['ema_crosses']:
                ema_cross_score -= 5
            if '长期死叉' in technical_analysis['ema_crosses']:
                ema_cross_score -= 5

        if 'ema_trends' in technical_analysis and technical_analysis['ema_trends'] != '暂无明确均线趋势':
            if '短期看涨' in technical_analysis['ema_trends']:
                ema_trend_score += 10
            if '中期看涨' in technical_analysis['ema_trends']:
                ema_trend_score += 10
            if '长期看涨' in technical_analysis['ema_trends']:
                ema_trend_score += 10
            if '短期看跌' in technical_analysis['ema_trends']:
                ema_trend_score -= 5
            if '中期看跌' in technical_analysis['ema_trends']:
                ema_trend_score -= 5
            if '长期看跌' in technical_analysis['ema_trends']:
                ema_trend_score -= 5

        if 'price_ema_relation' in technical_analysis and technical_analysis['price_ema_relation'] != '暂无明确价格与均线关系':
            if '短期支撑较强' in technical_analysis['price_ema_relation']:
                price_ema_score += 10
            if '中期支撑较强' in technical_analysis['price_ema_relation']:
                price_ema_score += 10
            if '长期支撑较强' in technical_analysis['price_ema_relation']:
                price_ema_score += 10
            if '短期压力较大' in technical_analysis['price_ema_relation']:
                price_ema_score -= 5
            if '中期压力较大' in technical_analysis['price_ema_relation']:
                price_ema_score -= 5
            if '长期压力较大' in technical_analysis['price_ema_relation']:
                price_ema_score -= 5

        if 'trend_judgment' in technical_analysis and technical_analysis['trend_judgment'] != '暂无明确趋势判断':
            if '短期趋势向上' in technical_analysis['trend_judgment']:
                trend_judgment_score += 10
            if '中期趋势向上' in technical_analysis['trend_judgment']:
                trend_judgment_score += 10
            if '长期趋势向上' in technical_analysis['trend_judgment']:
                trend_judgment_score += 10
            if '短期趋势向下' in technical_analysis['trend_judgment']:
                trend_judgment_score -= 5
            if '中期趋势向下' in technical_analysis['trend_judgment']:
                trend_judgment_score -= 5
            if '长期趋势向下' in technical_analysis['trend_judgment']:
                trend_judgment_score -= 5

        # Calculate total score
        total_score = (ema_cross_score * ema_cross_weight +
                       ema_trend_score * ema_trend_weight +
                       price_ema_score * price_ema_weight +
                       trend_judgment_score * trend_judgment_weight)

        # Determine grade
        if total_score >= 80:
            grade = 'A'
        elif total_score >= 60:
            grade = 'B'
        elif total_score >= 40:
            grade = 'C'
        elif total_score >= 20:
            grade = 'D'
        else:
            grade = 'F'

        return {'score': total_score, 'grade': grade}

    except Exception as e:
        logger.error(f"Error in calculate_technical_score: {str(e)}")
        logger.error(traceback.format_exc())
        return {'score': 0, 'grade': 'F'}


def analyze_with_deepseek_service(data):
    """
    使用DEEPSEEK分析股票数据
    
    Args:
        data: 包含股票数据的字典，需要包含:
            - symbol: 股票代码
            - technical_indicators: 技术指标数据
            - capital_flow: 资金流向数据
            
    Returns:
        dict: 包含分析结果的字典
    """
    import os
    import json
    import requests
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
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
        "30d_trend": "详细描述近半年资金的净流入/流出情况及其波动特征，例如：近半年累计净流入达到X亿元，资金活跃度较高，但近期波动有所增加。", // 近半年资金流向趋势
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

        # Define weights for different indicators
        ema_cross_weight = 0.3
        ema_trend_weight = 0.2
        price_ema_weight = 0.2
        trend_judgment_weight = 0.3

        # Initialize scores
        ema_cross_score = 0
        ema_trend_score = 0
        price_ema_score = 0
        trend_judgment_score = 0

        # Calculate scores based on technical analysis results
        if 'ema_crosses' in technical_analysis and technical_analysis['ema_crosses'] != '暂无均线交叉信号':
            if '短期金叉' in technical_analysis['ema_crosses']:
                ema_cross_score += 10
            if '中期金叉' in technical_analysis['ema_crosses']:
                ema_cross_score += 10
            if '长期金叉' in technical_analysis['ema_crosses']:
                ema_cross_score += 10
            if '短期死叉' in technical_analysis['ema_crosses']:
                ema_cross_score -= 5
            if '中期死叉' in technical_analysis['ema_crosses']:
                ema_cross_score -= 5
            if '长期死叉' in technical_analysis['ema_crosses']:
                ema_cross_score -= 5

        if 'ema_trends' in technical_analysis and technical_analysis['ema_trends'] != '暂无明确均线趋势':
            if '短期看涨' in technical_analysis['ema_trends']:
                ema_trend_score += 10
            if '中期看涨' in technical_analysis['ema_trends']:
                ema_trend_score += 10
            if '长期看涨' in technical_analysis['ema_trends']:
                ema_trend_score += 10
            if '短期看跌' in technical_analysis['ema_trends']:
                ema_trend_score -= 5
            if '中期看跌' in technical_analysis['ema_trends']:
                ema_trend_score -= 5
            if '长期看跌' in technical_analysis['ema_trends']:
                ema_trend_score -= 5

        if 'price_ema_relation' in technical_analysis and technical_analysis['price_ema_relation'] != '暂无明确价格与均线关系':
            if '短期支撑较强' in technical_analysis['price_ema_relation']:
                price_ema_score += 10
            if '中期支撑较强' in technical_analysis['price_ema_relation']:
                price_ema_score += 10
            if '长期支撑较强' in technical_analysis['price_ema_relation']:
                price_ema_score += 10
            if '短期压力较大' in technical_analysis['price_ema_relation']:
                price_ema_score -= 5
            if '中期压力较大' in technical_analysis['price_ema_relation']:
                price_ema_score -= 5
            if '长期压力较大' in technical_analysis['price_ema_relation']:
                price_ema_score -= 5

        if 'trend_judgment' in technical_analysis and technical_analysis['trend_judgment'] != '暂无明确趋势判断':
            if '短期趋势向上' in technical_analysis['trend_judgment']:
                trend_judgment_score += 10
            if '中期趋势向上' in technical_analysis['trend_judgment']:
                trend_judgment_score += 10
            if '长期趋势向上' in technical_analysis['trend_judgment']:
                trend_judgment_score += 10
            if '短期趋势向下' in technical_analysis['trend_judgment']:
                trend_judgment_score -= 5
            if '中期趋势向下' in technical_analysis['trend_judgment']:
                trend_judgment_score -= 5
            if '长期趋势向下' in technical_analysis['trend_judgment']:
                trend_judgment_score -= 5

        # Calculate total score
        total_score = (ema_cross_score * ema_cross_weight +
                       ema_trend_score * ema_trend_weight +
                       price_ema_score * price_ema_weight +
                       trend_judgment_score * trend_judgment_weight)

        # Determine grade
        if total_score >= 80:
            grade = 'A'
        elif total_score >= 60:
            grade = 'B'
        elif total_score >= 40:
            grade = 'C'
        elif total_score >= 20:
            grade = 'D'
        else:
            grade = 'F'

        return {'score': total_score, 'grade': grade}

    except Exception as e:
        logger.error(f"Error in calculate_technical_score: {str(e)}")
        logger.error(traceback.format_exc())
        return {'score': 0, 'grade': 'F'}

def calculate_capital_score(capital_flow_analysis):
    """
    Calculate a capital score based on capital flow analysis results.
    Returns a dictionary containing the score and grade.
    """
    try:
        if not capital_flow_analysis:
            return {'score': 0, 'grade': 'F'}

        # Define weights for different indicators
        trend_weight = 0.3
        main_capital_weight = 0.4
        strength_assessment_weight = 0.3

        # Initialize scores
        trend_score = 0
        main_capital_score = 0
        strength_assessment_score = 0

        # Calculate scores based on capital flow analysis results
        if '30d_trend' in capital_flow_analysis and capital_flow_analysis['30d_trend'] != '暂无资金流向数据':
            if '累计净流入' in capital_flow_analysis['30d_trend']:
                trend_score += 10
            if '日均净流入' in capital_flow_analysis['30d_trend']:
                trend_score += 10
            if '累计净流出' in capital_flow_analysis['30d_trend']:
                trend_score -= 5
            if '日均净流出' in capital_flow_analysis['30d_trend']:
                trend_score -= 5

        if 'main_capital' in capital_flow_analysis and capital_flow_analysis['main_capital'] != '暂无主力资金数据':
            if '主力资金近30日净流入' in capital_flow_analysis['main_capital']:
                main_capital_score += 10
            if '超大单净流入' in capital_flow_analysis['main_capital']:
                main_capital_score += 10
            if '大单净流入' in capital_flow_analysis['main_capital']:
                main_capital_score += 10
            if '主力资金近30日净流出' in capital_flow_analysis['main_capital']:
                main_capital_score -= 5
            if '超大单净流出' in capital_flow_analysis['main_capital']:
                main_capital_score -= 5
            if '大单净流出' in capital_flow_analysis['main_capital']:
                main_capital_score -= 5

        if 'strength_assessment' in capital_flow_analysis and capital_flow_analysis['strength_assessment'] != '暂无资金实力评估':
            if '资金实力雄厚' in capital_flow_analysis['strength_assessment']:
                strength_assessment_score += 10
            if '资金实力一般' in capital_flow_analysis['strength_assessment']:
                strength_assessment_score += 10
            if '资金实力较弱' in capital_flow_analysis['strength_assessment']:
                strength_assessment_score -= 5

        # Calculate total score
        total_score = (trend_score * trend_weight +
                       main_capital_score * main_capital_weight +
                       strength_assessment_score * strength_assessment_weight)

        # Determine grade
        if total_score >= 80:
            grade = 'A'
        elif total_score >= 60:
            grade = 'B'
        elif total_score >= 40:
            grade = 'C'
        elif total_score >= 20:
            grade = 'D'
        else:
            grade = 'F'

        return {'score': total_score, 'grade': grade}

    except Exception as e:
        logger.error(f"Error in calculate_capital_score: {str(e)}")
        logger.error(traceback.format_exc())
        return {'score': 0, 'grade': 'F'}

def get_score_grade(score):
    """
    Convert a total score to a grade.
    Returns a string containing the grade.
    """
    if score >= 90:
        return 'S'
    elif score >= 80:
        return 'A'
    elif score >= 70:
        return 'B'
    elif score >= 60:
        return 'C'
    elif score >= 50:
        return 'D'
    else:
        return 'F'

def calculate_overall_score(diagnosis_result):
    """
    Calculate an overall score based on diagnosis results.
    Returns a dictionary containing the score and grade.
    """
    try:
        logger.info(f"[calculate_overall_score] 输入: {json.dumps(diagnosis_result, ensure_ascii=False)}")
        if not diagnosis_result:
            logger.info("[calculate_overall_score] diagnosis_result为空，返回0分F级")
            return {'score': 0, 'grade': 'F'}

        # Define weights for different indicators
        technical_score_weight = 0.4
        capital_score_weight = 0.6
        logger.info(f"[calculate_overall_score] 权重: technical={technical_score_weight}, capital={capital_score_weight}")

        # Initialize scores
        technical_score = 0
        capital_score = 0

        # Calculate scores based on diagnosis results
        if 'technical_score' in diagnosis_result:
            technical_score = diagnosis_result['technical_score']
        if 'capital_score' in diagnosis_result:
            capital_score = diagnosis_result['capital_score']
        logger.info(f"[calculate_overall_score] technical_score={technical_score}, capital_score={capital_score}")

        # Calculate total score
        total_score = (technical_score * technical_score_weight +
                       capital_score * capital_score_weight)
        logger.info(f"[calculate_overall_score] total_score={total_score}")

        # Determine grade
        if total_score >= 90:
            grade = 'S'
        elif total_score >= 80:
            grade = 'A'
        elif total_score >= 70:
            grade = 'B'
        elif total_score >= 60:
            grade = 'C'
        elif total_score >= 50:
            grade = 'D'
        else:
            grade = 'F'
        logger.info(f"[calculate_overall_score] grade={grade}")

        return {'score': total_score, 'grade': grade}
    except Exception as e:
        logger.error(f"Error in calculate_overall_score: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error(f"[calculate_overall_score] 输入内容: {json.dumps(diagnosis_result, ensure_ascii=False)}")
        return {'score': 0, 'grade': 'F'}


def get_stock_news_data(symbol):
    """
    获取股票新闻数据
    
    Args:
        symbol: 股票代码，格式为 CODE.MARKET (例如: 000001.SZ)
        
    Returns:
        dict: 包含新闻列表的字典
    """
    import logging
    import pandas as pd
    import traceback
    import akshare as ak
    
    logger = logging.getLogger(__name__)
    
    try:
        # 解析股票代码和市场
        code_parts = symbol.split('.')
        if len(code_parts) != 2:
            return {'error': '股票代码格式错误', 'status': 400}
            
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
                    
                    if not stock_info.empty and '所属行业' in stock_info.columns:
                        industry = stock_info['所属行业'].iloc[0]
                        logger.info(f"获取到行业: {industry}")
                        
                        industry_news = ak.stock_news_industry(symbol=industry)
                        logger.info(f"行业新闻返回数据列名: {industry_news.columns.tolist() if not industry_news.empty else 'Empty DataFrame'}")
                        
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
                return {'error': f'获取A股新闻失败: {str(e)}', 'status': 500}
        
        # 港股市场
        elif market == 'HK':
            try:
                # 使用新的爬虫服务获取港股新闻
                try:
                    from service.stock_crawler import get_hk_stock_news
                    logger.info(f"正在使用爬虫服务获取港股新闻: {stock_code}")
                    crawled_news = get_hk_stock_news(stock_code, max_news=20)
                    
                    if crawled_news:
                        for news in crawled_news:
                            news_list.append({
                                'title': news.get('title', ''),
                                'content': news.get('content', ''),
                                'publish_time': news.get('publish_time', ''),
                                'source': news.get('source', '东方财富网'),
                                'url': news.get('url', None)
                            })
                        logger.info(f"爬虫服务成功获取 {len(crawled_news)} 条港股新闻")
                    else:
                        logger.warning("爬虫服务未获取到港股新闻")
                        
                except Exception as e:
                    logger.error(f"爬虫服务获取港股新闻失败: {str(e)}")
                    logger.error(traceback.format_exc())
                
                # 如果爬虫失败，尝试使用akshare作为备用
                if not news_list:
                    try:
                        logger.info("尝试使用akshare作为备用方案")
                        # 尝试获取港股新闻
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
                        logger.warning(f"akshare港股新闻接口失败: {str(e)}")
                    
                    try:
                        # 尝试获取港股公告
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
                        logger.warning(f"akshare港股公告接口失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"获取港股新闻失败: {str(e)}")
                logger.error(traceback.format_exc())
                return {'error': f'获取港股新闻失败: {str(e)}', 'status': 500}
        
        else:
            return {'error': '不支持的市场类型', 'status': 400}
        
        # 按发布时间排序
        news_list.sort(key=lambda x: x['publish_time'], reverse=True)
        
        # 限制返回最新的50条新闻
        news_list = news_list[:50]
        
        return {
            'news': news_list,
            'total': len(news_list),
            'status': 200
        }
        
    except Exception as e:
        logger.error(f"获取新闻失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {'error': f'获取新闻失败: {str(e)}', 'status': 500}


def execute_watchlist_rule_service(rule, user_id, config_data=None):
    """
    执行观察列表规则的业务逻辑
    
    Args:
        rule: 规则名称
        user_id: 用户ID
        config_data: 用户配置数据，如果为None则从文件加载
        
    Returns:
        dict: 包含执行结果的字典
    """
    import json
    import os
    import time
    from datetime import datetime
    
    def load_monitor_config():
        """加载监控配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'user_monitor_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            return {}
    
    def load_monitor_status():
        """加载监控状态"""
        try:
            status_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'monitor_status.json')
            if os.path.exists(status_path):
                with open(status_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            return {}
    
    def save_monitor_status(status_data):
        """保存监控状态"""
        try:
            status_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'monitor_status.json')
            os.makedirs(os.path.dirname(status_path), exist_ok=True)
            with open(status_path, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def load_strategy_log():
        """加载策略日志"""
        try:
            log_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'strategy_log.json')
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            return {}
    
    def save_strategy_log(log_data):
        """保存策略日志"""
        try:
            log_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'strategy_log.json')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def save_monitor_config(config_data):
        """保存监控配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'user_monitor_config.json')
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def get_stock_data(symbol, as_dict=False):
        """获取股票数据"""
        try:
            from backend.app import get_stock_data as app_get_stock_data
            return app_get_stock_data(symbol, as_dict)
        except Exception as e:
            return None
    
    def get_kline_data(symbol):
        """获取K线数据"""
        try:
            from backend.app import get_kline_data as app_get_kline_data
            return app_get_kline_data(symbol)
        except Exception as e:
            return []
    
    try:
        # 加载配置
        if config_data is None:
            all_data = load_monitor_config()
        else:
            all_data = config_data
            
        user_conf = all_data.get(user_id)
        if not user_conf:
            return {'error': '未找到该用户配置', 'status': 404}
            
        stocks = user_conf.get('stocks', [])
        if isinstance(stocks, str):
            stocks = [s.strip() for s in stocks.split(',') if s.strip()]
        rules = user_conf.get('rules', [])
        if rule not in rules:
            return {'error': f'用户未选择该规则: {rule}', 'status': 400}
            
        results = []
        execute_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        monitor_status = load_monitor_status()
        
        for symbol in stocks:
            # 获取股票名称
            name = symbol
            try:
                stock_info = get_stock_data(symbol)
                if isinstance(stock_info, dict) and stock_info.get('name'):
                    name = stock_info['name']
                elif hasattr(stock_info, 'json'):
                    stock_json = stock_info.json if not callable(stock_info.json) else stock_info.json()
                    if isinstance(stock_json, dict) and stock_json.get('name'):
                        name = stock_json['name']
            except Exception:
                name = symbol
                
            result_item = {
                'stock': symbol,
                'name': name,
                'rule': rule,
                'execute_time': execute_time,
                'status': 'success',
                'reason': '',
                'market_data': None,
                'extra': None,
                'hit': False
            }
            
            # 获取最近交易日日期
            trade_date = None
            try:
                snapshot = get_stock_data(symbol, as_dict=True)
                trade_time = snapshot.get('update_time')
                if trade_time:
                    trade_date = str(trade_time)[:10]
                else:
                    kline = get_kline_data(symbol)
                    if kline and len(kline) > 0:
                        last_time = kline[-1].get('time')
                        if last_time:
                            trade_date = str(last_time)[:10]
            except Exception:
                trade_date = datetime.now().strftime('%Y-%m-%d')
                
            # 执行具体规则逻辑
            if rule == 'wave3_start':
                try:
                    from quant import analyze_elliott_wave
                    result = analyze_elliott_wave(symbol)
                    # 直接用 is_wave3_start 字段作为 hit
                    hit = bool(result.get('is_wave3_start', False))
                    desc = result.get('desc') or result.get('description') or ''
                    main_wave = result.get('mainWave') or result.get('main_wave')
                    wave_signal = result.get('signal') or result.get('waveSignal')
                    detailed_reason = result.get('reason', '')
                    pattern_analysis = ''
                    if (wave_signal and '符合' in wave_signal) or ('符合' in desc):
                        pattern_analysis = '符合三浪形态'
                    elif (wave_signal and '不符合' in wave_signal) or ('不符合' in desc):
                        pattern_analysis = '不符合三浪形态'
                    result_item['hit'] = hit
                    result_item['reason'] = f"三浪信号: {'命中' if hit else '未命中'}，{desc}" if desc else ("三浪信号: 命中" if hit else "三浪信号: 未命中")
                    # 获取最新行情信息
                    try:
                        kline = get_kline_data(symbol)
                        if kline and len(kline) >= 2:
                            pct = (kline[-1]['close'] - kline[-2]['close']) / kline[-2]['close'] * 100
                            result_item['market_data'] = {
                                'close': kline[-1]['close'],
                                'pre_close': kline[-2]['close'],
                                'pct_change': round(pct,2),
                                'trigger_time': kline[-1]['time'] if 'time' in kline[-1] else None,
                                'main_wave': main_wave,
                                'wave_signal': wave_signal,
                                'desc': desc
                            }
                        else:
                            result_item['market_data'] = {
                                'main_wave': main_wave,
                                'wave_signal': wave_signal,
                                'desc': desc
                            }
                    except Exception:
                        result_item['market_data'] = {
                            'main_wave': main_wave,
                            'wave_signal': wave_signal,
                            'desc': desc
                        }
                    # 形态分析补充信息
                    if not pattern_analysis:
                        pattern_analysis = '符合三浪形态' if hit else '不符合三浪形态'
                    result_item['extra'] = {'形态分析': pattern_analysis, '详细分析': detailed_reason}
                except Exception as e:
                    result_item['status'] = 'fail'
                    result_item['reason'] = str(e)
                    result_item['extra'] = {'原因': str(e)}
                    
            elif rule == 'down_channel_start':
                try:
                    from quant import analyze_down_channel
                    result = analyze_down_channel(symbol, window=20)
                    hit = bool(result.get('is_down_channel', False))
                    reason = result.get('reason', '')
                    detail = result.get('detail', '')
                    kline = get_kline_data(symbol)
                    closes = [item['close'] for item in kline[-20:]] if kline and len(kline) >= 20 else []
                    # 获取最新快照
                    snapshot = get_stock_data(symbol, as_dict=True)
                    close = snapshot.get('current_price')
                    pre_close = snapshot.get('pre_close')
                    pct_change = round((close - pre_close) / pre_close * 100, 2) if close is not None and pre_close else None
                    result_item['hit'] = hit
                    result_item['reason'] = reason
                    result_item['market_data'] = {
                        'close': close,
                        'pre_close': pre_close,
                        'pct_change': pct_change,
                        'trigger_time': snapshot.get('update_time'),
                        'min_close_20d': min(closes) if closes else None
                    }
                    result_item['extra'] = {'形态分析': '下降通道开启' if hit else '未形成下降通道', '详细分析': detail}
                except Exception as e:
                    result_item['status'] = 'fail'
                    result_item['reason'] = str(e)
                    result_item['extra'] = {'原因': str(e)}
                    
            elif rule == 'pct_change_5':
                try:
                    # 优化：直接用快照接口，不查K线
                    stock_info = get_stock_data(symbol, as_dict=True)
                    if isinstance(stock_info, dict):
                        close = stock_info.get('current_price')
                        pre_close = stock_info.get('pre_close')
                    elif hasattr(stock_info, 'json'):
                        stock_json = stock_info.json if not callable(stock_info.json) else stock_info.json()
                        close = stock_json.get('current_price')
                        pre_close = stock_json.get('pre_close')
                    else:
                        close = None
                        pre_close = None
                    if close is not None and pre_close is not None and pre_close != 0:
                        pct = (close - pre_close) / pre_close * 100
                        hit = abs(pct) >= 5
                        result_item['reason'] = f"涨跌幅: {round(pct,2)}%，{'命中' if hit else '未命中'}"
                        result_item['market_data'] = {
                            'close': close,
                            'pre_close': pre_close,
                            'pct_change': round(pct,2),
                            'trigger_time': None
                        }
                        result_item['hit'] = hit
                        result_item['extra'] = {
                            '涨跌幅分析': f"最新价: {close}，前收: {pre_close}，涨跌幅: {round(pct,2)}%",
                            '命中情况': '涨跌幅绝对值大于等于5%' if hit else '涨跌幅绝对值小于5%'
                        }
                    else:
                        result_item['status'] = 'fail'
                        result_item['reason'] = '快照数据不足，无法计算涨跌幅'
                        result_item['extra'] = {'涨跌幅分析': '快照数据不足，无法计算涨跌幅'}
                except Exception as e:
                    result_item['reason'] = str(e)
                    result_item['extra'] = {'原因': str(e)}
                    
            elif rule == 'multi_factor_entry_exit':
                try:
                    from quant import analyze_multi_factor_entry_exit
                    result = analyze_multi_factor_entry_exit(symbol)
                    hit = bool(result.get('is_entry', False))
                    reason = result.get('reason', '')
                    detail = result.get('detail', {})
                    # 获取最新快照
                    snapshot = get_stock_data(symbol, as_dict=True)
                    close = snapshot.get('current_price')
                    pre_close = snapshot.get('pre_close')
                    pct_change = round((close - pre_close) / pre_close * 100, 2) if close is not None and pre_close else None
                    result_item['hit'] = hit
                    result_item['reason'] = reason
                    result_item['market_data'] = {
                        'close': close,
                        'pre_close': pre_close,
                        'pct_change': pct_change,
                        'trigger_time': snapshot.get('update_time')
                    }
                    result_item['extra'] = detail
                except Exception as e:
                    result_item['status'] = 'fail'
                    result_item['reason'] = str(e)
                    result_item['extra'] = {'原因': str(e)}
                    
            elif rule == 'undervalued_stock':
                try:
                    from quant import analyze_undervalued_stock
                    result = analyze_undervalued_stock(symbol)
                    hit = bool(result.get('is_undervalued', False))
                    reason = result.get('reason', '')
                    valuation = result.get('valuation', '')
                    result_item['hit'] = hit
                    result_item['reason'] = reason
                    result_item['extra'] = {
                        'valuation': valuation,
                        'fundamental': result.get('fundamental', {})
                    }
                except Exception as e:
                    result_item['status'] = 'fail'
                    result_item['reason'] = str(e)
                    result_item['extra'] = {'原因': str(e)}
                    
            elif rule == 'active_smallmidcap_stock':
                try:
                    from quant import analyze_active_smallmidcap_stock
                    result = analyze_active_smallmidcap_stock(symbol)
                    hit = bool(result.get('is_active', False))
                    reason = result.get('reason', '')
                    detail = result.get('detail', {})
                    # 获取最新快照
                    snapshot = get_stock_data(symbol, as_dict=True)
                    close = snapshot.get('current_price')
                    pre_close = snapshot.get('pre_close')
                    pct_change = round((close - pre_close) / pre_close * 100, 2) if close is not None and pre_close else None
                    result_item['hit'] = hit
                    result_item['reason'] = reason
                    result_item['market_data'] = {
                        'close': close,
                        'pre_close': pre_close,
                        'pct_change': pct_change,
                        'trigger_time': snapshot.get('update_time')
                    }
                    result_item['extra'] = detail
                except Exception as e:
                    result_item['status'] = 'fail'
                    result_item['reason'] = str(e)
                    result_item['extra'] = {'原因': str(e)}
                    
            else:
                result_item['status'] = 'fail'
                result_item['reason'] = '不支持的规则'
                result_item['extra'] = {'原因': '不支持的规则'}
                
            # 处理命中时间逻辑
            user_status = monitor_status.setdefault(user_id, {})
            symbol_status = user_status.setdefault(symbol, {})
            rule_status = symbol_status.setdefault(rule, {})
            prev_hit = rule_status.get('hit', False)
            hit_start_time = rule_status.get('hit_start_time')
            hit_end_time = rule_status.get('hit_end_time')
            
            if result_item['hit']:
                if not prev_hit:
                    # 首次命中，记录入场时间为最近交易日
                    hit_start_time = trade_date
                    hit_end_time = None
                # 命中时不更新结束时间
            else:
                if prev_hit:
                    # 从命中变为未命中，记录出场时间为最近交易日
                    hit_end_time = trade_date
                # 未命中时不更新开始时间
                
            # 更新状态
            rule_status['hit'] = result_item['hit']
            rule_status['hit_start_time'] = hit_start_time
            rule_status['hit_end_time'] = hit_end_time
            result_item['hit_start_time'] = hit_start_time
            result_item['hit_end_time'] = hit_end_time
            
            results.append(result_item)
            time.sleep(0.3)  # 每只股票间隔0.3秒，防止限流
            
        # 保存监控状态
        save_monitor_status(monitor_status)
        
        # 存储本次执行记录
        today = datetime.now().strftime('%Y-%m-%d')
        strategy_log = load_strategy_log()
        user_log = strategy_log.setdefault(today, {}).setdefault(user_id, [])
        
        # 追加本次执行结果
        user_log.append({
            'execute_time': execute_time,
            'results': results
        })
        
        # 按 execute_time 倒序排序
        user_log.sort(key=lambda x: x['execute_time'], reverse=True)
        save_strategy_log(strategy_log)
        
        # 更新 user_monitor_config.json 的 alerts 字段为最新 results
        if config_data is None:
            all_data = load_monitor_config()
        all_data[user_id]['alerts'] = results
        save_monitor_config(all_data)
        
        return {'results': results, 'status': 200}
        
    except Exception as e:
        return {'error': str(e), 'status': 500}


def analyze_with_deepseek_service(data):
    """
    使用DEEPSEEK分析股票数据
    
    Args:
        data: 包含股票数据的字典，需要包含:
            - symbol: 股票代码
            - technical_indicators: 技术指标数据
            - capital_flow: 资金流向数据
            
    Returns:
        dict: 包含分析结果的字典
    """
    import os
    import json
    import requests
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
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
        "30d_trend": "详细描述近半年资金的净流入/流出情况及其波动特征，例如：近半年累计净流入达到X亿元，资金活跃度较高，但近期波动有所增加。", // 近半年资金流向趋势
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
