import { Navigate } from 'react-router-dom';
import { useAuth } from '@/components/contexts/AuthContext';

export function OwnerGate({ children }: { children: React.ReactNode }) {
  const { levelOfAccess, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Checking access…</p>
      </div>
    );
  }

  if (levelOfAccess !== 'owner' && levelOfAccess !== 'super_admin') {
    return <Navigate to="/overview" replace />;
  }

  return <>{children}</>;
}

export function StandardGate({ children }: { children: React.ReactNode }) {
  const { levelOfAccess, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Checking access…</p>
      </div>
    );
  }

  // Guests cannot access the standard app layout
  if (levelOfAccess === 'guest') {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
