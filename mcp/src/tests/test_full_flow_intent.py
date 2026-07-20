"""W5-10: 统一非分析输入引导回复 — 单测覆盖一键全流程 + 白名单门禁 + 规则兜底。"""

import unittest

from llm.client import LLMClient


class TestFullFlowIntent(unittest.TestCase):
    def test_rule_based_full_flow(self):
        c = LLMClient()
        out = c.analyze_intent("帮我运行全流程")
        self.assertEqual(out["tool"], "run_full_flow")

    def test_rule_based_full_flow_variants(self):
        c = LLMClient()
        for q in ["一键全流程", "跑全流程", "执行全流程", "运行标准流程"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "run_full_flow")

    # --- W5-10: 非分析输入统一引导回复 ---
    def test_greeting_returns_direct_reply(self):
        c = LLMClient()
        for q in ["你好", "您好", "你是谁", "你能做什么", "hello", "hi"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "direct_reply")
            self.assertEqual(out["args"]["reply_key"], "non_analysis")

    def test_weather_returns_direct_reply(self):
        c = LLMClient()
        for q in ["今天天气怎么样", "天气", "北京今天气温多少"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "direct_reply")
            self.assertEqual(out["args"]["reply_key"], "non_analysis")

    def test_unknown_algorithm_returns_direct_reply(self):
        c = LLMClient()
        # 输入不包含分析关键词（"分析"/"预测"/"预处理"等），但提到未支持算法 → 统一引导回复
        for q in ["用XXX算法", "你知道RandomForest吗", "有没有GPT算法"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "direct_reply")
            self.assertEqual(out["args"]["reply_key"], "non_analysis")

    def test_random_chitchat_returns_direct_reply(self):
        c = LLMClient()
        for q in ["今天中午吃什么", "讲个笑话", "推荐一部电影"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "direct_reply")
            self.assertEqual(out["args"]["reply_key"], "non_analysis")

    def test_empty_returns_direct_reply_empty_key(self):
        c = LLMClient()
        for q in ["", "  "]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "direct_reply")
            self.assertEqual(out["args"]["reply_key"], "empty")

    # --- 白名单: 分析意图仍正常进入 ---
    def test_eda_keyword_still_in_whitelist(self):
        c = LLMClient()
        for q in ["帮我做一下EDA", "eda"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "eda_analysis")

    def test_preprocess_keyword_still_in_whitelist(self):
        c = LLMClient()
        for q in ["清洗数据", "预处理", "处理缺失值"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "preprocessing")

    def test_feature_keyword_still_in_whitelist(self):
        c = LLMClient()
        for q in ["分析特征", "做相关性分析"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "feature_analysis")

    def test_forecast_keyword_still_in_whitelist(self):
        c = LLMClient()
        for q in ["预测未来7天"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "naive_forecast")

    def test_export_keyword_still_in_whitelist(self):
        c = LLMClient()
        for q in ["导出报告"]:
            out = c.analyze_intent(q)
            self.assertEqual(out["tool"], "export_markdown")
