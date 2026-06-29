"""涨停数据 API 路由"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

limit_up_bp = Blueprint('limit_up', __name__, url_prefix='/api/limit-up')

_service = None
_init_done = False


def _ensure_init():
    global _service, _init_done
    if _init_done:
        return
    from .limit_up_service import limit_up_service
    _service = limit_up_service
    _init_done = True


@limit_up_bp.route('/collect', methods=['POST'])
def collect():
    """触发涨停数据采集（可指定日期）"""
    _ensure_init()
    try:
        body = request.get_json(force=True) or {}
        date = body.get('date') or None
        result = _service.collect_today(date)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[limit-up/collect] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@limit_up_bp.route('/today', methods=['GET'])
def today():
    """获取当日（或最近交易日）涨停复盘数据"""
    _ensure_init()
    try:
        date = request.args.get('date') or None
        result = _service.get_daily_summary(date)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[limit-up/today] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@limit_up_bp.route('/trend', methods=['GET'])
def trend():
    """获取近 N 日涨停数量趋势"""
    _ensure_init()
    try:
        days = request.args.get('days', 15, type=int)
        result = _service.get_trend(days)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[limit-up/trend] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@limit_up_bp.route('/backfill', methods=['POST'])
def backfill():
    """回补历史数据"""
    _ensure_init()
    try:
        body = request.get_json(force=True) or {}
        days = body.get('days', 10)
        result = _service.backfill(days)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[limit-up/backfill] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
