"use client";

import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui-store";
import { motion } from "framer-motion";
import { ReactNode } from "react";

interface ShellProps {
  children: ReactNode;
  className?: string;
}

export function Shell({ children, className }: ShellProps) {
  const { sidebarOpen, rightPanelOpen } = useUIStore();

  return (
    <div className={cn("min-h-screen bg-background mesh-gradient", className)}>
      <div className="grid-pattern fixed inset-0 pointer-events-none opacity-50" />
      <div className="relative z-10 flex h-screen overflow-hidden">
        {children}
      </div>
    </div>
  );
}
