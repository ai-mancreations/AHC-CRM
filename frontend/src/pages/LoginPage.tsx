import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@americanhairclub.in");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Invalid credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-charcoal-950 relative overflow-hidden">
      <div className="absolute inset-0 opacity-[0.07] pointer-events-none"
           style={{ backgroundImage: "radial-gradient(circle at 20% 20%, #C9A227 0, transparent 40%), radial-gradient(circle at 80% 80%, #C9A227 0, transparent 40%)" }} />

      <div className="relative w-full max-w-sm card p-8">
        <div className="text-center mb-8">
          <div className="font-display text-3xl text-gold-light">American</div>
          <div className="font-display text-3xl text-gold-light -mt-1">Hair Club</div>
          <div className="text-xs text-neutral-500 mt-2 tracking-widest uppercase">CRM &amp; Operations</div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs text-neutral-400 mb-1 block">Email</label>
            <input
              type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="input-field w-full" placeholder="you@americanhairclub.in"
            />
          </div>
          <div>
            <label className="text-xs text-neutral-400 mb-1 block">Password</label>
            <input
              type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className="input-field w-full" placeholder="••••••••"
            />
          </div>

          {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}

          <button type="submit" disabled={loading} className="btn-gold w-full disabled:opacity-60">
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="text-xs text-neutral-600 text-center mt-6">
          Demo: admin@americanhairclub.in / Admin@123 (Super Admin)<br />
          manager@americanhairclub.in / Manager@123 (Manager)
        </p>
      </div>
    </div>
  );
}
