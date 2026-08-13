import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SettingsItem } from "@/types";
import { Plus, Archive } from "lucide-react";
import { ServiceTypesPanel } from "@/components/settings/ServiceTypesPanel";
import { MessageTemplatesPanel } from "@/components/settings/MessageTemplatesPanel";
import { CompanyConfigPanel } from "@/components/settings/CompanyConfigPanel";

const LIST_TYPES = [
  "LEAD_SOURCE", "LEAD_STATUS", "VISIT_REASON", "HAIR_SYSTEM_SIZE", "HAIR_SYSTEM_MODEL",
  "HAIR_COLOR", "HAIR_LENGTH", "HAIR_DENSITY", "BASE_MATERIAL", "INVENTORY_CATEGORY",
  "EXPENSE_CATEGORY", "TECHNICIAN_DESIGNATION",
];

const SECTIONS = [
  { key: "MASTER_DATA", label: "Master Data" },
  { key: "SERVICE_TYPES", label: "Service Types & Pricing" },
  { key: "MESSAGE_TEMPLATES", label: "Message Templates" },
  { key: "COMPANY_CONFIG", label: "Company & GST" },
] as const;

function label(listType: string) {
  return listType.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function MasterDataPanel() {
  const [activeList, setActiveList] = useState(LIST_TYPES[0]);
  const [newName, setNewName] = useState("");
  const queryClient = useQueryClient();

  const { data: items, isLoading } = useQuery({
    queryKey: ["settings", activeList],
    queryFn: async () => (await api.get<SettingsItem[]>(`/settings/lists/${activeList}`)).data,
  });

  const createItem = useMutation({
    mutationFn: async (name: string) =>
      api.post("/settings/lists", { list_type: activeList, name, sort_order: (items?.length ?? 0) }),
    onSuccess: () => {
      setNewName("");
      queryClient.invalidateQueries({ queryKey: ["settings", activeList] });
    },
  });

  const archiveItem = useMutation({
    mutationFn: async (id: string) => api.post(`/settings/lists/${id}/archive`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", activeList] }),
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-6">
      <nav className="space-y-1">
        {LIST_TYPES.map((lt) => (
          <button
            key={lt}
            onClick={() => setActiveList(lt)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
              activeList === lt ? "bg-charcoal-700 text-gold-light border border-gold/30" : "text-neutral-400 hover:bg-charcoal-800"
            }`}
          >
            {label(lt)}
          </button>
        ))}
      </nav>

      <div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (newName.trim()) createItem.mutate(newName.trim());
          }}
          className="flex gap-2 mb-4"
        >
          <input
            className="input-field flex-1"
            placeholder={`Add new ${label(activeList).toLowerCase()}…`}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button type="submit" className="btn-gold flex items-center gap-1 text-sm">
            <Plus size={15} /> Add
          </button>
        </form>

        <div className="card divide-y divide-charcoal-border">
          {isLoading && <div className="p-4 text-neutral-600 text-sm">Loading…</div>}
          {(items ?? []).map((item) => (
            <div key={item.id} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-2">
                {item.extra?.color && (
                  <span className="w-2 h-2 rounded-full" style={{ background: item.extra.color }} />
                )}
                <span className="text-sm text-neutral-200">{item.name}</span>
              </div>
              <button
                onClick={() => archiveItem.mutate(item.id)}
                className="text-neutral-600 hover:text-red-400 transition"
                title="Archive"
              >
                <Archive size={15} />
              </button>
            </div>
          ))}
          {!isLoading && (items ?? []).length === 0 && (
            <div className="p-4 text-neutral-600 text-sm">No entries yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["key"]>("MASTER_DATA");

  return (
    <div>
      <div className="flex gap-2 mb-6 border-b border-charcoal-border">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            onClick={() => setSection(s.key)}
            className={`px-4 py-2.5 text-sm border-b-2 -mb-px transition ${
              section === s.key ? "border-gold text-gold-light" : "border-transparent text-neutral-500 hover:text-neutral-300"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === "MASTER_DATA" && <MasterDataPanel />}
      {section === "SERVICE_TYPES" && <ServiceTypesPanel />}
      {section === "MESSAGE_TEMPLATES" && <MessageTemplatesPanel />}
      {section === "COMPANY_CONFIG" && <CompanyConfigPanel />}
    </div>
  );
}
