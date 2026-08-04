import { useAuth } from '@/components/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function GuestDashboard() {
  const { user, signOut } = useAuth();

  return (
    <div className="h-screen w-full flex items-center justify-center bg-background p-4 theme-org">
      <Card className="w-full max-w-md shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] border-4 border-border rounded-none bg-card">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center bg-muted border-2 border-border shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <span className="material-symbols-outlined text-3xl text-muted-foreground">gpp_maybe</span>
          </div>
          <CardTitle className="font-display-lg text-2xl font-bold uppercase tracking-tight text-foreground">
            Access Restricted
          </CardTitle>
          <CardDescription className="font-mono text-sm mt-2 uppercase font-bold text-muted-foreground">
            Welcome, {user?.displayName || user?.email || 'Guest'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 text-center">
          <div className="bg-muted p-4 border-2 border-border text-sm text-foreground shadow-[inset_2px_2px_0px_0px_rgba(0,0,0,0.1)]">
            <p className="font-body-md">
              You are currently logged in as a <strong>Guest</strong>. 
              Your account is not associated with any organization, and you do not have permissions to view any dashboard data.
            </p>
            <p className="mt-4 font-body-sm text-muted-foreground">
              If you believe this is an error, please wait for an invite or contact your administrator.
            </p>
          </div>
          
          <button 
            onClick={() => void signOut()} 
            className="w-full py-3 flex items-center justify-center gap-2 border-2 border-border font-bold uppercase tracking-widest text-foreground hover:bg-[#FF857F] hover:text-[#611F1D] transition-colors shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:shadow-none bg-background"
          >
            <span className="material-symbols-outlined text-lg">logout</span>
            Sign Out
          </button>
        </CardContent>
      </Card>
    </div>
  );
}
