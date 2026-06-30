"""内容运营 API 路由"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

content_bp = Blueprint('content_ops', __name__, url_prefix='/api/content')

_service = None
_init_done = False


def _ensure_init():
    global _service, _init_done
    if _init_done:
        return
    from .content_service import ContentOpsService
    _service = ContentOpsService()
    _init_done = True
    logger.info("[content_ops] 模块初始化完成")


@content_bp.route('/generate-material', methods=['POST'])
def generate_material():
    """阶段1：生成素材（市场话题+行业+个股）"""
    _ensure_init()
    try:
        result = _service.generate_material()
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[content/generate-material] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@content_bp.route('/format', methods=['POST'])
def format_content():
    """阶段2：将素材转写为指定平台内容"""
    _ensure_init()
    try:
        body = request.get_json(force=True, silent=True) or {}
        content_id = body.get('content_id')
        if not content_id:
            return jsonify({'success': False, 'message': '缺少 content_id'}), 400
        platform = body.get('platform', 'note')
        user_instructions = body.get('user_instructions') or None
        goal = body.get('goal') or None
        modules = body.get('modules') or None
        result = _service.format_content(
            int(content_id), platform=platform,
            user_instructions=user_instructions, goal=goal, modules=modules
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        logger.error(f"[content/format] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@content_bp.route('/verify', methods=['POST'])
def verify_content():
    """阶段3：对内容进行事实核验"""
    _ensure_init()
    try:
        body = request.get_json(force=True, silent=True) or {}
        content_id = body.get('content_id')
        if not content_id:
            return jsonify({'success': False, 'message': '缺少 content_id'}), 400
        result = _service.verify_content(int(content_id))
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        logger.error(f"[content/verify] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@content_bp.route('/list', methods=['GET'])
def list_content():
    """查询内容列表"""
    _ensure_init()
    try:
        limit = request.args.get('limit', 20, type=int)
        result = _service.get_content_list(limit)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[content/list] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@content_bp.route('/<int:content_id>', methods=['GET'])
def get_content(content_id):
    """查询单条内容详情"""
    _ensure_init()
    try:
        result = _service.get_content_detail(content_id)
        if not result:
            return jsonify({'success': False, 'message': '内容不存在'}), 404
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"[content/{content_id}] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@content_bp.route('/<int:content_id>', methods=['DELETE'])
def delete_content(content_id):
    """删除内容"""
    _ensure_init()
    try:
        ok = _service.delete_content(content_id)
        if not ok:
            return jsonify({'success': False, 'message': '内容不存在'}), 404
        return jsonify({'success': True, 'data': {'deleted': content_id}})
    except Exception as e:
        logger.error(f"[content/delete/{content_id}] 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
