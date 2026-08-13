import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Sparkles, Send } from "lucide-react";

interface ChatEntry {
  question: string;
  answer: string;
  data: any[];
}

export default function AiAssistantPage() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<ChatEntry[]>([]);

  const ask = useMutation({
    mutationFn: async (q: string) => (await api.post("/ai-assistant/ask", { question: q })).data,
    onSuccess: (data, q) => {
      setHistory((h) => [...h, { question: q, answer: data.answer, data: data.data ?? [] }]);
      setQuestion("");
    },
  });

  return (
    <div className="max-w-3xl">
      <div className="card p-5 mb-4 flex items-start gap-3">
        <Sparkles size={18} className="text-gold-light mt-0.5 shrink-0" />
        <div className="text-sm text-neutral-400">
          Ask about revenue trends, lead sources, technician performance, low stock, or overdue follow-ups.
          Answers come from a whitelisted set of safe report queries — never arbitrary database access.
        </div>
      </div>

      <div className="space-y-4 mb-4">
        {history.map((entry, i) => (
          <div key={i} className="space-y-2">
            <div className="text-sm text-neutral-300 self-end bg-charcoal-700 rounded-lg px-3 py-2 inline-block">
              {entry.question}
            </div>
            <div className="card p-4">
              <p className="text-sm text-gold-light mb-2">{entry.answer}</p>
              {entry.data.length > 0 && (
                <pre className="text-xs text-neutral-400 overflow-x-auto bg-charcoal-900 rounded-lg p-3">
                  {JSON.stringify(entry.data.slice(0, 10), null, 2)}
                </pre>
              )}
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) ask.mutate(question.trim());
        }}
        className="flex gap-2"
      >
        <input
          className="input-field flex-1"
          placeholder="e.g. What's our revenue by branch this month?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" className="btn-gold flex items-center gap-2" disabled={ask.isPending}>
          <Send size={16} /> {ask.isPending ? "Thinking…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
