import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from './AuthContext';
import { getMyOrganizations } from '@/services/organizations';
import type { OrganizationWithRole } from '@/types/api';

interface OrgContextType {
  organizations: OrganizationWithRole[];
  currentOrg: OrganizationWithRole | null;
  setCurrentOrg: (org: OrganizationWithRole) => void;
  isLoading: boolean;
}

const OrgContext = createContext<OrgContextType | null>(null);

export function OrgProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [currentOrg, setCurrentOrgState] = useState<OrganizationWithRole | null>(null);

  const { data: organizations = [], isLoading } = useQuery({
    queryKey: ['organizations', 'me'],
    queryFn: getMyOrganizations,
    enabled: !!token,
  });

  useEffect(() => {
    if (organizations.length > 0 && !currentOrg) {
      const saved = localStorage.getItem('medcore_org_id');
      const found = organizations.find((o) => o.id === saved);
      setCurrentOrgState(found || organizations[0]);
    }
  }, [organizations, currentOrg]);

  const setCurrentOrg = (org: OrganizationWithRole) => {
    setCurrentOrgState(org);
    localStorage.setItem('medcore_org_id', org.id);
  };

  return (
    <OrgContext.Provider value={{ organizations, currentOrg, setCurrentOrg, isLoading }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg() {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error('useOrg must be used within OrgProvider');
  return ctx;
}
