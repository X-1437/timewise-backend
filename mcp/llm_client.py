
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMClient:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            api_key = "demo-key"
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def analyze_intent(self, query):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "eda_analysis",
                    "description": "执行探索性数据分析（EDA）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_name": {"type": "string"}
                        },
                        "required": ["data_name"]
                    }
                }
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
                            "method": {"type": "string", "enum": ["missing_fill", "outlier_remove", "type_convert"]}
                        },
                        "required": ["data_name", "method"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "feature_analysis",
                    "description": "特征分析",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_name": {"type": "string"}
                        },
                        "required": ["data_name"]
                    }
                }
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
                            "periods": {"type": "integer", "default": 7}
                        },
                        "required": ["data_name", "model"]
                    }
                }
            }
        ]

        system_prompt = """你是一个时间序列数据分析助手。用户会用自然语言描述他们的分析需求，你需要：
1. 理解用户的意图
2. 选择合适的工具（eda_analysis/preprocessing/feature_analysis/forecast）
3. 生成工具调用参数

常用意图对应工具：
- "看看数据"、"概览"、"基本情况" → eda_analysis
- "清洗数据"、"处理缺失值"、"处理异常值" → preprocessing
- "分析特征"、"相关性"、"重要性" → feature_analysis
- "预测"、"预报"、"未来趋势" → forecast

如果用户没有指定数据集名称，默认使用"sales_data"。"""

        if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "demo-key":
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    tools=tools,
                    tool_choice="auto"
                )
                message = response.choices[0].message
                if message.tool_calls:
                    tool_call = message.tool_calls[0]
                    return {
                        "tool": tool_call.function.name,
                        "args": json.loads(tool_call.function.arguments)
                    }
            except Exception as e:
                print(f"OpenAI API调用失败，使用规则匹配：{e}")

        return self._rule_based_intent(query)

    def _rule_based_intent(self, query):
        query_lower = query.lower()

        if any(keyword in query_lower for keyword in ["预测", "预报", "未来", "趋势", "forecast", "predict"]):
            return {
                "tool": "forecast",
                "args": {"data_name": "sales_data", "model": "arima", "periods": 7}
            }
        elif any(keyword in query_lower for keyword in ["特征", "相关性", "重要性", "feature", "correlation"]):
            return {
                "tool": "feature_analysis",
                "args": {"data_name": "sales_data"}
            }
        elif any(keyword in query_lower for keyword in ["清洗", "预处理", "缺失值", "异常值", "preprocess", "clean"]):
            return {
                "tool": "preprocessing",
                "args": {"data_name": "sales_data", "method": "missing_fill"}
            }
        else:
            return {
                "tool": "eda_analysis",
                "args": {"data_name": "sales_data"}
            }

