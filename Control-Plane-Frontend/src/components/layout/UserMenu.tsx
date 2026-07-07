import { Link } from 'react-router-dom';
import { LogOut, Shield } from 'lucide-react';
import { useAuth } from '@/components/contexts/AuthContext';
import { useOrg } from '@/components/contexts/OrgContext';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useSidebar } from '@/components/ui/sidebar';

export function UserMenu() {
  const { user, signOut, levelOfAccess } = useAuth();
  const { currentOrg } = useOrg();
  const { state } = useSidebar();
  const collapsed = state === 'collapsed';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 w-full rounded-lg px-2 py-1.5 hover:bg-secondary/30 transition-none outline-none">
        <Avatar className="h-7 w-7 rounded-full border border-primary">
          <AvatarFallback className="rounded-full bg-primary text-primary-foreground text-xs font-label-caps">
            {user?.email?.[0]?.toUpperCase() || 'U'}
          </AvatarFallback>
        </Avatar>
        {!collapsed && (
          <div className="flex-1 text-left min-w-0">
            <p className="text-xs font-medium truncate text-sidebar-foreground">
              {user?.email}
            </p>
            {currentOrg && (
              <Badge variant="outline" className="text-[9px] font-label-caps uppercase rounded-full border-primary text-primary bg-transparent px-1 py-0 mt-0.5">
                {currentOrg.role}
              </Badge>
            )}
          </div>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56 rounded-lg border border-primary shadow-none">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="font-data-sm text-data-sm font-bold uppercase">{user?.displayName || 'User'}</p>
            <p className="font-data-sm text-[10px] text-secondary">{user?.email}</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {levelOfAccess === 'super_admin' && (
          <DropdownMenuItem asChild className="text-xs cursor-pointer">
            <Link to="/admin/dashboard" className="flex items-center">
              <Shield className="mr-2 h-4 w-4" />
              Platform admin
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={signOut} className="text-destructive focus:bg-destructive focus:text-destructive-foreground font-label-caps uppercase transition-none">
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
