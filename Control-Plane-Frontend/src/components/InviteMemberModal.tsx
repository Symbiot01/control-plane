import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { inviteMember } from '@/services/organizations';
import type { OrgRole } from '@/types/api';
import WheelPicker from './WheelPicker';

interface InviteMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
}

export default function InviteMemberModal({ isOpen, onClose, orgId }: InviteMemberModalProps) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<OrgRole>('member');
  const [expiresInDays, setExpiresInDays] = useState<number>(3);
  const [successUrl, setSuccessUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const inviteMutation = useMutation({
    mutationFn: (data: { email: string, role: OrgRole, expiration_hours: number }) => inviteMember(orgId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['invites', orgId] });
      setSuccessUrl(data.invite_url);
      setErrorMsg(null);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || 'Failed to send invite. Please try again.');
    }
  });

  if (!isOpen) return null;

  const handleCopy = async () => {
    if (successUrl) {
      await navigator.clipboard.writeText(successUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClose = () => {
    // Reset state when closing
    setEmail('');
    setRole('member');
    setExpiresInDays(3);
    setSuccessUrl(null);
    setErrorMsg(null);
    setCopied(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card w-full max-w-lg border-4 border-border rounded-none !shadow-[12px_12px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] p-8 relative transition-all">
        
        {/* Close Button */}
        <button 
          onClick={handleClose}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center border-2 border-border hover:bg-[#FF857F] hover:text-[#611F1D] dark:hover:bg-[#FF857F] transition-colors !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] hover:translate-y-0.5 hover:!shadow-[1px_1px_0px_0px_rgba(15,23,42,1)]"
          aria-label="Close modal"
        >
          <span className="material-symbols-outlined text-sm font-bold">close</span>
        </button>

        {!successUrl ? (
          <>
            <h2 className="font-display-lg text-3xl text-foreground dark:!text-[#E4E2E3] uppercase font-black tracking-tighter mb-2">
              Invite Member
            </h2>
            <p className="font-mono text-xs text-muted-foreground uppercase font-bold tracking-wider mb-8">
              Add a new teammate to your organization
            </p>

            {errorMsg && (
              <div className="mb-6 p-4 bg-[#FF857F]/20 border-2 border-[#FF857F] text-[#FF857F] font-mono text-xs uppercase font-bold tracking-wide">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-lg">error</span>
                  <span>{errorMsg}</span>
                </div>
              </div>
            )}

            <div className="space-y-6">
              {/* Email Input */}
              <div>
                <label className="block font-mono text-xs font-bold text-foreground uppercase mb-2">
                  Email Address
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-muted-foreground">
                    mail
                  </span>
                  <input 
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="w-full bg-background border-2 border-border p-3 pl-12 text-foreground font-body-sm focus:outline-none focus:border-slate-900 dark:focus:border-white transition-all !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] focus:!shadow-none focus:translate-y-1"
                  />
                </div>
              </div>

              {/* Role Selection */}
              <div>
                <label className="block font-mono text-xs font-bold text-foreground uppercase mb-3">
                  Assign Role
                </label>
                <div className="space-y-3">
                  <RoleOption 
                    id="role-member"
                    title="Member"
                    description="Can view and interact with resources."
                    value="member"
                    currentValue={role}
                    onChange={(v) => setRole(v)}
                    icon="person"
                  />

                  <RoleOption 
                    id="role-owner"
                    title="Owner"
                    description="Full administrative and billing access."
                    value="owner"
                    currentValue={role}
                    onChange={(v) => setRole(v)}
                    icon="verified_user"
                  />
                </div>
              </div>

              {/* Expiration Input */}
              <div className="w-full pt-2">
                <WheelPicker 
                  label="Expires In"
                  min={1}
                  max={14}
                  value={expiresInDays}
                  onChange={setExpiresInDays}
                />
              </div>
            </div>

            <div className="flex gap-4 mt-8 pt-6 border-t-2 border-border">
              <button 
                onClick={handleClose}
                className="flex-1 py-3 border-2 border-border font-bold uppercase text-foreground bg-muted hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:!shadow-none"
              >
                Cancel
              </button>
              <button 
                onClick={() => inviteMutation.mutate({ email, role, expiration_hours: expiresInDays * 24 })}
                disabled={!email || inviteMutation.isPending}
                className="flex-1 py-3 border-2 border-border font-bold uppercase tracking-wider text-white bg-black dark:text-[#223243] dark:bg-[#B8C8DE] transition-colors !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:!shadow-none disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {inviteMutation.isPending ? (
                  <>
                    <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
                    Sending...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">send</span>
                    Send Invite
                  </>
                )}
              </button>
            </div>
          </>
        ) : (
          /* Success State */
          <div className="text-center py-6">
            <div className="w-20 h-20 mx-auto bg-[#9CF1C7] text-[#0A5636] border-4 border-border flex items-center justify-center !shadow-[6px_6px_0px_0px_rgba(15,23,42,1)] mb-6 rotate-3">
              <span className="material-symbols-outlined text-4xl">check_circle</span>
            </div>
            
            <h2 className="font-display-lg text-3xl text-foreground dark:!text-[#E4E2E3] uppercase font-black tracking-tighter mb-2">
              Invite Created!
            </h2>
            <p className="font-body-sm text-muted-foreground mb-8">
              We've generated a unique invite link for <strong className="text-foreground">{email}</strong>. 
              Share this link directly with them to join the organization.
            </p>

            <div className="bg-muted border-2 border-border p-4 mb-8 text-left relative !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
              <p className="font-mono text-xs font-bold uppercase text-foreground mb-2">Invite Link</p>
              <div className="font-mono text-sm text-muted-foreground break-all bg-background border-2 border-border p-3">
                {successUrl}
              </div>
            </div>

            <div className="flex gap-4">
              <button 
                onClick={handleClose}
                className="flex-1 py-3 border-2 border-border font-bold uppercase text-foreground bg-background hover:bg-muted transition-colors !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:!shadow-none"
              >
                Done
              </button>
              <button 
                onClick={handleCopy}
                className={`flex-1 py-3 border-2 border-border font-bold uppercase tracking-wider transition-colors !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:!shadow-none flex items-center justify-center gap-2 ${
                  copied 
                    ? 'bg-[#9CF1C7] text-[#0A5636]' 
                    : 'bg-[#B9CAFE] text-[#273B69] hover:bg-[#A3B8FA]'
                }`}
              >
                <span className="material-symbols-outlined text-sm">
                  {copied ? 'check' : 'content_copy'}
                </span>
                {copied ? 'Copied!' : 'Copy Link'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RoleOption({ id, title, description, value, currentValue, onChange, icon }: {
  id: string;
  title: string;
  description: string;
  value: OrgRole;
  currentValue: OrgRole;
  onChange: (val: OrgRole) => void;
  icon: string;
}) {
  const isSelected = value === currentValue;
  
  return (
    <label 
      htmlFor={id}
      className={`flex items-start gap-4 p-4 border-2 border-border cursor-pointer transition-all ${
        isSelected 
          ? 'bg-[#E8E6FF] dark:bg-[#2F2B66]/40 border-slate-900 dark:border-white !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] -translate-y-1' 
          : 'bg-background hover:bg-muted hover:!shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]'
      }`}
    >
      <div className="flex items-center h-5 mt-0.5">
        <input 
          type="radio" 
          id={id}
          name="role"
          value={value}
          checked={isSelected}
          onChange={() => onChange(value)}
          className="w-4 h-4 text-slate-900 bg-background border-2 border-border focus:ring-0 focus:ring-offset-0 cursor-pointer accent-slate-900"
        />
      </div>
      
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className={`material-symbols-outlined text-[16px] ${isSelected ? 'text-[#2F2B66] dark:text-[#E8E6FF]' : 'text-muted-foreground'}`}>
            {icon}
          </span>
          <span className={`font-mono text-sm font-bold uppercase tracking-wide ${isSelected ? 'text-foreground' : 'text-foreground'}`}>
            {title}
          </span>
        </div>
        <p className="font-mono text-[10px] text-muted-foreground leading-snug truncate uppercase font-bold tracking-wider opacity-80">
          {description}
        </p>
      </div>
    </label>
  );
}
