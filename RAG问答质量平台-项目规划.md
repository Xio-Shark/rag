# RAG问答质量平台-项目规划

## 1. 项目概览

- **项目名称**：RAG QA Bench｜检索增强问答与质量评测平台
- **项目简介**：面向知识库问答场景的 AI 应用工程项目，支持文档导入、切片索引、检索召回、重排、回答生成、引用溯源、离线评测与版本回归。项目重点不在“接一个模型接口”，而在于把检索、生成、评测、护栏和审计做成完整闭环。
- **核心目标**：
  - 建立“导入文档 -> 生成切片 -> 向量检索 -> 重排 -> 生成回答 -> 返回引用”的主链路。
  - 建立围绕 `检索命中率 / 引用正确率 / 拒答准确率 / 答案完整性 / 延迟预算` 的质量评测体系。
  - 记录 `model_name / prompt_version / top_k / chunk_size / reranker / latency_ms / token_usage / cost` 等审计字段，支持坏例回放和参数回归。
  - 建立护栏和降级策略，减少无依据回答与幻觉输出。
- **适用场景**：
  - AI 应用工程实习
  - AI 平台工具开发实习
  - LLM 工程化 / 质量治理方向项目展示

## 2. 项目管理

- **团队与负责人**：个人项目，负责人为滕彦翕。
- **时间计划**：建议按 `4` 周完成第一版可展示成果。
- **进度安排**：
  - 第 1 周：完成数据模型、文档导入、切片规则、基础索引与最小问答接口。
  - 第 2 周：完成向量检索、Top-K 召回、重排、引用返回与拒答策略。
  - 第 3 周：完成审计字段落库、离线评测脚本、坏例样例集与回归入口。
  - 第 4 周：完成监控指标、参数对比报告、简历证据页和演示样例。
- **风险及应对措施**：
  - 风险：检索效果不稳定，生成答案看起来“会说但不准”。
  - 应对：先把引用约束和拒答逻辑做稳，再优化生成质量。
  - 风险：模型和向量库堆得太重，本地演示成本高。
  - 应对：优先使用轻量嵌入模型和本地单机部署，先完成可运行 MVP。
  - 风险：评测维度太多，最后只有框架没有结果。
  - 应对：第一版只保留 `5` 个核心指标，先跑通评测和回归。

## 3. 资源与依赖

- **开发语言 / 框架 / 库**：
  - Python 3.11
  - FastAPI
  - SQLAlchemy
  - Pydantic
  - PostgreSQL + `pgvector`
  - Redis + RQ
  - `sentence-transformers`
  - 可选重排模型：`bge-reranker-base`
  - 测试：`pytest`
- **系统环境与配置**：
  - Docker Compose 拉起 PostgreSQL、Redis
  - `.env` 中配置 `OPENAI_API_KEY`、`EMBEDDING_MODEL_NAME`、`RERANKER_ENABLED`
  - 本地文档目录统一挂载到 `data/docs/`
- **外部依赖与数据资源**：
  - 本地 Markdown / PDF / TXT 文档
  - 自建问答样例集
  - 手工标注的 bad case 清单
- **测试与 CI/CD 配置**：
  - `pytest`
  - `pytest --cov`
  - `ruff check`
  - `python -m compileall app tests`
  - GitHub Actions 执行静态检查、单元测试与回归评测
- **优化说明**：优先使用轻量嵌入模型和单机 `pgvector`，避免一开始就引入过重的组件；检索阶段先召回少量候选，再做重排，减少耗时和资源占用。

## 4. 核心代码示例

```python
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="RAG QA Bench")


class Citation(BaseModel):
    # 引用来源，便于后续做证据回查
    chunk_id: str
    document_id: str
    snippet: str


class AskRequest(BaseModel):
    # 用户提问
    query: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=3, ge=1, le=10)


class AskResponse(BaseModel):
    # 标准化问答输出，避免返回无法消费的自由文本
    answer: str
    citations: List[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    refusal_reason: Optional[str] = None


CHUNKS = [
    {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "text": "系统支持文档导入、切片索引、检索召回、重排和引用返回。",
    },
    {
        "chunk_id": "chunk-2",
        "document_id": "doc-1",
        "text": "当检索不到足够证据时，系统应该拒答，而不是编造答案。",
    },
]


def retrieve_chunks(query: str, top_k: int) -> List[dict]:
    # 这里用最小关键词匹配示意主链路，正式版本替换为向量检索 + 重排
    matched = [chunk for chunk in CHUNKS if any(word in chunk["text"] for word in query.split())]
    return matched[:top_k]


@app.post("/qa/ask", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    chunks = retrieve_chunks(request.query, request.top_k)

    # 没有证据时直接拒答，避免无依据生成
    if not chunks:
        return AskResponse(
            answer="",
            citations=[],
            confidence=0.0,
            refusal_reason="no_evidence",
        )

    citations = [
        Citation(
            chunk_id=chunk["chunk_id"],
            document_id=chunk["document_id"],
            snippet=chunk["text"],
        )
        for chunk in chunks
    ]

    # 正式版本中这里由大模型基于检索证据生成回答
    answer = "；".join(chunk["text"] for chunk in chunks)

    return AskResponse(
        answer=answer,
        citations=citations,
        confidence=0.82,
        refusal_reason=None,
    )
```

## 5. 资源规划与优化

- **任务分解与执行顺序**：
  1. 定义 `document / chunk / retrieval_run / answer_run / eval_case / eval_result` 数据模型。
  2. 实现文档导入、切片、索引构建与基础检索接口。
  3. 接入重排器，完成 `top_k`、`chunk_size`、`overlap` 等参数可配置。
  4. 实现问答接口，返回 `answer / citations / confidence / refusal_reason` 结构化结果。
  5. 实现审计表，记录模型、提示词、耗时、Token 和成本。
  6. 实现离线评测脚本，沉淀 bad case 与参数回归报告。
  7. 增加监控指标与演示样例，补简历证据页。
- **依赖资源与环境准备**：
  - 准备 `20-50` 份结构相对清晰的知识库文档。
  - 手工整理 `30-50` 组问答样例，覆盖命中、拒答、歧义和引用错误场景。
  - 预留本地数据库、Redis 和模型服务的环境变量。
- **可扩展性与优化方向**：
  - 第一版先做单知识库问答，第二版扩展多知识库与租户隔离。
  - 第一版先做文本切片，第二版补 PDF 解析和表格抽取。
  - 第一版先做离线评测，第二版补在线反馈与人工标注后台。
  - 优化重点优先级：
    - 先稳住引用正确率和拒答准确率。
    - 再优化检索命中率和回答完整性。
    - 最后再做复杂的多轮对话和高级 Agent 能力。

## 6. 安全与最佳实践

- 严格限制文档上传类型、大小和来源，避免任意文件解析带来的安全风险。
- 所有模型密钥、数据库连接和第三方配置统一使用环境变量，不写入代码仓库。
- 问答输出必须依赖检索证据，禁止在无引用时直接生成“看起来合理”的答案。
- 对原始文档和问答日志做脱敏处理，避免把隐私数据写入审计表或评测样例。
- API 层增加速率限制、输入长度限制和异常兜底，避免大文本输入拖垮服务。
- 开发流程采用测试先行：
  - 单元测试覆盖切片、引用校验、拒答判断、评分逻辑。
  - 集成测试覆盖“导入 -> 索引 -> 检索 -> 回答 -> 评测”主链路。
  - 每轮提交前执行 `ruff check`、`pytest --cov` 和最小回归集。
