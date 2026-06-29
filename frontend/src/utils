import GIF from 'gif.js';

const COLS      = 2;
const CHART_W   = 144;
const CHART_H   = 58;
const LABEL_H   = 20;
const CELL_PAD  = 6;
const CELL_W    = CHART_W + CELL_PAD * 2;
const CELL_H    = LABEL_H + CHART_H + CELL_PAD;
const ROW_GAP   = 8;
const OUTER_PAD = 10;
const HEADER_H  = 52;
const FOOTER_H  = 24;
const CANVAS_W  = OUTER_PAD + COLS * CELL_W + (COLS - 1) * ROW_GAP + OUTER_PAD;

const C = {
  bg:         '#080f1c',
  cellBg:     '#0d1320',
  cellBorder: '#1a2535',
  baseline:   '#2c3548',
  text:       '#9fb4c6',
  title:      '#c2d6ea',
  sub:        '#3a5268',
  footer:     '#253444',
  up:         '#ff5060',
  down:       '#28c96a',
};

function drawChart(ctx, stock, points, prevClose, cellX, cellY, progress) {
  const prices = (points || []).map(p => p.price);
  const hasData = prices.length >= 2;

  const ref = prevClose ?? prices[0] ?? 0;
  const allP = ref ? [...prices, ref] : prices;
  const minP = hasData ? Math.min(...allP) : 0;
  const maxP = hasData ? Math.max(...allP) : 1;
  const range = maxP - minP || ref * 0.001 || 0.01;

  const cw = CHART_W, ch = CHART_H;
  const cx = cellX + CELL_PAD;
  const cy = cellY + LABEL_H;

  const toX = i => cx + (i / (prices.length - 1)) * cw;
  const toY = p => cy + ch - ((p - minP) / range) * ch;

  const lastIdx = hasData ? Math.max(1, Math.floor(progress * (prices.length - 1))) : 0;
  const lastPrice = prices[lastIdx] ?? ref;
  const isUp = lastPrice >= ref;
  const color = isUp ? C.up : C.down;
  const changePct = ref ? ((lastPrice - ref) / ref * 100).toFixed(2) : '0.00';

  ctx.fillStyle = C.cellBg;
  ctx.fillRect(cellX, cellY - CELL_PAD / 2, CELL_W, CELL_H);
  ctx.strokeStyle = C.cellBorder;
  ctx.lineWidth = 0.5;
  ctx.strokeRect(cellX + 0.5, cellY - CELL_PAD / 2 + 0.5, CELL_W - 1, CELL_H - 1);

  ctx.fillStyle = C.text;
  ctx.font = '600 10px "PingFang SC", Arial, sans-serif';
  ctx.fillText(stock.stock_name.slice(0, 6), cellX + CELL_PAD, cellY + 13);

  ctx.fillStyle = color;
  ctx.font = '700 10px Arial, monospace';
  const pctText = `${isUp && hasData ? '+' : ''}${hasData ? changePct + '%' : '--'}`;
  const tw = ctx.measureText(pctText).width;
  ctx.fillText(pctText, cellX + CELL_W - CELL_PAD - tw, cellY + 13);

  if (!hasData) return;

  const refY = toY(ref);
  ctx.save();
  ctx.setLineDash([3, 2]);
  ctx.strokeStyle = C.baseline;
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  ctx.moveTo(cx, refY);
  ctx.lineTo(cx + cw, refY);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  if (lastIdx >= 1) {
    const grad = ctx.createLinearGradient(0, cy, 0, cy + ch);
    grad.addColorStop(0, isUp ? 'rgba(255,80,96,0.28)' : 'rgba(40,201,106,0.28)');
    grad.addColorStop(1, 'rgba(8,15,28,0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(prices[0]));
    for (let i = 1; i <= lastIdx; i++) ctx.lineTo(toX(i), toY(prices[i]));
    ctx.lineTo(toX(lastIdx), cy + ch);
    ctx.lineTo(cx, cy + ch);
    ctx.closePath();
    ctx.fill();
  }

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(prices[0]));
  for (let i = 1; i <= lastIdx; i++) ctx.lineTo(toX(i), toY(prices[i]));
  ctx.stroke();

  ctx.fillStyle = C.sub;
  ctx.font = '7px Arial, monospace';
  ctx.fillText('09:30', cx, cy + ch + 9);
  ctx.fillText('15:00', cx + cw - 24, cy + ch + 9);
}

export function generateSectorGif(sector, stockData, date, onProgress) {
  return new Promise((resolve, reject) => {
    const stocks  = (sector.stocks || []).slice(0, 8);
    const rows    = Math.ceil(stocks.length / COLS);
    const CANVAS_H = HEADER_H + rows * (CELL_H + ROW_GAP) + FOOTER_H;

    const canvas = document.createElement('canvas');
    canvas.width  = CANVAS_W;
    canvas.height = CANVAS_H;
    const ctx = canvas.getContext('2d');

    const gif = new GIF({
      workers: 2,
      quality: 8,
      workerScript: '/gif.worker.js',
      width: CANVAS_W,
      height: CANVAS_H,
      repeat: 0,
    });

    const FRAMES = 200;

    const drawFrame = (progress) => {
      ctx.fillStyle = C.bg;
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

      const beam = ctx.createLinearGradient(0, 0, CANVAS_W, 0);
      beam.addColorStop(0,   '#080f1c');
      beam.addColorStop(0.5, '#12253a');
      beam.addColorStop(1,   '#080f1c');
      ctx.fillStyle = beam;
      ctx.fillRect(0, 0, CANVAS_W, 1);

      ctx.fillStyle = C.title;
      ctx.font = '700 14px "PingFang SC", Arial, sans-serif';
      ctx.fillText(sector.industry, OUTER_PAD, 22);

      ctx.fillStyle = C.sub;
      ctx.font = '10px "PingFang SC", Arial, sans-serif';
      ctx.fillText(`${stocks.length} 只涨停 · 分时走势 · ${date}`, OUTER_PAD, 38);

      ctx.strokeStyle = '#1a2535';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(OUTER_PAD, HEADER_H - 4);
      ctx.lineTo(CANVAS_W - OUTER_PAD, HEADER_H - 4);
      ctx.stroke();

      stocks.forEach((stock, i) => {
        const col  = i % COLS;
        const row  = Math.floor(i / COLS);
        const cellX = OUTER_PAD + col * (CELL_W + ROW_GAP);
        const cellY = HEADER_H + row * (CELL_H + ROW_GAP) + CELL_PAD;
        const data  = stockData[stock.stock_code] || { points: [], prevClose: null };
        drawChart(ctx, stock, data.points, data.prevClose, cellX, cellY, progress);
      });

      ctx.fillStyle = C.footer;
      ctx.font = '8px Arial, sans-serif';
      ctx.fillText('数据来源：公开数据 · 仅供参考', OUTER_PAD, CANVAS_H - 8);
    };

    for (let f = 0; f <= FRAMES; f++) {
      drawFrame(f / FRAMES);
      gif.addFrame(canvas, { delay: 40, copy: true });
      onProgress?.(Math.round((f / FRAMES) * 85));
    }

    drawFrame(1);
    gif.addFrame(canvas, { delay: 2000, copy: true });

    gif.on('progress', p => onProgress?.(85 + Math.round(p * 14)));

    gif.on('finished', (blob) => {
      onProgress?.(100);
      const url = URL.createObjectURL(blob);
      const a   = document.createElement('a');
      a.href     = url;
      a.download = `${sector.industry}_分时走势_${date}.gif`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
      resolve();
    });

    gif.on('error', reject);
    gif.render();
  });
}
