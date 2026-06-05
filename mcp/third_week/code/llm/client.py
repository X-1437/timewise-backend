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
        if not self._client:
            raise RuntimeError("LLM client is not configured. Please set OPENAI_API_KEY.")

        result = self._analyze_intent_with_openai(query)
        if result:
            q = (query or "").strip().lower()
            if result.get("tool") == "eda_analysis" and any(
                k in q for k in ["处理", "清洗", "预处理", "preprocess", "clean"]
            ):
                return self._rule_based_intent(query)
            return result
        return self._rule_based_intent(query)

    def _analyze_intent_with_openai(self, query: str) -> dict | None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "eda_analysis",
                    "description": "执行探索性数据分析（EDA）",
                    "parameters": {
                        "type": "object",
                        "properties": {"data_name": {"type": "string"}},
                        "required": ["data_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "preprocessing",
                    "description": "数据预处理",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_name": {"type": "string"},
                            "method": {
                                "type": "string",
                                "enum": ["missing_fill", "outlier_remove", "type_convert"],
                                "default": "missing_fill",
                            },
                        },
                        "required": ["data_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "feature_analysis",
                    "description": "特征分析",
                    "parameters": {
                        "type": "object",
                        "properties": {"data_name": {"type": "string"}},
                        "required": ["data_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "forecast",
                    "description": "时间序列预测",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_name": {"type": "string"},
                            "model": {"type": "string", "enum": ["arima", "prophet", "lstm"]},
                            "periods": {"type": "integer", "default": 7},
                        },
                        "required": ["data_name", "model"],
                    },
                },
            },
        ]

        system_prompt = (
            "你是一个时间序列数据分析助手。用户会用自然语言描述他们的分析需求，你需要：\n"
            "1. 理解用户的意图\n"
            "2. 选择合适的工具（eda_analysis/preprocessing/feature_analysis/forecast）\n"
            "3. 生成工具调用参数\n\n"
            "常用意图对应工具：\n"
            '- "看看数据"、"概览"、"基本情况" → eda_analysis\n'
            '- "清洗数据"、"处理数据"、"预处理"、"处理缺失值"、"处理异常值" → preprocessing\n'
            '- "分析特征"、"相关性"、"重要性" → feature_analysis\n'
            '- "预测"、"预报"、"未来趋势" → forecast\n\n'
            '如果用户没有指定数据集名称，默认使用"sales_data"；如果用户需要 preprocessing 但未指定 method，默认使用 missing_fill。'
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

    def _rule_based_intent(self, query: str) -> dict:
        q = (query or "").strip().lower()
        if any(k in q for k in ["预测", "预报", "未来", "趋势", "forecast", "predict"]):
            return {"tool": "forecast", "args": {"data_name": "sales_data", "model": "prophet", "periods": 30}}
        if any(k in q for k in ["特征", "相关", "相关性", "重要性", "feature", "correlation"]):
            return {"tool": "feature_analysis", "args": {"data_name": "sales_data"}}
        if any(k in q for k in ["处理", "清洗", "预处理", "缺失", "异常", "preprocess", "clean"]):
            return {
                "tool": "preprocessing",
                "args": {"data_name": "sales_data", "method": "missing_fill"},
            }
        return {"tool": "eda_analysis", "args": {"data_name": "sales_data"}}
