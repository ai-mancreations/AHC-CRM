import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export function ProtectedRoute({ requireSuperAdmin = false }: { requireSuperAdmin?: boolean }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-charcoal-950">
        <div className="text-gold-light font-display text-xl animate-pulse">American Hair Club</div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (requireSuperAdmin && user.role !== "SUPER_ADMIN") return <Navigate to="/" replace />;

  return <Outlet />;
}
