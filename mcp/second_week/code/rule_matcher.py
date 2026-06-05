import os
import csv
from pathlib import Path

UPLOAD_DIR = Path("temp_uploads")


class RuleMatcher:
    def __init__(self):
        self.current_file = None

    def set_current_file(self, filename: str):
        self.current_file = filename

    def _read_csv_preview(self, filename: str, max_lines: int = 10):
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            return None
        
        preview = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i >= max_lines:
                    break
                preview.append(row)
        
        return preview

    def match(self, query: str) -> str:
        query_lower = query.lower()
        
        if any(keyword in query_lower for keyword in ["csv", "数据", "文件", "里面", "有什么"]):
            if self.current_file:
                preview = self._read_csv_preview(self.current_file)
                if preview:
                    headers = preview[0] if preview else []
                    num_rows = sum(1 for _ in open(UPLOAD_DIR / self.current_file, 'r', encoding='utf-8')) - 1
                    return (f"我读取到了你的CSV文件 `{self.current_file}`，\n"
                            f"里面有 {num_rows} 行数据，\n"
                            f"包含以下字段：{', '.join(headers)}。\n\n"
                            f"前5行数据预览：\n{preview[:5]}")
                else:
                    return f"我读取到了你的CSV文件 `{self.current_file}`。"
            else:
                return "你还没有上传CSV文件，请先上传文件再提问。"
        
        elif any(keyword in query_lower for keyword in ["概览", "看看", "分析一下", "基本情况"]):
            if self.current_file:
                return ("好的，我来帮你做EDA分析（模拟）：\n"
                        "【数据概览】\n"
                        "- 数据时间范围：2024-01-01 至 2024-01-31\n"
                        "- 总数据点：31个\n"
                        "- 平均值：1658.06\n"
                        "- 最大值：2600\n"
                        "- 最小值：950")
            else:
                return "请先上传CSV文件再进行分析。"
        
        elif any(keyword in query_lower for keyword in ["上传", "成功", "了吗"]):
            if self.current_file:
                return f"是的，文件 `{self.current_file}` 已上传成功！"
            else:
                return "还没有上传文件，请先选择CSV文件上传。"
        
        elif any(keyword in query_lower for keyword in ["你好", "您好", "hi", "hello"]):
            return "你好！我是鸿溯时间序列数据分析助手，请上传CSV文件开始分析吧。"
        
        else:
            return ("我收到了你的问题！目前我支持以下查询：\n"
                    "1. 问CSV文件内容：如'这个CSV里有什么数据'\n"
                    "2. 问数据概览：如'帮我看看数据的基本情况'\n"
                    "3. 问上传状态：如'上传成功了吗'\n"
                    "4. 打招呼：如'你好'")
