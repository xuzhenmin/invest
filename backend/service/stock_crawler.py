#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一股票爬虫服务
整合港股新闻、财务数据等爬虫功能
"""

import requests
import json
import re
import time
import logging
import urllib.parse
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Union
import random

logger = logging.getLogger(__name__)

class StockCrawler:
    """统一股票爬虫服务"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 港股代码到名称的映射
        self.stock_name_map = {
            '00700': '腾讯控股',
            '09988': '阿里巴巴-SW',
            '03690': '美团-W',
            '01024': '快手-W',
            '02020': '安踏体育',
            '02318': '中国平安',
            '00941': '中国移动',
            '00388': '香港交易所',
            '01398': '工商银行',
            '03988': '中国银行',
            '00939': '建设银行',
            '01299': '友邦保险',
            '02382': '舜宇光学科技',
            '00728': '中国电信',
            '00883': '中国海洋石油',
            '00386': '中国石油化工股份',
            '00857': '中国石油股份',
            '01171': '兖州煤业股份',
            '01088': '中国神华',
            '01810': '小米集团-W',
            '09618': '京东集团-SW',
            '09888': '百度集团-SW',
            '06618': '京东健康',
            '09999': '网易-S',
            '03618': '重庆农村商业银行',
            '06862': '海底捞',
            '02015': '理想汽车-W',
            '09866': '蔚来-SW',
            '02518': '汽车之家-S',
            '09961': '携程集团-S',
            '09626': '哔哩哔哩-SW',
            '06690': '海尔智家',
            '02331': '李宁',
            '01051': '国际商业机器',
        }
    
    def get_stock_name_by_code(self, stock_code: str) -> str:
        """
        根据股票代码获取股票名称
        :param stock_code: 股票代码 (如: 00700)
        :return: 股票名称
        """
        return self.stock_name_map.get(stock_code, stock_code)
    
    # ==================== 港股新闻爬虫 ====================
    
    def generate_callback(self) -> str:
        """
        生成JSONP回调函数名
        :return: 回调函数名
        """
        timestamp = int(time.time() * 1000)
        random_num = random.randint(10000000000000000000, 99999999999999999999)
        return f"jQuery{random_num}_{timestamp}"
    
    def build_search_params(self, keyword: str, page_index: int = 1, page_size: int = 10) -> Dict:
        """
        构建搜索参数
        :param keyword: 搜索关键词
        :param page_index: 页码
        :param page_size: 每页数量
        :return: 参数字典
        """
        param_data = {
            "uid": "5984355543747886",
            "keyword": keyword,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": page_index,
                    "pageSize": page_size,
                    "preTag": "<em>",
                    "postTag": "</em>"
                }
            }
        }
        
        return {
            "cb": self.generate_callback(),
            "param": json.dumps(param_data, ensure_ascii=False),
            "_": int(time.time() * 1000)
        }
    
    def search_news_api(self, keyword: str, max_pages: int = 3) -> List[Dict]:
        """
        通过API搜索新闻
        :param keyword: 搜索关键词
        :param max_pages: 最大页数
        :return: 新闻列表
        """
        news_list = []
        base_api_url = "https://search-api-web.eastmoney.com/search/jsonp"
        
        try:
            for page in range(1, max_pages + 1):
                params = self.build_search_params(keyword, page, 10)
                
                logger.info(f"正在搜索第{page}页: {keyword}")
                
                response = self.session.get(base_api_url, params=params, timeout=10)
                response.raise_for_status()
                
                logger.info(f"API响应状态码: {response.status_code}")
                logger.debug(f"API响应内容: {response.text[:500]}...")
                
                # 解析JSONP响应
                try:
                    # 提取JSON部分
                    json_text = response.text
                    # 移除JSONP回调函数包装
                    if json_text.startswith('jQuery') and '(' in json_text and json_text.endswith(')'):
                        json_text = json_text[json_text.find('(') + 1:json_text.rfind(')')]
                    
                    data = json.loads(json_text)
                    
                    if data.get('code') == 0 and 'result' in data:
                        result = data['result']
                        if 'cmsArticleWebOld' in result:
                            articles = result['cmsArticleWebOld']
                            logger.info(f"第{page}页获取到 {len(articles)} 条新闻")
                            
                            for article in articles:
                                news_data = {
                                    'title': article.get('title', ''),
                                    'content': article.get('content', ''),
                                    'publish_time': article.get('date', ''),
                                    'source': article.get('mediaName', '东方财富网'),
                                    'url': article.get('url', ''),
                                    'code': article.get('code', '')
                                }
                                
                                # 清理标题和内容中的HTML标签
                                news_data['title'] = self.clean_html_tags(news_data['title'])
                                news_data['content'] = self.clean_html_tags(news_data['content'])
                                
                                if news_data['title'] and news_data['url']:
                                    news_list.append(news_data)
                        else:
                            logger.warning(f"第{page}页未找到新闻数据")
                    else:
                        logger.warning(f"API返回错误: {data.get('msg', 'Unknown error')}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"解析JSON失败: {e}")
                    logger.debug(f"原始响应: {response.text}")
                except Exception as e:
                    logger.error(f"处理API响应失败: {e}")
                
                # 如果当前页没有新闻，停止翻页
                if not articles:
                    logger.info(f"第{page}页没有新闻，停止翻页")
                    break
                
                # 避免请求过快
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"API搜索新闻失败: {e}")
        
        return news_list
    
    def clean_html_tags(self, text: str) -> str:
        """
        清理HTML标签
        :param text: 包含HTML标签的文本
        :return: 清理后的文本
        """
        if not text:
            return ""
        
        # 移除HTML标签
        clean_text = re.sub(r'<[^>]+>', '', text)
        # 移除多余的空格
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        # 移除下划线（可能是搜索高亮）
        clean_text = clean_text.replace('_', '')
        
        return clean_text
    
    def get_news_content(self, url: str) -> str:
        """
        获取新闻详细内容
        :param url: 新闻链接
        :return: 新闻内容
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种内容选择器
            content_selectors = [
                'div[class*="content"]',
                'div[class*="article"]',
                'div[class*="text"]',
                'div[class*="body"]',
                'article',
                '.news-content',
                '.article-content',
                '.content-body',
                '.detail-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 移除脚本和样式
                    for script in content_elem(["script", "style"]):
                        script.decompose()
                    
                    content = content_elem.get_text(strip=True)
                    if content and len(content) > 50:  # 确保内容足够长
                        return self.clean_html_tags(content)
            
            # 如果找不到特定内容区域，返回页面标题
            title_elem = soup.find('title')
            if title_elem:
                return title_elem.get_text(strip=True)
            
            return "内容获取失败"
            
        except Exception as e:
            logger.error(f"获取新闻内容失败: {e}")
            return "内容获取失败"
    
    def get_hk_stock_news(self, stock_code: str, max_news: int = 20) -> List[Dict]:
        """
        获取港股新闻
        :param stock_code: 股票代码 (如: 00700)
        :param max_news: 最大新闻数量
        :return: 新闻列表
        """
        try:
            # 获取股票名称
            stock_name = self.get_stock_name_by_code(stock_code)
            logger.info(f"获取股票 {stock_code} ({stock_name}) 的新闻")
            
            # 搜索新闻
            news_list = self.search_news_api(stock_name, max_pages=3)
            
            # 获取详细内容
            detailed_news = []
            for news in news_list[:max_news]:
                try:
                    # 如果API返回的内容不够详细，尝试获取详细内容
                    if news.get('url') and len(news.get('content', '')) < 100:
                        content = self.get_news_content(news['url'])
                        if content and content != "内容获取失败":
                            news['content'] = content
                    
                    detailed_news.append(news)
                    
                    # 避免请求过快
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"获取新闻详细内容失败: {e}")
                    detailed_news.append(news)  # 即使获取详细内容失败，也保留基本信息
            
            # 按时间排序
            detailed_news.sort(key=lambda x: x.get('publish_time', ''), reverse=True)
            
            logger.info(f"成功获取 {len(detailed_news)} 条新闻")
            return detailed_news
            
        except Exception as e:
            logger.error(f"获取港股新闻失败: {e}")
            return []
    
    # ==================== 港股财务数据爬虫 ====================
    
    def fetch_hk_financials_from_eastmoney(self, stock_code: str) -> pd.DataFrame:
        """
        爬取东方财富港股F10财务数据，返回DataFrame
        :param stock_code: 股票代码，如 '01810'（不带.HK后缀）
        :return: 财务数据DataFrame
        """
        # 使用新的数据接口
        url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        
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
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
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
    
    def get_hk_stock_financials(self, stock_code: str) -> pd.DataFrame:
        """
        获取港股财务数据（标准化格式）
        :param stock_code: 股票代码，如 '01810'（不带.HK后缀）
        :return: 标准化的财务数据DataFrame
        """
        try:
            df = self.fetch_hk_financials_from_eastmoney(stock_code)
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
                    logger.warning(f"[get_hk_stock_financials] 港股财务数据报告期排序异常: {e}")
                
                # 列名转为字符串，防止前端key为数字
                pivot_df.columns = [str(col) for col in pivot_df.columns]
                return pivot_df
            
            return df
            
        except Exception as e:
            logger.error(f"[get_hk_stock_financials] 港股财务数据异常: {e}")
            return pd.DataFrame()

# 创建全局实例
stock_crawler = StockCrawler()

# ==================== 便捷函数 ====================

def get_hk_stock_news(stock_code: str, max_news: int = 20) -> List[Dict]:
    """
    获取港股新闻的便捷函数
    :param stock_code: 股票代码 (如: 00700)
    :param max_news: 最大新闻数量
    :return: 新闻列表
    """
    return stock_crawler.get_hk_stock_news(stock_code, max_news)

def get_hk_stock_financials(stock_code: str) -> pd.DataFrame:
    """
    获取港股财务数据的便捷函数
    :param stock_code: 股票代码，如 '01810'（不带.HK后缀）
    :return: 财务数据DataFrame
    """
    return stock_crawler.get_hk_stock_financials(stock_code)

def fetch_hk_financials_from_eastmoney(stock_code: str) -> pd.DataFrame:
    """
    爬取东方财富港股F10财务数据的便捷函数
    :param stock_code: 股票代码，如 '01810'（不带.HK后缀）
    :return: 财务数据DataFrame
    """
    return stock_crawler.fetch_hk_financials_from_eastmoney(stock_code)

if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 测试获取腾讯控股的新闻
    print("=== 测试港股新闻爬虫 ===")
    news = get_hk_stock_news("00700", max_news=3)
    print(f"获取到 {len(news)} 条新闻")
    
    # 测试获取小米集团的财务数据
    print("\n=== 测试港股财务数据爬虫 ===")
    financials = get_hk_stock_financials("01810")
    print(f"获取到财务数据，形状: {financials.shape}")
    if not financials.empty:
        print(f"列名: {list(financials.columns)}")
        print(f"前几行数据:\n{financials.head()}") 
