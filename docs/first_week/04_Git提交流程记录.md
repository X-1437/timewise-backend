
# Git提交流程记录 - 第一周

## 一、概述
本文档记录了第一周产出物提交到GitHub的完整流程，供后续周次参考。

**完成日期**：2026.5.20  
**提交仓库**：https://github.com/X-1437/timewise-backend  
**提交分支**：master  
**标签**：week1-finished

---

## 二、提交内容清单

### 2.1 文档部分
| 文件 | 说明 |
|------|------|
| `docs/first_week/01_第一周最终目标.md` | 第一周目标 |
| `docs/first_week/02_第一周需求文档.md` | 需求文档 |
| `docs/first_week/03_第一周执行文档.md` | 执行文档 |
| `docs/first_week/MCP功能开发计划.md` | MCP开发计划 |
| `docs/first_week/MCP封装方式调研报告.md` | MCP调研报告 |
| `docs/first_week/大模型接入方式调研报告.md` | 大模型调研报告 |
| `docs/first_week/技术方案验证报告.md` | 验证报告 |

### 2.2 代码部分
| 文件 | 说明 |
|------|------|
| `mcp/.env.example` | 环境变量示例 |
| `mcp/llm_client.py` | 大模型接入模块 |
| `mcp/main.py` | 完整版主程序 |
| `mcp/mcp_tools.py` | MCP工具封装 |
| `mcp/requirements.txt` | 依赖清单 |
| `mcp/run_demo.py` | 简化版演示 |
| `mcp/test_mcp_full.py` | 测试脚本 |

---

## 三、完整操作流程

### 3.1 准备工作
```powershell
# 创建工作目录
cd D:\trae_workspace\
mkdir github
cd .\github\
```

### 3.2 克隆仓库
```powershell
git clone https://github.com/X-1437/timewise-backend.git
cd .\timewise-backend\
```

### 3.3 切换到master分支并拉取最新代码
```powershell
git checkout master
git pull origin master
```

### 3.4 创建功能分支
```powershell
git checkout -b feature/first-week
```

### 3.5 创建目录结构
```powershell
mkdir docs
mkdir docs\first_week
mkdir mcp
```

### 3.6 复制文件
```powershell
# 复制文档
Copy-Item -Path "D:\trae_workspace\data\file\first_week\*.md" -Destination "docs\first_week\"

# 复制代码
Copy-Item -Path "D:\trae_workspace\data\file\first_week\demo\*" -Destination "mcp\" -Recurse
```

### 3.7 查看状态
```powershell
git status
```

### 3.8 添加文件到暂存区
```powershell
git add docs/
git add mcp/
```

### 3.9 提交更改
```powershell
git commit -m "feat: 添加第一周产出"
```

### 3.10 推送到远程分支
```powershell
git push origin feature/first-week
```

### 3.11 移除不必要的文件（修正提交）
```powershell
git rm "docs/first_week/MCP入门教程 - 问答记录.md"
git commit -m "docs: 移除MCP入门教程问答记录"
git push origin feature/first-week
```

### 3.12 在GitHub上创建Pull Request
1. 访问：https://github.com/X-1437/timewise-backend/pull/new/feature/first-week
2. 填写PR标题和描述
3. 创建PR
4. 确认代码变更
5. 执行 "Confirm merge"

### 3.13 本地切换回master并拉取最新代码
```powershell
git checkout master
git pull origin master
```

### 3.14 创建标签标记第一周完成
```powershell
git tag -a week1-finished -m "第一周完成：技术方案验证"
```

### 3.15 推送标签到GitHub
```powershell
git push origin week1-finished
```

### 3.16 删除本地功能分支（可选）
```powershell
git branch -d feature/first-week
```

---

## 四、验证结果

### 4.1 GitHub仓库验证
- ✅ master分支包含第一周所有文档和代码
- ✅ 存在 `week1-finished` 标签
- ✅ Pull Request历史记录完整

### 4.2 访问链接
- 仓库主页：https://github.com/X-1437/timewise-backend
- 标签页面：https://github.com/X-1437/timewise-backend/tags
- 第一周标签代码：https://github.com/X-1437/timewise-backend/tree/week1-finished

---

## 五、Git工作流总结

### 5.1 分支策略
```
master (主分支，稳定)
  ↓
feature/first-week (功能分支，开发中)
  ↓ (PR合并)
master (更新)
  ↓ (打标签)
week1-finished (里程碑标签)
```

### 5.2 关键命令速查
| 操作 | 命令 |
|------|------|
| 创建分支 | `git checkout -b &lt;branch-name&gt;` |
| 查看状态 | `git status` |
| 添加文件 | `git add &lt;path&gt;` |
| 提交 | `git commit -m "&lt;message&gt;"` |
| 推送 | `git push origin &lt;branch&gt;` |
| 拉取 | `git pull origin &lt;branch&gt;` |
| 创建标签 | `git tag -a &lt;tag-name&gt; -m "&lt;message&gt;"` |
| 推送标签 | `git push origin &lt;tag-name&gt;` |
| 删除本地分支 | `git branch -d &lt;branch-name&gt;` |

---

## 六、遇到的问题与解决方案

| 问题 | 解决方案 |
|------|---------|
| LF将被CRLF替换警告 | 正常提示，Windows系统的换行符差异，不影响功能 |
| 第一次推送后需要修正 | 在本地删除文件后再次commit和push |
| 网络连接超时 | 重试即可，GitHub偶尔连接不稳定 |

---

## 七、后续周次参考

第二周提交时可参考此流程：
1. 创建新分支 `feature/second-week`
2. 添加第二周文档到 `docs/second_week/`
3. 添加代码到对应目录
4. 提交、推送、创建PR
5. 合并后打标签 `week2-finished`

---

**文档版本**：v1.0  
**编写日期**：2026.5.20  
**编写人**：潘文鑫

