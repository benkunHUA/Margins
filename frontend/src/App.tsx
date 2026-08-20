import { NavLink, Route, Routes } from "react-router-dom";
import { BookOpen, MessagesSquare } from "lucide-react";

import ChatPage from "@/pages/ChatPage";
import DocumentsPage from "@/pages/DocumentsPage";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
  }`;

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-4">
        <h1 className="mb-6 px-3 text-lg font-semibold tracking-tight">Margins 知识库</h1>
        <nav className="flex flex-col gap-1">
          <NavLink to="/" end className={navLinkClass}>
            <BookOpen className="size-4" />
            文档管理
          </NavLink>
          <NavLink to="/chat" className={navLinkClass}>
            <MessagesSquare className="size-4" />
            知识问答
          </NavLink>
        </nav>
      </aside>
      <main className="min-w-0 flex-1">
        <Routes>
          <Route path="/" element={<DocumentsPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </main>
    </div>
  );
}
