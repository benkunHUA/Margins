# Margins 前端

React 19 + TypeScript + Vite + Tailwind CSS 4 构建的知识库 Web 界面。

## 开发

```bash
pnpm install
pnpm dev
```

开发服务器默认运行在 http://localhost:5173，`/api` 已代理到 http://localhost:8000。

## 构建

```bash
pnpm build
```

产物输出到 `dist/`。

依赖由 pnpm 管理（`package.json` 中通过 `packageManager` 固定版本），首次使用可执行 `corepack enable` 启用 pnpm。

## 目录

```text
src/
├── api/          # HTTP 客户端与 SSE 流式解析
├── components/   # 上传、文档表格、聊天面板、引用卡片等
├── hooks/        # TanStack Query 数据 hooks
├── pages/        # 文档管理页 / 对话页
├── stores/       # Zustand 状态
└── lib/          # 工具函数
```
