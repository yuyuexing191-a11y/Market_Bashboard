# 前端

这是市场看板的最小 React + TypeScript + Vite 前端。开发服务器监听 `5173`，并将 `/api` 请求代理到后端 `http://localhost:8000`。

```bash
npm install
npm run dev
```

打开 <http://localhost:5173> 后，页面会请求 `/api/health`，展示后端服务、数据库状态和 API 地址。生产构建使用：

```bash
npm run build
```
