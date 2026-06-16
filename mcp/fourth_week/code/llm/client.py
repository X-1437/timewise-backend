import json

from openai import OpenAI

from config import settings


class LLMClient:
    def __init__(self):
        self._model = settings.openai_model
        self._api_key = settings.openai_api_key
        self._client = (
            OpenAI(api_key=self._api_key, base_url=settings.openai_base_url) if self._api_key else None
        )

    def analyze_intent(self, query: str) -> dict:
        query = (query or "").strip()
        result = self._analyze_intent_with_openai(query) if self._client else None
        normalized = self._normalize_intent(query, result)
        return normalized or self._rule_based_intent(query)

    def _analyze_intent_with_openai(self, query: str) -> dict | None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "upload_data",
                    "description": "确认并展示当前数据文件信息与样例",
                    "parameters": {
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}, "file_id": {"type": "string"}},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "eda_analysis",
                    "description": "执行探索性数据分析（EDA）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "file_id": {"type": "string"},
                            "data_version": {"type": "string", "enum": ["raw", "preprocessed"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "preprocessing",
                    "description": "数据预处理：缺失值填充/异常值移除/类型转换",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "file_id": {"type": "string"},
                            "method": {
                                "type": "string",
                                "enum": ["missing_fill", "outlier_remove", "type_convert"],
                                "default": "missing_fill",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "feature_analysis",
                    "description": "特征分析：趋势、自相关、滚动统计等基础特征",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "file_id": {"type": "string"},
                            "data_version": {"type": "string", "enum": ["raw", "preprocessed"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "naive_forecast",
                    "description": "朴素预测（基线）：next_row/same_time/daily_sum",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "file_id": {"type": "string"},
                            "data_version": {"type": "string", "enum": ["raw", "preprocessed"]},
                            "method": {
                                "type": "string",
                                "enum": ["next_row", "same_time", "daily_sum"],
                                "default": "next_row",
                            },
                            "periods": {"type": "integer", "default": 7},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "export_markdown",
                    "description": "导出 Markdown 报告",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "file_id": {"type": "string"},
                            "scope": {"type": "string", "enum": ["standard_flow"], "default": "standard_flow"},
                        },
                    },
                },
            },
        ]

        system_prompt = (
            "你是一个时间序列数据分析助手。用户会用自然语言描述他们的分析需求，你需要：\n"
            "1. 理解用户的意图\n"
            "2. 选择合适的工具（upload_data/eda_analysis/preprocessing/feature_analysis/naive_forecast/export_markdown）\n"
            "3. 生成工具调用参数（不要求你提供 session_id/file_id；如需要可留空，由系统补齐）\n\n"
            "常用意图对应工具：\n"
            '- "用哪个文件"、"确认文件"、"看看文件信息" → upload_data\n'
            '- "看看数据"、"概览"、"基本情况" → eda_analysis\n'
            '- "清洗数据"、"处理数据"、"预处理"、"处理缺失值"、"处理异常值" → preprocessing\n'
            '- "分析特征"、"相关性"、"趋势分析"、"重要性" → feature_analysis\n'
            '- "预测"、"预报"、"基线预测"、"未来几天" → naive_forecast\n'
            '- "导出"、"导出报告"、"生成报告" → export_markdown\n\n'
            "参数约束：\n"
            '- 若用户明确提到“原始数据/原表/未清洗”，则 data_version=raw\n'
            '- 若用户明确提到“预处理后/清洗后/处理后”，则 data_version=preprocessed\n'
            "- preprocessing.method：仅说“清洗/clean”时，默认 outlier_remove（会先填缺失再移除异常值）\n"
            "- preprocessing.method：仅说“处理缺失/补齐”时，默认 missing_fill\n"
            "- naive_forecast.method 默认 next_row；periods 默认 7\n"
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                return {
                    "tool": tool_call.function.name,
                    "args": json.loads(tool_call.function.arguments),
                }
        except Exception:
            return None

        return None

    def _normalize_intent(self, query: str, result: dict | None) -> dict | None:
        q = (query or "").strip().lower()
        explicit_forecast = any(k in q for k in ["预测", "预报", "future", "forecast", "predict"])
        feature_keywords = ["特征", "相关", "相关性", "important", "importance", "feature"]
        trend_keywords = ["趋势分析", "趋势情况", "trend analysis"]
        data_version = self._extract_data_version(query)

        if any(k in q for k in feature_keywords) and not explicit_forecast:
            return {"tool": "feature_analysis", "args": {"data_version": data_version} if data_version else {}}
        if any(k in q for k in trend_keywords) and not explicit_forecast:
            return {"tool": "feature_analysis", "args": {"data_version": data_version} if data_version else {}}

        if result and data_version and result.get("tool") in {"eda_analysis", "feature_analysis", "naive_forecast"}:
            result = {
                "tool": result["tool"],
                "args": {**dict(result.get("args") or {}), "data_version": data_version},
            }

        return result

    def _extract_data_version(self, query: str) -> str | None:
        q = (query or "").strip().lower()
        raw_keywords = ["原始数据", "原始", "原表", "未清洗", "raw"]
        preprocessed_keywords = ["预处理后", "清洗后", "处理后", "预处理数据", "清洗后的数据", "preprocessed"]
        if any(k in q for k in preprocessed_keywords):
            return "preprocessed"
        if any(k in q for k in raw_keywords):
            return "raw"
        return None

    def _rule_based_intent(self, query: str) -> dict:
        q = (query or "").strip().lower()
        data_version = self._extract_data_version(query)
        if any(k in q for k in ["导出", "报告", "export", "download"]):
            return {"tool": "export_markdown", "args": {"scope": "standard_flow"}}
        if any(k in q for k in ["文件", "数据集", "上传", "upload", "dataset"]):
            return {"tool": "upload_data", "args": {}}
        if any(k in q for k in ["特征", "相关", "相关性", "重要性", "feature", "correlation"]):
            return {"tool": "feature_analysis", "args": {"data_version": data_version} if data_version else {}}
        if any(k in q for k in ["趋势分析", "趋势情况", "trend analysis"]):
            return {"tool": "feature_analysis", "args": {"data_version": data_version} if data_version else {}}
        if any(k in q for k in ["预测", "预报", "未来", "forecast", "predict"]):
            args = {"method": "next_row", "periods": 7}
            if data_version:
                args["data_version"] = data_version
            return {"tool": "naive_forecast", "args": args}
        if any(k in q for k in ["异常", "outlier", "remove"]):
            return {"tool": "preprocessing", "args": {"method": "outlier_remove"}}
        if any(k in q for k in ["清洗", "clean"]):
            return {"tool": "preprocessing", "args": {"method": "outlier_remove"}}
        if any(k in q for k in ["处理", "预处理", "缺失", "preprocess"]):
            return {"tool": "preprocessing", "args": {"method": "missing_fill"}}
        return {"tool": "eda_analysis", "args": {"data_version": data_version} if data_version else {}}
