# RAG QA Bench Benchmark Report

> 生成时间：2026-04-10
> 评测环境：本地 macOS + PostgreSQL 16 + pgvector + `sentence-transformers`

## 数据规模

- 文档总数：`123`
- Chunk 总数：`360`
- 样例文档：`3`
- 新增公开中文文档：`120`
- 评测集：`baseline_v2`
- 评测样例数：`70`
- 拒答样例数：`10`

## 索引性能

本轮测量对象为 `data/docs/` 下新增的 `120` 份公开中文文档，导入命令为：

```bash
/usr/bin/time -lp python3.12 -m app.cli.import_docs --source-dir data/docs
```

结果：

| 指标 | 数值 |
| --- | --- |
| imported_count | `120` |
| skipped_count | `3` |
| 新增 chunk | `360` |
| 端到端耗时 | `14.71s` |
| 文档吞吐 | `8.16 docs/s` |
| chunk 吞吐 | `24.47 chunks/s` |
| peak memory footprint | `1984923064` bytes |

## 检索延迟

基于 `baseline_v2` 前 20 条非拒答查询，分别测量 `top_k=5/10/20` 的单次检索耗时：

| top_k | samples | P50(ms) | P95(ms) | P99(ms) | Mean(ms) |
| --- | --- | --- | --- | --- | --- |
| `5` | `20` | `18.354` | `36.067` | `193.596` | `29.605` |
| `10` | `20` | `21.936` | `25.916` | `26.629` | `21.399` |
| `20` | `20` | `26.451` | `28.848` | `30.373` | `25.720` |

## 召回与引用质量

评测命令：

```bash
/usr/bin/time -lp python3.12 -m app.cli.eval run --dataset baseline_v2 --snapshot default
```

评测输出：

- 评测运行 ID：`a567b3ff-1e52-4273-af6a-467a4cfaccc0`
- 报告 JSON：[report.json](/Users/xioshark/Desktop/career/滕彦翕/项目/rag/output/evals/a567b3ff-1e52-4273-af6a-467a4cfaccc0/report.json)
- 报告 Markdown：[report.md](/Users/xioshark/Desktop/career/滕彦翕/项目/rag/output/evals/a567b3ff-1e52-4273-af6a-467a4cfaccc0/report.md)

| 指标 | 数值 |
| --- | --- |
| `hit@5` | `1.0` |
| `hit@10` | `1.0` |
| `citation_precision@3` | `1.0` |
| `refusal_accuracy` | `0.9429` |
| `grounded_answer_rate` | `0.9429` |
| `latency_p95_ms` | `47.572` |
| 评测总耗时 | `10.81s` |

## 结论

- 在 `123` 份文档、`360` 个 chunk 的规模下，`sentence-transformers + pgvector` 链路已经稳定跑通。
- 对定义型公开语料，当前精确检索在 `hit@5`、`hit@10`、`citation_precision@3` 上都达到了 `1.0`。
- 当前主要短板是拒答策略，`10` 条拒答样例中有 `4` 条被误答，导致 `refusal_accuracy` 与 `grounded_answer_rate` 都停在 `0.9429`。
- 延迟方面，默认 `snapshot=default` 的整套评测 `P95` 为 `47.572ms`，检索层面 `top_k=20` 仍保持在 `30ms` 量级。

## 后端对比

三组对比均在临时 SQLite 数据库中独立完成，结果文件见：

- [backend_compare.json](/Users/xioshark/Desktop/career/滕彦翕/项目/rag/output/benchmarks/backend_compare.json)

| backend | import_seconds | eval_seconds | hit@5 | citation_precision@3 | refusal_accuracy | grounded_answer_rate | latency_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `hash` | `0.481` | `1.041` | `0.9167` | `0.9167` | `0.8857` | `0.8714` | `18.071` |
| `bge-small-zh` | `12.316` | `12.471` | `1.0` | `1.0` | `0.9429` | `0.9429` | `83.658` |
| `bge-base-zh` | `17.142` | `16.644` | `1.0` | `1.0` | `0.9429` | `0.9429` | `238.237` |

结论：

- `hash` 后端速度最快，但在 `hit@5`、`citation_precision@3`、`grounded_answer_rate` 上都有可见损失。
- `bge-small-zh` 与 `bge-base-zh` 在当前 `baseline_v2` 上质量相同，但 `bge-small-zh` 的导入和评测耗时明显更低。
- 在当前规模下，`bge-small-zh` 是更均衡的默认选择。

## 风险与未完成项

- 公开语料当前来自随机中文维基摘要，覆盖面够用，但还未按主题做分层抽样。
- 拒答样例仍存在误答，需要后续针对阈值、拒答规则或 query hygiene 单独收敛。
