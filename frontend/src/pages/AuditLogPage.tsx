import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface AuditEntry {
  id: string;
  user_email?: string | null;
  action: string;
  collection_name: string;
  document_id: string;
  created_at: string;
}

const actionColors: Record<string, string> = {
  CREATE: "text-emerald-400 bg-emerald-950/40",
  UPDATE: "text-amber-400 bg-amber-950/40",
  ARCHIVE: "text-red-400 bg-red-950/40",
  LOGIN: "text-blue-400 bg-blue-950/40",
};

export default function AuditLogPage() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ["audit-log"],
    queryFn: async () => (await api.get<AuditEntry[]>("/audit-log")).data,
  });

  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
            <th className="px-4 py-3 font-medium">User</th>
            <th className="px-4 py-3 font-medium">Action</th>
            <th className="px-4 py-3 font-medium">Collection</th>
            <th className="px-4 py-3 font-medium">Document</th>
            <th className="px-4 py-3 font-medium">When</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
          {(entries ?? []).map((e) => (
            <tr key={e.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
              <td className="px-4 py-3 text-neutral-300">{e.user_email ?? "system"}</td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-1 rounded-full ${actionColors[e.action] ?? "text-neutral-400 bg-neutral-800/60"}`}>
                  {e.action}
                </span>
              </td>
              <td className="px-4 py-3 text-neutral-400">{e.collection_name}</td>
              <td className="px-4 py-3 text-neutral-600 font-mono text-xs">{e.document_id}</td>
              <td className="px-4 py-3 text-neutral-500">{new Date(e.created_at).toLocaleString("en-IN")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
