import { Routes, Route } from "react-router-dom";
import Layout from "./Layout";
import ColonyOverview from "./ColonyOverview";
import AgentDetail from "./AgentDetail";
import Traces from "./Traces";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ColonyOverview />} />
        <Route path="/agent/:agentId" element={<AgentDetail />} />
        <Route path="/traces" element={<Traces />} />
      </Routes>
    </Layout>
  );
}
