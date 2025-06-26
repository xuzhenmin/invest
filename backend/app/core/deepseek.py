import os
from typing import Dict, Any
import requests
from dotenv import load_dotenv

load_dotenv()

class DeepseekClient:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")
        
    async def analyze(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        调用Deepseek API进行市场分析
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "analysis_type": "technical"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/analyze",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Deepseek API调用失败: {str(e)}") 
