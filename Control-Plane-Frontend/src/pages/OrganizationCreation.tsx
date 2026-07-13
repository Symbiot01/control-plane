import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Building2 } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { PendingInviteResponse, AcceptInviteRequest } from '@/types/api';

export default function OrganizationCreation() {
  const navigate = useNavigate();
  const [orgName, setOrgName] = useState('');
  const [inviteId, setInviteId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetchPendingInvite = async () => {
      try {
        const data = await apiClient<PendingInviteResponse[]>('/invites/me/pending');
        if (data && data.length > 0) {
          setInviteId(data[0].id);
        } else {
          // No pending invites found, this shouldn't happen based on the previous redirect,
          // but if it does, send them to overview.
          navigate('/overview', { replace: true });
        }
      } catch (err: any) {
        setError(err.message || 'Failed to check pending invites.');
      } finally {
        setLoading(false);
      }
    };

    fetchPendingInvite();
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteId || !orgName.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      await apiClient<void>(`/invites/${inviteId}/accept`, {
        method: 'POST',
        body: JSON.stringify({ organization_name: orgName.trim() } as AcceptInviteRequest),
      });
      // Force reload to update org context and roles if needed, or rely on existing state.
      // A standard redirect will hit StandardGate which might refetch data.
      navigate('/overview', { replace: true });
    } catch (err: any) {
      setError(err.message || 'Failed to create organization.');
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-4">
        <p className="text-sm text-muted-foreground animate-pulse">Setting things up…</p>
      </div>
    );
  }

  if (error && !inviteId) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-4 overflow-hidden">
        <Card className="w-full max-w-sm -mt-16 border-destructive/50">
          <CardHeader className="text-center pb-4">
            <CardTitle className="text-xl text-destructive">Error</CardTitle>
            <CardDescription className="text-xs mt-2">{error}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="h-full flex items-center justify-center bg-background p-4 overflow-hidden">
      <Card className="w-full max-w-sm -mt-16">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
            <Building2 className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">Welcome to the platform!</CardTitle>
          <CardDescription className="text-sm mt-2">
            Let's set up your workspace. What is the name of your organization?
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="orgName" className="text-sm font-medium">Organization Name</Label>
              <Input
                id="orgName"
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Corp"
                className="h-10 text-base transition-all duration-200 focus:ring-2 focus:ring-primary/20"
                required
                autoFocus
              />
            </div>
            
            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}
            
            <Button type="submit" className="w-full h-10 text-sm font-medium mt-2" disabled={submitting || !orgName.trim()}>
              {submitting ? 'Creating Workspace…' : 'Complete Setup'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
