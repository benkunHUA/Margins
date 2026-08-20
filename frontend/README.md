# Margins 前端

React 19 + TypeScript + Vite + Tailwind CSS 4 构建的知识库 Web 界面。

## 开发

```bash
npm install
npm run dev
```

开发服务器默认运行在 http://localhost:5173，`/api` 已代理到 http://localhost:8000。

## 构建

```bash
npm run build
```

产物输出到 `dist/`。

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
