# Honeywell Download Library

**简体中文** | [English](README.en.md)

面向 霍尼韦尔 工控产品的公开手册搜集工具与通用 AI Skill。支持 Codex、Claude Code、其他能运行 Python 的 AI 工具，也能独立运行，不依赖模拟网页点击。

## 本次增强

示例将经典 Safety Manager 与 Safety Manager SC 分开，覆盖硬件参考、安全手册、安装、技术规格及变更说明。两个公开产品页本次提取到 28 个文件链接，其中包含宣传与培训资料，不能称为 28 份手册。SC 官方页面明确提示登录后可查看更多文档。

- 产品别名、手册类别、文档号与公开网页组合查缺；PDF 引用还会生成下一轮搜索计划。
- 累积 JSON / CSV 清单；中断后续下，后续更新不删除历史记录。
- 跨网址比对已核实的文档号与版本，单独报告“新版待获取”和适用性待审。
- 文件签名、SHA-256 与原子状态保存；拒绝空文件、登录页和伪 PDF。
- 本地 RAG 索引保留来源、哈希与版本；版本冲突单独进入待审清单。

**边界：不是官网全部资料的完整枚举，也不承诺全网搜全。** 搜索引擎有限额，登录资料、失效链接和访问限制会留下记录，不绕过限制。

## 开始使用

Python 3.10+。下载逻辑只依赖标准库；PDF 提取需安装可选依赖：

```bash
python -m pip install -r requirements-inspection.txt
```

把整个仓库目录交给支持 Skill 的 AI 工具读取 `SKILL.md`，或按下面命令直接运行。输出目录应位于 Skill 目录之外。先复制示例配置到自己的配置文件再调整产品；保持产品 ID 和输出目录稳定。

```bash
python scripts/manual_watch.py plan --config references/honeywell.example.json --out web-query-plan.json
python scripts/manual_watch.py run --config references/honeywell.example.json --root honeywell-manuals --web-results web-results.json
python scripts/manual_watch.py resume --config references/honeywell.example.json --root honeywell-manuals
python scripts/manual_watch.py audit --config references/honeywell.example.json --root honeywell-manuals
```

`plan` 示例目前生成 19 条查询。由任意搜索工具执行后，按[导入格式](references/manual-watch.md)生成 `web-results.json`，记录真实搜索时间；不要把旧结果当新搜索。首次正常运行不加 `--limit`，将下载所选范围内全部可访问候选。测试才加 `--limit 2`。

无需搜索导出文件时，也可在进程环境设置 `TAVILY_API_KEY`，将 `--web-results web-results.json` 换为 `--web-provider tavily`。该服务可收费；先检查计划数量。密钥不要写进文件或仓库。没有新搜索结果时只能说明官网公开页/旧清单覆盖情况，不能声称完成全网更新。

后续 `run` 更新清单并补下载；`resume` 不搜索，只处理已保存清单；`audit` 完全离线重建版本报告。检查同网址内容替换时加 `--revalidate`。续传是文件级，单个中断文件重新下载，不是字节级续传。

## 输出与版本

文件按 `文档类型 - 文档号 - 文档名称 - 版本.pdf` 命名；缺项省略，多文件与名称冲突会加后缀。未知元数据不猜测。

| 文件 | 用途 |
| --- | --- |
| `catalog.json / catalog.csv` | 累积清单，包含未下载与非手册条目 |
| `download-manifest.json` | 按格式和类别筛选后的下载清单 |
| `version-report.json` | 跨网址版本系列、新版待获取、身份不明项 |
| `followup-plan.json` | PDF 引用产生的文档号查询与官方链接，需先审查相关性 |
| `pdf-evidence.json` | PDF 前言、物理页码、引用与提取错误 |
| `rag-index.jsonl` | 全部有效本地文件及历史版本 |
| `rag-current.jsonl / rag-review.jsonl` | 排除已知冲突后的资料 / 版本待审资料 |

宣传、培训资料保留在清单中，示例默认不下载已识别的此类文件；未分类 PDF 仍保留为候选，避免误漏。PDF 默认检查前 40 页，按哈希缓存，扫描件可能需要另行 OCR。详细规则见[版本与查缺说明](references/version-aware-collection.md)。

较高版本不等于适合你的工程。RAG 用于未来方案审核时，必须结合实际硬件、固件、软件发行版及安全认证要求进行人工确认。本工具不自动批准版本，不建立向量数据库，也不代替工程审核。

## 测试与限制

2026-10-30（中国时间）共享引擎通过 **68 项离线回归测试**，包括两品牌 2+2 续传、跨网址版本比对、语言隔离、错误文件拒绝及历史保留。

真实下载了 SC Direct Landing Adapter FC-TUDL01 技术资料，版本 1.0，294,817 字节；再次续传为 0 新下载、1 跳过。封面没有独立文档号，命名中留空而不拿产品型号冒充。

真实验收采用限量下载和已核实的官方来源导入，未全量下载、未执行全部生成查询，也未测试独立 Tavily HTTP 后端。退出码：`0` 当前操作成功，`2` 搜索覆盖/来源或检查不完整，`1` 配置或运行错误；查看报告，不把非零退出当成“没有资料”。

```bash
python -B -m unittest discover -s scripts -p "test_*.py"
```

定期更新可交给任意调度器运行同一配置与目录；安装 Skill 本身不会创建定时任务。并发运行由目录锁阻止。仅在确认无活动进程后处理遗留锁。

## 资料权利

本项目与 Honeywell 无隶属关系。厂商手册版权归原权利人；请遵守访问条款及内部使用要求。GitHub 仅发布代码和说明，不包含原始手册、下载状态、用户资料或密钥。
