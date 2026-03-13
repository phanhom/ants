import { Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";
import Layout from "./Layout";
import { Skeleton } from "@/components/ui/skeleton";

const Overview = lazy(() => import("./pages/Overview"));
const CostCenter = lazy(() => import("./pages/CostCenter"));
const TaskFlow = lazy(() => import("./pages/TaskFlow"));
const ReportsHub = lazy(() => import("./pages/ReportsHub"));
const Traces = lazy(() => import("./pages/Traces"));
const CloudDrive = lazy(() => import("./pages/CloudDrive"));
const AgentDetail = lazy(() => import("./pages/AgentDetail"));

function PageFallback() {
  return (
    <div className="space-y-6 animate-fade-in">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-64" />
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/costs" element={<CostCenter />} />
          <Route path="/tasks" element={<TaskFlow />} />
          <Route path="/reports" element={<ReportsHub />} />
          <Route path="/traces" element={<Traces />} />
          <Route path="/artifacts" element={<CloudDrive />} />
          <Route path="/agent/:agentId" element={<AgentDetail />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
