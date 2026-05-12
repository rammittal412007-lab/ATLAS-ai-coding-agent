"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { AgentStatus as AgentStatusType } from "@/types";

interface StatusIndicatorProps {
  status: AgentStatusType;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

const statusConfig = {
  idle: { color: "bg-muted-foreground", label: "Idle", animation: "none" },
  thinking: { color: "bg-accent", label: "Thinking", animation: "pulse" },
  coding: { color: "bg-terminal-green", label: "Coding", animation: "bounce" },
  waiting: { color: "bg-terminal-yellow", label: "Waiting", animation: "pulse" },
  error: { color: "bg-error", label: "Error", animation: "shake" },
};

export function StatusIndicator({
  status,
  size = "md",
  showLabel = true,
}: StatusIndicatorProps) {
  const config = statusConfig[status.state];
  const sizeClasses = {
    sm: "w-2 h-2",
    md: "w-3 h-3",
    lg: "w-4 h-4",
  };

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        {config.animation === "pulse" && (
          <motion.span
            className={cn("absolute inline-flex rounded-full opacity-75", config.color, sizeClasses[size])}
            animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        )}
        <span className={cn("relative inline-flex rounded-full", config.color, sizeClasses[size])} />
      </div>
      {showLabel && (
        <span className="text-sm text-muted-foreground font-medium">
          {config.label}
          {status.currentTask && (
            <span className="text-muted-foreground/50 ml-1">• {status.currentTask}</span>
          )}
        </span>
      )}
    </div>
  );
}
