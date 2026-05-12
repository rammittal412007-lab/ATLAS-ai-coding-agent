"use client";

import { CodeDiff } from "@/types";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";

interface DiffViewerProps {
  diff: CodeDiff;
  className?: string;
}

export function DiffViewer({ diff, className }: DiffViewerProps) {
  const [expanded, setExpanded] = useState(true);

  const oldLines = diff.oldContent.split("\n");
  const newLines = diff.newContent.split("\n");

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-panel overflow-hidden", className)}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b border-border cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-mono text-foreground">{diff.filePath}</span>
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-terminal-green">+{diff.additions}</span>
            <span className="text-error">-{diff.deletions}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-xs px-2 py-0.5 rounded-full border",
              diff.status === "applied" && "bg-terminal-green/10 text-terminal-green border-terminal-green/20",
              diff.status === "pending" && "bg-terminal-yellow/10 text-terminal-yellow border-terminal-yellow/20",
              diff.status === "rejected" && "bg-error/10 text-error border-error/20"
            )}
          >
            {diff.status}
          </span>
          <motion.span
            animate={{ rotate: expanded ? 180 : 0 }}
            className="text-muted-foreground"
          >
            ▼
          </motion.span>
        </div>
      </div>

      {/* Diff Content */}
      {expanded && (
        <div className="grid grid-cols-2 divide-x divide-border">
          {/* Old */}
          <div className="overflow-auto max-h-[400px]">
            <div className="sticky top-0 bg-background/80 backdrop-blur px-3 py-1 text-xs text-muted-foreground border-b border-border">
              Before
            </div>
            <div className="font-mono text-xs leading-6">
              {oldLines.map((line, i) => (
                <div
                  key={i}
                  className="flex px-3 hover:bg-white/[0.02] text-red-400/70"
                >
                  <span className="text-muted-foreground/30 w-8 shrink-0 select-none">
                    {i + 1}
                  </span>
                  <span className="text-red-400/60">-{line}</span>
                </div>
              ))}
            </div>
          </div>

          {/* New */}
          <div className="overflow-auto max-h-[400px]">
            <div className="sticky top-0 bg-background/80 backdrop-blur px-3 py-1 text-xs text-muted-foreground border-b border-border">
              After
            </div>
            <div className="font-mono text-xs leading-6">
              {newLines.map((line, i) => (
                <div
                  key={i}
                  className="flex px-3 hover:bg-white/[0.02]"
                >
                  <span className="text-muted-foreground/30 w-8 shrink-0 select-none">
                    {i + 1}
                  </span>
                  <span className="text-terminal-green/80">+{line}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
