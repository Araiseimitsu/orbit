"""
ORBIT MVP - File Operations Actions
ファイル読み書きアクション
"""
import logging
import shutil
from pathlib import Path
from typing import Any

from ..core.registry import register_action

logger = logging.getLogger(__name__)


@register_action(
    "file_write",
    metadata={
        "title": "ファイル書き込み",
        "description": "指定パスへ内容を書き込みます（相対パスはプロジェクトルート基準）。",
        "category": "ファイル",
        "color": "#3b82f6",
        "params": [
            {
                "key": "path",
                "description": "出力先パス",
                "required": True,
                "example": "runs/output/{{ run_id }}.txt"
            },
            {
                "key": "content",
                "description": "書き込む内容",
                "required": True,
                "example": "結果: {{ step_1.text }}"
            },
            {
                "key": "encoding",
                "description": "文字コード",
                "required": False,
                "default": "utf-8",
                "example": "utf-8"
            }
        ],
        "outputs": [
            {"key": "written", "description": "書き込み成功フラグ"},
            {"key": "path", "description": "書き込んだパス"},
            {"key": "size", "description": "ファイルサイズ（bytes）"}
        ]
    }
)
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


@register_action(
    "file_read",
    metadata={
        "title": "ファイル読み込み",
        "description": "指定パスの内容を読み込みます（相対パスはプロジェクトルート基準）。",
        "category": "ファイル",
        "color": "#3b82f6",
        "params": [
            {
                "key": "path",
                "description": "読み込み元パス",
                "required": True,
                "example": "runs/output/{{ run_id }}.txt"
            },
            {
                "key": "encoding",
                "description": "文字コード",
                "required": False,
                "default": "utf-8",
                "example": "utf-8"
            }
        ],
        "outputs": [
            {"key": "content", "description": "ファイル内容"},
            {"key": "path", "description": "読み込んだパス"},
            {"key": "size", "description": "ファイルサイズ（bytes）"}
        ]
    }
)
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


@register_action(
    "file_copy",
    metadata={
        "title": "ファイルコピー",
        "description": "ファイルをコピーします（相対パスはプロジェクトルート基準）。",
        "category": "ファイル",
        "color": "#3b82f6",
        "params": [
            {
                "key": "src",
                "description": "コピー元パス",
                "required": True,
                "example": "runs/input/data.txt"
            },
            {
                "key": "dst",
                "description": "コピー先パス",
                "required": True,
                "example": "runs/backup/data_{{ run_id }}.txt"
            },
            {
                "key": "overwrite",
                "description": "上書き許可",
                "required": False,
                "default": False,
                "example": True
            }
        ],
        "outputs": [
            {"key": "copied", "description": "コピー成功フラグ"},
            {"key": "src", "description": "コピー元パス（絶対パス）"},
            {"key": "dst", "description": "コピー先パス（絶対パス）"},
            {"key": "size", "description": "ファイルサイズ（bytes）"}
        ]
    }
)
async def action_file_copy(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ファイルコピーアクション

    params:
        src: コピー元パス（相対パスはプロジェクトルート基準）
        dst: コピー先パス（相対パスはプロジェクトルート基準）
        overwrite: 上書き許可（デフォルト: False）

    returns:
        copied: True/False
        src: コピー元ファイルパス（絶対パス）
        dst: コピー先ファイルパス（絶対パス）
        size: ファイルサイズ（bytes）
    """
    src_str = params.get("src", "")
    dst_str = params.get("dst", "")
    overwrite = params.get("overwrite", False)

    if not src_str:
        raise ValueError("src is required")
    if not dst_str:
        raise ValueError("dst is required")

    base_dir = context.get("base_dir", Path.cwd())

    # コピー元パス解決
    src_path = Path(src_str)
    if not src_path.is_absolute():
        src_path = base_dir / src_path

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")
    if not src_path.is_file():
        raise ValueError(f"Source is not a file: {src_path}")

    # コピー先パス解決
    dst_path = Path(dst_str)
    if not dst_path.is_absolute():
        dst_path = base_dir / dst_path

    # 上書きチェック
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"Destination file already exists: {dst_path} (set overwrite=True to overwrite)")

    # 親ディレクトリ作成
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # コピー実行（メタデータ保持）
    shutil.copy2(src_path, dst_path)
    size = dst_path.stat().st_size

    logger.info(f"File copied: {src_path} -> {dst_path} ({size} bytes)")

    return {
        "copied": True,
        "src": str(src_path),
        "dst": str(dst_path),
        "size": size
    }


@register_action(
    "file_move",
    metadata={
        "title": "ファイル移動",
        "description": "ファイルを移動します（相対パスはプロジェクトルート基準）。",
        "category": "ファイル",
        "color": "#3b82f6",
        "params": [
            {
                "key": "src",
                "description": "移動元パス",
                "required": True,
                "example": "runs/temp/output.txt"
            },
            {
                "key": "dst",
                "description": "移動先パス",
                "required": True,
                "example": "runs/final/output.txt"
            },
            {
                "key": "overwrite",
                "description": "上書き許可",
                "required": False,
                "default": False,
                "example": True
            }
        ],
        "outputs": [
            {"key": "moved", "description": "移動成功フラグ"},
            {"key": "src", "description": "移動元パス（絶対パス）"},
            {"key": "dst", "description": "移動先パス（絶対パス）"},
            {"key": "size", "description": "ファイルサイズ（bytes）"}
        ]
    }
)
async def action_file_move(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ファイル移動アクション

    params:
        src: 移動元パス（相対パスはプロジェクトルート基準）
        dst: 移動先パス（相対パスはプロジェクトルート基準）
        overwrite: 上書き許可（デフォルト: False）

    returns:
        moved: True/False
        src: 移動元ファイルパス（絶対パス）
        dst: 移動先ファイルパス（絶対パス）
        size: ファイルサイズ（bytes）
    """
    src_str = params.get("src", "")
    dst_str = params.get("dst", "")
    overwrite = params.get("overwrite", False)

    if not src_str:
        raise ValueError("src is required")
    if not dst_str:
        raise ValueError("dst is required")

    base_dir = context.get("base_dir", Path.cwd())

    # 移動元パス解決
    src_path = Path(src_str)
    if not src_path.is_absolute():
        src_path = base_dir / src_path

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")
    if not src_path.is_file():
        raise ValueError(f"Source is not a file: {src_path}")

    # 移動先パス解決
    dst_path = Path(dst_str)
    if not dst_path.is_absolute():
        dst_path = base_dir / dst_path

    # 上書きチェック
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"Destination file already exists: {dst_path} (set overwrite=True to overwrite)")

    # 親ディレクトリ作成
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # サイズ記録（移動前に取得）
    size = src_path.stat().st_size

    # 移動実行
    shutil.move(src_path, dst_path)

    logger.info(f"File moved: {src_path} -> {dst_path} ({size} bytes)")

    return {
        "moved": True,
        "src": str(src_path),
        "dst": str(dst_path),
        "size": size
    }


@register_action(
    "file_delete",
    metadata={
        "title": "ファイル削除",
        "description": "ファイルを削除します（相対パスはプロジェクトルート基準）。force=Trueで重要ファイルも削除可能。",
        "category": "ファイル",
        "color": "#ef4444",
        "params": [
            {
                "key": "path",
                "description": "削除対象パス",
                "required": True,
                "example": "runs/temp/{{ run_id }}.txt"
            },
            {
                "key": "force",
                "description": "強制削除（安全確認をスキップ）",
                "required": False,
                "default": False,
                "example": True
            }
        ],
        "outputs": [
            {"key": "deleted", "description": "削除成功フラグ"},
            {"key": "path", "description": "削除したパス（絶対パス）"},
            {"key": "size", "description": "削除したファイルサイズ（bytes）"}
        ]
    }
)
async def action_file_delete(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ファイル削除アクション

    params:
        path: 削除対象パス（相対パスはプロジェクトルート基準）
        force: 強制削除フラグ（デフォルト: False）

    returns:
        deleted: True/False
        path: 削除したファイルパス（絶対パス）
        size: ファイルサイズ（bytes）
    """
    path_str = params.get("path", "")
    force = params.get("force", False)

    if not path_str:
        raise ValueError("path is required")

    base_dir = context.get("base_dir", Path.cwd())

    # パス解決
    file_path = Path(path_str)
    if not file_path.is_absolute():
        file_path = base_dir / file_path

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    # 安全チェック（force=false の場合）
    if not force:
        resolved_path = file_path.resolve()
        resolved_base = base_dir.resolve()

        # プロジェクトルート直下の重要ディレクトリチェック
        protected_patterns = [
            "src/app",
            ".env",
            "secrets",
        ]

        for pattern in protected_patterns:
            protected_path = (resolved_base / pattern).resolve()
            try:
                if resolved_path == protected_path or protected_path in resolved_path.parents or str(protected_path) in str(resolved_path):
                    raise PermissionError(f"Protected path (set force=True to delete): {file_path}")
            except (ValueError, OSError):
                # 異なるドライブなどで比較できない場合はスキップ
                pass

        # workflows ディレクトリの .yaml ファイルチェック
        if "workflows" in resolved_path.parts and resolved_path.suffix == ".yaml":
            raise PermissionError(f"Workflow YAML files are protected (set force=True to delete): {file_path}")

        # 拡張子による警告
        dangerous_extensions = {".py", ".yaml", ".md", ".txt"}
        if resolved_path.suffix.lower() in dangerous_extensions:
            logger.warning(f"Deleting file with extension {resolved_path.suffix}: {file_path}")

    # サイズ記録（削除前に取得）
    size = file_path.stat().st_size

    # 削除実行
    file_path.unlink()

    logger.info(f"File deleted: {file_path} ({size} bytes)")

    return {
        "deleted": True,
        "path": str(file_path),
        "size": size
    }


@register_action(
    "file_rename",
    metadata={
        "title": "ファイルリネーム",
        "description": "ファイル名を変更します（相対パスはプロジェクトルート基準）。同じディレクトリ内でのリネームのみ。",
        "category": "ファイル",
        "color": "#3b82f6",
        "params": [
            {
                "key": "src",
                "description": "リネーム元パス",
                "required": True,
                "example": "runs/data.txt"
            },
            {
                "key": "new_name",
                "description": "新しいファイル名（パスではなく名前のみ）",
                "required": True,
                "example": "data_{{ run_id }}.txt"
            },
            {
                "key": "overwrite",
                "description": "上書き許可",
                "required": False,
                "default": False,
                "example": True
            }
        ],
        "outputs": [
            {"key": "renamed", "description": "リネーム成功フラグ"},
            {"key": "old_path", "description": "リネーム前のパス（絶対パス）"},
            {"key": "new_path", "description": "リネーム後のパス（絶対パス）"}
        ]
    }
)
async def action_file_rename(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ファイルリネームアクション

    params:
        src: リネーム元パス（相対パスはプロジェクトルート基準）
        new_name: 新しいファイル名（名前のみ、パス区切り文字を含まないこと）
        overwrite: 上書き許可（デフォルト: False）

    returns:
        renamed: True/False
        old_path: リネーム前のファイルパス（絶対パス）
        new_path: リネーム後のファイルパス（絶対パス）
    """
    src_str = params.get("src", "")
    new_name = params.get("new_name", "")
    overwrite = params.get("overwrite", False)

    if not src_str:
        raise ValueError("src is required")
    if not new_name:
        raise ValueError("new_name is required")

    base_dir = context.get("base_dir", Path.cwd())

    # リネーム元パス解決
    src_path = Path(src_str)
    if not src_path.is_absolute():
        src_path = base_dir / src_path

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")
    if not src_path.is_file():
        raise ValueError(f"Source is not a file: {src_path}")

    # new_name にパス区切り文字が含まれる場合はエラー
    if "/" in new_name or "\\" in new_name:
        raise ValueError("new_name must be a filename only, not a path")

    # 新しいパスを作成（親ディレクトリは維持）
    new_path = src_path.parent / new_name

    # 上書きチェック
    if new_path.exists() and not overwrite:
        raise FileExistsError(f"File with new name already exists: {new_path} (set overwrite=True to overwrite)")

    # リネーム実行
    src_path.rename(new_path)

    logger.info(f"File renamed: {src_path} -> {new_path}")

    return {
        "renamed": True,
        "old_path": str(src_path),
        "new_path": str(new_path)
    }
