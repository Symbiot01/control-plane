import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate, useLocation } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider, useAuth } from "@/components/contexts/AuthContext";

import { AdminLayout } from "@/components/layout/AdminLayout";
import { AdminGate } from "@/components/layout/AdminGate";

import Login from "./pages/Login";
import InviteSignup from "./pages/InviteSignup";
import Onboarding from "./pages/Onboarding";
import OrganizationCreation from "./pages/OrganizationCreation";
import RoleDashboard from "./pages/RoleDashboard";
import GuestDashboard from "./pages/GuestDashboard";
import ViewerDashboard from "./pages/ViewerDashboard";
import NotFound from "./pages/NotFound";

import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminOrganizations from "./pages/admin/AdminOrganizations";
import AdminOrgDetail from "./pages/admin/AdminOrgDetail";
import AdminPlans from "./pages/admin/AdminPlans";
import AdminBilling from "./pages/admin/AdminBilling";
import AdminInvoiceDetail from "./pages/admin/AdminInvoiceDetail";
import AdminAccounts from "./pages/admin/AdminAccounts";
import AuditLog from "./pages/admin/AuditLog";
import AdminProducts from "./pages/admin/AdminProducts";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, hasPendingInvites } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-pulse text-sm text-muted-foreground">Loading…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  if (hasPendingInvites && location.pathname !== '/onboarding/organization') {
    return <Navigate to="/onboarding/organization" replace />;
  }

  return <>{children}</>;
}

function IndexRedirect() {
  const { levelOfAccess } = useAuth();
  if (levelOfAccess === 'super_admin') {
    return <Navigate to="/admin/dashboard" replace />;
  }
  if (levelOfAccess === 'guest') {
    return <Navigate to="/guest" replace />;
  }
  if (levelOfAccess === 'viewer') {
    return <Navigate to="/viewer" replace />;
  }
  return <Navigate to="/overview" replace />;
}

const App = () => (
  <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/invite" element={<InviteSignup />} />
              <Route path="/" element={<ProtectedRoute><IndexRedirect /></ProtectedRoute>} />
              <Route path="/overview" element={<ProtectedRoute><RoleDashboard /></ProtectedRoute>} />
              <Route path="/guest" element={<ProtectedRoute><GuestDashboard /></ProtectedRoute>} />
              <Route path="/viewer" element={<ProtectedRoute><ViewerDashboard /></ProtectedRoute>} />
              <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
              <Route path="/onboarding/organization" element={<ProtectedRoute><OrganizationCreation /></ProtectedRoute>} />
              
              <Route
                path="/admin"
                element={
                  <ProtectedRoute>
                    <AdminGate>
                      <AdminLayout />
                    </AdminGate>
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<AdminDashboard />} />
                <Route path="organizations" element={<AdminOrganizations />} />
                <Route path="organizations/:orgId" element={<AdminOrgDetail />} />
                <Route path="products" element={<AdminProducts />} />
                <Route path="plans" element={<AdminPlans />} />
                <Route path="billing" element={<AdminBilling />} />
                <Route path="billing/invoices/:invoiceId" element={<AdminInvoiceDetail />} />
                <Route path="accounts" element={<AdminAccounts />} />
                <Route path="audit-log" element={<AuditLog />} />
              </Route>
              
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
