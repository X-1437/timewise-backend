
# MCP入门教程 - 问答记录

## 概述
本文档记录了MCP入门学习过程中的问答内容。

---

## 问答记录

### Q1: mcp_tools.py里边儿封装的工具都是设置好return的，就比如eda_analysis，后续是在这里调用我原有的后端代码吗？我可不可以理解为现在这个阶段就是，一旦MCP Client这一端选择eda_analysis这个工具，那么就返回预设好的result的结果？

#### A1:
你的理解完全正确！

**现在这个阶段（第一周）：**
- 是的！Client选择工具 → Server返回预设好的字符串
- 目的是快速验证MCP协议通不通，工具能不能被正确调用
- 不需要真实的后端算法

**后续（第四周左右）：**
- 就在这里接入你原有的后端代码！
- 示例：
```python
# 后续改造
from my_backend.eda import run_eda_analysis  # 导入你的后端代码
real_result = run_eda_analysis(data_name)      # 调用真实算法
result = format_eda_result(real_result)        # 格式化返回
```

---

### Q2: `@server.list_resources()` 这一段代码是什么意思？

#### A2:
`@server.list_resources()` 是MCP的另一个功能，但我们现在用不到，所以返回空列表 `[]`。

**MCP三大功能：**
| 功能 | 装饰器 | 我们用了吗？ | 说明 |
|------|--------|-------------|------|
| **Tools（工具）** | `@server.list_tools()` | ✅ 用了！ | 让大模型调用你的工具 |
| **Resources（资源）** | `@server.list_resources()` | ❌ 没用到 | 让大模型读取文件、数据库等 |
| **Prompts（提示）** | `@server.list_prompts()` | ❌ 没用到 | 预设提示词模板 |

---

### Q3: `types.Tool(...)` 这一段是告诉Client用户输入类似的词就调用这个工具对吧？这个词我后面可以自己定义吗？

#### A3:
可以自己定义！完全没问题！

**这段代码的作用：**
```python
types.Tool(
    name="eda_analysis",      # 工具ID（内部用）
    description="...",         # 给大模型看的描述
    inputSchema={...}
)
```

**可以改的字段：**
| 字段 | 作用 | 可以改吗？ |
|------|------|-----------|
| `name` | 工具的唯一ID | ✅ 可以改，建议英文+下划线 |
| `description` | 给大模型看的，告诉它这个工具是干什么的 | ✅ 完全可以自己改！你想怎么描述就怎么描述 |
| `inputSchema` | 告诉大模型需要什么参数 | ✅ 可以改 |

---

### Q4: `main.py` 有错误

#### A4:
已修复！问题是类型注解的语法错误（`-&gt;` 应该是 `->`）。已移除类型注解，现在没有语法错误了。

---

### Q5: `mcp_tools.py#L209-218` 这是什么意思？

#### A5:
这段代码是**启动MCP Server的入口函数**。

**逐行解释：**
```python
async def main():
    # 创建异步上下文，管理stdio连接
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # 启动Server，传入读写流
        await server.run(
            read_stream,   # 从Client读取消息
            write_stream,  # 向Client发送消息
            InitializationOptions(
                server_name="hongsu-time-series",
                server_version="0.1.0"
            ),
        )
```

**通俗理解：**
1. 打开一个"通信通道"（stdio，标准输入输出）
2. 让Server在这个通道上监听
3. 当Client发消息过来时，Server能收到
4. Server处理完后，通过这个通道把结果发回去

---

### Q6: MCP的三大功能能具体给我解释一下吗？我感觉那个预提示词模板挺好用的

#### A6:
好的，详细解释MCP三大功能：

**1. Tools（工具）- 我们已经在用了！**
- 作用：让大模型调用你的代码/算法
- 例子：eda_analysis、forecast等
- 比喻：厨房里的锅、刀、铲子

**2. Resources（资源）- 让大模型读取东西**
- 作用：让大模型读取外部资源（文件、数据库等）
- 例子：读取用户上传的CSV文件
- 比喻：冰箱里的食材
- 开发计划：第二周加入

**3. Prompts（提示）- 预提示词模板**
- 作用：预设提示词模板，让大模型"记住"常用提示词
- 好处：
  - 不用每次重复写长提示词
  - 分析更专业、格式更统一
- 例子："时间序列分析专家"提示词
- 开发计划：第三/四周加入

---

## MCP功能开发计划

| 功能 | 开发周次 | 状态 |
|------|---------|------|
| Tools（工具） | 第一周 | ✅ 已完成 |
| Resources（资源） | 第二周 | 📅 计划中 |
| Prompts（提示） | 第三/四周 | 📅 计划中 |

---

### Q7: 我现在demo里的MCP框架以及接入的大模型都是真实的吗？就是我接入的是真实的openai模型吗？那不是需要APIkey吗？

#### A7:
好问题！情况是这样的：

**1. MCP框架：是真实的！**
- ✅ 用的是真实的Python MCP框架（`mcp` PyPI包）

**2. 大模型接入：有两种模式！**

看 `llm_client.py` 的代码逻辑：
```python
if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "demo-key":
    # 模式A：用真实的OpenAI API（需要API Key）
    response = self.client.chat.completions.create(...)
else:
    # 模式B：规则匹配（默认，不需要API Key）
    return self._rule_based_intent(query)
```

**两种模式对比：**
| 模式 | 需要API Key吗？ | 用的是什么？ | 我们现在用的是？ |
|------|--------------|-------------|-----------------|
| 模式A：真实OpenAI API | ✅ 需要 | 真实的GPT-4o / GPT-3.5 | ❌ 没用到 |
| 模式B：规则匹配 | ❌ 不需要 | Python代码规则匹配 | ✅ 现在用的是这个！ |

**我们现在的情况：**
- 用的是模式B（规则匹配）
- 原因：不需要API Key，快速验证，没有费用
- 核心逻辑一样（意图识别 → 工具调用 → 结果输出）

**怎么切换到真实OpenAI API？（可选）**
1. 在demo文件夹下创建 `.env` 文件
2. 配置 `OPENAI_API_KEY=你的真实Key`
3. 代码会自动切换到模式A

---

**记录日期**：2026.5.18  
**记录人**：潘文鑫
