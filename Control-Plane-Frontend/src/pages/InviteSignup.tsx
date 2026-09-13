import { useState, useEffect } from 'react';
import { Navigate, useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@/components/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Shield, Eye, EyeOff } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { InviteDetailResponse } from '@/types/api';

export default function InviteSignup() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const { user, levelOfAccess, hasPendingInvites, loading: authLoading, signUp, signIn } = useAuth();
  
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isExistingAccount, setIsExistingAccount] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [inviteLoading, setInviteLoading] = useState(true);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setInviteError("Invalid or missing invite token.");
      setInviteLoading(false);
      return;
    }

    const fetchInviteDetails = async () => {
      try {
        const data = await apiClient<InviteDetailResponse>(`/invites/${token}`);
        setEmail(data.email);
        if (data.account_exists) {
          setIsExistingAccount(true);
        }
      } catch (err: any) {
        setInviteError(err.message || "Failed to load invite details.");
      } finally {
        setInviteLoading(false);
      }
    };

    fetchInviteDetails();
  }, [token]);

  if (authLoading || inviteLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-4">
        <p className="text-sm text-muted-foreground animate-pulse">Loading invite details…</p>
      </div>
    );
  }

  if (user) {
    if (hasPendingInvites) {
      return <Navigate to="/onboarding/organization" replace />;
    }
    if (levelOfAccess === 'super_admin') {
      return <Navigate to="/admin/dashboard" replace />;
    }
    if (levelOfAccess === 'viewer') {
      return <Navigate to="/viewer" replace />;
    }
    return <Navigate to="/overview" replace />;
  }

  if (inviteError) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-4 overflow-hidden">
        <Card className="w-full max-w-sm -mt-16 border-destructive/50">
          <CardHeader className="text-center pb-4">
            <CardTitle className="text-xl text-destructive">Invalid Invite</CardTitle>
            <CardDescription className="text-xs mt-2">{inviteError}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (password !== confirmPassword) {
      setSubmitError("Passwords do not match");
      return;
    }

    setSubmitLoading(true);
    try {
      const res = await signUp(email, password, firstName, lastName);
      if (res?.has_pending_invites) {
        navigate('/onboarding/organization', { replace: true });
      } else {
        navigate('/overview', { replace: true });
      }
    } catch (err: any) {
      setSubmitError(err.message || "Account creation failed.");
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitLoading(true);
    try {
      await signIn(email, password);
      // We don't navigate manually here because the useEffect on `user` will trigger
      // the redirect to `/onboarding/organization` since hasPendingInvites will be true.
    } catch (err: any) {
      setSubmitError(err.message || "Sign in failed.");
    } finally {
      setSubmitLoading(false);
    }
  };

  if (isExistingAccount) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-4 overflow-hidden">
        <Card className="w-full max-w-sm -mt-16">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
              <Shield className="h-5 w-5 text-primary-foreground" />
            </div>
            <CardTitle className="text-xl">Welcome Back</CardTitle>
            <CardDescription className="text-xs">
              You've been invited to join an organization. Login to accept.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLoginSubmit} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  disabled
                  className="h-9 text-sm opacity-60 cursor-not-allowed bg-muted"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-9 text-sm transition-all duration-200 pr-9"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              
              {submitError && (
                <p className="text-xs text-destructive">{submitError}</p>
              )}
              
              <Button type="submit" className="w-full h-9 text-sm mt-2" disabled={submitLoading}>
                {submitLoading ? 'Signing in…' : 'Sign in to accept'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="h-full flex items-center justify-center bg-background p-4 overflow-hidden">
      <Card className="w-full max-w-sm -mt-16">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
            <Shield className="h-5 w-5 text-primary-foreground" />
          </div>
          <CardTitle className="text-xl">Accept Invite</CardTitle>
          <CardDescription className="text-xs">
            Create your account to join the organization
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSignupSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="firstName" className="text-xs">First Name</Label>
                <Input
                  id="firstName"
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="John"
                  className="h-9 text-sm transition-all duration-200"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="lastName" className="text-xs">Last Name</Label>
                <Input
                  id="lastName"
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Doe"
                  className="h-9 text-sm transition-all duration-200"
                  required
                />
              </div>
            </div>
            
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                disabled
                className="h-9 text-sm opacity-60 cursor-not-allowed bg-muted"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-9 text-sm transition-all duration-200 pr-9"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirmPassword" className="text-xs">Confirm Password</Label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="h-9 text-sm transition-all duration-200 pr-9"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            
            {submitError && (
              <p className="text-xs text-destructive">{submitError}</p>
            )}
            
            <Button type="submit" className="w-full h-9 text-sm mt-2" disabled={submitLoading}>
              {submitLoading ? 'Creating Account…' : 'Create Account'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
