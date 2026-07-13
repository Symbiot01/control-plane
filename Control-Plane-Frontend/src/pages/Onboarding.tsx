import { useAuth } from '@/components/contexts/AuthContext';
import { Navigate } from 'react-router-dom';

export default function Onboarding() {
  const { levelOfAccess } = useAuth();

  if (levelOfAccess !== 'guest') {
    return <Navigate to="/overview" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="max-w-md w-full space-y-8 text-center">
        <div>
          <h2 className="mt-6 text-3xl font-bold tracking-tight">Welcome to MedCore</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            You haven't joined a workspace yet.
          </p>
        </div>
        <div className="space-y-4">
          <button className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90">
            Create New Workspace
          </button>
          <button className="w-full flex justify-center py-2 px-4 border border-input rounded-md shadow-sm text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground">
            Join Existing Workspace
          </button>
        </div>
      </div>
    </div>
  );
}
