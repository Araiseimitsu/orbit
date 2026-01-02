"""
ORBIT MVP - File Operations Actions
ファイル読み書きアクション
"""
import logging
from pathlib import Path
from typing import Any

from ..core.registry import register_action

logger = logging.getLogger(__name__)


@register_action("file_write")
async def action_file_write(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ファイル書き込みアクション

    params:
        path: 出力パス（相対パスはプロジェクトルート基準）
        content: 書き込む内容（テンプレート展開済み）
        encoding: 文字コード（デフォルト: utf-8）

    returns:
        written: True/False
        path: 書き込んだファイルパス
        size: ファイルサイズ（bytes）
    """
    path_str = params.get("path", "")
    content = params.get("content", "")
    encoding = params.get("encoding", "utf-8")

    if not path_str:
        raise ValueError("path is required")

    # パス解決（base_dir が context に設定されていればそこを基準にする）
    base_dir = context.get("base_dir", Path.cwd())
    file_path = Path(path_str)

    if not file_path.is_absolute():
        file_path = base_dir / file_path

    # 親ディレクトリ作成
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 書き込み
    file_path.write_text(content, encoding=encoding)
    size = file_path.stat().st_size

    logger.info(f"File written: {file_path} ({size} bytes)")

    return {
        "written": True,
        "path": str(file_path),
        "size": size
    }


@register_action("file_read")
async def action_file_read(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ファイル読み込みアクション

    params:
        path: 読み込むファイルパス
        encoding: 文字コード（デフォルト: utf-8）

    returns:
        content: ファイル内容
        path: 読み込んだファイルパス
        size: ファイルサイズ（bytes）
    """
    path_str = params.get("path", "")
    encoding = params.get("encoding", "utf-8")

    if not path_str:
        raise ValueError("path is required")

    base_dir = context.get("base_dir", Path.cwd())
    file_path = Path(path_str)

    if not file_path.is_absolute():
        file_path = base_dir / file_path

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = file_path.read_text(encoding=encoding)
    size = file_path.stat().st_size

    logger.info(f"File read: {file_path} ({size} bytes)")

    return {
        "content": content,
        "path": str(file_path),
        "size": size
    }
