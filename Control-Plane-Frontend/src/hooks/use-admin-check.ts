import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/components/contexts/AuthContext';
import { getAdminStats } from '@/services/admin';

export function useAdminCheck() {
  const { token } = useAuth();

  const { data, isSuccess, isPending } = useQuery({
    queryKey: ['admin', 'check'],
    queryFn: getAdminStats,
    enabled: !!token,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return {
    isAdmin: isSuccess && !!data,
    isCheckingAdmin: !!token && isPending,
  };
}
