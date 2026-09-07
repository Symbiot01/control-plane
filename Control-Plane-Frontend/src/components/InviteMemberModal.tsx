import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { inviteMember } from '@/services/organizations';
import type { OrgRole } from '@/types/api';
import { useToast } from '@/hooks/use-toast';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Check, Copy, Loader2, Send } from 'lucide-react';

interface InviteMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
}

export default function InviteMemberModal({ isOpen, onClose, orgId }: InviteMemberModalProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<number>(3);
  const [successUrl, setSuccessUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const inviteMutation = useMutation({
    mutationFn: (data: { name: string, email: string, role: OrgRole, expiration_hours: number }) => inviteMember(orgId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['invites', orgId] });
      setSuccessUrl(data.invite_url);
      setErrorMsg(null);
      
      if (data.email_sent === true) {
        toast({
          title: "Success",
          description: "Invite email sent successfully!",
        });
      } else if (data.email_sent === false) {
        toast({
          title: "Warning",
          description: "Invite created, but the email failed to send.",
          variant: "destructive",
        });
      }
    },
    onError: (err: any) => {
      setErrorMsg(err.message || 'Failed to send invite. Please try again.');
    }
  });

  const handleCopy = async () => {
    if (successUrl) {
      await navigator.clipboard.writeText(successUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast({ title: "Link copied to clipboard" });
    }
  };

  const handleClose = () => {
    setName('');
    setEmail('');
    setExpiresInDays(3);
    setSuccessUrl(null);
    setErrorMsg(null);
    setCopied(false);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) return;
    
    // Defaulting role to 'member' silently as it's not needed for the UI
    inviteMutation.mutate({ 
      name, 
      email, 
      role: 'member', 
      expiration_hours: expiresInDays * 24 
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[425px]">
        {!successUrl ? (
          <>
            <DialogHeader>
              <DialogTitle>Invite Member</DialogTitle>
              <DialogDescription>
                Add a new teammate to your organization. They will join as a Member.
              </DialogDescription>
            </DialogHeader>

            {errorMsg && (
              <div className="bg-destructive/15 text-destructive p-3 rounded-md text-sm mb-4">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="invite-name">Name</Label>
                <Input 
                  id="invite-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="invite-email">Email Address</Label>
                <Input 
                  id="invite-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="invite-expires">Expires In</Label>
                <Select 
                  value={String(expiresInDays)} 
                  onValueChange={(val) => setExpiresInDays(parseInt(val, 10))}
                >
                  <SelectTrigger id="invite-expires">
                    <SelectValue placeholder="Select expiration time" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 Day</SelectItem>
                    <SelectItem value="3">3 Days</SelectItem>
                    <SelectItem value="7">7 Days</SelectItem>
                    <SelectItem value="14">14 Days</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex justify-end gap-3 pt-4 mt-4 border-t">
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!name || !email || inviteMutation.isPending}>
                  {inviteMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send Invite
                    </>
                  )}
                </Button>
              </div>
            </form>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="text-center flex flex-col items-center gap-2">
                <div className="h-12 w-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-2">
                  <Check className="h-6 w-6" />
                </div>
                Invite Created!
              </DialogTitle>
              <DialogDescription className="text-center pt-2">
                We've generated a unique invite link for <strong>{email}</strong>.
                Share this link directly with them to join.
              </DialogDescription>
            </DialogHeader>

            <div className="bg-muted p-4 rounded-md my-4 flex items-center gap-2">
              <Input value={successUrl} readOnly className="font-mono text-xs bg-background" />
              <Button variant="secondary" size="icon" onClick={handleCopy} className="shrink-0" title="Copy Link">
                {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>

            <div className="flex justify-center mt-2">
              <Button onClick={handleClose} className="w-full">
                Done
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
