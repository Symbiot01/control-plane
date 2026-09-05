import { Outlet, Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useAuth } from '@/components/contexts/AuthContext';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { motion } from 'framer-motion';

const adminLinks = [
  { to: '/admin/dashboard', label: 'Dashboard' },
  { to: '/admin/organizations', label: 'Orgs' },
  { to: '/admin/deliverables', label: 'Deliverables' },
  { to: '/admin/products', label: 'Products' },
  { to: '/admin/plans', label: 'Plans' },
  { to: '/admin/billing', label: 'Billing' },
  { to: '/admin/accounts', label: 'Accounts' },
  { to: '/admin/audit-log', label: 'Audit log' },
];

export function AdminLayout() {
  const location = useLocation();
  const { user, signOut } = useAuth();

  return (
    <div className="bg-background min-h-screen text-foreground antialiased flex flex-col">
      <nav className="fixed top-0 w-full z-50 bg-card border-b border-border shadow-sm flex items-center justify-between px-md py-xs h-16">
        <div className="flex items-center gap-md">
          <div className="flex items-center gap-sm">
            <span className="material-symbols-outlined text-primary cursor-pointer hover:bg-muted rounded-full p-2 transition-colors">menu</span>
            <span className="font-headline-lg text-headline-lg text-primary tracking-tight hidden md:flex items-center">
              <span className="font-cursive text-4xl leading-none">C</span>ontrolPlane
            </span>
          </div>

        </div>
        
        {/* Navigation Links inside Nav for quick access */}
        <div className="hidden lg:flex items-center gap-1 overflow-x-auto mx-4 flex-1 justify-center">
          {adminLinks.map(({ to, label }) => {
            const isActive = location.pathname === to || location.pathname.startsWith(`${to}/`);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  'relative text-sm px-3 py-1.5 rounded-md transition-colors whitespace-nowrap',
                  isActive ? 'font-medium text-primary' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="admin-nav-indicator"
                    className="absolute inset-0 bg-muted rounded-md z-[-1]"
                    initial={false}
                    transition={{
                      type: 'spring',
                      stiffness: 500,
                      damping: 30,
                    }}
                  />
                )}
                <span className="relative z-10">{label}</span>
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-sm">
          <ThemeToggle />
          <span className="material-symbols-outlined text-muted-foreground cursor-pointer hover:bg-muted p-2 rounded-full transition-colors active:opacity-80" onClick={() => void signOut()} title="Sign out">logout</span>
          <Avatar className="w-8 h-8 ml-2 border border-primary cursor-pointer hover:opacity-80 transition-opacity">
            <AvatarFallback className="bg-primary text-primary-foreground text-xs font-semibold uppercase">
              {user?.email?.[0] || 'A'}
            </AvatarFallback>
          </Avatar>
        </div>
      </nav>

      <div className="flex-1 flex mt-16 overflow-hidden">
        <main className="flex-1 overflow-y-auto p-margin-mobile md:p-margin-desktop">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
