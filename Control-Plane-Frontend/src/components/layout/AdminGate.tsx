import { Navigate } from 'react-router-dom';
import { useAuth } from '@/components/contexts/AuthContext';

export function AdminGate({ children }: { children: React.ReactNode }) {
  const { levelOfAccess, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Checking access…</p>
      </div>
    );
  }

  if (levelOfAccess !== 'super_admin') {
    return <Navigate to="/overview" replace />;
  }

  return <>{children}</>;
}
