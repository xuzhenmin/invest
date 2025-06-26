import React, { useEffect, useRef } from 'react';
import { Card } from 'antd';

const TradingChart = ({ symbol }) => {
  const containerRef = useRef();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/tv.js';
      script.async = true;
      script.onload = () => {
        if (window.TradingView) {
          new window.TradingView.widget({
            container_id: containerRef.current.id,
            symbol: symbol,
            interval: 'D',
            timezone: 'Asia/Shanghai',
            theme: 'dark',
            style: '1',
            locale: 'zh_CN',
            toolbar_bg: '#f1f3f6',
            enable_publishing: false,
            allow_symbol_change: true,
            save_image: false,
            height: 500,
            width: '100%',
          });
        }
      };
      document.head.appendChild(script);
    }
  }, [symbol]);

  return (
    <Card title={`${symbol} 交易图表`}>
      <div id="tradingview_chart" ref={containerRef} style={{ height: '500px' }} />
    </Card>
  );
};

export default TradingChart; 
