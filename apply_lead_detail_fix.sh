#!/bin/bash
# Run this from inside: /c/dev/american-hair-club_pythonversion/american-hair-club
#
# Fixes:
#  1. Slot booking failing after the first booking — MongoDB was returning
#     "naive" datetimes (no timezone) while the rest of the app uses
#     timezone-aware ones, so comparing them crashed. Fixed once, globally,
#     by making the DB client timezone-aware.
#  2. Clicking a lead in the pipeline did nothing — there was no detail view
#     wired up at all. Added one with comments, follow-up scheduling, and a
#     "Convert to Customer" button.
#  3. Dragging a lead into "Won" didn't create a customer — conversion was
#     never automatic. Now dragging into any status flagged as "won" (like
#     the seeded "Won" status) auto-converts it.
set -e
echo "Applying lead-detail + booking-timezone fix..."

mkdir -p "$(dirname "backend/app/core/db.py")"
cat > "backend/app/core/db.py" << 'PYEOF_0'
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import get_settings
from app.models import ALL_DOCUMENT_MODELS

settings = get_settings()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        # tz_aware=True is critical: without it, Motor/PyMongo returns naive
        # datetimes (no tzinfo) for every date read from Mongo, while the rest
        # of the app works with timezone-aware UTC datetimes (from
        # datetime.now(timezone.utc) and from parsing incoming ISO-8601
        # request bodies). Comparing a naive and an aware datetime raises a
        # TypeError in Python — this was silently breaking appointment
        # double-booking checks, follow-up due-date bucketing, and inventory
        # expiry filtering, whenever there was existing data to compare against.
        _client = AsyncIOMotorClient(settings.MONGO_URI, tz_aware=True)
    return _client


async def init_db():
    client = get_client()
    db = client[settings.MONGO_DB_NAME]
    await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)
    return db
PYEOF_0
echo "  wrote backend/app/core/db.py"

mkdir -p "$(dirname "backend/app/routers/leads.py")"
cat > "backend/app/routers/leads.py" << 'PYEOF_1'
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.lead import Lead, LeadActivity
from app.models.appointment import Customer
from app.models.enums import VisitReasonType, Role
from app.core.deps import get_current_user, require_super_admin
from app.services.audit import write_audit

router = APIRouter(prefix="/api/leads", tags=["leads"])


class LeadIn(BaseModel):
    branch_id: str
    name: str
    phone: str
    email: str | None = None
    lead_source_id: str
    lead_status_id: str
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    assigned_to_user_id: str | None = None
    campaign_name: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    notes: str | None = None


class StatusChangeIn(BaseModel):
    lead_status_id: str


class ConvertIn(BaseModel):
    address: str | None = None
    gst_state_code: str | None = None


@router.get("")
async def list_leads(branch_id: str | None = None, status_id: str | None = None,
                      _: User = Depends(get_current_user)):
    query = Lead.find(Lead.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Lead.branch_id == branch_id)
    if status_id:
        query = query.find(Lead.lead_status_id == status_id)
    return await query.sort("-created_at").to_list()


@router.get("/{lead_id}")
async def get_lead(lead_id: str, _: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    activities = await LeadActivity.find(LeadActivity.lead_id == lead_id).sort("-created_at").to_list()
    return {"lead": lead, "activities": activities}


@router.post("")
async def create_lead(body: LeadIn, user: User = Depends(get_current_user)):
    # duplicate-phone detection (same branch, not archived)
    dup = await Lead.find_one(Lead.phone == body.phone, Lead.branch_id == body.branch_id,
                               Lead.is_archived == False)  # noqa: E712
    lead = Lead(**body.model_dump())
    if dup:
        lead.is_duplicate_of = str(dup.id)
    await lead.insert()
    await LeadActivity(
        lead_id=str(lead.id), branch_id=lead.branch_id, activity_type="SYSTEM",
        description=f"Lead created via manual entry" + (" (possible duplicate detected)" if dup else ""),
        performed_by_user_id=str(user.id),
    ).insert()
    await write_audit(user, "CREATE", "leads", str(lead.id), after=lead)
    return lead


@router.put("/{lead_id}")
async def update_lead(lead_id: str, body: LeadIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    before = lead.model_copy()
    for k, v in body.model_dump().items():
        setattr(lead, k, v)
    lead.updated_at = datetime.now(timezone.utc)
    await lead.save()
    await write_audit(user, "UPDATE", "leads", str(lead.id), before=before, after=lead)
    return lead


@router.post("/{lead_id}/status")
async def change_status(lead_id: str, body: StatusChangeIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    old_status = lead.lead_status_id
    lead.lead_status_id = body.lead_status_id
    lead.updated_at = datetime.now(timezone.utc)
    await lead.save()
    await LeadActivity(
        lead_id=lead_id, branch_id=lead.branch_id, activity_type="STATUS_CHANGE",
        description=f"Status changed", performed_by_user_id=str(user.id),
        meta={"from": old_status, "to": body.lead_status_id},
    ).insert()
    return lead


@router.post("/{lead_id}/convert")
async def convert_to_customer(lead_id: str, body: ConvertIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.converted_customer_id:
        raise HTTPException(400, "Lead already converted")

    customer = Customer(
        branch_id=lead.branch_id, name=lead.name, phone=lead.phone, email=lead.email,
        address=body.address, gst_state_code=body.gst_state_code, source_lead_id=lead_id,
    )
    await customer.insert()
    lead.converted_customer_id = str(customer.id)
    lead.converted_at = datetime.now(timezone.utc)
    await lead.save()
    await LeadActivity(
        lead_id=lead_id, branch_id=lead.branch_id, activity_type="SYSTEM",
        description="Converted to customer", performed_by_user_id=str(user.id),
    ).insert()
    await write_audit(user, "UPDATE", "leads", lead_id, after=lead)
    return {"lead": lead, "customer": customer}


@router.post("/{lead_id}/archive")
async def archive_lead(lead_id: str, user: User = Depends(require_super_admin)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.is_archived = True
    await lead.save()
    await write_audit(user, "ARCHIVE", "leads", lead_id, after=lead)
    return lead


class NoteIn(BaseModel):
    text: str


@router.post("/{lead_id}/notes")
async def add_note(lead_id: str, body: NoteIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    await LeadActivity(
        lead_id=lead_id, branch_id=lead.branch_id, activity_type="NOTE",
        description=body.text, performed_by_user_id=str(user.id),
    ).insert()
    return {"ok": True}
PYEOF_1
echo "  wrote backend/app/routers/leads.py"

mkdir -p "$(dirname "backend/app/routers/calls_followups.py")"
cat > "backend/app/routers/calls_followups.py" << 'PYEOF_2'
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.lead import Call, FollowUp, LeadActivity
from app.models.enums import CallOutcome, FollowUpStatus
from app.core.deps import get_current_user

router = APIRouter(prefix="/api", tags=["calls-followups"])


class CallIn(BaseModel):
    lead_id: str | None = None
    customer_id: str | None = None
    branch_id: str
    direction: str = "OUTBOUND"
    phone: str
    outcome: CallOutcome
    duration_seconds: int | None = None
    notes: str | None = None


class FollowUpIn(BaseModel):
    lead_id: str | None = None
    customer_id: str | None = None
    branch_id: str
    due_date: datetime
    notes: str | None = None
    assigned_to_user_id: str | None = None


class CommentIn(BaseModel):
    text: str


class CompleteIn(BaseModel):
    comment: str | None = None
    reschedule_due_date: datetime | None = None
    reschedule_notes: str | None = None


@router.get("/calls")
async def list_calls(branch_id: str | None = None, lead_id: str | None = None,
                      _: User = Depends(get_current_user)):
    query = Call.find()
    if branch_id:
        query = query.find(Call.branch_id == branch_id)
    if lead_id:
        query = query.find(Call.lead_id == lead_id)
    return await query.sort("-called_at").to_list()


@router.post("/calls")
async def log_call(body: CallIn, user: User = Depends(get_current_user)):
    call = Call(**body.model_dump(), performed_by_user_id=str(user.id))
    await call.insert()
    if body.lead_id:
        await LeadActivity(
            lead_id=body.lead_id, branch_id=body.branch_id, activity_type="CALL",
            description=f"Call logged: {body.outcome.value}", performed_by_user_id=str(user.id),
        ).insert()
    return call


@router.get("/follow-ups")
async def list_follow_ups(branch_id: str | None = None, bucket: str | None = None,
                           lead_id: str | None = None, _: User = Depends(get_current_user)):
    """bucket: today | overdue | upcoming. When lead_id is given, returns full
    history for that lead (all statuses) rather than only PENDING ones."""
    query = FollowUp.find() if lead_id else FollowUp.find(FollowUp.status == FollowUpStatus.PENDING)
    if branch_id:
        query = query.find(FollowUp.branch_id == branch_id)
    if lead_id:
        query = query.find(FollowUp.lead_id == lead_id)
    items = await query.sort("-due_date" if lead_id else "+due_date").to_list()

    if bucket:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        if bucket == "overdue":
            items = [i for i in items if i.due_date < today_start]
        elif bucket == "today":
            items = [i for i in items if today_start <= i.due_date <= today_end]
        elif bucket == "upcoming":
            items = [i for i in items if i.due_date > today_end]
    return items


@router.post("/follow-ups")
async def create_follow_up(body: FollowUpIn, _: User = Depends(get_current_user)):
    fu = FollowUp(**body.model_dump())
    await fu.insert()
    return fu


@router.post("/follow-ups/{fu_id}/comments")
async def add_comment(fu_id: str, body: CommentIn, user: User = Depends(get_current_user)):
    fu = await FollowUp.get(fu_id)
    if not fu:
        raise HTTPException(404, "Follow-up not found")
    fu.comments.append({
        "text": body.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user.id),
        "user_name": user.name,
    })
    await fu.save()
    return fu


@router.post("/follow-ups/{fu_id}/complete")
async def complete_follow_up(fu_id: str, body: CompleteIn | None = None, user: User = Depends(get_current_user)):
    fu = await FollowUp.get(fu_id)
    if not fu:
        raise HTTPException(404, "Follow-up not found")

    body = body or CompleteIn()
    if body.comment:
        fu.comments.append({
            "text": body.comment,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user.id),
            "user_name": user.name,
        })

    fu.status = FollowUpStatus.DONE
    fu.completed_at = datetime.now(timezone.utc)
    await fu.save()

    new_follow_up = None
    if body.reschedule_due_date:
        new_follow_up = FollowUp(
            lead_id=fu.lead_id, customer_id=fu.customer_id, branch_id=fu.branch_id,
            due_date=body.reschedule_due_date, notes=body.reschedule_notes or fu.notes,
            assigned_to_user_id=fu.assigned_to_user_id,
        )
        await new_follow_up.insert()

    return {"completed": fu, "next_follow_up": new_follow_up}
PYEOF_2
echo "  wrote backend/app/routers/calls_followups.py"

mkdir -p "$(dirname "frontend/src/components/leads/LeadDetailModal.tsx")"
cat > "frontend/src/components/leads/LeadDetailModal.tsx" << 'PYEOF_3'
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SettingsItem } from "@/types";
import { Phone, MessageSquarePlus, UserCheck, Clock } from "lucide-react";

interface LeadFull {
  id: string;
  branch_id: string;
  name: string;
  phone: string;
  email?: string | null;
  lead_source_id: string;
  lead_status_id: string;
  visit_reason: string;
  notes?: string | null;
  converted_customer_id?: string | null;
}

interface Activity {
  id: string;
  activity_type: string;
  description: string;
  created_at: string;
}

interface FollowUp {
  id: string;
  due_date: string;
  notes?: string | null;
  status: string;
}

const ACTIVITY_LABELS: Record<string, string> = {
  SYSTEM: "System", CALL: "Call", STATUS_CHANGE: "Status Change", NOTE: "Note", WHATSAPP: "WhatsApp",
};

export function LeadDetailModal({ leadId, statuses, onClose }: {
  leadId: string;
  statuses: SettingsItem[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [followUpDate, setFollowUpDate] = useState("");
  const [followUpNotes, setFollowUpNotes] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["lead-detail", leadId],
    queryFn: async () => (await api.get<{ lead: LeadFull; activities: Activity[] }>(`/leads/${leadId}`)).data,
  });

  const { data: followUps } = useQuery({
    queryKey: ["follow-ups", "for-lead", leadId],
    queryFn: async () => (await api.get<FollowUp[]>("/follow-ups", { params: { lead_id: leadId } })).data,
  });

  const addComment = useMutation({
    mutationFn: async (text: string) => api.post(`/leads/${leadId}/notes`, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lead-detail", leadId] });
      setComment("");
    },
  });

  const addFollowUp = useMutation({
    mutationFn: async () =>
      api.post("/follow-ups", {
        lead_id: leadId,
        branch_id: data!.lead.branch_id,
        due_date: new Date(followUpDate).toISOString(),
        notes: followUpNotes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups", "for-lead", leadId] });
      setFollowUpDate("");
      setFollowUpNotes("");
    },
  });

  const convertToCustomer = useMutation({
    mutationFn: async () => api.post(`/leads/${leadId}/convert`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lead-detail", leadId] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  if (isLoading || !data) return <div className="text-neutral-500 text-sm">Loading…</div>;
  const { lead, activities } = data;
  const status = statuses.find((s) => s.id === lead.lead_status_id);

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-lg text-neutral-100 font-medium">{lead.name}</h3>
          {status && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${status.extra?.color ?? "#C9A227"}22`, color: status.extra?.color ?? "#C9A227" }}>
              {status.name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-sm text-neutral-400 mt-1">
          <Phone size={13} /> {lead.phone} {lead.email && `· ${lead.email}`}
        </div>
        {lead.notes && <p className="text-sm text-neutral-400 mt-2">{lead.notes}</p>}
      </div>

      {lead.converted_customer_id ? (
        <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-3 py-2">
          <UserCheck size={15} /> Converted to customer
        </div>
      ) : (
        <button
          onClick={() => convertToCustomer.mutate()}
          disabled={convertToCustomer.isPending}
          className="btn-gold w-full text-sm disabled:opacity-60"
        >
          {convertToCustomer.isPending ? "Converting…" : "Convert to Customer"}
        </button>
      )}

      <div>
        <h4 className="text-sm font-medium text-neutral-300 mb-2 flex items-center gap-2">
          <Clock size={14} /> Follow-Ups
        </h4>
        <div className="space-y-2 mb-3">
          {(followUps ?? []).map((fu) => (
            <div key={fu.id} className="bg-charcoal-700 rounded-lg px-3 py-2 text-xs">
              <div className="flex justify-between">
                <span className="text-neutral-300">{fu.notes ?? "Follow-up"}</span>
                <span className={fu.status === "PENDING" ? "text-amber-400" : "text-neutral-500"}>{fu.status}</span>
              </div>
              <div className="text-neutral-500 mt-1">{new Date(fu.due_date).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</div>
            </div>
          ))}
          {(followUps ?? []).length === 0 && <div className="text-xs text-neutral-600">No follow-ups scheduled yet.</div>}
        </div>
        <div className="flex gap-2">
          <input type="date" className="input-field text-sm" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)} />
          <input
            className="input-field flex-1 text-sm" placeholder="Follow-up notes…"
            value={followUpNotes} onChange={(e) => setFollowUpNotes(e.target.value)}
          />
          <button
            onClick={() => followUpDate && addFollowUp.mutate()}
            disabled={!followUpDate || addFollowUp.isPending}
            className="btn-ghost text-xs px-3 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      <div>
        <h4 className="text-sm font-medium text-neutral-300 mb-2 flex items-center gap-2">
          <MessageSquarePlus size={14} /> Timeline &amp; Comments
        </h4>
        <div className="flex gap-2 mb-3">
          <input
            className="input-field flex-1 text-sm" placeholder="Add a comment…"
            value={comment} onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && comment.trim()) addComment.mutate(comment.trim()); }}
          />
          <button
            onClick={() => comment.trim() && addComment.mutate(comment.trim())}
            className="btn-ghost text-xs px-3"
          >
            Post
          </button>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto border-l-2 border-charcoal-border pl-3">
          {activities.map((a) => (
            <div key={a.id} className="text-xs">
              <span className="text-neutral-500">[{ACTIVITY_LABELS[a.activity_type] ?? a.activity_type}]</span>{" "}
              <span className="text-neutral-300">{a.description}</span>
              <div className="text-neutral-600">{new Date(a.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}</div>
            </div>
          ))}
          {activities.length === 0 && <div className="text-xs text-neutral-600">No activity yet.</div>}
        </div>
      </div>
    </div>
  );
}
PYEOF_3
echo "  wrote frontend/src/components/leads/LeadDetailModal.tsx"

mkdir -p "$(dirname "frontend/src/pages/LeadsKanbanPage.tsx")"
cat > "frontend/src/pages/LeadsKanbanPage.tsx" << 'PYEOF_4'
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
PYEOF_4
echo "  wrote frontend/src/pages/LeadsKanbanPage.tsx"

echo ""
echo "All files applied. Now rebuild and restart:"
echo "  docker compose down"
echo "  find backend -name __pycache__ -exec rm -rf {} +"
echo "  docker compose build --no-cache backend celery-worker"
echo "  docker compose up -d"
