from pydantic import BaseModel
from typing import List, Optional

class TradingRequest(BaseModel):
    symbol: str
    timeframe: str
    indicators: Optional[List[str]] = None

class TradingResponse(BaseModel):
    symbol: str
    analysis: dict
    recommendation: str 
