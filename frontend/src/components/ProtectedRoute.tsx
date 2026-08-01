import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { getToken, getCurrentUser } from "../lib/api";
import { tokens } from "../lib/theme";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"checking" | "valid" | "invalid">("checking");

  useEffect(() => {
    if (!getToken()) {
      setStatus("invalid");
      return;
    }
    // A token existing in localStorage doesn't mean it's still valid —
    // it could be expired or revoked. Confirm with the backend before
    // trusting it, rather than just checking presence.
    getCurrentUser()
      .then(() => setStatus("valid"))
      .catch(() => setStatus("invalid"));
  }, []);

  if (status === "checking") {
    return (
      <div
        className="min-h-screen w-full flex items-center justify-center"
        style={{ background: tokens.paper, color: tokens.muted }}
      >
        Checking your session…
      </div>
    );
  }

  if (status === "invalid") {
    return <Navigate to="/signin" replace />;
  }

  return <>{children}</>;
}
