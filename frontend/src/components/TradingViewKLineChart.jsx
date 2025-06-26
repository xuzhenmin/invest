import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

const TradingViewKLineChart = ({ klineData }) => {
  const chartContainerRef = useRef();
  const chartInstanceRef = useRef(null);
  const candleSeriesInstanceRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) {
      console.log("Chart container ref is null on effect run.");
      return;
    }

    // 检查并记录输入数据
    console.log("Received kline data:", klineData);

    const containerWidth = chartContainerRef.current.clientWidth;
    const containerHeight = chartContainerRef.current.clientHeight;

    if (containerWidth === 0 || containerHeight === 0) {
        console.warn("Chart container has zero dimensions. Waiting for resize.");
        return;
    }

    if (chartInstanceRef.current) 
      console.log("Removing previous chart instance.");
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
      candleSeriesInstanceRef.current = null;
    }

    const createChartWithDelay = setTimeout(() => {
      console.log("Attempting to create chart after delay. Container:", chartContainerRef.current);
      const chart = createChart(chartContainerRef.current, {
        width: containerWidth,
        height: containerHeight,
        layout: {
            backgroundColor: '#131722',
            textColor: 'rgba(255, 255, 255, 0.9)',
        },
        grid: {
            vertLines: {
                color: 'rgba(19, 21, 29, 0.9)',
            },
            horzLines: {
                color: 'rgba(19, 21, 29, 0.9)',
            },
        },
        crosshair: {
            mode: 0,
        },
        rightPriceScale: {
            borderColor: 'rgba(197, 203, 206, 0.8)',
        },
        timeScale: {
            borderColor: 'rgba(197, 203, 206, 0.8)',
            timeVisible: true,
            secondsVisible: false,
        },
      });
      console.log("Chart instance created:", chart);

      chartInstanceRef.current = chart;

      if (chartInstanceRef.current) {
        console.log("Attempting to add candlestick series.");
        try {
          candleSeriesInstanceRef.current = chartInstanceRef.current.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderDownColor: '#ef5350',
            borderUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            wickUpColor: '#26a69a',
          });
          console.log("Candlestick series added:", candleSeriesInstanceRef.current);
        } catch (error) {
          console.error("Error adding series:", error);
          // 尝试使用替代方法
          try {
            candleSeriesInstanceRef.current = chartInstanceRef.current.addSeries({
              type: 'Candlestick',
              upColor: '#26a69a',
              downColor: '#ef5350',
              borderDownColor: '#ef5350',
              borderUpColor: '#26a69a',
              wickDownColor: '#ef5350',
              wickUpColor: '#26a69a',
            });
            console.log("Candlestick series added using alternative method:", candleSeriesInstanceRef.current);
          } catch (secondError) {
            console.error("Error adding series with alternative method:", secondError);
          }
        }
      } else {
        console.error("Chart instance is null when trying to add series.");
        return;
      }

      // 格式化数据并记录
      const formattedData = klineData.map(item => {
        const time = new Date(item.time_key).getTime() / 1000;
        const dataPoint = {
          time: time,
          open: parseFloat(item.open_price),
          high: parseFloat(item.high_price),
          low: parseFloat(item.low_price),
          close: parseFloat(item.close_price),
        };
        return dataPoint;
      }).sort((a, b) => a.time - b.time);

      console.log("Formatted data sample:", formattedData.slice(0, 5));

      if (candleSeriesInstanceRef.current) {
        console.log("Setting data to candlestick series.");
        candleSeriesInstanceRef.current.setData(formattedData);
        
        // 设置可见范围以显示所有数据
        if (formattedData.length > 0) {
          const firstTime = formattedData[0].time;
          const lastTime = formattedData[formattedData.length - 1].time;
          chartInstanceRef.current.timeScale().fitContent();
          console.log("Time range set:", { firstTime, lastTime });
        }
      } else {
        console.error("Candlestick series instance is null when trying to set data.");
      }
    }, 100);

    const handleResize = () => {
      if (chartInstanceRef.current && chartContainerRef.current) {
        chartInstanceRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(createChartWithDelay);
      window.removeEventListener('resize', handleResize);
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
      }
      chartInstanceRef.current = null;
      candleSeriesInstanceRef.current = null;
    };
  }, [klineData]);

  return (
    <div ref={chartContainerRef} style={{ width: '100%', height: '400px' }} />
  );
};

export default TradingViewKLineChart; 
