import akshare as ak
import pandas as pd
import numpy as np
from futu import OpenQuoteContext, RET_OK
import logging
from datetime import datetime
logger = logging.getLogger(__name__)
import requests
import time as pytime
import json
import threading
import os
from collections import defaultdict
import tempfile

print(f"[DEBUG] quant.py loaded from: {__file__}")
print(f"[DEBUG] pd id at top: {id(pd)}")

def get_stock_list(market):
    """
    根据市场代码返回股票列表。
    market: 'SH', 'SZ', 'BJ', 'US', 'HK'
    返回 pandas.DataFrame，包含股票代码、名称等信息。
    """
    if market == 'SH':
        df = ak.stock_sh_a_spot_em()
    elif market == 'SZ':
        df = ak.stock_sz_a_spot_em()
    elif market == 'BJ':
        df = ak.stock_bj_a_spot_em()
    elif market == 'HK':
        df = ak.stock_hk_spot_em()
    elif market == 'US':
        df = ak.stock_us_spot()
    else:
        raise ValueError(f"不支持的市场类型: {market}")
    return df

def get_stock_capital_flow(symbol):
    """
    查询个股资金流向
    symbol: 股票代码，形如 '600519.SH', '00700.HK', 'AAPL.US'
    返回 pandas.DataFrame
    """
    if symbol.endswith('.SZ') or symbol.endswith('.SH'):
        stock_code = symbol.split('.')[0]
        df = ak.stock_individual_fund_flow(stock=stock_code)
    elif symbol.endswith('.HK'):
        stock_code = symbol.split('.')[0]
        df = ak.stock_hk_money_flow(symbol=stock_code)
    elif symbol.endswith('.US'):
        stock_code = symbol.split('.')[0]
        df = ak.stock_us_fund_flow(symbol=stock_code)
    else:
        raise ValueError(f"不支持的symbol格式: {symbol}")
    return df

def fetch_hk_financials_from_eastmoney(stock_code):
    """
    爬取东方财富港股F10财务数据，返回DataFrame
    stock_code: '01810'（不带.HK后缀）
    """
    # 使用新的数据接口
    url = f"https://datacenter.eastmoney.com/securities/api/data/v1/get"
    
    # 构建请求参数
    params = {
        'reportName': 'RPT_HKF10_FN_INCOME_PC',
        'columns': 'SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,REPORT_DATE,DATE_TYPE_CODE,FISCAL_YEAR,START_DATE,STD_ITEM_CODE,STD_ITEM_NAME,AMOUNT',
        'quoteColumns': '',
        'filter': f'(SECUCODE="{stock_code}.HK")(REPORT_DATE in (\'2025-03-31\',\'2024-12-31\',\'2024-09-30\',\'2024-06-30\',\'2024-03-31\',\'2023-12-31\',\'2023-09-30\',\'2023-06-30\'))',
        'pageNumber': '1',
        'pageSize': '',
        'sortTypes': '-1,1',
        'sortColumns': 'REPORT_DATE,STD_ITEM_CODE',
        'source': 'F10',
        'client': 'PC',
        'v': '0008504766745329406'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://datacenter.eastmoney.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }
    
    try:
        logger.info(f"[fetch_hk_financials_from_eastmoney] 请求港股财务数据: {stock_code}")
        
        # 发送请求
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        
        # 解析JSON响应
        data = resp.json()
        
        # 检查响应状态
        if not data.get('success', False):
            logger.error(f"[fetch_hk_financials_from_eastmoney] API返回失败: {data.get('message', 'Unknown error')}")
            return pd.DataFrame()
        
        # 提取数据
        records = data.get('result', {}).get('data', [])
        if not records:
            logger.warning(f"[fetch_hk_financials_from_eastmoney] 无财务数据记录: {stock_code}")
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(records)
        
        # 数据清洗和格式化
        if not df.empty:
            # 转换金额字段为数值类型
            if 'AMOUNT' in df.columns:
                df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
            
            # 格式化报告日期
            if 'REPORT_DATE' in df.columns:
                df['REPORT_DATE'] = pd.to_datetime(df['REPORT_DATE']).dt.strftime('%Y-%m-%d')
            
            # 按报告期和指标代码排序
            df = df.sort_values(['REPORT_DATE', 'STD_ITEM_CODE'], ascending=[False, True])
            
            logger.info(f"[fetch_hk_financials_from_eastmoney] 成功获取 {stock_code} 财务数据，共 {len(df)} 条记录")
            return df
        else:
            logger.warning(f"[fetch_hk_financials_from_eastmoney] 数据为空: {stock_code}")
            return pd.DataFrame()
            
    except requests.exceptions.RequestException as e:
        logger.error(f"[fetch_hk_financials_from_eastmoney] 网络请求异常 for {stock_code}: {e}")
        return pd.DataFrame()
    except ValueError as e:
        logger.error(f"[fetch_hk_financials_from_eastmoney] JSON解析失败 for {stock_code}: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"[fetch_hk_financials_from_eastmoney] 其他异常 for {stock_code}: {e}")
        return pd.DataFrame()

def get_stock_financials(symbol):
    """
    查询个股财务数据
    symbol: 股票代码，形如 '600519.SH', '00700.HK', 'AAPL.US'
    返回 pandas.DataFrame
    """
    if symbol.endswith('.SZ') or symbol.endswith('.SH'):
        stock_code = symbol.split('.')[0]
        df = ak.stock_financial_abstract(symbol=stock_code)
        # 转置，报告期为行，指标为列
        if not df.empty:
            df = df.set_index(df.columns[0]).T.reset_index().rename(columns={'index': '报告期'})
    elif symbol.endswith('.HK'):
        stock_code = symbol.split('.')[0]
        try:
            df = fetch_hk_financials_from_eastmoney(stock_code)
            if not df.empty:
                # 标准化字段
                df['报告期'] = df['REPORT_DATE'] if 'REPORT_DATE' in df.columns else df.get('报告期', '')
                df['指标名称'] = df['STD_ITEM_NAME']
                df['数值'] = df['AMOUNT']
                # 透视为横表：每行一个报告期，每列一个指标
                pivot_df = df.pivot_table(
                    index='报告期',
                    columns='指标名称',
                    values='数值',
                    aggfunc='first'
                ).reset_index()
                # 按报告期倒序排列
                try:
                    pivot_df['报告期'] = pd.to_datetime(pivot_df['报告期'])
                    pivot_df = pivot_df.sort_values('报告期', ascending=False)
                    pivot_df['报告期'] = pivot_df['报告期'].dt.strftime('%Y-%m-%d')
                except Exception as e:
                    logger.warning(f"[get_stock_financials] 港股财务数据报告期排序异常: {e}")
                # 列名转为字符串，防止前端key为数字
                pivot_df.columns = [str(col) for col in pivot_df.columns]
                return pivot_df
            return df
        except Exception as e:
            logger.error(f"[get_stock_financials] 港股财务数据异常: {e}")
            return pd.DataFrame()
    elif symbol.endswith('.US'):
        # 美股暂不支持财务数据，直接返回空DataFrame
        df = pd.DataFrame()
    else:
        raise ValueError(f"不支持的symbol格式: {symbol}")
    return df

def quant_get_stock_kline(symbol, start, end):
    """
    查询股票历史K线（日线），并计算EMA5/10/12/20/26/30/60/120
    symbol: 股票代码，形如 '600519.SH', '00700.HK', 'AAPL.US'
    start, end: 'YYYY-MM-DD'
    返回 pandas.DataFrame
    """
    if symbol.endswith('.SZ') or symbol.endswith('.SH'):
        stock_code = symbol.split('.')[0]
        ak_start_date = start.replace('-', '')
        ak_end_date = end.replace('-', '')
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=ak_start_date, end_date=ak_end_date, adjust="qfq")
        df = df.rename(columns={
            '日期': 'time_key', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'
        })
    elif symbol.endswith('.HK'):
        stock_code = symbol.split('.')[0]
        df = ak.stock_hk_daily(symbol=stock_code)
        # 兼容不同数据源的列名
        if '日期' in df.columns:
            df = df.rename(columns={
                '日期': 'time_key', '开盘价': 'open', '收盘价': 'close', '最高价': 'high', '最低价': 'low', '成交量': 'volume'
            })
        elif 'date' in df.columns:
            df = df.rename(columns={
                'date': 'time_key', 'open': 'open', 'close': 'close', 'high': 'high', 'low': 'low', 'volume': 'volume'
            })
        # 如果还没有 time_key，尝试用 index
        if 'time_key' not in df.columns and df.index.name in ['date', '日期']:
            df = df.reset_index().rename(columns={df.index.name: 'time_key'})
        if 'time_key' not in df.columns:
            raise ValueError('港股K线数据缺少日期列，无法分析')
        # 修复：先转为字符串再过滤，避免类型不匹配
        df['time_key'] = df['time_key'].astype(str)
        df = df[(df['time_key'] >= start) & (df['time_key'] <= end)]
    elif symbol.endswith('.US'):
        stock_code = symbol.split('.')[0]
        df = ak.stock_us_daily(symbol=stock_code)
        df = df.rename(columns={
            '日期': 'time_key', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'
        })
        # 修复：先转为字符串再过滤，避免类型不匹配
        df['time_key'] = df['time_key'].astype(str)
        df = df[(df['time_key'] >= start) & (df['time_key'] <= end)]
    else:
        raise ValueError(f"不支持的symbol格式: {symbol}")
    df['time_key'] = pd.to_datetime(df['time_key']).dt.date.astype(str)
    df = df.sort_values('time_key')
    for span in [5, 10, 12, 20, 26, 30, 60, 120]:
        df[f'EMA{span}'] = df['close'].ewm(span=span, adjust=False).mean()
    return df

def get_stock_news(symbol):
    """
    参考 app.py 的 get_stock_news 路由实现，返回 DataFrame 格式的新闻列表。
    """
    code_parts = symbol.split('.')
    if len(code_parts) != 2:
        raise ValueError('股票代码格式错误')
    stock_code = code_parts[0]
    market = code_parts[1].upper()
    news_list = []
    if market == 'SH' or market == 'SZ':
        # 1. 公司公告
        try:
            stock_code_6 = stock_code.split('.')[0] if '.' in stock_code else stock_code
            try:
                notice_df = ak.stock_notice_report(symbol=stock_code_6)
            except KeyError:
                notice_df = pd.DataFrame()
            if not notice_df.empty:
                for _, row in notice_df.iterrows():
                    news_list.append({
                        'title': row['公告标题'] if '公告标题' in row else row.get('title', ''),
                        'content': row['公告内容'] if '公告内容' in row else row.get('content', ''),
                        'publish_time': str(row['公告日期'] if '公告日期' in row else row.get('date', '')),
                        'source': '公司公告',
                        'url': row['公告链接'] if '公告链接' in row else row.get('url', None)
                    })
        except Exception:
            pass
        # 2. 公司新闻
        try:
            news_df = ak.stock_news_em(symbol=stock_code)
            if not news_df.empty:
                for _, row in news_df.iterrows():
                    news_list.append({
                        'title': row['title'] if 'title' in row else row.get('新闻标题', ''),
                        'content': row['content'] if 'content' in row else row.get('新闻内容', ''),
                        'publish_time': str(row['time'] if 'time' in row else row.get('发布时间', '')),
                        'source': row['source'] if 'source' in row else row.get('来源', '东方财富网'),
                        'url': row['url'] if 'url' in row else row.get('链接', None)
                    })
        except Exception:
            pass
        # 3. 行业新闻
        try:
            stock_info = ak.stock_individual_info_em(symbol=stock_code)
            if not stock_info.empty and '所属行业' in stock_info.columns:
                industry = stock_info['所属行业'].iloc[0]
                industry_news = ak.stock_news_industry(symbol=industry)
                if not industry_news.empty:
                    for _, row in industry_news.iterrows():
                        news_list.append({
                            'title': row['title'] if 'title' in row else row.get('新闻标题', ''),
                            'content': row['content'] if 'content' in row else row.get('新闻内容', ''),
                            'publish_time': str(row['time'] if 'time' in row else row.get('发布时间', '')),
                            'source': '行业新闻',
                            'url': row['url'] if 'url' in row else row.get('链接', None)
                        })
        except Exception:
            pass
    elif market == 'HK':
        # 港股新闻
        try:
            news_df = ak.stock_hk_news_em(symbol=stock_code)
            if not news_df.empty:
                for _, row in news_df.iterrows():
                    news_list.append({
                        'title': row['title'] if 'title' in row else row.get('新闻标题', ''),
                        'content': row['content'] if 'content' in row else row.get('新闻内容', ''),
                        'publish_time': str(row['time'] if 'time' in row else row.get('发布时间', '')),
                        'source': row['source'] if 'source' in row else row.get('来源', ''),
                        'url': row['url'] if 'url' in row else row.get('链接', None)
                    })
        except Exception:
            pass
        # 港股公告
        try:
            notice_df = ak.stock_hk_report_em(symbol=stock_code)
            if not notice_df.empty:
                for _, row in notice_df.iterrows():
                    news_list.append({
                        'title': row['title'] if 'title' in row else row.get('公告标题', ''),
                        'content': row['content'] if 'content' in row else row.get('公告内容', ''),
                        'publish_time': str(row['time'] if 'time' in row else row.get('公告日期', '')),
                        'source': '公司公告',
                        'url': row['url'] if 'url' in row else row.get('公告链接', None)
                    })
        except Exception:
            pass
        # 港股行业新闻
        try:
            stock_info = ak.stock_hk_spot_em()
            if not stock_info.empty:
                stock_row = stock_info[stock_info['代码'] == stock_code]
                if not stock_row.empty and '所属行业' in stock_row.columns:
                    industry = stock_row['所属行业'].iloc[0]
                    industry_news = ak.stock_news_industry(symbol=industry)
                    if not industry_news.empty:
                        for _, row in industry_news.iterrows():
                            news_list.append({
                                'title': row['title'] if 'title' in row else row.get('新闻标题', ''),
                                'content': row['content'] if 'content' in row else row.get('新闻内容', ''),
                                'publish_time': str(row['time'] if 'time' in row else row.get('发布时间', '')),
                                'source': '行业新闻',
                                'url': row['url'] if 'url' in row else row.get('链接', None)
                            })
        except Exception:
            pass
    elif market == 'US':
        try:
            news_df = ak.stock_us_news(symbol=stock_code)
            if not news_df.empty:
                for _, row in news_df.iterrows():
                    news_list.append({
                        'title': row['title'] if 'title' in row else row.get('新闻标题', ''),
                        'content': row['content'] if 'content' in row else row.get('新闻内容', ''),
                        'publish_time': str(row['time'] if 'time' in row else row.get('发布时间', '')),
                        'source': row['source'] if 'source' in row else row.get('来源', ''),
                        'url': row['url'] if 'url' in row else row.get('链接', None)
                    })
        except Exception:
            pass
    else:
        raise ValueError('不支持的市场类型')
    # 按发布时间排序
    news_list = [n for n in news_list if n.get('publish_time')]
    news_list.sort(key=lambda x: x['publish_time'], reverse=True)
    news_list = news_list[:50]
    return pd.DataFrame(news_list)

def analyze_stock(symbol):
    """
    综合技术面、资金面、财务面分析股票，给出趋势判断、买卖建议和风险提示。
    输入：symbol（如 '600519.SH'）
    返回：dict，包括趋势、买卖建议、技术面、资金面、财务面、风险提示等
    """
    result = {
        'symbol': symbol,
        'trend': '',
        'advice': '',
        'technical': '',
        'capital': '',
        'financial': '',
        'risk': ''
    }
    try:
        # 1. 技术面分析
        kline = None
        try:
            kline = quant_get_stock_kline(symbol, pd.Timestamp.today().strftime('%Y-%m-%d'), pd.Timestamp.today().strftime('%Y-%m-%d'))
        except Exception:
            pass
        tech_desc = []
        trend = ''
        advice = ''
        if kline is not None and not kline.empty:
            df = kline.copy()
            df = df.sort_values('time_key')
            # 取最近60日
            df = df.tail(60)
            close = df['close']
            ema5 = df['EMA5']
            ema20 = df['EMA20']
            ema60 = df['EMA60']
            macd = df['EMA12'] - df['EMA26']
            rsi = df['close'].diff().rolling(14).apply(lambda x: 100 - 100/(1 + (x[x>0].mean() / abs(x[x<0].mean()) if abs(x[x<0].mean())>0 else 1)), raw=False)
            latest = df.iloc[-1]
            # 趋势判断
            if latest['close'] > latest['EMA5'] > latest['EMA20'] > latest['EMA60']:
                trend = '多头排列，趋势向上'
                advice = '可考虑持有或逢低加仓'
            elif latest['close'] < latest['EMA5'] < latest['EMA20'] < latest['EMA60']:
                trend = '空头排列，趋势向下'
                advice = '建议观望或减仓'
            else:
                trend = '震荡整理，趋势不明朗'
                advice = '建议耐心等待方向明朗'
            # MACD
            if latest['EMA12'] > latest['EMA26'] and macd.iloc[-2] <= 0:
                tech_desc.append('MACD金叉，短线有反弹机会')
            elif latest['EMA12'] < latest['EMA26'] and macd.iloc[-2] >= 0:
                tech_desc.append('MACD死叉，短线有回调风险')
            # RSI
            if latest['RSI'] > 70:
                tech_desc.append('RSI超买，注意回调风险')
            elif latest['RSI'] < 30:
                tech_desc.append('RSI超卖，或有反弹')
            # 均线
            tech_desc.append(f"当前价:{latest['close']:.2f}，EMA5:{latest['EMA5']:.2f}，EMA20:{latest['EMA20']:.2f}，EMA60:{latest['EMA60']:.2f}")
        else:
            tech_desc.append('无足够K线数据')
        result['trend'] = trend
        result['advice'] = advice
        result['technical'] = '；'.join(tech_desc)

        # 2. 资金面分析
        capital_desc = []
        try:
            capital = get_stock_capital_flow(symbol)
            if capital is not None and not capital.empty:
                # 以近5日主力净流入为例
                if '主力净流入' in capital.columns:
                    net_main = capital['主力净流入'].tail(5).sum()
                    if net_main > 0:
                        capital_desc.append(f'主力资金近5日净流入{net_main:.2f}万元，资金偏多')
                    else:
                        capital_desc.append(f'主力资金近5日净流出{abs(net_main):.2f}万元，资金偏空')
                else:
                    capital_desc.append('无主力资金数据')
            else:
                capital_desc.append('无资金流数据')
        except Exception:
            capital_desc.append('资金面获取失败')
        result['capital'] = '；'.join(capital_desc)

        # 3. 财务面分析
        financial_desc = []
        try:
            fin = get_stock_financials(symbol)
            if fin is not None and not fin.empty:
                # 以净利润、营收、ROE等为例
                if '净利润' in fin.columns:
                    profit = fin['净利润'].iloc[0]
                    financial_desc.append(f'最新净利润：{profit}')
                if '营业总收入' in fin.columns:
                    revenue = fin['营业总收入'].iloc[0]
                    financial_desc.append(f'最新营收：{revenue}')
                if 'ROE' in fin.columns:
                    roe = fin['ROE'].iloc[0]
                    financial_desc.append(f'ROE：{roe}')
            else:
                financial_desc.append('无财务数据')
        except Exception:
            financial_desc.append('财务面获取失败')
        result['financial'] = '；'.join(financial_desc)

        # 4. 风险提示
        risk = []
        if '空头' in trend or '净流出' in result['capital']:
            risk.append('短期下跌风险较大，注意控制仓位')
        if '财务面获取失败' in result['financial'] or '无财务数据' in result['financial']:
            risk.append('财务数据不全，需警惕基本面风险')
        if not risk:
            risk.append('暂无明显风险，但仍需关注市场波动')
        result['risk'] = '；'.join(risk)
    except Exception as e:
        result['trend'] = '分析失败'
        result['advice'] = '分析失败'
        result['technical'] = str(e)
        result['capital'] = '分析失败'
        result['financial'] = '分析失败'
        result['risk'] = '分析失败'
    return result

def analyze_elliott_wave(symbol, window=120):
    """
    分析股票是否处于上升通道及三浪结构（二浪末期或三浪起始）。
    返回 dict: { 'is_up_channel': bool, 'is_wave3_start': bool, 'stage': '二浪末期/三浪起始/其它', 'reason': str }
    """
    result = {
        'symbol': symbol,
        'is_up_channel': False,
        'is_wave3_start': False,
        'stage': '其它',
        'reason': ''
    }
    try:
        # 1. 获取历史K线
        end = pd.Timestamp.today().strftime('%Y-%m-%d')
        start = (pd.Timestamp.today() - pd.Timedelta(days=window*1.5)).strftime('%Y-%m-%d')
        df = quant_get_stock_kline(symbol, start, end)
        if df is None or df.empty or len(df) < 60:
            result['reason'] = f'K线数据不足，symbol={symbol}，实际行数={0 if df is None else len(df)}'
            return result
        df = df.sort_values('time_key').tail(window).reset_index(drop=True)
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        dates = df['time_key'].values
        # 2. 识别局部高低点（swing high/low）
        def find_peaks(arr, order=3):
            """返回局部极大值的索引"""
            return [i for i in range(order, len(arr)-order)
                    if arr[i] == max(arr[i-order:i+order+1])]
        def find_troughs(arr, order=3):
            """返回局部极小值的索引"""
            return [i for i in range(order, len(arr)-order)
                    if arr[i] == min(arr[i-order:i+order+1])]
        peak_idx = find_peaks(highs, order=3)
        trough_idx = find_troughs(lows, order=3)
        # 只保留最近3个高点和低点
        peak_idx = peak_idx[-3:]
        trough_idx = trough_idx[-3:]
        # 检查高低点数量
        if len(peak_idx) < 1 or len(trough_idx) < 1:
            result['reason'] = f'高低点数量不足，无法判别三浪结构。高点数={len(peak_idx)}，低点数={len(trough_idx)}'
            return result
        # 3. 判断上升通道（高点、低点逐步抬高）
        is_up_channel = False
        up_channel_reason = ''
        if len(peak_idx) >= 2 and len(trough_idx) >= 2:
            if highs[peak_idx[-2]] < highs[peak_idx[-1]] and lows[trough_idx[-2]] < lows[trough_idx[-1]]:
                is_up_channel = True
                up_channel_reason = f'高点({highs[peak_idx[-2]]:.2f}->{highs[peak_idx[-1]]:.2f})、低点({lows[trough_idx[-2]]:.2f}->{lows[trough_idx[-1]]:.2f})逐步抬高，处于上升通道'
            else:
                up_channel_reason = f'高点({highs[peak_idx[-2]]:.2f}->{highs[peak_idx[-1]]:.2f})或低点({lows[trough_idx[-2]]:.2f}->{lows[trough_idx[-1]]:.2f})未抬高，不满足上升通道'
        else:
            up_channel_reason = f'高低点数量不足以判断上升通道（高点数={len(peak_idx)}，低点数={len(trough_idx)}）'
        result['is_up_channel'] = is_up_channel
        # 4. 判断三浪结构
        stage = '其它'
        reason = [up_channel_reason]
        if is_up_channel:
            peak1 = peak_idx[-1]
            trough2 = trough_idx[-1]
            # 二浪末期：当前价接近二浪低点，且未跌破前低
            if abs(closes[-1] - lows[trough2]) / closes[-1] < 0.03 and closes[-1] > lows[trough2]:
                stage = '二浪末期'
                reason.append(f'当前价({closes[-1]:.2f})接近最近低点({lows[trough2]:.2f})，有止跌迹象')
            # 三浪起始：当前价突破一浪高点，且放量（可用均量对比）
            elif closes[-1] > highs[peak1]:
                if 'volume' in df.columns and not df['volume'].isnull().all():
                    vol3 = df['volume'].tail(3).mean()
                    vol20 = df['volume'].tail(20).mean()
                    if vol3 > 1.2 * vol20:
                        stage = '三浪起始'
                        reason.append(f'当前价({closes[-1]:.2f})突破前高({highs[peak1]:.2f})，且放量明显(3日均量={vol3:.2f} > 20日均量={vol20:.2f})')
                    else:
                        stage = '三浪起始(无明显放量)'
                        reason.append(f'当前价({closes[-1]:.2f})突破前高({highs[peak1]:.2f})，但放量不明显(3日均量={vol3:.2f}，20日均量={vol20:.2f})')
                else:
                    stage = '三浪起始(无成交量数据)'
                    reason.append(f'当前价({closes[-1]:.2f})突破前高({highs[peak1]:.2f})，但缺少成交量数据，无法判断放量')
            else:
                reason.append(f'当前价({closes[-1]:.2f})未突破前高({highs[peak1]:.2f})，也未接近最近低点({lows[trough2]:.2f})，不满足三浪结构')
        else:
            reason.append('未满足上升通道，不判别三浪结构')
        result['stage'] = stage
        result['is_wave3_start'] = (stage.startswith('三浪起始'))
        if not reason:
            reason.append('未检测到典型三浪结构')
        result['reason'] = '；'.join(reason)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        result['reason'] = f'分析异常: {e}，symbol={symbol}，traceback={tb}'
    return result

def analyze_down_channel(symbol, window=20):
    """
    优化版：下降通道不仅要求低点递减，还要求最近3个高点递减，且收盘价未突破前2高点且靠近低点。
    返回 dict: { 'is_down_channel': bool, 'reason': str, 'detail': str }
    """
    result = {
        'symbol': symbol,
        'is_down_channel': False,
        'reason': '',
        'detail': ''
    }
    try:
        end = pd.Timestamp.today().strftime('%Y-%m-%d')
        start = (pd.Timestamp.today() - pd.Timedelta(days=window*1.5)).strftime('%Y-%m-%d')
        df = quant_get_stock_kline(symbol, start, end)
        if df is None or df.empty or len(df) < window:
            result['reason'] = f'K线数据不足，symbol={symbol}，实际行数={0 if df is None else len(df)}'
            return result
        df = df.sort_values('time_key').tail(window).reset_index(drop=True)
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        dates = df['time_key'].values
        # 识别局部高低点
        def find_peaks(arr, order=3):
            return [i for i in range(order, len(arr)-order)
                    if arr[i] == max(arr[i-order:i+order+1])]
        def find_troughs(arr, order=3):
            return [i for i in range(order, len(arr)-order)
                    if arr[i] == min(arr[i-order:i+order+1])]
        peak_idx = find_peaks(highs, order=3)[-3:]
        trough_idx = find_troughs(lows, order=3)[-3:]
        reason = []
        # 判断高点递减
        high_desc = ''
        high_cond = False
        if len(peak_idx) == 3:
            h1, h2, h3 = highs[peak_idx[0]], highs[peak_idx[1]], highs[peak_idx[2]]
            if h1 > h2 > h3:
                high_cond = True
                high_desc = f'最近3个高点递减({h1:.2f}>{h2:.2f}>{h3:.2f})'
            else:
                high_desc = f'最近3个高点未递减({h1:.2f}, {h2:.2f}, {h3:.2f})'
        else:
            high_desc = f'高点数量不足3个，无法判断高点递减'
        reason.append(high_desc)
        # 判断低点递减
        low_desc = ''
        low_cond = False
        if len(trough_idx) == 3:
            l1, l2, l3 = lows[trough_idx[0]], lows[trough_idx[1]], lows[trough_idx[2]]
            if l1 > l2 > l3:
                low_cond = True
                low_desc = f'最近3个低点递减({l1:.2f}>{l2:.2f}>{l3:.2f})'
            else:
                low_desc = f'最近3个低点未递减({l1:.2f}, {l2:.2f}, {l3:.2f})'
        else:
            low_desc = f'低点数量不足3个，无法判断低点递减'
        reason.append(low_desc)
        # 判断收盘价未突破前2高点，且靠近低点
        close_desc = ''
        close_cond = False
        latest_close = closes[-1]
        if len(peak_idx) >= 2 and len(trough_idx) >= 1:
            prev_high1 = highs[peak_idx[-1]]
            prev_high2 = highs[peak_idx[-2]]
            latest_low = lows[trough_idx[-1]]
            not_break_high = latest_close < prev_high1 and latest_close < prev_high2
            near_low = abs(latest_close - latest_low) / latest_close < 0.03  # 距离低点3%以内
            if not_break_high and near_low:
                close_cond = True
                close_desc = f'收盘价({latest_close:.2f})未突破前2高点({prev_high1:.2f}, {prev_high2:.2f})且接近低点({latest_low:.2f})'
            else:
                close_desc = f'收盘价({latest_close:.2f})未满足未突破高点且接近低点条件'
        else:
            close_desc = '高点或低点数量不足，无法判断收盘价条件'
        reason.append(close_desc)
        # 综合判断
        is_down_channel = high_cond and low_cond and close_cond
        result['is_down_channel'] = is_down_channel
        if is_down_channel:
            reason.append('下降通道开启')
        result['reason'] = '；'.join(reason)
        result['detail'] = f'高点索引:{peak_idx}, 高点值:{[float(highs[i]) for i in peak_idx]}, 低点索引:{trough_idx}, 低点值:{[float(lows[i]) for i in trough_idx]}, 收盘价序列:{closes.tolist()}'
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        result['reason'] = f'分析异常: {e}，symbol={symbol}，traceback={tb}'
    return result

def batch_market_snapshot(symbols, quote_ctx=None):
    """
    批量快照查询，将股票列表按市场分组，每20只一批调用get_market_snapshot。
    symbols: ['HK.00700', '02171.HK', '600000.SH', ...]
    返回: dict { 'HK.00700': 行情dict, ... }
    """
    results = {}
    def normalize_symbol(s):
        if '.' in s:
            code, market = s.split('.')
            market = market.upper()
            if market == 'HK' and code.isdigit():
                return f"{market}.{code.zfill(5)}"
            elif market == 'US':
                # 美股统一为US.BABA格式
                return f"US.{code.upper()}"
            else:
                return f"{market}.{code}"
        else:
            return s
    if quote_ctx is not None:
        norm_syms = [normalize_symbol(s) for s in symbols]
        market_groups = {}
        for s in norm_syms:
            parts = s.split('.')
            if len(parts) != 2:
                continue
            market = parts[0].upper()
            market_groups.setdefault(market, []).append(s)
        for market, syms in market_groups.items():
            for i in range(0, len(syms), 20):
                batch = syms[i:i+20]
                if market == 'US':
                    print(f"[FUTU美股快照] 查询入参: {batch}")
                ret, data = quote_ctx.get_market_snapshot(batch)
                if market == 'US':
                    print(f"[FUTU美股快照] 返回ret: {ret}, data: {data if isinstance(data, str) else data.to_dict() if hasattr(data, 'to_dict') else data}")
                if ret == RET_OK and data is not None and not data.empty:
                    for idx, row in data.iterrows():
                        results[row['code']] = row.to_dict()
        return results
    # 否则每次新建并自动关闭
    with OpenQuoteContext(host='127.0.0.1', port=11111) as ctx:
        norm_syms = [normalize_symbol(s) for s in symbols]
        market_groups = {}
        for s in norm_syms:
            parts = s.split('.')
            if len(parts) != 2:
                continue
            market = parts[0].upper()
            market_groups.setdefault(market, []).append(s)
        for market, syms in market_groups.items():
            for i in range(0, len(syms), 20):
                batch = syms[i:i+20]
                if market == 'US':
                    print(f"[FUTU美股快照] 查询入参: {batch}")
                ret, data = ctx.get_market_snapshot(batch)
                if market == 'US':
                    print(f"[FUTU美股快照] 返回ret: {ret}, data: {data if isinstance(data, str) else data.to_dict() if hasattr(data, 'to_dict') else data}")
                if ret == RET_OK and data is not None and not data.empty:
                    for idx, row in data.iterrows():
                        results[row['code']] = row.to_dict()
        return results

def analyze_multi_factor_entry_exit(symbol):
    """
    多维度策略：
    入场：
      - 周线EMA(5)>EMA(20)
      - 日线收盘突破布林带中轨且BBwidth<20日均值
      - 当日成交量>5日均量150%
      - 量比连续3日>1.2且递增
      - 主力资金连续3日净流入（大单净量>0）
      - 北向资金持仓比例周增幅>0.5%
      - 换手率处于近3月30%-70%分位
    出场：
      - 收盘价连续2日低于10日均线
      - 成交量<20日均量且资金连续2日净流出
    """
    import numpy as np
    from datetime import datetime, timedelta
    result = {
        'is_entry': False,
        'is_exit': False,
        'reason': '',
        'detail': {}
    }
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        # 1. 周线K线（含EMA5/20）
        df_week = None
        try:
            if symbol.endswith('.SH') or symbol.endswith('.SZ'):
                stock_code = symbol.split('.')[0]
                df_week = ak.stock_zh_a_hist(symbol=stock_code, period="weekly", adjust="qfq")
                df_week = df_week.rename(columns={'日期': 'time_key', '收盘': 'close'})
            elif symbol.endswith('.HK'):
                stock_code = symbol.split('.')[0]
                df_week = ak.stock_hk_hist(symbol=stock_code, period="weekly")
                df_week = df_week.rename(columns={'日期': 'time_key', '收盘价': 'close'})
            else:
                df_week = None
            if df_week is not None and not df_week.empty:
                df_week['EMA5'] = df_week['close'].ewm(span=5, adjust=False).mean()
                df_week['EMA20'] = df_week['close'].ewm(span=20, adjust=False).mean()
        except Exception:
            df_week = None
        # 2. 日线K线（含布林带、EMA、量、换手率）
        window = 120
        end = today
        start = (datetime.now() - timedelta(days=window*2)).strftime('%Y-%m-%d')
        df = quant_get_stock_kline(symbol, start, end)
        if df is None or df.empty or len(df) < 30:
            result['reason'] = 'K线数据不足'
            return result
        df = df.sort_values('time_key').reset_index(drop=True)
        # 计算布林带
        df['MA20'] = df['close'].rolling(20).mean()
        df['STD20'] = df['close'].rolling(20).std()
        df['BOLL_UP'] = df['MA20'] + 2 * df['STD20']
        df['BOLL_DOWN'] = df['MA20'] - 2 * df['STD20']
        df['BBwidth'] = (df['BOLL_UP'] - df['BOLL_DOWN']) / df['MA20']
        # 量能、换手率
        try:
            if symbol.endswith('.SH') or symbol.endswith('.SZ'):
                stock_code = symbol.split('.')[0]
                vol_df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if '成交量' in vol_df.columns:
                    df['volume'] = vol_df['成交量'].values[-len(df):]
                if '换手率' in vol_df.columns:
                    df['turnover_rate'] = vol_df['换手率'].values[-len(df):]
        except Exception:
            pass
        # 量比（如有）
        try:
            lb_df = ak.stock_individual_info_em(symbol=stock_code)
            if '量比' in lb_df.columns:
                df['volume_ratio'] = lb_df['量比'].values[-len(df):]
        except Exception:
            df['volume_ratio'] = np.nan
        # 主力资金流（如有）
        try:
            fund_df = ak.stock_individual_fund_flow(stock=stock_code)
            if '大单净量' in fund_df.columns:
                df['main_fund'] = fund_df['大单净量'].values[-len(df):]
        except Exception:
            df['main_fund'] = np.nan
        # 北向资金持仓比例（如有）
        try:
            north_df = ak.stock_hsgt_hold_stock_statistics_em(symbol=stock_code)
            if '持股比例' in north_df.columns:
                df['north_ratio'] = north_df['持股比例'].values[-len(df):]
        except Exception:
            df['north_ratio'] = np.nan
        # 1. 价格维度
        entry_price = None
        if df_week is not None and not df_week.empty:
            if df_week.iloc[-1]['EMA5'] > df_week.iloc[-1]['EMA20']:
                entry_price = True
            else:
                entry_price = False
        # 其余条件同理，初始化为 None，只有有数据时才赋值 True/False
        boll_entry = None
        if not np.isnan(df.iloc[-1]['close']) and not np.isnan(df.iloc[-1]['MA20']):
            boll_entry = df.iloc[-1]['close'] > df.iloc[-1]['MA20']
        bbwidth_entry = None
        bbwidth_mean = df['BBwidth'].tail(20).mean()
        if not np.isnan(df.iloc[-1]['BBwidth']) and not np.isnan(bbwidth_mean):
            bbwidth_entry = df.iloc[-1]['BBwidth'] < bbwidth_mean
        vol_entry = None
        if 'volume' in df.columns and not df['volume'].isnull().all():
            vol5 = df['volume'].tail(5).mean()
            if not np.isnan(df.iloc[-1]['volume']) and not np.isnan(vol5):
                vol_entry = df.iloc[-1]['volume'] > 1.5 * vol5
        lb_entry = None
        if 'volume_ratio' in df.columns and not df['volume_ratio'].isnull().all():
            last3 = df['volume_ratio'].tail(3)
            if all(~last3.isnull()):
                lb_entry = all(last3 > 1.2) and all(np.diff(last3) > 0)
        fund_entry = None
        if 'main_fund' in df.columns and not df['main_fund'].isnull().all():
            last3 = df['main_fund'].tail(3)
            if all(~last3.isnull()):
                fund_entry = all(last3 > 0)
        north_entry = None
        week_delta = None
        if 'north_ratio' in df.columns and not df['north_ratio'].isnull().all():
            last5 = df['north_ratio'].tail(5)
            if len(last5) >= 2 and not last5.isnull().all():
                week_delta = last5.iloc[-1] - last5.iloc[0]
                north_entry = week_delta > 0.5
        turnover_entry = None
        if 'turnover_rate' in df.columns and not df['turnover_rate'].isnull().all():
            last_3m = df['turnover_rate'].tail(60)
            if len(last_3m) >= 10 and not last_3m.isnull().all():
                p30 = np.percentile(last_3m.dropna(), 30)
                p70 = np.percentile(last_3m.dropna(), 70)
                cur = df.iloc[-1]['turnover_rate']
                if not np.isnan(cur):
                    turnover_entry = p30 <= cur <= p70
        # 统计缺失项
        entry_conditions = {
            'entry_price': entry_price,
            'boll_entry': boll_entry,
            'bbwidth_entry': bbwidth_entry,
            'vol_entry': vol_entry,
            'lb_entry': lb_entry,
            'fund_entry': fund_entry,
            'north_entry': north_entry,
            'turnover_entry': turnover_entry
        }
        missing_entry_conditions = [k for k, v in entry_conditions.items() if v is None]
        # 只用非None条件判断
        entry_hit = all(v for v in entry_conditions.values() if v is not None)
        # 日志打印
        if missing_entry_conditions:
            logger.info(f"[multi_factor_entry_exit] {symbol} 缺失入场条件: {missing_entry_conditions}")
        # 出场判定同理
        exit_trend = None
        if len(df) >= 2 and 'EMA10' in df.columns and not df['EMA10'].isnull().all():
            if not np.isnan(df.iloc[-1]['close']) and not np.isnan(df.iloc[-2]['close']) and not np.isnan(df.iloc[-1]['EMA10']) and not np.isnan(df.iloc[-2]['EMA10']):
                exit_trend = df.iloc[-1]['close'] < df.iloc[-1]['EMA10'] and df.iloc[-2]['close'] < df.iloc[-2]['EMA10']
        exit_vol = None
        if 'volume' in df.columns and 'main_fund' in df.columns and not df['volume'].isnull().all() and not df['main_fund'].isnull().all():
            vol20 = df['volume'].tail(20).mean()
            last2_fund = df['main_fund'].tail(2)
            if not np.isnan(df.iloc[-1]['volume']) and not np.isnan(vol20) and all(~last2_fund.isnull()):
                exit_vol = df.iloc[-1]['volume'] < vol20 and all(last2_fund < 0)
        exit_conditions = {
            'exit_trend': exit_trend,
            'exit_vol': exit_vol
        }
        missing_exit_conditions = [k for k, v in exit_conditions.items() if v is None]
        exit_hit = any(v for v in exit_conditions.values() if v is not None)
        if missing_exit_conditions:
            logger.info(f"[multi_factor_entry_exit] {symbol} 缺失出场条件: {missing_exit_conditions}")
        # 汇总
        result['is_entry'] = bool(entry_hit)
        result['is_exit'] = bool(exit_hit)
        reason = []
        if entry_hit:
            reason.append('入场条件全部满足')
        else:
            reason.append('入场条件未全部满足')
        if exit_hit:
            reason.append('出场条件满足')
        result['reason'] = '；'.join(reason)
        result['detail'] = {
            '周线EMA5': float(df_week.iloc[-1]['EMA5']) if df_week is not None and not df_week.empty else None,
            '周线EMA20': float(df_week.iloc[-1]['EMA20']) if df_week is not None and not df_week.empty else None,
            '日线收盘': float(df.iloc[-1]['close']),
            '布林带中轨': float(df.iloc[-1]['MA20']),
            'BBwidth': float(df.iloc[-1]['BBwidth']),
            'BBwidth均值': float(bbwidth_mean) if 'bbwidth_mean' in locals() else None,
            '当日成交量': float(df.iloc[-1]['volume']) if 'volume' in df.columns else None,
            '5日均量': float(vol5) if 'vol5' in locals() else None,
            '量比3日': list(df['volume_ratio'].tail(3)) if 'volume_ratio' in df.columns else None,
            '主力资金3日': list(df['main_fund'].tail(3)) if 'main_fund' in df.columns else None,
            '北向资金周增': float(week_delta) if week_delta is not None else None,
            '换手率': float(df.iloc[-1]['turnover_rate']) if 'turnover_rate' in df.columns else None,
            '换手率分位区间': f"{p30:.2f}~{p70:.2f}" if 'p30' in locals() and 'p70' in locals() else None,
            '趋势破坏': exit_trend,
            '量能衰竭': exit_vol,
            'missing_entry_conditions': missing_entry_conditions,
            'missing_exit_conditions': missing_exit_conditions
        }
        # --- 新增：递归处理NaN/null ---
        import math
        import numpy as np
        def clean_nan(obj):
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(v) for v in obj]
            elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            elif isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, (np.bool_,)):
                return bool(obj)
            elif obj is None:
                return None
            else:
                return obj
        result['detail'] = clean_nan(result['detail'])
        # ---
    except Exception as e:
        import traceback
        result['reason'] = f'分析异常: {e}\n{traceback.format_exc()}'
    return result

def get_hk_minute_data(symbol, quote_ctx):
    """
    获取港股分时数据，返回 [{time, price, volume}]
    """
    from futu import SubType, RET_OK
    stock_code = symbol.split('.')[0]
    futu_symbol = f'HK.{stock_code}'
    # 先订阅分时数据
    ret_sub, err_message = quote_ctx.subscribe([futu_symbol], [SubType.RT_DATA], subscribe_push=False)
    if ret_sub != RET_OK:
        return []
    ret, df = quote_ctx.get_rt_data(futu_symbol)
    if ret != RET_OK or df is None or df.empty:
        return []
    # 只取今天的数据
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    data = []
    for _, row in df.iterrows():
        if str(row['time']).startswith(today):
            data.append({
                'time': row['time'],
                'price': float(row['cur_price']),
                'volume': float(row['volume'])
            })
    return data

def analyze_fundamental(symbol):
    """
    综合当前行情和历史财务数据，调用DEEPSEEK分析股票基本面，输出专业分析、观点、理由、操作建议和未来预测。
    返回 dict: { 'summary': ..., 'viewpoints': ..., 'reasons': ..., 'advice': ..., 'forecast': ... }
    """
    import requests
    import json
    import os
    # 1. 获取当前行情
    try:
        from app import get_stock_data, get_stock_financials
        # 行情数据
        market_data = get_stock_data(symbol, as_dict=True)
        # 财务数据
        financials = get_stock_financials(symbol)
        if hasattr(financials, 'to_dict'):
            financials_data = financials.fillna('').to_dict(orient='records')
        else:
            financials_data = []
    except Exception as e:
        return {'error': f'获取行情或财务数据失败: {e}'}

    # 2. 构造 prompt
    prompt = f"""
你是一名资深股票分析师，请结合以下股票的最新行情数据和历史财务数据，全面分析其基本面，输出：
1. 基本面总体评价（简明扼要）
2. 具体的分析观点（不少于3条，需有数据支撑）
3. 每条观点的详细分析理由（结合财务和行情数据）
4. 操作建议（如买入/观望/减持，并说明理由）
5. 对未来1-2年业绩和股价的合理预测（结合行业、财务、估值等）
6. 估值判断：请根据市盈率（PE）、市净率（PB）、历史估值区间、行业对比等，判断当前股票的估值水平，分为"严重高估、高估、正常、低估、严重低估"五档，并给出具体理由。

【最新行情数据】
{json.dumps(market_data, ensure_ascii=False, indent=2)}

【历史财务数据（每行为一个报告期）】
{json.dumps(financials_data, ensure_ascii=False, indent=2)}

请用结构化JSON格式输出，字段包括：summary, viewpoints, reasons, advice, forecast, valuation。
特别要求：valuation 字段必须为非空字符串，且只能为"严重高估、高估、正常、低估、严重低估"五档之一，不允许为空或缺失，否则视为不合格答案。
    """.strip()

    # 3. 调用DEEPSEEK
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {os.getenv("DEEPSEEK_API_KEY")}'
    }
    messages = [
        {'role': 'system', 'content': '你是一名专业的股票基本面分析师，擅长结合财务和行情数据给出专业判断。'},
        {'role': 'user', 'content': prompt}
    ]
    # 日志打印DEEPSEEK入参
    logger.info(f"DEEPSEEK Fundamental Input - symbol: {symbol}\nMessages: {json.dumps(messages, ensure_ascii=False, indent=2)}")
    try:
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json={
                'model': 'deepseek-chat',
                'messages': messages,
                'temperature': 0.5,
                'max_tokens': 1200
            }
        )
        # 日志打印DEEPSEEK出参
        logger.info(f"DEEPSEEK Fundamental Output - symbol: {symbol}\nStatus: {response.status_code}\nResponse: {response.text}")
        if response.status_code != 200:
            return {'error': f'DEEPSEEK API 调用失败: {response.text}'}
        result = response.json()
        content = result['choices'][0]['message']['content']
        # 尝试解析JSON
        try:
            # 兼容有无markdown围栏
            if content.startswith('```json'):
                content = content[7:-3].strip()
            content = content.replace('```', '').strip()
            data = json.loads(content)
        except Exception:
            data = {'raw': content}
        return data
    except Exception as e:
        logger.error(f"DEEPSEEK Fundamental Exception - symbol: {symbol}, error: {e}")
        return {'error': f'DEEPSEEK分析失败: {e}'}

def analyze_undervalued_stock(symbol):
    """
    低估股票策略：调用基本面分析，筛选估值为"低估"或"严重低估"的股票
    返回 dict: { 'is_undervalued': bool, 'valuation': str, 'reason': str, 'fundamental': ... }
    """
    try:
        result = analyze_fundamental(symbol)
        # 兼容不同返回结构
        valuation = ''
        if isinstance(result, dict):
            if 'valuation' in result:
                # 结构化返回
                if isinstance(result['valuation'], dict):
                    valuation = result['valuation'].get('level', '') or result['valuation'].get('估值判断', '')
                elif isinstance(result['valuation'], str):
                    valuation = result['valuation']
            elif '估值判断' in result:
                valuation = result['估值判断']
        # 判断是否低估
        is_undervalued = any(x in str(valuation) for x in ['低估', '严重低估'])
        reason = f"估值判断: {valuation}"
        return {
            'is_undervalued': is_undervalued,
            'valuation': valuation,
            'reason': reason,
            'fundamental': result
        }
    except Exception as e:
        return {
            'is_undervalued': False,
            'valuation': '',
            'reason': f'基本面分析异常: {e}',
            'fundamental': {}
        }

def analyze_active_smallmidcap_stock(symbol):
    """
    判断是否为中小盘活跃股：
    - 总市值大于100亿小于等于200亿
    - 收盘价<=20
    - 换手率>5%且<=15%
    - 量比>1
    - 今日涨跌幅>3%小于等于5%
    返回 dict: {is_active: bool, reason: str, detail: dict}
    """
    try:
        from app import get_stock_data
        data = get_stock_data(symbol, as_dict=True)
        if not data or 'error' in data:
            return {'is_active': False, 'reason': '未获取到行情数据', 'detail': data}
        total_mv = data.get('total_market_val')
        close = data.get('current_price')
        turnover_rate = data.get('turnover_rate')
        volume_ratio = data.get('volume_ratio')
        pre_close = data.get('pre_close')
        # 计算涨跌幅
        pct_chg = None
        if close is not None and pre_close not in (None, 0):
            pct_chg = (close - pre_close) / pre_close * 100
        # 条件判断
        cond_mv = total_mv is not None and 100 <= total_mv/1e8 <= 200
        cond_close = close is not None and close <= 20
        cond_turnover = turnover_rate is not None and turnover_rate > 5 and turnover_rate <= 15
        cond_volume_ratio = volume_ratio is not None and volume_ratio > 1
        cond_pct = pct_chg is not None and pct_chg > 3 and pct_chg <= 5
        is_active = all([cond_mv, cond_close, cond_turnover, cond_volume_ratio, cond_pct])
        reason = []
        if not cond_mv:
            reason.append('总市值不在100-200亿之间')
        if not cond_close:
            reason.append('收盘价大于20')
        if not cond_turnover:
            reason.append('换手率不在5%-15%之间')
        if not cond_volume_ratio:
            reason.append('量比不大于1')
        if not cond_pct:
            reason.append('涨跌幅不在3%-5%之间')
        if is_active:
            reason = ['满足全部条件']
        return {
            'is_active': is_active,
            'reason': '；'.join(reason),
            'detail': {
                '总市值(元)': total_mv,
                '收盘价': close,
                '换手率(%)': turnover_rate,
                '量比': volume_ratio,
                '涨跌幅(%)': pct_chg
            }
        }
    except Exception as e:
        import traceback
        return {'is_active': False, 'reason': f'分析异常: {e}\n{traceback.format_exc()}', 'detail': {}}

def smart_watchlist_monitor(symbols):
    """
    智能盯盘：对股票列表进行行情、分时、K线、资金流分析，结合TA-Lib和已有分析逻辑，给出异动信号。
    入参：symbols - 股票代码列表
    返回：[{stock, name, time, signal}]
    """
    print(f"[DEBUG] pd id in smart_watchlist_monitor: {id(pd)}")
    import time as pytime
    from app import get_stock_data, get_capital_flow_data
    import json
    import threading
    import os
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[smart_watchlist_monitor] 收到symbols: {symbols}，共{len(symbols)}只")
    results = []
    processed_symbols = []
    for idx, symbol in enumerate(symbols):
        logger.info(f"[smart_watchlist_monitor] 开始处理({idx+1}/{len(symbols)}): {symbol}")
        try:
            # 1. 快照/行情
            snapshot = None
            if symbol.endswith('.US'):
                snapshot = get_us_stock_snapshot(symbol)
            else:
                snapshot = get_stock_data(symbol, as_dict=True)
            
            if not snapshot or 'error' in snapshot:
                logger.error(f"[smart_watchlist_monitor] {symbol} snapshot error: {snapshot.get('error') if snapshot else 'No data'}")
                results.append({
                    'stock': symbol,
                    'name': symbol,
                    'time': pytime.strftime('%Y-%m-%d %H:%M:%S'),
                    'signal': f"获取行情失败: {snapshot.get('error') if snapshot else 'No data'}"
                })
                continue
            
            logger.info(f"[smart_watchlist_monitor] {symbol} snapshot: {snapshot}")
            name = snapshot.get('name', symbol)
            now_time = snapshot.get('update_time') or pytime.strftime('%Y-%m-%d %H:%M:%S')
            # 2. 历史K线（100日）
            end = pytime.strftime('%Y-%m-%d')
            start = (pytime.time() - 86400*120)
            start_str = pytime.strftime('%Y-%m-%d', pytime.localtime(start))
            kline = None
            try:
                kline = quant_get_stock_kline(symbol, start_str, end)
                logger.info(f"[smart_watchlist_monitor] {symbol} kline rows: {0 if kline is None else len(kline)}")
            except Exception as e:
                logger.warning(f"[smart_watchlist_monitor] {symbol} kline error: {e}")
                kline = None
            # 3. 资金流
            capital_flow = get_capital_flow_data(symbol)
            # logger.info(f"[smart_watchlist_monitor] {symbol} capital_flow: {capital_flow}")
            # 增加每次资金接口调用间隔0.3秒
            pytime.sleep(0.3)
            # 4. 技术指标（EMA等）
            signal = ''
            signal_type = ''
            value = None
            signals = []
            # --- 涨速/跌速异动 ---
            try:
                minute_df = None
                if symbol.endswith('.SH') or symbol.endswith('.SZ'):
                    stock_code = symbol.split('.')[0]
                    import akshare as ak
                    minute_df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1')
                    if not minute_df.empty:
                        minute_df = minute_df.rename(columns={'时间': 'time', '收盘': 'price'})
                elif symbol.endswith('.HK'):
                    from app import get_hk_minute_data, quote_ctx
                    minute_data = get_hk_minute_data(symbol, quote_ctx)
                    
                    if minute_data:
                        minute_df = pd.DataFrame(minute_data)
                if (minute_df is None or minute_df.empty or len(minute_df) < 3):
                    try:
                        from futu import OpenQuoteContext, KLType, RET_OK
                        market, code = symbol.split('.')
                        futu_code = f"{market}.{code.zfill(5) if market == 'HK' and code.isdigit() else code}"
                        with OpenQuoteContext(host='127.0.0.1', port=11111) as ctx:
                            ret, df, _ = ctx.request_history_kline(futu_code, ktype=KLType.K_1M, max_count=3)
                            if ret == RET_OK and df is not None and not df.empty and len(df) >= 3:
                                df = df.sort_values('time_key')
                                minute_df = df.rename(columns={'close': 'price', 'time_key': 'time'})
                    except Exception:
                        pass
                if minute_df is not None and not minute_df.empty and len(minute_df) >= 3:
                    last3 = minute_df.tail(3)
                    try:
                        p0 = float(last3.iloc[0]['price'])
                        p2 = float(last3.iloc[-1]['price'])
                        if p0 != 0:
                            pct3 = (p2 - p0) / p0 * 100
                            if pct3 > 1:
                                signals.append({'signal': f'涨速异动（3min+{pct3:.2f}%）', 'signal_type': '涨速异动', 'value': round(pct3, 2)})
                            elif pct3 < -1:
                                signals.append({'signal': f'跌速异动（3min{pct3:.2f}%）', 'signal_type': '跌速异动', 'value': round(pct3, 2)})
                    except Exception:
                        pass
            except Exception:
                pass
            # --- 分时MACD/RSI信号 ---
            if minute_df is not None and not minute_df.empty and len(minute_df) > 30:
                try:
                    import talib
                    close_min = minute_df['price'].astype(float).values
                    dif_min, dea_min, _ = talib.MACD(close_min, fastperiod=12, slowperiod=26, signalperiod=9)
                    rsi_min = talib.RSI(close_min, timeperiod=14)
                    min_anomaly = []
                    if len(dif_min) >= 2 and pd.notna(dif_min[-1]) and pd.notna(dif_min[-2]) and pd.notna(dea_min[-1]) and pd.notna(dea_min[-2]):
                        if dif_min[-2] < dea_min[-2] and dif_min[-1] > dea_min[-1]:
                            min_anomaly.append(f"MACD金叉(DIF:{dif_min[-1]:.2f})")
                        elif dif_min[-2] > dea_min[-2] and dif_min[-1] < dea_min[-1]:
                            min_anomaly.append(f"MACD死叉(DIF:{dif_min[-1]:.2f})")
                    if len(rsi_min) >= 2 and pd.notna(rsi_min[-1]) and pd.notna(rsi_min[-2]):
                        if rsi_min[-2] < 70 and rsi_min[-1] > 70:
                            min_anomaly.append(f"RSI超买(RSI:{rsi_min[-1]:.1f})")
                        elif rsi_min[-2] > 30 and rsi_min[-1] < 30:
                            min_anomaly.append(f"RSI超卖(RSI:{rsi_min[-1]:.1f})")
                    if min_anomaly:
                        signals.append({'signal': f"分时异动（{'，'.join(min_anomaly)}）", 'signal_type': '分时异动', 'value': None})
                except Exception as e:
                    logger.warning(f"[smart_watchlist_monitor] {symbol} 分时MACD/RSI计算异常: {e}")
            # --- 日K MACD/RSI/EMA/涨跌幅/资金流信号 ---
            if kline is not None and not kline.empty:
                import talib
                # TA-Lib需要float64 (double)类型的输入数组
                close = kline['close'].values.astype(np.float64)
                high = kline['high'].values.astype(np.float64) if 'high' in kline.columns else None
                low = kline['low'].values.astype(np.float64) if 'low' in kline.columns else None
                volume = kline['volume'].values.astype(np.float64) if 'volume' in kline.columns else None
                
                ema5 = talib.EMA(close, timeperiod=5)
                ema10 = talib.EMA(close, timeperiod=10)
                ema20 = talib.EMA(close, timeperiod=20)
                ema60 = talib.EMA(close, timeperiod=60)
                kline['EMA5'] = ema5
                kline['EMA10'] = ema10
                kline['EMA20'] = ema20
                kline['EMA60'] = ema60
                dif, dea, macdhist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
                kline['DIF'] = dif
                kline['DEA'] = dea
                rsi = talib.RSI(close, timeperiod=14)
                kline['RSI'] = rsi
                if len(kline) >= 2:
                    if kline.iloc[-2]['EMA5'] < kline.iloc[-2]['EMA20'] and kline.iloc[-1]['EMA5'] > kline.iloc[-1]['EMA20']:
                        signals.append({'signal': '短线金叉异动（EMA5上穿EMA20）', 'signal_type': '短线金叉异动', 'value': None})
                    elif kline.iloc[-2]['EMA5'] > kline.iloc[-2]['EMA20'] and kline.iloc[-1]['EMA5'] < kline.iloc[-1]['EMA20']:
                        signals.append({'signal': '短线死叉异动（EMA5下穿EMA20）', 'signal_type': '短线死叉异动', 'value': None})
                    if pd.notna(kline.iloc[-1]['DIF']) and pd.notna(kline.iloc[-2]['DIF']):
                        if kline.iloc[-2]['DIF'] < kline.iloc[-2]['DEA'] and kline.iloc[-1]['DIF'] > kline.iloc[-1]['DEA']:
                            signals.append({'signal': f"日K MACD金叉（DIF:{kline.iloc[-1]['DIF']:.2f}）", 'signal_type': '日K MACD金叉', 'value': round(kline.iloc[-1]['DIF'], 2)})
                        elif kline.iloc[-2]['DIF'] > kline.iloc[-2]['DEA'] and kline.iloc[-1]['DIF'] < kline.iloc[-1]['DEA']:
                            signals.append({'signal': f"日K MACD死叉（DIF:{kline.iloc[-1]['DIF']:.2f}）", 'signal_type': '日K MACD死叉', 'value': round(kline.iloc[-1]['DIF'], 2)})
                    if pd.notna(kline.iloc[-1]['RSI']) and pd.notna(kline.iloc[-2]['RSI']):
                        if kline.iloc[-2]['RSI'] < 70 and kline.iloc[-1]['RSI'] > 70:
                            signals.append({'signal': f"日K RSI超买（RSI:{kline.iloc[-1]['RSI']:.1f}）", 'signal_type': '日K RSI超买', 'value': round(kline.iloc[-1]['RSI'], 1)})
                        elif kline.iloc[-2]['RSI'] > 30 and kline.iloc[-1]['RSI'] < 30:
                            signals.append({'signal': f"日K RSI超卖（RSI:{kline.iloc[-1]['RSI']:.1f}）", 'signal_type': '日K RSI超卖', 'value': round(kline.iloc[-1]['RSI'], 1)})
                if snapshot.get('pre_close') and snapshot.get('current_price'):
                    pct = (snapshot['current_price'] - snapshot['pre_close']) / snapshot['pre_close'] * 100
                    if abs(pct) > 3:
                        signals.append({'signal': f'涨跌幅异动（{pct:.2f}%）', 'signal_type': '涨跌幅异动', 'value': round(pct, 2)})
                if capital_flow and 'historical' in capital_flow and len(capital_flow['historical']) >= 2:
                    last = capital_flow['historical'][-1]
                    prev = capital_flow['historical'][-2]
                    avg_turnover = 0
                    if 'turnover' in snapshot and snapshot['turnover']:
                        avg_turnover = float(snapshot['turnover']) / 5 if snapshot.get('turnover') else 0
                    else:
                        turnovers = [x.get('turnover') for x in capital_flow['historical'][-6:-1] if x.get('turnover')]
                        if turnovers:
                            avg_turnover = sum(turnovers) / len(turnovers)
                    min_pct, max_pct = 0.01, 0.05
                    if avg_turnover <= 1e7:
                        threshold = avg_turnover * min_pct
                    elif avg_turnover >= 1e8:
                        threshold = avg_turnover * max_pct
                    else:
                        pct = min_pct + (max_pct - min_pct) * (avg_turnover - 1e7) / (1e8 - 1e7)
                        threshold = avg_turnover * pct
                    threshold = max(threshold, 10000)
                    in_flow_wan = last['in_flow'] / 10000 if last['in_flow'] is not None else 0
                    logger.info(f"[smart_monitor][{symbol}] avg_turnover={avg_turnover:.2f}, min_pct={min_pct}, max_pct={max_pct}, threshold={threshold:.2f}, last_in_flow={last['in_flow']}, prev_in_flow={prev['in_flow']}, in_flow_wan={in_flow_wan:.2f}")
                    if last['in_flow'] > threshold and prev['in_flow'] < threshold * 0.2:
                        signals.append({'signal': f"主力资金大幅流入（{in_flow_wan:.2f} 万元，阈值{threshold/10000:.2f}万）", 'signal_type': '主力资金大幅流入', 'value': round(in_flow_wan, 2)})
                    elif last['in_flow'] < -threshold and prev['in_flow'] > -threshold * 0.2:
                        signals.append({'signal': f"主力资金大幅流出（{in_flow_wan:.2f} 万元，阈值{threshold/10000:.2f}万）", 'signal_type': '主力资金大幅流出', 'value': round(in_flow_wan, 2)})
                # OBV
                if volume is not None:
                    obv = talib.OBV(close, volume)
                    if len(obv) >= 2 and pd.notna(obv[-1]):
                        # OBV创新高/低 辅助说明
                        price_pos_desc = ''
                        kdj_bottom_div = False
                        if len(close) >= 20:
                            recent_high = np.nanmax(close[-60:]) if len(close) >= 60 else np.nanmax(close)
                            recent_low = np.nanmin(close[-60:]) if len(close) >= 60 else np.nanmin(close)
                            cur_price = close[-1]
                            # 计算KDJ
                            try:
                                low_arr = kline['low'].values.astype(np.float64)
                                high_arr = kline['high'].values.astype(np.float64)
                                rsv = (close[-9:] - np.minimum.reduce([low_arr[-9:], close[-9:]])) / (np.maximum.reduce([high_arr[-9:], close[-9:]]) - np.minimum.reduce([low_arr[-9:], close[-9:]]) + 1e-9) * 100
                                K = np.zeros_like(rsv)
                                D = np.zeros_like(rsv)
                                J = np.zeros_like(rsv)
                                K[0] = 50
                                D[0] = 50
                                for i in range(1, len(rsv)):
                                    K[i] = 2/3 * K[i-1] + 1/3 * rsv[i]
                                    D[i] = 2/3 * D[i-1] + 1/3 * K[i]
                                    J[i] = 3 * K[i] - 2 * D[i]
                                # 判断底背离：价格创新低但J未创新低
                                price_new_low = np.isclose(cur_price, recent_low, atol=1e-6)
                                j_new_low = np.isclose(J[-1], np.nanmin(J), atol=1e-6)
                                if price_new_low and not j_new_low:
                                    kdj_bottom_div = True
                            except Exception:
                                pass
                            if kdj_bottom_div:
                                price_pos_desc = 'KDJ底背离'
                            elif np.isclose(cur_price, recent_high, atol=1e-6):
                                price_pos_desc = '价格新高'
                            elif np.isclose(cur_price, recent_low, atol=1e-6):
                                price_pos_desc = '价格底部'
                            else:
                                price_pos_desc = '价格未新高'
                        if obv[-1] == obv.max():
                            desc = f'OBV创新高'
                            if price_pos_desc:
                                desc += f'（{price_pos_desc}）'
                            signals.append({'signal': desc, 'signal_type': 'OBV创新高', 'value': round(obv[-1], 2)})
                        elif obv[-1] == obv.min():
                            signals.append({'signal': f'OBV创新低', 'signal_type': 'OBV创新低', 'value': round(obv[-1], 2)})
            logger.info(f"[smart_watchlist_monitor] {symbol} signals: {signals}")
            # 新增：每次检测到实际异动信号时打印详细内容
            # 按优先级排序：价格异动 > 技术指标类 > 其他
            def signal_priority(sig):
                price_keywords = ['涨跌幅异动', '涨速异动', '跌速异动']
                tech_keywords = ['分时异动', 'MACD', 'RSI', 'KDJ', 'OBV', 'CCI', 'WR', 'SAR', 'ATR', '金叉', '死叉', '超买', '超卖', '底背离', '顶背离']
                s = sig.get('signal', '')
                if any(k in s for k in price_keywords):
                    return 0
                if any(k in s for k in tech_keywords):
                    return 1
                return 2
            signals = sorted(signals, key=signal_priority)
            for sig in signals:
                # 缩短主力资金大幅流入/流出为资金大幅流入/流出
                short_signal_type = sig['signal_type']
                short_signal = sig['signal']
                if short_signal_type in ['主力资金大幅流入', '主力资金大幅流出']:
                    short_signal_type = short_signal_type.replace('主力资金', '资金')
                if isinstance(short_signal, str) and short_signal.startswith('主力资金大幅流'):
                    short_signal = short_signal.replace('主力资金', '资金', 1)
                logger.info(f"[smart_watchlist_monitor][ANOMALY] symbol={symbol}, name={name}, time={now_time}, signal={short_signal}, signal_type={short_signal_type}, value={sig.get('value')}")
                results.append({
                    'stock': symbol,
                    'name': name,
                    'time': now_time,
                    'signal': short_signal,
                    'signal_type': short_signal_type,
                    'value': sig.get('value')
                })
            # --- 新增：存储异动信号到文件 ---
            # 只存储有实际异动信号的结果
            filtered_results = [r for r in results if r.get('signal') and r['signal'] != '无明显异动']
            monitor_signal_file = os.path.join(os.path.dirname(__file__), 'smart_monitor_signals.json')
            monitor_signal_lock = threading.Lock()
            try:
                with monitor_signal_lock:
                    # 读取原有数据，格式为 {stock: [信号, ...], ...}
                    if os.path.exists(monitor_signal_file):
                        with open(monitor_signal_file, 'r', encoding='utf-8') as f:
                            try:
                                all_data = json.load(f)
                            except Exception:
                                all_data = {}
                    else:
                        all_data = {}
                    # 按股票分组本次信号
                    new_by_stock = defaultdict(list)
                    for r in filtered_results:
                        # 写入 signal, signal_type, value
                        if r.get('signal') and r.get('signal_type'):
                            new_by_stock[r['stock']].append({
                                'stock': r['stock'],
                                'name': r['name'],
                                'time': r['time'],
                                'signal': r['signal'],
                                'signal_type': r['signal_type'],
                                'value': r.get('value')
                            })
                    # 合并逻辑
                    N = 100  # 每个股票最多保留N条
                    for stock, new_signals in new_by_stock.items():
                        old_list = all_data.get(stock, [])
                        # 先把旧的信号按时间倒序
                        old_list = sorted(old_list, key=lambda x: x.get('time', ''), reverse=True)
                        # 合并到新列表，连续同类型只保留最新
                        merged = []
                        for new in new_signals:
                            if merged and merged[0]['signal'] == new['signal']:
                                # 连续同类型，覆盖为最新
                                merged[0] = new
                            else:
                                merged.insert(0, new)
                        # 再加旧的（跳过已连续的同类型）
                        for item in old_list:
                            if merged and merged[-1]['signal'] == item['signal']:
                                continue
                            merged.append(item)
                        # --- 新增：一小时内signal_type相同的合并，只保留最新 ---
                        import datetime
                        grouped = defaultdict(list)
                        for ev in merged:
                            try:
                                dt = datetime.datetime.strptime(ev['time'], '%Y-%m-%d %H:%M:%S')
                                hour_key = dt.strftime('%Y-%m-%d %H')
                            except Exception:
                                hour_key = ev['time'][:13] if 'time' in ev and isinstance(ev['time'], str) else ''
                            key = (hour_key, ev.get('signal_type'))
                            grouped[key].append(ev)
                        merged_onehour = []
                        for key, evs in grouped.items():
                            # 只保留最新一条
                            evs_sorted = sorted(evs, key=lambda x: x.get('time', ''), reverse=True)
                            merged_onehour.append(evs_sorted[0])
                        # 按时间倒序，保留N条
                        merged_onehour = sorted(merged_onehour, key=lambda x: x.get('time', ''), reverse=True)[:N]
                        all_data[stock] = merged_onehour
                    # 写回文件，先写入临时文件再原子替换，防止异常清空
                    tmp_dir = os.path.dirname(monitor_signal_file)
                    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=tmp_dir, delete=False) as tf:
                        json.dump(all_data, tf, ensure_ascii=False, indent=2)
                        tempname = tf.name
                    os.replace(tempname, monitor_signal_file)
            except Exception as e:
                import traceback
                logger.error(f"[smart_watchlist_monitor] 存储异动信号异常: {e}\n{traceback.format_exc()}")
            # 不要在这里return
            processed_symbols.append(symbol)
        except Exception as e:
            import traceback
            logger.error(f"[smart_watchlist_monitor] {symbol} exception: {e}\n{traceback.format_exc()}")
            results.append({
                'stock': symbol,
                'name': symbol,
                'time': pytime.strftime('%Y-%m-%d %H:%M:%S'),
                'signal': f'盯盘异常: {e}'
            })
    logger.info(f"[smart_watchlist_monitor] 实际处理symbol列表: {processed_symbols}，共{len(processed_symbols)}只")
    logger.info(f"[smart_watchlist_monitor] 生成results条数: {len(results)}，示例: {results[:2]}")
    return all_data

# 新增：加载最新异动信号

def load_latest_smart_monitor_signals():
    import os
    import json
    import threading
    import logging
    logger = logging.getLogger(__name__)
    monitor_signal_file = os.path.join(os.path.dirname(__file__), 'smart_monitor_signals.json')
    monitor_signal_lock = threading.Lock()
    if not os.path.exists(monitor_signal_file):
        logger.warning('[load_latest_smart_monitor_signals] File does not exist: %s', monitor_signal_file)
        return []
    try:
        with monitor_signal_lock:
            with open(monitor_signal_file, 'r', encoding='utf-8') as f:
                try:
                    all_data = json.load(f)
                    logger.debug('[load_latest_smart_monitor_signals] Loaded data keys: %s', list(all_data.keys()) if isinstance(all_data, dict) else type(all_data))
                    if not all_data:
                        logger.info('[load_latest_smart_monitor_signals] all_data is empty')
                        return []
                    latest_key = sorted(all_data.keys())[-1]
                    logger.info('[load_latest_smart_monitor_signals] Returning data for latest_key: %s, count: %d', latest_key, len(all_data[latest_key]))
                    return all_data[latest_key]
                except Exception as e:
                    logger.error('[load_latest_smart_monitor_signals] Exception during json load or processing: %s', e, exc_info=True)
                    return []
    except Exception as e:
        logger.error('[load_latest_smart_monitor_signals] Outer exception: %s', e, exc_info=True)
        return []

# 新增：加载全部历史异动信号
def load_all_smart_monitor_signals():
    import os
    import json
    import threading
    monitor_signal_file = os.path.join(os.path.dirname(__file__), 'smart_monitor_signals.json')
    monitor_signal_lock = threading.Lock()
    if not os.path.exists(monitor_signal_file):
        return {}
    with monitor_signal_lock:
        with open(monitor_signal_file, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
                if not all_data:
                    return {}
                return all_data
            except Exception:
                return {}

def get_capital_distribution(symbol, host='127.0.0.1', port=11111):
    """
    查询个股资金分布（Futu/OpenD接口）。
    symbol: 股票代码，形如 '600519.SH', '00700.HK', 'AAPL.US'
    返回 pandas.DataFrame 或 dict
    """
    from futu import OpenQuoteContext, RET_OK
    # 解析市场和代码
    code_parts = symbol.split('.')
    if len(code_parts) != 2:
        raise ValueError('symbol格式错误，需如00700.HK')
    stock_code = code_parts[0]
    market = code_parts[1].upper()
    futu_code = f"{market}.{stock_code}"
    with OpenQuoteContext(host=host, port=port) as ctx:
        ret, data = ctx.get_capital_distribution(futu_code)
        if ret != RET_OK:
            raise RuntimeError(f"Futu get_capital_distribution失败: {data}")
        # 直接返回DataFrame，或可转dict
        return data

def get_us_stock_snapshot(symbol):
    """
    获取美股单只股票快照 (akshare)
    """
    try:
        stock_code = symbol.split('.')[0]
        df = pd.DataFrame()
        
        # 优先使用实时接口
        try:
            df = ak.stock_us_realtime(symbols=stock_code)
        except Exception as e:
            logger.warning(f"ak.stock_us_realtime an {symbol} fail: {e}")
            df = pd.DataFrame()

        # 如果实时接口失败或为空，尝试使用备用接口
        if df.empty:
            try:
                all_df = ak.stock_us_spot_em()
                if not all_df.empty:
                    df = all_df[all_df["代码"] == stock_code]
            except Exception as e:
                logger.warning(f"备用接口 ak.stock_us_spot_em an {symbol} fail: {e}")
        
        if df.empty:
            return {'error': f"未在akshare中找到美股 {symbol} 的行情数据"}

        stock_info = df.iloc[0].to_dict()
        
        # 字段名映射，以兼容现有结构
        return {
            'name': stock_info.get('名称', stock_info.get('name', stock_code)),
            'current_price': stock_info.get('最新价', stock_info.get('price')),
            'pre_close': stock_info.get('昨收', stock_info.get('close')),
            'open_price': stock_info.get('今开', stock_info.get('open')),
            'high_price': stock_info.get('最高', stock_info.get('high')),
            'low_price': stock_info.get('最低', stock_info.get('low')),
            'volume': stock_info.get('成交量', stock_info.get('volume')),
            'turnover': stock_info.get('成交额', stock_info.get('amount')),
            'update_time': stock_info.get('时间', stock_info.get('更新时间', pytime.strftime('%Y-%m-%d %H:%M:%S'))),
            'total_market_val': stock_info.get('总市值'),
            'turnover_rate': stock_info.get('换手率'),
        }
    except Exception as e:
        logger.error(f"获取美股 {symbol} 快照失败: {e}")
        return {'error': str(e)}
