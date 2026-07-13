"""Beyond Compare 适配器（纯 Python 实现）。

使用 difflib 标准库实现文件对比功能，不依赖外部 exe。
支持文本文件差异对比、统一 diff 输出和相似度计算。
"""

import difflib
import os
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult


class BeyondCompareAdapter(BaseToolAdapter):
    """Beyond Compare 文件对比适配器（纯 Python 实现）。

    使用 difflib 进行文件对比，支持:
        - action="compare": 对比两个文本文件，输出差异行数、统一 diff、相似度百分比（默认）
        - action="unified_diff": 仅输出统一 diff 格式的差异
    """

    @property
    def tool_name(self) -> str:
        return "beyond_compare"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return (
            "Beyond Compare 文件对比工具（纯 Python 实现），"
            "基于 difflib 标准库，支持文本文件差异对比、统一 diff 输出和相似度计算"
        )

    @property
    def capabilities(self) -> list[str]:
        return ["file_comparison", "unified_diff", "similarity_analysis"]

    def validate_input(self, params: dict) -> bool:
        """验证输入参数。

        需要 file1 和 file2 两个参数。
        """
        return "file1" in params and "file2" in params

    def _read_file_lines(self, file_path: str) -> list[str]:
        """读取文件内容，按行返回。

        尝试多种编码方式读取文本文件。
        """
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.readlines()
            except UnicodeDecodeError:
                continue
        # 最后尝试忽略错误
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()

    def _compute_similarity(self, lines1: list[str], lines2: list[str]) -> float:
        """计算两个文件的相似度百分比。

        使用 difflib.SequenceMatcher 计算序列相似度。
        """
        if not lines1 and not lines2:
            return 100.0
        if not lines1 or not lines2:
            return 0.0

        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        return round(matcher.ratio() * 100, 2)

    def _compute_diff_count(self, lines1: list[str], lines2: list[str]) -> dict:
        """统计差异行数。

        Returns:
            包含 added_count, removed_count, total_diff_count 的字典。
        """
        differ = difflib.Differ()
        diff_result = list(differ.compare(lines1, lines2))

        added = 0
        removed = 0
        for line in diff_result:
            if line.startswith("+ "):
                added += 1
            elif line.startswith("- "):
                removed += 1

        return {
            "added_count": added,
            "removed_count": removed,
            "total_diff_count": added + removed,
        }

    def _generate_unified_diff(self, lines1: list[str], lines2: list[str],
                               file1_name: str, file2_name: str) -> str:
        """生成统一 diff 格式的差异文本。"""
        diff_lines = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=file1_name,
            tofile=file2_name,
            lineterm="",
        )
        return "\n".join(diff_lines)

    async def run(self, params: dict) -> ToolResult:
        """执行文件对比。

        Args:
            params: 参数字典，必须包含:
                - file1: 第一个文件路径
                - file2: 第二个文件路径
                可选:
                - action: "compare"（默认）或 "unified_diff"

        Returns:
            ToolResult 包含对比结果。
        """
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 需要提供 file1 和 file2 两个文件路径"
            )

        file1 = params["file1"]
        file2 = params["file2"]
        action = params.get("action", "compare")

        # 验证文件存在
        if not os.path.isfile(file1):
            return ToolResult(
                success=False,
                error=f"文件未找到: {file1}"
            )
        if not os.path.isfile(file2):
            return ToolResult(
                success=False,
                error=f"文件未找到: {file2}"
            )

        start = time.perf_counter()

        try:
            lines1 = self._read_file_lines(file1)
            lines2 = self._read_file_lines(file2)

            file1_name = os.path.basename(file1)
            file2_name = os.path.basename(file2)

            if action == "unified_diff":
                diff_text = self._generate_unified_diff(lines1, lines2, file1_name, file2_name)
                diff_count = self._compute_diff_count(lines1, lines2)

                data = {
                    "action": "unified_diff",
                    "file1": file1,
                    "file2": file2,
                    "file1_lines": len(lines1),
                    "file2_lines": len(lines2),
                    "unified_diff": diff_text,
                    "diff_empty": diff_text == "",
                    "added_count": diff_count["added_count"],
                    "removed_count": diff_count["removed_count"],
                    "total_diff_count": diff_count["total_diff_count"],
                }
            else:
                # action == "compare" (默认)
                diff_count = self._compute_diff_count(lines1, lines2)
                similarity = self._compute_similarity(lines1, lines2)
                unified_diff_text = self._generate_unified_diff(lines1, lines2, file1_name, file2_name)

                differ = difflib.Differ()
                full_diff = list(differ.compare(lines1, lines2))

                data = {
                    "action": "compare",
                    "file1": file1,
                    "file2": file2,
                    "file1_lines": len(lines1),
                    "file2_lines": len(lines2),
                    "added_count": diff_count["added_count"],
                    "removed_count": diff_count["removed_count"],
                    "total_diff_count": diff_count["total_diff_count"],
                    "similarity_percent": similarity,
                    "identical": diff_count["total_diff_count"] == 0,
                    "unified_diff": unified_diff_text,
                    "full_diff": [line.rstrip("\n") for line in full_diff],
                }

            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except PermissionError as e:
            return ToolResult(
                success=False,
                error=f"文件读取权限不足: {str(e)}",
                duration=time.perf_counter() - start,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"文件对比执行异常: {str(e)}",
                duration=time.perf_counter() - start,
            )