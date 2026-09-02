# Margins 知识库系统

基于 **上传文档 → RAG 问答** 的本地/小团队知识库系统。前端 React，后端 FastAPI + LangChain 1.x，文档解析走 MinerU 在线服务，向量检索用 Faiss，检索管线包含查询重写、混合检索（Faiss + BM25 + RRF）与重排序（百炼 qwen3-rerank）。

## 功能特性（MVP）

- 文档管理：上传（PDF / Word / Markdown / TXT）、解析状态跟踪、列表、删除、Markdown 预览
- 多轮问答：会话管理、SSE 流式输出
- 引用溯源：回答附带来源文档、章节与原文片段
- 检索管线：查询重写 → 混合检索 → 重排序 → 上下文组装
- 图片理解：MinerU 提取 PDF 图片 → 百炼 qwen3.8-max 生成中文文字总结 → 随正文一起分块入库检索（纯文字文档仍走免费 flash 快通道）

## 技术栈

| 层面 | 选型 |
|---|---|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS + TanStack Query + Zustand |
| 后端 | Python 3.12 + FastAPI + Pydantic v2 |
| LLM | LangChain 1.x + `langchain-openai`（OpenAI 兼容接口，默认 DeepSeek） |
| Embedding | 阿里云百炼 `text-embedding-v4` |
| Rerank | 阿里云百炼 `qwen3-rerank`（备选 `gte-rerank-v2`） |
| 文档解析 | MinerU 在线解析服务（`mineru-open-sdk`） |
| 向量库 | Faiss（本地落盘持久化） |
| 元数据存储 | SQLite（SQLAlchemy 2.0 async，预留 PostgreSQL 升级位） |

## 快速开始

### 方式一：本地开发

后端（需要 Python 3.12）：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 填入 DASHSCOPE_API_KEY、MINERU_API_TOKEN、LLM_API_KEY
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
pnpm install
pnpm dev
```

访问 http://localhost:5173，前端已将 `/api` 代理到 http://localhost:8000。

> 前端依赖由 pnpm 管理（版本见 `frontend/package.json` 的 `packageManager`），首次使用可执行 `corepack enable`。

### 方式二：Docker Compose

```bash
cp .env.example .env   # 填入密钥
docker compose up --build
```

访问 http://localhost:3000。

## 环境变量

主要配置项见 [.env.example](.env.example)：

| 变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 百炼 API Key（Embedding / Rerank） |
| `EMBEDDING_MODEL` | 默认 `text-embedding-v4` |
| `RERANK_MODEL` | 默认 `qwen3-rerank` |
| `MINERU_API_TOKEN` | MinerU 在线解析 Token（[获取](https://mineru.net/apiManage/token)） |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | OpenAI 兼容 LLM 配置，默认 DeepSeek |
| `DATA_DIR` | 数据目录（SQLite、Faiss 索引、上传文件） |
| `IMAGE_SUMMARY_*` | 图片文字总结配置（开关 / qwen3.8-max 模型 / 数量上限 / 大小阈值 / 温度 / 思考模式），见 [.env.example](.env.example) |

检索参数（`RECALL_K`、`RERANK_TOP_N`、`RELEVANCE_THRESHOLD`、`MAX_CHUNKS_PER_DOCUMENT`、`MIN_CHUNK_CHARS`、`MAX_CITATIONS` 等）见 [.env.example](.env.example)。

## 部署（Docker Compose）

```bash
cp .env.example .env   # 填入 DASHSCOPE_API_KEY / MINERU_API_TOKEN / LLM_API_KEY
docker compose up --build
```

- 前端：http://localhost:3000（nginx 托管，`/api` 反向代理到后端）
- 后端：http://localhost:8000，健康检查 `GET /api/health` 返回 `{"status":"ok","version":"...","documents":N}`
- 数据持久化在 `./data`（SQLite、Faiss 索引、上传文件、解析结果）
- 后端容器带 healthcheck，前端等后端健康后才启动；SSE 流式已关闭 nginx 缓冲

## 数据库迁移（Alembic）

应用启动时会自动执行 `alembic upgrade head`。手动管理迁移：

```bash
cd backend
alembic revision --autogenerate -m "描述"   # 生成新迁移
alembic upgrade head                       # 应用迁移
```

## 目录结构

```text
.
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── core/             # 配置、日志、依赖容器、异常
│   │   ├── domain/           # 领域实体与事件
│   │   ├── api/              # 路由与请求/响应模型
│   │   ├── repositories/     # 仓储接口 + SQL/内存实现
│   │   ├── vector/           # Faiss 向量库、BM25、RRF 融合
│   │   ├── services/         # 解析、索引、检索、问答服务
│   │   └── workers/          # 异步解析任务
│   └── tests/
├── frontend/                 # React 前端
│   └── src/
│       ├── pages/            # 文档管理页 / 对话页
│       ├── components/       # 上传、表格、聊天、引用卡片等
│       ├── api/              # HTTP 客户端与 SSE
│       ├── stores/           # Zustand 状态
│       └── hooks/
├── docker-compose.yml
└── .env.example
```

## 开发路线图

- M1：工程骨架 + 文档上传 + MinerU 解析 + 入库
- M2：基础问答（向量检索 + SSE 流式）
- M3：查询重写 + 混合检索 + 重排序
- M4：UI 打磨 + 会话管理 + 部署完善

## 说明

- 详细设计文档保留在本地 `docs/` 目录，未纳入版本库。
- 后端接口与类的设计遵循面向对象 + 依赖倒置，各层通过抽象接口解耦，便于替换存储与模型供应商。

## 常见问题

- **每个 worktree / 新环境都要复制密钥**：`.env` 被 gitignore，新建 worktree 后需执行 `cp backend/.env .worktrees/<名称>/backend/.env`（或从任意已配置目录复制）。
- **解析失败提示"requires an authenticated client"**：说明 `MINERU_API_TOKEN` 未配置或为空，检查 `.env` 后重启后端。
- **提问时引用为空或过多**：检索参数（`RECALL_K`、`RELEVANCE_THRESHOLD`、`RERANK_TOP_N`、`MAX_CHUNKS_PER_DOCUMENT`、`MAX_CITATIONS`）可在 `.env` 调整。
