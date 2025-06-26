from fastapi import APIRouter, HTTPException, Depends
from app.schemas.trading import TradingRequest, TradingResponse
from app.core.deepseek import DeepseekClient
from app.core.futu_client import FutuClient

router = APIRouter()
deepseek_client = DeepseekClient()
futu_client = FutuClient() # Instantiate FutuClient

@router.post("/analyze", response_model=TradingResponse)
async def analyze_market(request: TradingRequest):
    try:
        # 调用Deepseek API进行分析
        analysis_result = await deepseek_client.analyze(request.symbol, request.timeframe)
        return TradingResponse(
            symbol=request.symbol,
            analysis=analysis_result,
            recommendation="Based on the analysis..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/symbols")
async def get_symbols():
    # 返回可交易的股票列表
    return {
        "symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "HK.00700", "US.AAPL"]
    }

@router.get("/futu/quote")
async def get_futu_quote(symbol: str):
    try:
        data = futu_client.get_realtime_quote(symbol)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/futu/kline")
async def get_futu_kline(symbol: str, ktype: str = 'K_DAY', num: int = 100):
    try:
        data = futu_client.get_kline(symbol, ktype, num)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
