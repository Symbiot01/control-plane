import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-none bg-secondary/30 border border-primary/10", className)} {...props} />;
}

export { Skeleton };
