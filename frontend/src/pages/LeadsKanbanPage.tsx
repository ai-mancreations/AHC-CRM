import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { Modal } from "@/components/shared/Modal";
import { AddLeadForm } from "@/components/leads/AddLeadForm";
import { ImportLeadsForm } from "@/components/leads/ImportLeadsForm";
import { LeadDetailModal } from "@/components/leads/LeadDetailModal";
import type { Lead, SettingsItem } from "@/types";
import { Plus, Phone, UploadCloud } from "lucide-react";

export default function LeadsKanbanPage() {
  const { selectedBranchId, branches } = useBranch();
  const queryClient = useQueryClient();
  const [dragLeadId, setDragLeadId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [openLeadId, setOpenLeadId] = useState<string | null>(null);

  const { data: statuses } = useQuery({
    queryKey: ["settings", "LEAD_STATUS"],
    queryFn: async () => (await api.get<SettingsItem[]>("/settings/lists/LEAD_STATUS")).data,
  });

  const { data: sources } = useQuery({
    queryKey: ["settings", "LEAD_SOURCE"],
    queryFn: async () => (await api.get<SettingsItem[]>("/settings/lists/LEAD_SOURCE")).data,
  });

  const { data: leads } = useQuery({
    queryKey: ["leads", selectedBranchId],
    queryFn: async () =>
      (await api.get<Lead[]>("/leads", { params: selectedBranchId ? { branch_id: selectedBranchId } : {} })).data,
  });

  const sourceById = useMemo(() => Object.fromEntries((sources ?? []).map((s) => [s.id, s.name])), [sources]);

  const changeStatus = useMutation({
    mutationFn: async ({ leadId, statusId }: { leadId: string; statusId: string }) =>
      api.post(`/leads/${leadId}/status`, { lead_status_id: statusId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["leads"] }),
  });

  const convertToCustomer = useMutation({
    mutationFn: async (leadId: string) => api.post(`/leads/${leadId}/convert`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  const leadsByStatus = useMemo(() => {
    const map: Record<string, Lead[]> = {};
    for (const status of statuses ?? []) map[status.id] = [];
    for (const lead of leads ?? []) {
      if (!map[lead.lead_status_id]) map[lead.lead_status_id] = [];
      map[lead.lead_status_id].push(lead);
    }
    return map;
  }, [leads, statuses]);

  const readyToAdd = branches.length > 0 && (sources?.length ?? 0) > 0 && (statuses?.length ?? 0) > 0;

  async function handleDrop(targetStatus: SettingsItem) {
    if (!dragLeadId) return;
    const lead = (leads ?? []).find((l) => l.id === dragLeadId);
    await changeStatus.mutateAsync({ leadId: dragLeadId, statusId: targetStatus.id });
    // Auto-convert to customer when dropped into a status flagged as "won",
    // so a lead won via drag-and-drop doesn't require a separate manual step.
    if (targetStatus.extra?.is_won && lead && !lead.converted_customer_id) {
      convertToCustomer.mutate(dragLeadId);
    }
    setDragLeadId(null);
  }

  return (
    <div>
      <div className="flex justify-end gap-2 mb-4">
        <button onClick={() => setShowImportModal(true)} className="btn-ghost flex items-center gap-2 text-sm">
          <UploadCloud size={16} /> Import CSV
        </button>
        <button
          onClick={() => setShowAddModal(true)}
          disabled={!readyToAdd}
          className="btn-gold flex items-center gap-2 text-sm disabled:opacity-50"
        >
          <Plus size={16} /> Quick Add Lead
        </button>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {(statuses ?? []).map((status) => (
          <div
            key={status.id}
            className="w-72 shrink-0"
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => handleDrop(status)}
          >
            <div className="flex items-center gap-2 mb-3 px-1">
              <span className="w-2 h-2 rounded-full" style={{ background: status.extra?.color ?? "#C9A227" }} />
              <h3 className="text-sm font-medium text-neutral-300">{status.name}</h3>
              <span className="text-xs text-neutral-600 ml-auto">{leadsByStatus[status.id]?.length ?? 0}</span>
            </div>

            <div className="space-y-2 min-h-[120px]">
              {(leadsByStatus[status.id] ?? []).map((lead) => (
                <div
                  key={lead.id}
                  draggable
                  onDragStart={() => setDragLeadId(lead.id)}
                  onClick={() => setOpenLeadId(lead.id)}
                  className="card p-3 cursor-pointer hover:border-gold/40 transition"
                >
                  <div className="text-sm font-medium text-neutral-100">{lead.name}</div>
                  <div className="flex items-center gap-1.5 text-xs text-neutral-500 mt-1">
                    <Phone size={11} /> {lead.phone}
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-[11px] text-gold-light/80 bg-gold/10 px-2 py-0.5 rounded-full">
                      {sourceById[lead.lead_source_id] ?? "—"}
                    </span>
                    {lead.campaign_name && (
                      <span className="text-[10px] text-neutral-600 truncate max-w-[100px]">{lead.campaign_name}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Modal open={showAddModal} onClose={() => setShowAddModal(false)} title="Add Lead">
        {readyToAdd && (
          <AddLeadForm
            branches={branches}
            sources={sources ?? []}
            statuses={statuses ?? []}
            defaultBranchId={selectedBranchId}
            onDone={() => setShowAddModal(false)}
          />
        )}
      </Modal>

      <Modal open={showImportModal} onClose={() => setShowImportModal(false)} title="Import Leads from CSV">
        {branches.length > 0 && (
          <ImportLeadsForm
            branches={branches}
            defaultBranchId={selectedBranchId}
            onDone={() => setShowImportModal(false)}
          />
        )}
      </Modal>

      <Modal open={!!openLeadId} onClose={() => setOpenLeadId(null)} title="Lead Details" maxWidth="max-w-lg">
        {openLeadId && <LeadDetailModal leadId={openLeadId} statuses={statuses ?? []} onClose={() => setOpenLeadId(null)} />}
      </Modal>
    </div>
  );
}
