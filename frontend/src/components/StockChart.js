import React, { useEffect, useState } from 'react';

const StockChart = ({ stockCode }) => {
    const [stockData, setStockData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                setError(null);
                const response = await fetch(`http://localhost:5001/api/stock/${stockCode}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log('Received data:', data);
                setStockData(data);
            } catch (error) {
                console.error('Error fetching stock data:', error);
                setError(error.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [stockCode]);

    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>Error: {error}</div>;
    }

    if (!stockData) {
        return <div>No data available</div>;
    }

    return (
        <div className="stock-info">
            <h2>{stockData.name} ({stockData.code})</h2>
            <div className="price-info">
                <p>Current Price: {stockData.current_price}</p>
                <p>Open: {stockData.open_price}</p>
                <p>High: {stockData.high_price}</p>
                <p>Low: {stockData.low_price}</p>
                <p>Previous Close: {stockData.pre_close}</p>
                <p>Volume: {stockData.volume}</p>
                <p>Turnover: {stockData.turnover}</p>
                <p>Last Update: {stockData.update_time}</p>
            </div>
        </div>
    );
};

export default StockChart; 
