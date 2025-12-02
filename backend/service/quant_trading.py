"""
重新实现的量化交易服务
基于DeepSeek的结构化诊断分析
"""

import logging
import json
import traceback
import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional

# 导入查询服务和数据服务
from .storage.query_service import query_service
from .storage.data_service import data_service

logger = logging.getLogger(__name__)

class StockDiagnosisService:
    """个股诊断服务"""
    
    def __init__(self):
        pass
        
    def get_individual_diagnosis(self, symbol: str) -> Dict[str, Any]:
        """
        获取个股诊断内容 - 按照1-4步逻辑实现
        1. 获取基础数据 2. 构建prompt 3. 请求DeepSeek 4. 构建结构化数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 结构化诊断数据
        """
        try:
            logger.info(f"=== 开始个股诊断: {symbol} ===")
            
            # 第1步：获取基础数据
            basic_data = self._get_basic_data(symbol)
            if not basic_data:
                logger.error(f"获取基础数据失败: {symbol}")
                return self._create_error_diagnosis(symbol, "无法获取基础数据")
            
            # 压缩基础数据
            basic_data = self._compress_basic_data(basic_data)
            
            logger.info(f"【基础数据】{symbol}: {json.dumps(basic_data, ensure_ascii=False, indent=2, default=str)}")
            
            # 第2步：基于数据构建prompt
            diagnosis_prompt = self._build_diagnosis_prompt(symbol, basic_data)
            prompt_tokens = len(diagnosis_prompt.encode('utf-8')) // 4  # 粗略估算token数量
            logger.info(f"【诊断Prompt】{symbol}: 输入token数量 ≈ {prompt_tokens}")
            logger.info(f"【诊断Prompt】{symbol}:\n{diagnosis_prompt}")
            
            # 第3步：请求DeepSeek获取诊断报告
            deepseek_response = self._call_deepseek_analysis(diagnosis_prompt, basic_data)
            if not deepseek_response:
                logger.error(f"DeepSeek API调用失败: {symbol}")
                return self._create_error_diagnosis(symbol, "DeepSeek API调用失败")
            
            #logger.info(f"【DeepSeek响应】{symbol}: {json.dumps(deepseek_response, ensure_ascii=False, indent=2, default=str)}")
            
            # 第4步：基于诊断报告构建结构化数据
            structured_data = self._parse_deepseek_response(symbol, basic_data, deepseek_response)
            
            # 存储诊断报告到文件（异常情况不存储）
            self._save_diagnosis_report(symbol, structured_data)
            
            logger.info(f"【最终结构化数据】{symbol}: {json.dumps(structured_data, ensure_ascii=False, indent=2, default=str)}")
            logger.info(f"=== 完成个股诊断: {symbol} ===")
            
            return structured_data
            
        except Exception as e:
            logger.error(f"个股诊断失败 {symbol}: {str(e)}", exc_info=True)
            # 异常情况不存储到文件
            return self._create_error_diagnosis(symbol, str(e))
    
    def _compress_basic_data(self, basic_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        压缩基础数据，减少数据量
        
        Args:
            basic_data: 原始基础数据
            
        Returns:
            Dict: 压缩后的基础数据
        """
        try:
            logger.info("【数据压缩】开始压缩基础数据...")
            
            # 1. 财务数据压缩：只保留最新的2条
            if 'financials' in basic_data and basic_data['financials']:
                original_count = len(basic_data['financials'])
                basic_data['financials'] = basic_data['financials'][:2]  # 只保留最新的2条（已按倒序排列）
                compressed_count = len(basic_data['financials'])
                logger.info(f"【数据压缩】财务数据：从{original_count}条压缩到{compressed_count}条")
            
            # 2. K线数据压缩：去除EMA10/EMA20/EMA26字段
            if 'kline_data' in basic_data and basic_data['kline_data']:
                original_count = len(basic_data['kline_data'])
                compressed_kline = []
                
                for item in basic_data['kline_data']:
                    if isinstance(item, dict):
                        # 创建新字典，排除EMA字段
                        compressed_item = {k: v for k, v in item.items() 
                                         if k not in ['EMA10', 'EMA20', 'EMA26', 'ema10', 'ema20', 'ema26']}
                        compressed_kline.append(compressed_item)
                    else:
                        compressed_kline.append(item)
                
                basic_data['kline_data'] = compressed_kline
                logger.info(f"【数据压缩】K线数据：从{original_count}条记录中移除EMA字段")
            
            # 2.1 15分钟K线数据压缩：限制数据量
            if 'min15_kline_data' in basic_data and basic_data['min15_kline_data']:
                original_count = len(basic_data['min15_kline_data'])
                # 限制最多30条15分钟K线数据（约7.5小时的交易数据）
                basic_data['min15_kline_data'] = basic_data['min15_kline_data'][-30:] if len(basic_data['min15_kline_data']) > 30 else basic_data['min15_kline_data']
                compressed_count = len(basic_data['min15_kline_data'])
                logger.info(f"【数据压缩】15分钟K线数据：从{original_count}条压缩到{compressed_count}条")
            
            # 2.2 周K线数据压缩：限制数据量
            if 'weekly_kline_data' in basic_data and basic_data['weekly_kline_data']:
                original_count = len(basic_data['weekly_kline_data'])
                # 限制最多25条周K线数据（约6个月的数据）
                basic_data['weekly_kline_data'] = basic_data['weekly_kline_data'][-25:] if len(basic_data['weekly_kline_data']) > 25 else basic_data['weekly_kline_data']
                compressed_count = len(basic_data['weekly_kline_data'])
                logger.info(f"【数据压缩】周K线数据：从{original_count}条压缩到{compressed_count}条")
            
            # 3. 资金流数据压缩
            if 'capital_flow' in basic_data and basic_data['capital_flow']:
                capital_flow = basic_data['capital_flow']
                
                # 处理historical数据：去掉out_flow/net_flow/main_out字段
                if 'historical' in capital_flow and capital_flow['historical']:
                    original_historical_count = len(capital_flow['historical'])
                    compressed_historical = []
                    
                    for item in capital_flow['historical']:
                        if isinstance(item, dict):
                            # 只保留需要的字段
                            compressed_item = {k: v for k, v in item.items() 
                                             if k not in ['out_flow', 'net_flow', 'main_out']}
                            compressed_historical.append(compressed_item)
                        else:
                            compressed_historical.append(item)
                    
                    capital_flow['historical'] = compressed_historical
                    logger.info(f"【数据压缩】资金流历史数据：从{original_historical_count}条记录中移除指定字段")
                
                # 处理intraday数据：智能压缩，保留关键内容
                if 'intraday' in capital_flow and capital_flow['intraday']:
                    original_intraday_count = len(capital_flow['intraday'])
                    
                    # 策略1: 时间窗口聚合压缩（每5分钟聚合一次）
                    compressed_intraday = self._compress_intraday_data(capital_flow['intraday'])
                    
                    # 策略2: 如果数据量仍然很大，使用采样压缩
                    if len(compressed_intraday) > 50:
                        # 保留开盘、收盘和关键时间点的数据
                        compressed_intraday = self._sample_intraday_data(compressed_intraday)
                    
                    capital_flow['intraday'] = compressed_intraday
                    compressed_count = len(compressed_intraday)
                    logger.info(f"【数据压缩】资金流当日数据：从{original_intraday_count}条压缩到{compressed_count}条，压缩率{(1-compressed_count/original_intraday_count)*100:.1f}%")
            
            # 4. 新闻数据压缩：限制长度（如果过长）
            if 'news_summary' in basic_data and basic_data['news_summary']:
                original_length = len(basic_data['news_summary'])
                if original_length > 2000:  # 限制新闻摘要长度
                    basic_data['news_summary'] = basic_data['news_summary'][:2000] + "..."
                    logger.info(f"【数据压缩】新闻数据：从{original_length}字符压缩到2000字符")
            
            logger.info("【数据压缩】基础数据压缩完成")
            return basic_data
            
        except Exception as e:
            logger.error(f"【数据压缩】压缩基础数据失败: {str(e)}")
            return basic_data  # 如果压缩失败，返回原始数据

    def _compress_intraday_data(self, intraday_data: list) -> list:
        """
        压缩日内资金数据 - 时间窗口聚合压缩
        
        Args:
            intraday_data: 原始日内资金数据列表
            
        Returns:
            list: 压缩后的日内资金数据
        """
        try:
            if not intraday_data:
                return []
            
            from datetime import datetime, timedelta
            import pandas as pd
            
            # 将数据转换为DataFrame便于处理
            df = pd.DataFrame(intraday_data)
            if df.empty:
                return intraday_data
            
            # 确保时间字段存在且格式正确
            if 'time' not in df.columns:
                return intraday_data
            
            # 转换时间格式
            try:
                df['time'] = pd.to_datetime(df['time'])
            except:
                # 如果时间格式有问题，返回原始数据
                return intraday_data[:30]  # 最多返回30条
            
            # 按5分钟时间窗口聚合
            df = df.sort_values('time')
            df['time_window'] = df['time'].dt.floor('5T')  # 5分钟窗口
            
            # 聚合计算
            aggregated = df.groupby('time_window').agg({
                'in_flow': 'sum',
                'super_in': 'sum',
                'big_in': 'sum',
                'mid_in': 'sum',
                'small_in': 'sum'
            }).reset_index()
            
            # 转换回字典格式
            compressed_data = []
            for _, row in aggregated.iterrows():
                compressed_data.append({
                    'time': row['time_window'].strftime('%Y-%m-%d %H:%M:%S'),
                    'in_flow': round(float(row['in_flow']), 2),
                    'super_in': round(float(row['super_in']), 2),
                    'big_in': round(float(row['big_in']), 2),
                    'mid_in': round(float(row['mid_in']), 2),
                    'small_in': round(float(row['small_in']), 2)
                })
            
            return compressed_data
            
        except Exception as e:
            logger.error(f"【数据压缩】日内资金数据聚合压缩失败: {str(e)}")
            # 失败时返回前30条数据
            return intraday_data[:30] if len(intraday_data) > 30 else intraday_data

    def _sample_intraday_data(self, intraday_data: list) -> list:
        """
        采样压缩日内资金数据 - 保留关键时间点
        
        Args:
            intraday_data: 日内资金数据列表
            
        Returns:
            list: 采样后的关键数据
        """
        try:
            if not intraday_data or len(intraday_data) <= 50:
                return intraday_data
            
            from datetime import datetime
            
            # 保留关键时间点的数据
            key_times = ['09:30', '09:45', '10:00', '10:30', '11:00', '11:30', 
                        '13:00', '13:30', '14:00', '14:30', '15:00']
            
            sampled_data = []
            
            # 首先保留关键时间点的数据
            for item in intraday_data:
                if isinstance(item, dict) and 'time' in item:
                    time_str = item['time']
                    # 提取时间部分
                    if isinstance(time_str, str) and len(time_str) >= 16:
                        time_part = time_str[11:16]  # 提取HH:MM格式
                        if time_part in key_times:
                            sampled_data.append(item)
            
            # 如果关键时间点数据不足，补充其他时间点
            if len(sampled_data) < 20:
                # 每30分钟采样一次
                step = max(1, len(intraday_data) // 20)
                for i in range(0, len(intraday_data), step):
                    if len(sampled_data) < 30:  # 最多保留30条
                        sampled_data.append(intraday_data[i])
            
            # 去重并保持时间顺序
            seen_times = set()
            unique_data = []
            for item in sampled_data:
                if isinstance(item, dict) and 'time' in item:
                    time_key = str(item['time'])
                    if time_key not in seen_times:
                        seen_times.add(time_key)
                        unique_data.append(item)
            
            # 按时间排序
            try:
                unique_data.sort(key=lambda x: x['time'])
            except:
                pass
            
            return unique_data[:30]  # 最多返回30条
            
        except Exception as e:
            logger.error(f"【数据压缩】日内资金数据采样压缩失败: {str(e)}")
            return intraday_data[:30] if len(intraday_data) > 30 else intraday_data

    def _get_basic_data(self, symbol: str) -> Dict[str, Any]:
        """获取股票基础数据，避免Flask上下文依赖"""
        try:
            import sys
            import os
            import json
            import requests
            import pandas as pd
            
            # 确保当前目录在路径中
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            # 使用独立的数据获取方法，避免Flask依赖
            try:
                # 获取行情数据 - 使用独立实现
                market_data = self._get_market_data_independent(symbol)
                kline_data = self._get_kline_data_independent(symbol)
                min15_kline_data = self._get_15min_kline_data_independent(symbol)
                weekly_kline_data = self._get_weekly_kline_data_independent(symbol)
                capital_flow_data = self._get_capital_flow_data_independent(symbol)
                news_data = self._get_news_data_independent(symbol)
                
            except Exception as e:
                logger.error(f"【数据获取】独立获取失败: {str(e)}")
                # 使用备用方法
                market_data = self._get_fallback_market_data(symbol)
                kline_data = []
                capital_flow_data = {}
                news_data = ""
            
            if not market_data:
                raise Exception("无法获取行情数据")
            
            # 获取财务数据
            financials = self._get_financial_data_independent(symbol)
            logger.info(f"【财务数据】financials内容: {financials}")
            if hasattr(financials, 'to_dict'):
                financials_data = financials.fillna('').to_dict(orient='records')
            else:
                financials_data = financials if isinstance(financials, list) else []
            logger.info(f"【财务数据】financials_data内容: {financials_data}")
            
            # 新闻数据已经在上一步获取
            news_text = news_data
            
            # 提取关键数据并格式化为4位小数
            def safe_round(value, default=0.0, decimals=4):
                """安全地格式化数字，处理None值"""
                try:
                    if value is None or value == '' or str(value).lower() == 'nan':
                        return round(float(default), decimals)
                    return round(float(value), decimals)
                except (ValueError, TypeError):
                    return round(float(default), decimals)
            
            current_price = safe_round(market_data.get('current_price'), 0.0)
            pe_ratio = safe_round(market_data.get('pe_ratio'), 0.0)
            pb_ratio = safe_round(market_data.get('pb_ratio'), 0.0)
            volume = int(market_data.get('volume', 0))
            change_rate = safe_round(market_data.get('change_rate'), 0.0)
            high_52w = safe_round(market_data.get('high_52w'), 0.0)
            low_52w = safe_round(market_data.get('low_52w'), 0.0)
            market_cap = safe_round(market_data.get('market_cap'), 0.0)
            name = str(market_data.get('name', symbol))
            industry = str(market_data.get('industry', '未知'))
            sector = str(market_data.get('sector', '未知'))
            
            # 处理K线数据，格式化数值
            kline_recent = []
            if kline_data and len(kline_data) >= 30:
                for item in kline_data[-30:]:
                    if isinstance(item, dict):
                        formatted_item = {}
                        for key, value in item.items():
                            if isinstance(value, (int, float)):
                                formatted_item[key] = round(float(value), 4)
                            else:
                                formatted_item[key] = value
                        kline_recent.append(formatted_item)
                    else:
                        kline_recent.append(item)
            
            # 处理15分钟K线数据
            min15_kline_recent = []
            if min15_kline_data and len(min15_kline_data) > 0:
                for item in min15_kline_data:
                    if isinstance(item, dict):
                        formatted_item = {}
                        for key, value in item.items():
                            if isinstance(value, (int, float)):
                                formatted_item[key] = round(float(value), 4)
                            else:
                                formatted_item[key] = value
                        min15_kline_recent.append(formatted_item)
                    else:
                        min15_kline_recent.append(item)
            
            # 处理周K线数据
            weekly_kline_recent = []
            if weekly_kline_data and len(weekly_kline_data) > 0:
                for item in weekly_kline_data:
                    if isinstance(item, dict):
                        formatted_item = {}
                        for key, value in item.items():
                            if isinstance(value, (int, float)):
                                formatted_item[key] = round(float(value), 4)
                            else:
                                formatted_item[key] = value
                        weekly_kline_recent.append(formatted_item)
                    else:
                        weekly_kline_recent.append(item)
            
            # 处理资金流向数据，格式化数值
            capital_analysis = {}
            if capital_flow_data:
                def format_capital_data(data_list):
                    if not isinstance(data_list, list):
                        return data_list
                    formatted_list = []
                    for item in data_list:
                        if isinstance(item, dict):
                            formatted_item = {}
                            for key, value in item.items():
                                if isinstance(value, (int, float)) and key != 'date' and 'time' not in str(key).lower():
                                    formatted_item[key] = round(float(value), 4)
                                else:
                                    formatted_item[key] = value
                            formatted_list.append(formatted_item)
                        else:
                            formatted_list.append(item)
                    return formatted_list
                
                capital_analysis = {
                    'historical': format_capital_data(capital_flow_data.get('historical', [])),
                    'intraday': format_capital_data(capital_flow_data.get('intraday', [])),
                    'distribution': format_capital_data(capital_flow_data.get('distribution', []))
                }
            
            # 格式化财务数据
            formatted_financials = []
            for item in financials_data:
                if isinstance(item, dict):
                    formatted_item = {}
                    for key, value in item.items():
                        if isinstance(value, (int, float)) and str(key).lower() not in ['date', '报告期', 'period']:
                            formatted_item[key] = round(float(value), 4)
                        else:
                            formatted_item[key] = value
                    formatted_financials.append(formatted_item)
                else:
                    formatted_financials.append(item)
            
            return {
                "symbol": str(symbol),
                "name": name,
                "current_price": current_price,
                "pe_ratio": pe_ratio,
                "pb_ratio": pb_ratio,
                "market_cap": market_cap,
                "volume": volume,
                "change_rate": change_rate,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "industry": industry,
                "sector": sector,
                "financials": formatted_financials,
                "kline_data": kline_recent,
                "min15_kline_data": min15_kline_recent,
                "weekly_kline_data": weekly_kline_recent,
                "capital_flow": capital_analysis,
                "news_summary": str(news_text)
            }
            
        except Exception as e:
            logger.error(f"【数据获取】获取基础数据失败 {symbol}: {str(e)}", exc_info=True)
            raise Exception(f"获取基础数据失败: {str(e)}")
    
    def _calculate_months_ago(self, financials: list) -> str:
        """计算最新财报距今的月份数"""
        try:
            import pandas as pd
            from datetime import datetime
            
            if not financials or not financials[0].get('报告期'):
                return '未知'
            
            report_date = pd.to_datetime(str(financials[0].get('报告期')))
            months_diff = (datetime.now() - report_date).days // 30
            return str(months_diff)
        except:
            return '未知'

    def _build_diagnosis_prompt(self, symbol: str, basic_data: Dict[str, Any]) -> str:
        """构建个股诊断prompt，优化财务数据权重和时效性影响"""
        
        # 处理K线数据为JSON格式，处理日期序列化问题
        def json_serial(obj):
            """JSON序列化辅助函数"""
            from datetime import date, datetime
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        kline_data = basic_data.get('kline_data', [])[-30:] if basic_data.get('kline_data') else []
        kline_json = json.dumps(kline_data, ensure_ascii=False, indent=2, default=json_serial) if kline_data else '无足够K线数据'
        
        min15_kline_data = basic_data.get('min15_kline_data', [])[-30:] if basic_data.get('min15_kline_data') else []
        min15_kline_json = json.dumps(min15_kline_data, ensure_ascii=False, indent=2, default=json_serial) if min15_kline_data else '无当日15分钟K线数据'
        
        weekly_kline_data = basic_data.get('weekly_kline_data', [])[-25:] if basic_data.get('weekly_kline_data') else []
        weekly_kline_json = json.dumps(weekly_kline_data, ensure_ascii=False, indent=2, default=json_serial) if weekly_kline_data else '无周K线数据'
        
        capital_data = basic_data.get('capital_flow', {})
        capital_json = json.dumps(capital_data, ensure_ascii=False, indent=2, default=json_serial) if capital_data else '无资金流向数据'
        
        return f"""
        你是一名资深金融分析师，请结合以下个股行情走势、技术指标、财务面、资金面和最新资讯，为投资者生成一份全面的诊断报告：

        【基本信息】
        股票代码：{symbol}
        股票名称：{basic_data.get('name', symbol)}
        当前价格：{basic_data.get('current_price', 0):.2f}
        市盈率：{basic_data.get('pe_ratio', 0):.2f}
        市净率：{basic_data.get('pb_ratio', 0):.2f}
        市值：{basic_data.get('market_cap', 0):,.0f}
        成交量：{basic_data.get('volume', 0):,}
        涨跌幅：{basic_data.get('change_rate', 0):.2f}%
        52周最高：{basic_data.get('high_52w', 0):.2f}
        52周最低：{basic_data.get('low_52w', 0):.2f}
        行业：{basic_data.get('industry', '未知')}
        板块：{basic_data.get('sector', '未知')}

        【行情与技术指标】
        近30日K线数据（JSON）：
        {kline_json}

        【当日15分钟K线数据】
        当日15分钟K线数据（JSON）：
        {min15_kline_json}

        【25周K线数据】
        25周K线数据（JSON）：
        {weekly_kline_json}

        【资金面数据】
        资金流向数据（JSON）：
        {capital_json}

        【新闻资讯】
        {basic_data.get('news_summary', '暂无相关新闻')}

        【财务数据】
        历史财务数据：{basic_data.get('financials', [])}
        
        今天日期：{datetime.now().strftime('%Y-%m-%d')}
        最新财报时间：{basic_data.get('financials', [{}])[0].get('报告期', '未知') if basic_data.get('financials') else '无数据'}
        财报距今：{self._calculate_months_ago(basic_data.get('financials', []))}个月

        【财务数据时效性权重规则】
        在评估基本面时，请严格遵循以下时效性权重规则：
        - 最新财报（3个月内）：权重100%，正常参与基本面评分
        - 上一期财报（3-6个月）：权重70%，评分×0.7
        - 上上期财报（6-24个月）：权重30%，评分×0.3  
        - 更早财报：权重0%，不计入基本面评分

        【评分权重指导原则】
        综合评分时，请按以下权重分配考虑各因素：
        - 技术面：35%（K线走势、技术指标、短期趋势）
        - 资金面：30%（资金流向、主力动向、成交量）
        - 估值面：20%（PE、PB、相对估值水平）
        - 基本面：15%（财务数据，需按上述时效性权重调整）

        【分析要求】
        请基于以上数据，进行以下结构化分析并返回结果：

        1. **综合评分** (0-100分)：基于加权因素的综合评估
        2. **基本面评分** (0-100分)：基于时效性加权的财务数据分析
        3. **技术面评分** (0-100分)：基于K线走势和技术指标
        4. **资金面评分** (0-100分)：基于资金流向和主力动向
        5. **估值评分** (0-100分)：基于PE、PB等估值指标
        6. **风险评估** (low/medium/high)：综合风险等级
        7. **投资建议** (buy/hold/sell)：明确的投资建议
        8. **目标价位** (具体数值)：预期目标价格
        9. **止损价位** (具体数值)：建议止损价格
        10. **支撑位** (具体数值)：技术支撑位
        11. **压力位** (具体数值)：技术压力位
        12. **买入价** (具体数值)：建议买入价格
        13. **卖出价** (具体数值)：建议卖出价格
        14. **投资理由** (详细分析)：包含技术面、资金面、估值、财务数据的综合分析
        15. **关键指标** (影响决策的核心指标)：列出3-5个最重要的决策指标
        16. **风险提示** (主要风险点)：列出主要风险因素

        【重要提醒】
        1. 财务数据对分值的影响应随时间递减，财报期越久影响越小
        2. 整体降低财报对诊断的影响权重，技术面和资金面应占主导地位,估值和基本面逐级下降
        3. 在投资理由中不要说明时效性权重的具体值

        【输出格式要求】
        请严格按照以下JSON格式返回，确保所有字段都有值：
        {{
            "综合评分": 85,
            "基本面评分": 80,
            "技术面评分": 85,
            "资金面评分": 75,
            "估值评分": 70,
            "风险评估": "medium",
            "投资建议": "buy",
            "目标价位": 12.50,
            "止损价位": 9.20,
            "支撑位": 10.20,
            "压力位": 11.80,
            "买入价": 10.50,
            "卖出价": 12.00,
            "投资理由": "基于技术面强势突破、资金持续流入、估值合理...",
            "关键指标": ["MACD金叉", "成交量放大", "资金净流入"],
            "风险提示": ["大盘系统性风险", "行业政策变化", "流动性风险"]
        }}

        请以专业、客观的角度进行分析，确保数据准确可靠。
        """
    

    
    def _calculate_fundamental_score(self, pe_ratio: float, pb_ratio: float) -> float:
        """计算基本面评分"""
        score = 50  # 基础分
        
        # PE评分 (合理PE 10-20)
        if 10 <= pe_ratio <= 20:
            score += 25
        elif 5 <= pe_ratio < 10 or 20 < pe_ratio <= 30:
            score += 15
        elif pe_ratio < 5 or pe_ratio > 30:
            score += 5
        
        # PB评分 (合理PB 1-3)
        if 1 <= pb_ratio <= 3:
            score += 25
        elif 0.5 <= pb_ratio < 1 or 3 < pb_ratio <= 5:
            score += 15
        elif pb_ratio < 0.5 or pb_ratio > 5:
            score += 5
        
        return min(score, 100)
    
    def _calculate_technical_score(self, change_rate: float, kline_data: list) -> float:
        """计算技术面评分"""
        score = 50  # 基础分
        
        # 基于涨跌幅评分
        if change_rate > 5:
            score += 20
        elif change_rate > 2:
            score += 15
        elif change_rate > -2:
            score += 10
        elif change_rate > -5:
            score += 5
        else:
            score += 0
        
        # 基于K线数据长度评分
        if len(kline_data) >= 20:
            score += 15
        elif len(kline_data) >= 10:
            score += 10
        else:
            score += 5
        
        return min(score, 100)
    
    def _calculate_valuation_score(self, pe_ratio: float, pb_ratio: float) -> float:
        """计算估值评分"""
        score = 50  # 基础分
        
        # 综合估值评分
        valuation_ratio = (pe_ratio + pb_ratio * 10) / 2
        
        if valuation_ratio < 15:
            score += 40  # 低估
        elif valuation_ratio < 25:
            score += 30  # 合理偏低
        elif valuation_ratio < 35:
            score += 20  # 合理
        elif valuation_ratio < 50:
            score += 10  # 偏高
        else:
            score += 0   # 高估
        
        return min(score, 100)
    
    def _calculate_capital_score(self, capital_flow: Dict[str, Any]) -> float:
        """计算资金面评分"""
        score = 50  # 基础分
        
        # 基于资金流向数据评分
        historical = capital_flow.get('historical', [])
        if len(historical) >= 10:
            score += 30
        elif len(historical) >= 5:
            score += 20
        elif len(historical) >= 1:
            score += 10
        else:
            score += 5
        
        return min(score, 100)
    

    

    


    def _generate_detailed_reason(self, overall_score: float, basic_data: Dict[str, Any]) -> str:
        """生成详细的投资理由"""
        current_price = basic_data.get('current_price', 0)
        pe_ratio = basic_data.get('pe_ratio', 0)
        pb_ratio = basic_data.get('pb_ratio', 0)
        change_rate = basic_data.get('change_rate', 0)
        
        reasons = []
        
        if overall_score >= 80:
            reasons.append("综合评分优秀，各项指标表现良好")
            if pe_ratio < 20:
                reasons.append("估值合理，具备投资价值")
            if change_rate > 2:
                reasons.append("技术面强势，短期趋势向上")
            if len(basic_data.get('capital_flow', {}).get('historical', [])) > 10:
                reasons.append("资金持续流入，主力看好")
            return "；".join(reasons) + "。建议积极买入并持有。"
        elif overall_score >= 60:
            reasons.append("综合评分良好，整体表现稳健")
            if 15 <= pe_ratio <= 25:
                reasons.append("估值适中，风险可控")
            if -2 <= change_rate <= 5:
                reasons.append("技术面中性，适合观望")
            return "；".join(reasons) + "。建议持有观察，等待更好时机。"
        else:
            reasons.append("综合评分偏低，存在较多风险因素")
            if pe_ratio > 30:
                reasons.append("估值偏高，存在回调风险")
            if change_rate < -3:
                reasons.append("技术面弱势，短期承压")
            return "；".join(reasons) + "。建议谨慎操作或考虑减仓。"

    def _generate_detailed_indicators(self, basic_data: Dict[str, Any]) -> list:
        """生成详细的关键指标"""
        indicators = []
        
        # 估值指标
        pe_ratio = basic_data.get('pe_ratio', 0)
        if pe_ratio < 15:
            indicators.append("低估值")
        elif pe_ratio > 30:
            indicators.append("高估值")
        
        # 技术面指标
        change_rate = basic_data.get('change_rate', 0)
        if change_rate > 5:
            indicators.append("强势上涨")
        elif change_rate < -5:
            indicators.append("弱势下跌")
        elif abs(change_rate) <= 2:
            indicators.append("震荡整理")
        
        # 资金面指标
        capital_data = basic_data.get('capital_flow', {})
        if len(capital_data.get('historical', [])) > 10:
            indicators.append("资金活跃")
        
        # 成交量指标
        volume = basic_data.get('volume', 0)
        if volume > 1000000:
            indicators.append("高成交量")
        elif volume < 100000:
            indicators.append("低成交量")
        
        return indicators[:5]  # 最多返回5个关键指标

    def _generate_detailed_warnings(self, basic_data: Dict[str, Any]) -> list:
        """生成详细的风险提示"""
        warnings = []
        
        # 估值风险
        pe_ratio = basic_data.get('pe_ratio', 0)
        if pe_ratio > 50:
            warnings.append("估值过高，存在回调风险")
        elif pe_ratio < 5:
            warnings.append("估值过低，可能存在基本面问题")
        
        # 技术面风险
        change_rate = basic_data.get('change_rate', 0)
        if change_rate < -10:
            warnings.append("短期大幅下跌，技术面恶化")
        
        # 流动性风险
        volume = basic_data.get('volume', 0)
        if volume < 50000:
            warnings.append("成交量低迷，流动性不足")
        
        # 行业风险
        industry = basic_data.get('industry', '')
        if industry in ['房地产', '钢铁', '煤炭']:
            warnings.append("周期性行业，受宏观经济影响较大")
        
        # 系统性风险
        if basic_data.get('high_52w', 0) > 0:
            price_position = basic_data.get('current_price', 0) / basic_data.get('high_52w', 1)
            if price_position > 0.9:
                warnings.append("股价接近历史高位，回调风险较大")
            elif price_position < 0.3:
                warnings.append("股价处于历史低位，可能存在基本面问题")
        
        return warnings[:3]  # 最多返回3个主要风险

    def _call_deepseek_analysis(self, prompt: str, basic_data: Dict[str, Any]) -> Dict[str, Any]:
        """调用DeepSeek API获取诊断报告"""
        try:
            logger.info("【DeepSeek调用】开始API调用...")
            
            # 加载环境变量（参考app.py的实现）
            from dotenv import load_dotenv
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
            load_dotenv(dotenv_path=env_path, override=True)
            
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                logger.error("【DeepSeek调用】未配置API密钥")
                raise Exception("未配置DeepSeek API密钥")
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            # 清理prompt中的换行和多余空格
            import re
            clean_prompt = re.sub(r'\s+', ' ', prompt).strip()
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的金融分析师，请基于提供的股票数据生成结构化诊断报告。请严格按照JSON格式返回结果。"
                    },
                    {
                        "role": "user",
                        "content": clean_prompt
                    }
                ],
                "temperature": 0.6,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"}
            }
            
            logger.info("【DeepSeek调用】发送API请求...")
            logger.debug(f"【DeepSeek请求头】: {json.dumps(headers, ensure_ascii=False)}")
            logger.debug(f"【DeepSeek请求体】: {json.dumps(payload, ensure_ascii=False, default=str)}")
            
            response = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"【DeepSeek调用】API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # 计算响应token数量
                usage = result.get('usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)
                
                logger.info(f"【DeepSeek调用】API响应成功 - 输入token: {prompt_tokens}, 输出token: {completion_tokens}, 总token: {total_tokens}")
                logger.info(f"【DeepSeek调用】API响应成功: {json.dumps(result, ensure_ascii=False, default=str)[:500]}...")
                
                content = result['choices'][0]['message']['content']
                response_tokens = len(content.encode('utf-8')) // 4  # 粗略估算响应token数量
                logger.info(f"【DeepSeek响应】响应内容token数量 ≈ {response_tokens}")
                
                parsed_content = json.loads(content)
                #logger.info(f"【DeepSeek调用】解析后的响应内容: {json.dumps(parsed_content, ensure_ascii=False, indent=2)}")
                return parsed_content
            else:
                logger.error(f"【DeepSeek调用】API调用失败: {response.status_code}, 响应: {response.text}")
                raise Exception(f"DeepSeek API调用失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"【DeepSeek调用】API调用异常: {str(e)}", exc_info=True)
            raise Exception(f"DeepSeek API调用异常: {str(e)}")
    
    def _parse_deepseek_response(self, symbol: str, basic_data: Dict[str, Any], deepseek_response: Dict[str, Any]) -> Dict[str, Any]:
        """基于DeepSeek响应构建结构化数据"""
        try:
            logger.info("【数据解析】开始解析DeepSeek响应...")
            logger.info(f"【原始响应数据】: {json.dumps(deepseek_response, ensure_ascii=False, indent=2)}")
            
            # 标准化DeepSeek响应字段
            current_price = basic_data.get('current_price', 0)
            
            # 映射DeepSeek响应到标准格式
            structured_data = {
                "symbol": symbol,
                "name": basic_data.get('name', symbol),
                "current_price": current_price,
                "overall_score": float(deepseek_response.get("综合评分", deepseek_response.get("overall_score", 50))),
                "fundamental_score": float(deepseek_response.get("基本面评分", deepseek_response.get("fundamental_score", 50))),
                "technical_score": float(deepseek_response.get("技术面评分", deepseek_response.get("technical_score", 50))),
                "capital_score": float(deepseek_response.get("资金面评分", deepseek_response.get("capital_score", 50))),
                "valuation_score": float(deepseek_response.get("估值评分", deepseek_response.get("valuation_score", 50))),
                "risk_level": deepseek_response.get("风险评估", deepseek_response.get("risk_level", "medium")),
                "recommendation": deepseek_response.get("投资建议", deepseek_response.get("recommendation", "hold")),
                "target_price": float(deepseek_response.get("目标价位", deepseek_response.get("target_price", current_price * 1.1))),
                "stop_loss": float(deepseek_response.get("止损价位", deepseek_response.get("stop_loss", current_price * 0.9))),
                "support": float(deepseek_response.get("支撑位", deepseek_response.get("support", current_price * 0.95))),
                "resistance": float(deepseek_response.get("压力位", deepseek_response.get("resistance", current_price * 1.05))),
                "buy_price": float(deepseek_response.get("买入价", deepseek_response.get("buy_price", current_price * 0.98))),
                "sell_price": float(deepseek_response.get("卖出价", deepseek_response.get("sell_price", current_price * 1.02))),
                "investment_reason": str(deepseek_response.get("投资理由", deepseek_response.get("investment_reason", "基于综合分析的投资建议"))),
                "key_indicators": deepseek_response.get("关键指标", deepseek_response.get("key_indicators", [])),
                "risk_warnings": deepseek_response.get("风险提示", deepseek_response.get("risk_warnings", [])),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("【数据解析】解析完成，结构化数据:")
            logger.info(f"【解析结果】: {json.dumps(structured_data, ensure_ascii=False, indent=2)}")
            return structured_data
            
        except Exception as e:
            logger.error(f"【数据解析】解析DeepSeek响应失败: {str(e)}", exc_info=True)
            raise Exception(f"解析DeepSeek响应失败: {str(e)}")

    def _get_market_data_independent(self, symbol: str) -> Dict[str, Any]:
        """独立获取行情数据，使用与app.py相同的方法"""
        try:
            import sys
            import os
            from datetime import datetime
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                # 使用与app.py相同的Futu API方法
                from futu import OpenQuoteContext, RET_OK
                
                # 解析股票代码并转换为Futu格式
                code_parts = symbol.split('.')
                if len(code_parts) != 2:
                    return self._get_fallback_market_data(symbol)
                
                stock_code = code_parts[0]
                market = code_parts[1].upper()
                
                # 转换为Futu格式
                if market == 'HK' and stock_code.isdigit():
                    futu_symbol = f'HK.{stock_code.zfill(5)}'
                elif market == 'SH' and stock_code.isdigit():
                    futu_symbol = f'SH.{stock_code}'
                elif market == 'SZ' and stock_code.isdigit():
                    futu_symbol = f'SZ.{stock_code}'
                elif market == 'US':
                    futu_symbol = f'US.{stock_code.upper()}'
                else:
                    futu_symbol = f'{market}.{stock_code}'
                
                # 创建Futu连接
                quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
                
                try:
                    # 获取实时行情快照
                    ret, data = quote_ctx.get_market_snapshot([futu_symbol])
                    logger.info(f"【Futu行情】{symbol} API调用结果: ret={ret}, data_shape={data.shape if data is not None else 'None'}")
                    
                    if ret == RET_OK and data is not None and not data.empty:
                        logger.info(f"【Futu行情】{symbol} 原始数据: {data.iloc[0].to_dict()}")
                        row = data.iloc[0]
                        return {
                            'current_price': float(row.get('last_price', 0)),
                            'pe_ratio': float(row.get('pe_ratio', 0)),
                            'pb_ratio': float(row.get('pb_ratio', 0)),
                            'volume': int(row.get('volume', 0)),
                            'change_rate': float(row.get('change_rate', 0)) if 'change_rate' in row else 
                                          ((float(row.get('last_price', 0)) - float(row.get('prev_close_price', 0))) / float(row.get('prev_close_price', 1)) * 100) if 'prev_close_price' in row else 0.0,
                            'high_52w': float(row.get('highest52weeks_price', 0)),
                            'low_52w': float(row.get('lowest52weeks_price', 0)),
                            'market_cap': float(row.get('total_market_val', 0)),
                            'name': str(row.get('name', symbol)),
                            'industry': str(row.get('industry', str(row.get('name', symbol)))),
                            'sector': str(row.get('sector', '未知'))
                        }
                    else:
                        logger.warning(f"【Futu行情】{symbol} 数据异常: ret={ret}, data={data}")
                        logger.info(f"【Futu行情】{symbol} 使用备用数据源")
                        
                finally:
                    quote_ctx.close()
                    
            except ImportError:
                # 如果Futu模块不可用，使用备用方法
                logger.warning("Futu模块不可用，使用备用行情数据获取方法")
                
        except Exception as e:
            logger.error(f"获取{symbol}行情数据失败: {str(e)}")
            
        return self._get_fallback_market_data(symbol)
    
    def _get_kline_data_independent(self, symbol: str) -> list:
        """独立获取K线数据，使用与app.py相同的方法"""
        try:
            import sys
            import os
            import pandas as pd
            from datetime import datetime, timedelta
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                from quant import quant_get_stock_kline
                
                # 计算日期范围（最近90天）
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
                
                # 获取K线数据
                kline_data = quant_get_stock_kline(symbol, start=start_date, end=end_date)
                
                # 增加100ms等待时间，避免API调用过于频繁
                import time
                time.sleep(0.1)
                
                # 处理DataFrame布尔值判断错误
                if kline_data is not None:
                    if isinstance(kline_data, pd.DataFrame):
                        if not kline_data.empty:
                            # 转换为列表格式
                            data_list = kline_data.to_dict('records')
                            return data_list[-30:] if len(data_list) >= 30 else data_list
                        else:
                            logger.warning(f"{symbol}的K线数据为空DataFrame")
                    elif isinstance(kline_data, list):
                        if len(kline_data) > 0:
                            return kline_data[-30:] if len(kline_data) >= 30 else kline_data
                        else:
                            logger.warning(f"{symbol}的K线数据为空列表")
                    else:
                        # 其他类型，直接返回
                        return kline_data if kline_data else []
                else:
                    logger.warning(f"无法获取{symbol}的K线数据")
                    
            except ImportError:
                # 如果quant模块不可用，使用备用方法
                logger.warning("quant模块不可用，使用备用K线数据获取方法")
                return []
                
        except Exception as e:
            logger.error(f"获取{symbol}K线数据失败: {str(e)}")
            
        return []

    def _get_15min_kline_data_independent(self, symbol: str) -> list:
        """独立获取当日15分钟K线数据"""
        try:
            import sys
            import os
            import pandas as pd
            from datetime import datetime, timedelta
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                from futu import OpenQuoteContext, RET_OK, KLType, AuType
                
                # 解析股票代码
                code_parts = symbol.split('.')
                if len(code_parts) != 2:
                    return []
                
                stock_code = code_parts[0]
                market = code_parts[1].upper()
                
                # 转换为Futu格式
                if market == 'HK' and stock_code.isdigit():
                    futu_symbol = f'HK.{stock_code.zfill(5)}'
                elif market == 'SH' and stock_code.isdigit():
                    futu_symbol = f'SH.{stock_code}'
                elif market == 'SZ' and stock_code.isdigit():
                    futu_symbol = f'SZ.{stock_code}'
                elif market == 'US':
                    futu_symbol = f'US.{stock_code.upper()}'
                else:
                    futu_symbol = f'{market}.{stock_code}'
                
                # 创建Futu连接
                quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
                
                try:
                    # 获取当日5分钟K线数据，使用明确的日期范围获取最新数据
                    from datetime import datetime, timedelta
                    
                    # 设置日期范围为今天到明天，确保获取最新数据
                    start_date = datetime.now().strftime('%Y-%m-%d')
                    end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                    
                    ret, data, page_req_key = quote_ctx.request_history_kline(
                        futu_symbol,
                        start=start_date,
                        end=end_date,
                        ktype=KLType.K_15M,
                        autype=AuType.QFQ
                    )
                    
                    if ret == RET_OK and data is not None and not data.empty:
                        # 转换为列表格式
                        kline_list = []
                        for _, row in data.iterrows():
                            kline_list.append({
                                'time': str(row.get('time_key', '')),
                                'open': float(row.get('open', 0)),
                                'close': float(row.get('close', 0)),
                                'high': float(row.get('high', 0)),
                                'low': float(row.get('low', 0)),
                                'volume': int(row.get('volume', 0)),
                                'turnover': float(row.get('turnover', 0)),
                                'change_rate': float(row.get('change_rate', 0)) if 'change_rate' in row else 0.0
                            })
                        
                        # 按时间排序并返回最新数据
                        kline_list.sort(key=lambda x: x['time'], reverse=True)
                        logger.info(f"成功获取{symbol}的15分钟K线数据: {len(kline_list)}条, 时间范围{start_date}到{end_date}")
                        return kline_list
                    else:
                        logger.warning(f"获取{symbol}的15分钟K线数据失败: ret={ret}, data={data}, 时间范围{start_date}到{end_date}")
                        return []
                        
                finally:
                    quote_ctx.close()
                    
            except ImportError:
                logger.warning("Futu模块不可用，使用备用5分钟K线数据获取方法")
                return []
                
        except Exception as e:
            logger.error(f"获取{symbol}5分钟K线数据失败: {str(e)}")
            
        return []
    
    def _get_weekly_kline_data_independent(self, symbol: str) -> list:
        """独立获取周K线数据，查询25周历史数据"""
        try:
            import sys
            import os
            import pandas as pd
            from datetime import datetime, timedelta
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                from futu import OpenQuoteContext, RET_OK, KLType, AuType
                
                # 解析股票代码
                code_parts = symbol.split('.')
                if len(code_parts) != 2:
                    return []
                
                stock_code = code_parts[0]
                market = code_parts[1].upper()
                
                # 转换为Futu格式
                if market == 'HK' and stock_code.isdigit():
                    futu_symbol = f'HK.{stock_code.zfill(5)}'
                elif market == 'SH' and stock_code.isdigit():
                    futu_symbol = f'SH.{stock_code}'
                elif market == 'SZ' and stock_code.isdigit():
                    futu_symbol = f'SZ.{stock_code}'
                elif market == 'US':
                    futu_symbol = f'US.{stock_code.upper()}'
                else:
                    futu_symbol = f'{market}.{stock_code}'
                
                # 创建Futu连接
                quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
                
                try:
                    # 计算日期范围（最近25周，约6个月）
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date = (datetime.now() - timedelta(weeks=30)).strftime('%Y-%m-%d')  # 多取几周确保有25周数据
                    
                    ret, data, page_req_key = quote_ctx.request_history_kline(
                        futu_symbol,
                        start=start_date,
                        end=end_date,
                        ktype=KLType.K_WEEK,
                        autype=AuType.QFQ
                    )
                    
                    if ret == RET_OK and data is not None and not data.empty:
                        # 转换为列表格式
                        kline_list = []
                        for _, row in data.iterrows():
                            kline_list.append({
                                'time': str(row.get('time_key', '')),
                                'open': float(row.get('open', 0)),
                                'close': float(row.get('close', 0)),
                                'high': float(row.get('high', 0)),
                                'low': float(row.get('low', 0)),
                                'volume': int(row.get('volume', 0)),
                                'turnover': float(row.get('turnover', 0)),
                                'change_rate': float(row.get('change_rate', 0)) if 'change_rate' in row else 0.0
                            })
                        
                        # 按时间排序并返回最近25周数据
                        kline_list.sort(key=lambda x: x['time'], reverse=False)
                        weekly_data = kline_list[-25:] if len(kline_list) >= 25 else kline_list
                        
                        logger.info(f"成功获取{symbol}的周K线数据: {len(weekly_data)}条, 时间范围{start_date}到{end_date}")
                        return weekly_data
                    else:
                        logger.warning(f"获取{symbol}的周K线数据失败: ret={ret}, data={data}, 时间范围{start_date}到{end_date}")
                        return []
                        
                finally:
                    quote_ctx.close()
                    
            except ImportError:
                logger.warning("Futu模块不可用，使用备用周K线数据获取方法")
                return []
                
        except Exception as e:
            logger.error(f"获取{symbol}周K线数据失败: {str(e)}")
            
        return []
    
    def _get_capital_flow_data_independent(self, symbol: str) -> Dict[str, Any]:
        """独立获取资金流向数据，使用与app.py相同的方法"""
        try:
            import sys
            import os
            import pandas as pd
            from datetime import datetime, timedelta
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                # 使用与app.py相同的Futu API方法
                from futu import OpenQuoteContext, RET_OK, PeriodType
                
                # 解析股票代码
                code_parts = symbol.split('.')
                if len(code_parts) != 2:
                    return {'historical': [], 'intraday': [], 'distribution': []}
                
                stock_code = code_parts[0]
                market = code_parts[1].upper()
                
                # 市场映射
                market_map = {'HK': 'HK', 'SH': 'SH', 'SZ': 'SZ', 'US': 'US'}
                futu_market = market_map.get(market, market)
                
                # 创建Futu连接（使用独立连接避免上下文问题）
                quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
                
                try:
                    # 获取历史资金流向数据（最近60天）
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
                    
                    ret, historical_data = quote_ctx.get_capital_flow(
                        stock_code=f'{futu_market}.{stock_code}',
                        period_type=PeriodType.DAY,
                        start=start_date,
                        end=end_date
                    )
                    
                    if ret != RET_OK:
                        logger.warning(f"获取历史资金流向失败: {historical_data}")
                        return {'historical': [], 'intraday': [], 'distribution': []}
                    
                    # 获取当日资金流向数据
                    ret, intraday_data = quote_ctx.get_capital_flow(
                        stock_code=f'{futu_market}.{stock_code}',
                        period_type=PeriodType.INTRADAY
                    )
                    
                    if ret != RET_OK:
                        logger.warning(f"获取当日资金流向失败: {intraday_data}")
                        return {'historical': [], 'intraday': [], 'distribution': []}
                    
                    # 处理历史资金流向数据 - 使用正确的字段名
                    historical_flow = []
                    if historical_data is not None and not historical_data.empty:
                        for _, row in historical_data.iterrows():
                            historical_flow.append({
                                'date': str(row.get('capital_flow_item_time', '')),
                                'in_flow': float(row.get('in_flow', 0)),
                                'out_flow': float(row.get('out_flow', 0)),
                                'net_flow': float(row.get('capital_net', 0)),
                                'main_in': float(row.get('main_in_flow', 0)),
                                'main_out': float(row.get('main_out_flow', 0))
                            })
                    
                    # 处理当日资金流向数据 - 使用正确的字段名
                    intraday_flow = []
                    if intraday_data is not None and not intraday_data.empty:
                        for _, row in intraday_data.iterrows():
                            intraday_flow.append({
                                'time': str(row.get('capital_flow_item_time', '')),
                                'in_flow': float(row.get('in_flow', 0)),
                                'out_flow': float(row.get('out_flow', 0)),
                                'net_flow': float(row.get('capital_net', 0)),
                                'super_in': float(row.get('super_in_flow', 0)),
                                'big_in': float(row.get('big_in_flow', 0)),
                                'mid_in': float(row.get('mid_in_flow', 0)),
                                'small_in': float(row.get('sml_in_flow', 0))
                            })
                    
                    # 获取资金分布数据
                    ret, distribution_data = quote_ctx.get_capital_distribution(
                        stock_code=f'{futu_market}.{stock_code}'
                    )
                    
                    distribution = []
                    if ret == RET_OK and distribution_data is not None and not distribution_data.empty:
                        for _, row in distribution_data.iterrows():
                            distribution.append({
                                'update_time': str(row.get('update_time', '')),
                                'capital_in': {
                                    'super': float(row.get('capital_in_super', 0)),
                                    'big': float(row.get('capital_in_big', 0)),
                                    'mid': float(row.get('capital_in_mid', 0)),
                                    'small': float(row.get('capital_in_small', 0))
                                },
                                'capital_out': {
                                    'super': float(row.get('capital_out_super', 0)),
                                    'big': float(row.get('capital_out_big', 0)),
                                    'mid': float(row.get('capital_out_mid', 0)),
                                    'small': float(row.get('capital_out_small', 0))
                                }
                            })
                    
                    return {
                        'historical': historical_flow,
                        'intraday': intraday_flow,
                        'distribution': distribution
                    }
                    
                finally:
                    # 确保关闭连接
                    quote_ctx.close()
                    
            except ImportError:
                # Futu模块不可用，使用备用方案
                logger.warning("Futu模块不可用，使用备用资金流向数据获取方法")
                return {'historical': [], 'intraday': [], 'distribution': []}
                
        except Exception as e:
            logger.error(f"获取{symbol}资金流向数据失败: {str(e)}")
            
        return {'historical': [], 'intraday': [], 'distribution': []}
    
    def _get_news_data_independent(self, symbol: str) -> str:
        """独立获取新闻数据，使用与app.py相同的方法"""
        try:
            import sys
            import os
            import pandas as pd
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                from quant import get_stock_news
                
                # 获取新闻数据
                news_data = get_stock_news(symbol)
                
                # 处理DataFrame布尔值判断错误
                if news_data is not None:
                    news_list = []
                    
                    # 处理DataFrame类型
                    if isinstance(news_data, pd.DataFrame):
                        if not news_data.empty:
                            news_list = news_data.to_dict('records')
                        else:
                            logger.warning(f"{symbol}的新闻数据为空DataFrame")
                    # 处理字典类型
                    elif isinstance(news_data, dict):
                        news_list = news_data.get('news', [])
                    # 处理列表类型
                    elif isinstance(news_data, list):
                        news_list = news_data
                    # 处理其他类型
                    elif hasattr(news_data, 'json'):
                        try:
                            news_json = news_data.json
                            if callable(news_json):
                                news_json = news_json()
                            news_list = news_json.get('news', []) if isinstance(news_json, dict) else []
                        except Exception:
                            pass
                    
                    # 格式化新闻数据
                    if news_list and len(news_list) > 0:
                        formatted_news = []
                        for n in news_list[:10]:
                            if isinstance(n, dict):
                                title = str(n.get('title', '')) or str(n.get('Title', ''))
                                content = str(n.get('content', '')) or str(n.get('Content', ''))
                                if title or content:
                                    formatted_news.append(f"标题: {title}\n内容: {content}")
                        
                        if formatted_news:
                            return '\n\n'.join(formatted_news)
                
                logger.warning(f"无法获取{symbol}的有效新闻数据")
                
            except ImportError:
                # 如果quant模块不可用，使用备用方法
                logger.warning("quant模块不可用，使用备用新闻数据获取方法")
                return ""
                
        except Exception as e:
            logger.error(f"获取{symbol}新闻数据失败: {str(e)}")
            
        return ""
    
    def _get_financial_data_independent(self, symbol: str) -> Any:
        """独立获取财务数据，区分A股和港股处理，按报告期返回每个报告期的结构化数据"""
        
        def clean_and_convert_value(value):
            """清洗并转换数值"""
            import pandas as pd
            import numpy as np
            
            if pd.isna(value) or value is None or value == '':
                return None
            
            # 如果是字符串，去除空格和逗号
            if isinstance(value, str):
                value = value.strip().replace(',', '')
                if value == '' or value == '-':
                    return None
                
                # 尝试转换为数值
                try:
                    # 处理百分比
                    if value.endswith('%'):
                        return float(value.rstrip('%')) / 100
                    # 处理普通数值
                    return float(value)
                except (ValueError, TypeError):
                    return value
            
            # 已经是数值类型
            if isinstance(value, (int, float, np.number)):
                return float(value) if not pd.isna(value) else None
            
            return str(value)
        
        def parse_report_date(date_str):
            """解析报告期日期，支持多种格式"""
            if pd.isna(date_str) or date_str is None:
                return None
            
            date_str = str(date_str).strip()
            if not date_str or date_str.lower() == 'nan':
                return None
            
            # 尝试不同的日期格式
            formats = ['%Y%m%d', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']
            
            for fmt in formats:
                try:
                    return pd.to_datetime(date_str, format=fmt)
                except (ValueError, TypeError):
                    continue
            
            # 如果所有格式都失败，尝试自动解析
            try:
                return pd.to_datetime(date_str, format='mixed')
            except (ValueError, TypeError):
                return None
        
        def is_hk_stock(symbol):
            """判断是否为港股"""
            return symbol.upper().endswith('.HK')
        
        def adapt_hk_financial_data(raw_data):
            """适配港股财务数据结构 - 直接使用接口返回的指标名称"""
            if raw_data is None or raw_data.empty:
                return None
            
            try:
                # 港股数据结构：接口已返回正确的指标名称
                # 直接使用原始数据的列名，无需映射
                
                # 获取数据行
                data_rows = raw_data.copy()
                
                # 创建重组后的数据结构
                restructured_data = []
                
                # 获取列名（第一行应该是指标名称）
                if len(data_rows) > 0:
                    # 如果港股也是第一行是指标名称，则使用A股处理方式
                    if isinstance(data_rows.iloc[0, 0], str) and '报告期' in str(data_rows.iloc[0, 0]):
                        # 港股也使用A股处理方式
                        return process_a_share_data(raw_data)
                    
                    # 否则直接使用列名
                    columns = list(data_rows.columns)
                    
                    for idx, row in data_rows.iterrows():
                        row_data = {}
                        
                        # 直接使用列名和对应值
                        for col_name, value in zip(columns, row):
                            cleaned_value = clean_and_convert_value(value)
                            if cleaned_value is not None:
                                row_data[str(col_name)] = cleaned_value
                        
                        if row_data.get('报告期') or row_data.get('报告期', '').strip():
                            restructured_data.append(row_data)
                
                # 创建DataFrame
                if restructured_data:
                    result_df = pd.DataFrame(restructured_data)
                    
                    # 确保报告期列存在且格式正确
                    report_period_col = None
                    for col in result_df.columns:
                        if '报告期' in str(col) or 'period' in str(col).lower():
                            report_period_col = col
                            break
                    
                    if report_period_col and report_period_col != '报告期':
                        # 重命名报告期列
                        result_df = result_df.rename(columns={report_period_col: '报告期'})
                    
                    return result_df
                
                return pd.DataFrame()
                
            except Exception as e:
                logger.error(f"适配港股财务数据失败: {str(e)}")
                return None
        
        def process_a_share_data(raw_data):
            """处理A股财务数据"""
            if raw_data is None or raw_data.empty:
                return None
            
            try:
                # A股数据结构：第一行是指标名称，从第二行开始是数据
                indicator_names = raw_data.iloc[0].tolist()
                data_rows = raw_data.iloc[1:].copy()
                
                # 创建重组后的数据结构
                restructured_data = []
                
                # 遍历每一行（每个报告期）
                for idx, row in data_rows.iterrows():
                    report_data = {}
                    
                    # 遍历每个值和对应的指标名称
                    for col_idx, (indicator_name, value) in enumerate(zip(indicator_names, row)):
                        if col_idx == 0:  # 第一列是报告期
                            report_data['报告期'] = str(value)
                        elif indicator_name and indicator_name not in ['常用指标', '每股指标', '盈利能力', '成长能力', '收益质量', '财务风险', '营运能力', '指标']:
                            # 跳过分类标题，只保留具体指标
                            cleaned_value = clean_and_convert_value(value)
                            if cleaned_value is not None:
                                report_data[indicator_name] = cleaned_value
                    
                    if report_data.get('报告期') and report_data['报告期'] != 'nan':
                        restructured_data.append(report_data)
                
                return pd.DataFrame(restructured_data)
                
            except Exception as e:
                logger.error(f"处理A股财务数据失败: {str(e)}")
                return None
        
        try:
            import sys
            import os
            import pandas as pd
            
            # 确保项目根目录在Python路径中
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            try:
                from quant import get_stock_financials
                
                # 获取财务数据
                financial_data = get_stock_financials(symbol)
                
                if financial_data is not None and isinstance(financial_data, pd.DataFrame) and not financial_data.empty:
                    
                    # 判断市场类型并选择相应的处理方式
                    if is_hk_stock(symbol):
                        result_df = adapt_hk_financial_data(financial_data)
                    else:
                        result_df = process_a_share_data(financial_data)
                    
                    if result_df is None or result_df.empty:
                        return pd.DataFrame()
                    
                    # 按报告期排序（最新的在前面）
                    try:
                        # 过滤掉报告期为空的数据
                        result_df = result_df[result_df['报告期'].notna()]
                        result_df = result_df[result_df['报告期'] != 'nan']
                        
                        if result_df.empty:
                            return pd.DataFrame()
                        
                        # 应用日期解析
                        result_df['报告期_dt'] = result_df['报告期'].apply(parse_report_date)
                        
                        # 过滤掉报告期解析失败的数据
                        result_df = result_df[result_df['报告期_dt'].notna()]
                        
                        if result_df.empty:
                            return pd.DataFrame()
                        
                        # 按报告期排序（最新的在前面）
                        result_df = result_df.sort_values('报告期_dt', ascending=False)
                        result_df = result_df.drop('报告期_dt', axis=1)
                        
                    except Exception as e:
                        # 如果日期解析失败，按字符串排序
                        result_df = result_df[result_df['报告期'].notna()]
                        result_df = result_df[result_df['报告期'] != 'nan']
                        result_df = result_df.sort_values('报告期', ascending=False)
                    
                    # 重置索引
                    result_df = result_df.reset_index(drop=True)
                    
                    return result_df
                else:
                    return pd.DataFrame()
                    
            except ImportError:
                # 如果quant模块不可用，使用备用方法
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"获取{symbol}财务数据失败: {str(e)}")
            
        return pd.DataFrame()
    
    def _get_fallback_market_data(self, symbol: str) -> Dict[str, Any]:
        """获取备用市场数据"""
        logger.info(f"使用备用市场数据: {symbol}")
        try:
            import requests
            import json
            
            # 尝试使用备用API获取数据
            try:
                # 使用新浪财经API作为备用
                code_parts = symbol.split('.')
                if len(code_parts) == 2:
                    stock_code = code_parts[0]
                    market = code_parts[1].upper()
                    
                    # 构建新浪财经API请求
                    if market == 'SZ':
                        sina_code = f'sz{stock_code}'
                    elif market == 'SH':
                        sina_code = f'sh{stock_code}'
                    else:
                        sina_code = stock_code
                    
                    url = f'https://hq.sinajs.cn/list={sina_code}'
                    response = requests.get(url, timeout=5)
                    
                    if response.status_code == 200:
                        data_str = response.text
                        if 'var hq_str_' in data_str:
                            parts = data_str.split('"')[1].split(',')
                            if len(parts) >= 33:
                                return {
                                    'symbol': str(symbol),
                                    'name': str(parts[0]) if parts[0] else str(symbol),
                                    'current_price': float(parts[3]) if parts[3] else 0.0,
                                    'volume': int(parts[8]) if parts[8] else 0,
                                    'change_rate': float(parts[3]) - float(parts[2]) if parts[2] and parts[3] else 0.0,
                                    'high_52w': float(parts[4]) if parts[4] else 0.0,
                                    'low_52w': float(parts[5]) if parts[5] else 0.0,
                                    'market_cap': float(parts[9]) * float(parts[3]) if parts[9] and parts[3] else 0.0,
                                    'pe_ratio': float(parts[39]) if len(parts) > 39 and parts[39] else 0.0,
                                    'pb_ratio': float(parts[40]) if len(parts) > 40 and parts[40] else 0.0,
                                    'industry': '未知行业',
                                    'sector': '未知板块'
                                }
            except Exception as e:
                logger.warning(f"备用API获取失败: {e}")
                
        except Exception as e:
            logger.error(f"备用市场数据获取异常: {e}")
            
        # 返回基础数据，避免全为0
        return {
            'symbol': str(symbol),
            'name': str(symbol),
            'current_price': 0.0,
            'pe_ratio': 0.0,
            'pb_ratio': 0.0,
            'volume': 0,
            'change_rate': 0.0,
            'high_52w': 0.0,
            'low_52w': 0.0,
            'market_cap': 0.0,
            'industry': '未知行业',
            'sector': '未知板块'
        }
    
    def _create_error_diagnosis(self, symbol: str, error_msg: str) -> Dict[str, Any]:
        """创建错误诊断"""
        return {
            "symbol": str(symbol),
            "name": str(symbol),
            "current_price": 0.0000,
            "overall_score": 0.0000,
            "fundamental_score": 0.0000,
            "technical_score": 0.0000,
            "valuation_score": 0.0000,
            "capital_score": 0.0000,
            "risk_level": "high",
            "recommendation": "hold",
            "target_price": 0.0000,
            "stop_loss": 0.0000,
            "support": 0.0000,
            "resistance": 0.0000,
            "buy_price": 0.0000,
            "sell_price": 0.0000,
            "investment_reason": f"诊断失败: {error_msg}",
            "key_indicators": [],
            "risk_warnings": [error_msg],
            "timestamp": datetime.now().isoformat()
        }

    def _save_diagnosis_report(self, symbol: str, diagnosis_data: Dict[str, Any]) -> None:
        """
        存储诊断报告到数据库
        使用data_service将诊断数据存储到数据库
        
        Args:
            symbol: 股票代码
            diagnosis_data: 诊断数据
        """
        try:
            # 打印方法入参信息
            logger.info(f"【方法入参】_save_diagnosis_report - symbol: {symbol}, diagnosis_data: {json.dumps(diagnosis_data, ensure_ascii=False, default=str)[:500]}...")
            
            # 检查是否为异常结果（overall_score为0表示异常）
            if diagnosis_data.get('overall_score', 0) == 0:
                logger.info(f"【存储】跳过异常结果的存储: {symbol}")
                return
            
            # 准备诊断报告数据
            from .storage.models import DiagnosisReport
            
            diagnosis_report = DiagnosisReport(
                symbol=symbol,
                name=diagnosis_data.get('name', symbol),
                date=datetime.now().date(),
                current_price=diagnosis_data.get('current_price', 0.0),
                overall_score=diagnosis_data.get('overall_score', 0.0),
                fundamental_score=diagnosis_data.get('fundamental_score', 0.0),
                technical_score=diagnosis_data.get('technical_score', 0.0),
                valuation_score=diagnosis_data.get('valuation_score', 0.0),
                capital_score=diagnosis_data.get('capital_score', 0.0),
                risk_level=diagnosis_data.get('risk_level', 'medium'),
                recommendation=diagnosis_data.get('recommendation', 'hold'),
                target_price=diagnosis_data.get('target_price', 0.0),
                stop_loss=diagnosis_data.get('stop_loss', 0.0),
                support=diagnosis_data.get('support', 0.0),
                resistance=diagnosis_data.get('resistance', 0.0),
                buy_price=diagnosis_data.get('buy_price', 0.0),
                sell_price=diagnosis_data.get('sell_price', 0.0),
                investment_reason=diagnosis_data.get('investment_reason', ''),
                key_indicators=diagnosis_data.get('key_indicators', []),
                risk_warnings=diagnosis_data.get('risk_warnings', []),
                timestamp=datetime.now()
            )
            
            # 使用data_service存储诊断报告
            record_id = data_service.save_diagnosis_report(diagnosis_report)
            
            logger.info(f"【存储】成功存储诊断报告到数据库: {symbol} (记录ID: {record_id})")
            
        except Exception as e:
            logger.error(f"【存储】存储诊断报告到数据库失败: {str(e)}", exc_info=True)

    def query_diagnosis_reports(self, symbols: str or list, date: str = None) -> Dict[str, Any]:
        """
        按股票代码查询诊断报告
        支持单个股票代码或多个股票代码查询
        使用query_service从数据库查询诊断报告
        
        Args:
            symbols: 股票代码（字符串或列表）
            date: 查询日期（格式：YYYY-MM-DD），未指定时返回最新数据
            
        Returns:
            Dict: 查询结果，按股票代码分组
        """
        try:
            # 处理symbols参数，支持字符串或列表
            if isinstance(symbols, str):
                symbols = [symbols]
            
            # 使用query_service查询诊断报告
            results = {}
            found_symbols = []
            missing_symbols = []
            
            if date:
                # 指定日期查询
                for symbol in symbols:
                    reports = query_service.get_diagnosis_reports(symbol=symbol, date=date)
                    if reports:
                        # 取最新的一条报告
                        latest_report = reports[0]
                        results[symbol] = {
                            'symbol': symbol,
                            'date': date,
                            'timestamp': latest_report.get('timestamp'),
                            'diagnosis': latest_report
                        }
                        found_symbols.append(symbol)
                    else:
                        missing_symbols.append(symbol)
            else:
                # 未指定日期，获取最新数据
                for symbol in symbols:
                    latest_report = query_service.get_latest_diagnosis(symbol)
                    if latest_report:
                        results[symbol] = {
                            'symbol': symbol,
                            'date': latest_report.get('date'),
                            'timestamp': latest_report.get('timestamp'),
                            'diagnosis': latest_report
                        }
                        found_symbols.append(symbol)
                    else:
                        missing_symbols.append(symbol)
            
            response = {
                "date": date or datetime.now().strftime('%Y-%m-%d'),
                "total_queried": len(symbols),
                "found": len(found_symbols),
                "missing": len(missing_symbols),
                "results": results,
                "found_symbols": found_symbols,
                "missing_symbols": missing_symbols
            }
            
            if missing_symbols:
                response["message"] = f"部分股票无诊断报告数据"
            else:
                response["message"] = f"成功查询{len(found_symbols)}个股票的诊断报告"
            
            logger.info(f"【查询】成功查询诊断报告: 日期={date}, 查询={len(symbols)}个, 找到={len(found_symbols)}个")
            return response
            
        except Exception as e:
            logger.error(f"【查询】查询诊断报告失败: {str(e)}", exc_info=True)
            return {"error": str(e), "symbols": symbols, "date": date or datetime.now().strftime('%Y-%m-%d')}

    def get_all_diagnosis_reports(self) -> Dict[str, Any]:
        """
        获取所有诊断报告
        使用query_service从数据库获取所有诊断报告
        
        Returns:
            Dict: 所有诊断报告数据
        """
        try:
            # 使用query_service获取所有诊断报告
            all_reports = query_service.get_diagnosis_reports()
            
            # 按日期分组数据
            grouped_reports = {}
            for report in all_reports:
                date = report.get('date')
                symbol = report.get('symbol')
                if date not in grouped_reports:
                    grouped_reports[date] = {}
                
                grouped_reports[date][symbol] = {
                    'symbol': symbol,
                    'date': date,
                    'timestamp': report.get('timestamp'),
                    'diagnosis': report
                }
            
            total_reports = len(all_reports)
            total_dates = len(grouped_reports)
            
            logger.info(f"【查询】成功获取所有诊断报告: 共{total_dates}天, {total_reports}条记录")
            
            return {
                "total_dates": total_dates,
                "total_reports": total_reports,
                "data": grouped_reports,
                "message": f"成功获取所有诊断报告数据"
            }
            
        except Exception as e:
            logger.error(f"【查询】获取所有诊断报告失败: {str(e)}", exc_info=True)
            return {"error": str(e), "data": {}}

# 全局服务实例
diagnosis_service = StockDiagnosisService()

# 从交易执行器导入交易相关函数
from .trading_executor import (
    get_user_trade_history,
    get_quant_account_summary,
    execute_daily_quant_trading,
    get_active_quant_orders,
    clear_active_quant_orders,
    buy_stock_with_signal,
    sell_stock_with_reason,
    get_quant_trade_history,
    quant_user_manager,
    QuantTradingSimulator,
    QuantTradeExecutor
)

# 便捷函数
def get_stock_diagnosis(symbol: str) -> Dict[str, Any]:
    """获取个股诊断"""
    return diagnosis_service.get_individual_diagnosis(symbol)

def get_batch_diagnosis(symbols: list) -> list:
    """批量获取个股诊断"""
    results = []
    for symbol in symbols:
        result = diagnosis_service.get_individual_diagnosis(symbol)
        results.append(result)
    return results

def query_diagnosis_reports(symbols: str or list, date: str = None) -> Dict[str, Any]:
    """查询诊断报告（便捷函数）"""
    return diagnosis_service.query_diagnosis_reports(symbols, date)

def get_all_diagnosis_reports() -> Dict[str, Any]:
    """获取所有诊断报告（便捷函数）"""
    return diagnosis_service.get_all_diagnosis_reports()
