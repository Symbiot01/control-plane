import { useOrg } from '@/components/contexts/OrgContext';
import { useAuth } from '@/components/contexts/AuthContext';
import { Badge } from '@/components/ui/badge';
import { useSidebar } from '@/components/ui/sidebar';

export function OrgSwitcher() {
  const { currentOrg } = useOrg();
  const { user } = useAuth();
  const { state } = useSidebar();

  if (state === 'collapsed' || !currentOrg) return null;

  return (
    <div className="flex flex-col gap-1 px-3 py-2 mt-2 bg-secondary/10 rounded-md border border-primary/20">
      <span className="text-sm font-semibold truncate">{currentOrg.name}</span>
      <span className="text-xs text-muted-foreground truncate">
        {user?.displayName || user?.email}
      </span>
      <Badge variant="outline" className="w-fit text-[9px] font-label-caps uppercase rounded-sm border-primary text-primary bg-transparent px-1.5 py-0 mt-1">
        {currentOrg.role}
      </Badge>
    </div>
  );
}
