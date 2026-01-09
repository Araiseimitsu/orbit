"""
ORBIT MVP - Subworkflow Action
他のワークフローを呼び出すアクション
"""
import logging
from pathlib import Path
from typing import Any

from ..core.loader import WorkflowLoader
from ..core.executor import Executor
from ..core.templating import render_params
from ..core.models import Workflow
from ..core.registry import register_action

logger = logging.getLogger(__name__)

# 最大呼び出し深度（循環参照防止用）
DEFAULT_MAX_DEPTH = 5

# 呼び出しチェーンのキー（context内）
CALL_CHAIN_KEY = "_call_chain"


@register_action(
    "subworkflow",
    metadata={
        "title": "サブワークフロー",
        "description": "他のワークフローを呼び出して実行します。再利用可能なワークフローモジュールを作成できます。",
        "category": "制御フロー",
        "color": "#8b5cf6",
        "params": [
            {
                "key": "workflow_name",
                "description": "呼び出すワークフロー名（YAMLファイル名）",
                "required": True,
                "example": "data_processing"
            },
            {
                "key": "max_depth",
                "description": "最大呼び出し深度（デフォルト: 5）",
                "required": False,
                "default": 5,
                "example": 5
            },
            {
                "key": "continue_on_error",
                "description": "エラー時も続行するか（デフォルト: false）",
                "required": False,
                "default": False,
                "example": False
            }
        ],
        "outputs": [
            {"key": "success", "description": "成功フラグ"},
            {"key": "status", "description": "実行ステータス (success/failed/skipped)"},
            {"key": "run_id", "description": "サブワークフローの実行ID"},
            {"key": "results", "description": "各ステップの実行結果 {step_id: {...}}"},
            {"key": "error", "description": "エラーメッセージ（失敗時）"}
        ],
        "example": """
steps:
  - id: prepare_data
    type: log
    params:
      message: "Preparing data"
  
  - id: call_subworkflow
    type: subworkflow
    params:
      workflow_name: data_processing
      source_data: "{{ prepare_data.result }}"
  
  - id: use_result
    type: log
    params:
      message: "Result: {{ call_subworkflow.results.step_1.output }}"
"""
    }
)
async def action_subworkflow(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    サブワークフローアクション
    
    params:
        workflow_name: 呼び出すワークフロー名（必須）
        max_depth: 最大呼び出し深度（デフォルト: 5）
        continue_on_error: エラー時も続行するか（デフォルト: false）
        [他の任意のパラメータ]: すべてサブワークフローのcontextに渡される
    
    returns:
        success: 成功フラグ
        status: 実行ステータス
        run_id: サブワークフローの実行ID
        results: 各ステップの実行結果
        error: エラーメッセージ（失敗時）
    """
    workflow_name = params.get("workflow_name")
    if not workflow_name:
        raise ValueError("workflow_name is required")
    
    max_depth = int(params.get("max_depth", DEFAULT_MAX_DEPTH))
    continue_on_error = params.get("continue_on_error", False)
    
    # 呼び出しチェーンを取得（または初期化）
    call_chain = context.get(CALL_CHAIN_KEY, [])
    
    # 循環参照チェック
    if workflow_name in call_chain:
        error_msg = f"Circular dependency detected: {workflow_name} is already in call chain: {' -> '.join(call_chain)}"
        logger.error(error_msg)
        if continue_on_error:
            return {
                "success": False,
                "status": "failed",
                "run_id": None,
                "results": {},
                "error": error_msg
            }
        raise RecursionError(error_msg)
    
    # 深度制限チェック
    if len(call_chain) >= max_depth:
        error_msg = f"Maximum subworkflow depth ({max_depth}) exceeded. Call chain: {' -> '.join(call_chain)}"
        logger.error(error_msg)
        if continue_on_error:
            return {
                "success": False,
                "status": "failed",
                "run_id": None,
                "results": {},
                "error": error_msg
            }
        raise RecursionError(error_msg)
    
    # ワークフローローダーとエグゼキューターの準備
    base_dir = context.get("base_dir", Path.cwd())
    workflows_dir = base_dir / "workflows"
    loader = WorkflowLoader(workflows_dir)
    executor = Executor(base_dir)
    
    # ワークフローを読み込み
    workflow, error = loader.load_workflow(workflow_name)
    if error:
        error_msg = f"Failed to load workflow '{workflow_name}': {error}"
        logger.error(error_msg)
        if continue_on_error:
            return {
                "success": False,
                "status": "failed",
                "run_id": None,
                "results": {},
                "error": error_msg
            }
        raise FileNotFoundError(error_msg)
    
    # パラメータをテンプレートレンダリング
    rendered_params = render_params(params, context)
    
    # サブワークフロー用のcontextを作成
    # - 基本変数は引き継ぐ（空のcontextで初期化してrun()内で基本変数を追加させる）
    sub_context: dict[str, Any] = {
        "run_id": context.get("run_id"),
        "workflow": workflow_name,
        "now": context.get("now"),
        "base_dir": context.get("base_dir"),
        "today": context.get("today"),
        "yesterday": context.get("yesterday"),
        "tomorrow": context.get("tomorrow"),
        "today_ymd": context.get("today_ymd"),
        "now_ymd_hms": context.get("now_ymd_hms"),
    }
    
    # - 呼び出しチェーンを更新
    sub_context[CALL_CHAIN_KEY] = call_chain + [workflow_name]
    
    # - 明示的に渡されたパラメータを追加（workflow_name, max_depth, continue_on_errorは除く）
    param_keys_to_exclude = {"workflow_name", "max_depth", "continue_on_error"}
    for key, value in rendered_params.items():
        if key not in param_keys_to_exclude:
            sub_context[key] = value
    
    # ワークフローを実行（contextを渡す）
    try:
        run_log = await executor.run(workflow, context=sub_context)
        
        # 結果を整形
        results = {}
        for step in run_log.steps:
            if step["status"] != "skipped":
                results[step["id"]] = step.get("result", {})
        
        status = run_log.status
        success = status == "success"
        error_msg = run_log.error if not success else None
        
        logger.info(
            f"Subworkflow completed: {workflow_name} "
            f"(run_id: {run_log.run_id}, status: {status})"
        )
        
        return {
            "success": success,
            "status": status,
            "run_id": run_log.run_id,
            "results": results,
            "error": error_msg
        }
    
    except Exception as e:
        error_msg = f"Subworkflow execution error: {workflow_name} - {e}"
        logger.exception(error_msg)
        
        if continue_on_error:
            return {
                "success": False,
                "status": "failed",
                "run_id": None,
                "results": {},
                "error": error_msg
            }
        
        raise
