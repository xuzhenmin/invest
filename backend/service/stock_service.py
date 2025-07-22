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
from futu import RET_OK, KLType, AuType, PeriodType
from futu.common.constant import OptionType, SecurityType
import akshare as ak
import os
import talib

logger = logging.getLogger(__name__)

# 迁移自 app.py
# 依赖注入: quote_ctx, batch_market_snapshot, get_stock_news, analyze_fundamental 等需在app.py中传入或全局导入

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
