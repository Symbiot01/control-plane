import { createContext, useContext, useEffect, useState, useCallback, useRef, type ReactNode } from 'react';
import {
  type User,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
  createUserWithEmailAndPassword,
  updateProfile,
} from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { setAuthToken } from '@/lib/api-client';
import { exchangeToken } from '@/services/auth';
import { jwtDecode } from 'jwt-decode';

interface DecodedToken {
  sub: string;
  org_id?: string;
  level_of_access: 'super_admin' | 'owner' | 'member' | 'viewer' | 'guest';
}

interface AuthState {
  user: User | null;
  token: string | null;
  levelOfAccess: 'super_admin' | 'owner' | 'member' | 'viewer' | 'guest' | null;
  hasPendingInvites: boolean;
  loading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, firstName: string, lastName: string) => Promise<import('@/types/api').AuthExchangeResponse | undefined>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    levelOfAccess: null,
    hasPendingInvites: false,
    loading: true,
    error: null,
  });
  const refreshTimer = useRef<ReturnType<typeof setTimeout>>();
  const isSigningUp = useRef(false);

  const doExchange = useCallback(async (user: User) => {
    try {
      const idToken = await user.getIdToken(true);
      const res = await exchangeToken(idToken, user.displayName);
      const decoded = jwtDecode<DecodedToken>(res.access_token);
      setAuthToken(res.access_token);
      setState({ 
        user, 
        token: res.access_token, 
        levelOfAccess: decoded.level_of_access, 
        hasPendingInvites: !!res.has_pending_invites,
        loading: false, 
        error: null 
      });

      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(() => {
        if (auth.currentUser) doExchange(auth.currentUser);
      }, Math.max((res.expires_in - 300) * 1000, 60000));
      
      return res;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Token exchange failed';
      setState({ user, token: null, levelOfAccess: 'guest', hasPendingInvites: false, loading: false, error: message });
      setAuthToken(null);
    }
  }, []);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (user) => {
      if (user) {
        if (!isSigningUp.current) {
          await doExchange(user);
        }
      } else {
        setState({ user: null, token: null, levelOfAccess: null, hasPendingInvites: false, loading: false, error: null });
        setAuthToken(null);
      }
    });
    return () => {
      unsub();
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [doExchange]);

  const signIn = async (email: string, password: string) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Sign in failed';
      setState((s) => ({ ...s, loading: false, error: message }));
    }
  };

  const signUp = async (email: string, password: string, firstName: string, lastName: string) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    isSigningUp.current = true;
    try {
      const userCred = await createUserWithEmailAndPassword(auth, email, password);
      const fullName = `${firstName.trim()} ${lastName.trim()}`;
      await updateProfile(userCred.user, {
        displayName: fullName
      });
      await userCred.user.getIdToken(true);
      return await doExchange(userCred.user);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Sign up failed';
      setState((s) => ({ ...s, loading: false, error: message }));
    } finally {
      isSigningUp.current = false;
    }
  };

  const signInWithGoogle = async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      await signInWithPopup(auth, new GoogleAuthProvider());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Google sign in failed';
      setState((s) => ({ ...s, loading: false, error: message }));
    }
  };

  const signOut = async () => {
    await firebaseSignOut(auth);
    setAuthToken(null);
  };

  return (
    <AuthContext.Provider value={{ ...state, signIn, signUp, signInWithGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
