"use client";

import { Shell } from "@/components/layout/shell";
import { Sidebar } from "@/components/layout/sidebar";
import { Terminal } from "@/components/terminal/terminal";
import { GlassCard } from "@/components/glass/glass-card";
import { StatusIndicator } from "@/components/agent/status-indicator";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { LogEntry, Thought, DockerSandbox } from "@/types";
import {
  RotateCcw,
  Square,
  Play,
  Container,
  Cpu,
  HardDrive,
  Timer,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";

const mockThoughts: Thought[] = [
  {
    id: "1",
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
    content: "I need to implement OAuth2 authentication. First, let me check the existing auth structure.",
    type: "plan",
  },
  {
    id: "2",
    timestamp: new Date(Date.now() - 1000 * 60 * 4),
    content: "Found passport.js in dependencies. I'll create strategies for Google and GitHub providers.",
    type: "reasoning",
  },
  {
    id: "3",
    timestamp: new Date(Date.now() - 1000 * 60 * 3),
    content: "Created src/auth/strategies/google.ts with proper error handling and token refresh logic.",
    type: "action",
  },
  {
    id: "4",
    timestamp: new Date(Date.now() - 1000 * 60 * 2),
    content: "The implementation looks solid. I should add tests for the token refresh flow.",
    type: "reflection",
  },
];

const mockSandbox: DockerSandbox = {
  id: "sb_7f3a9d",
  status: "running",
  containerId: "container_7f3a9d2e",
  resources: { cpu: 45, memory: 62, disk: 23 },
  uptime: 734,
};

export default function AgentPage({ params }: { params: { id: string } }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"running" | "paused" | "failed" | "complete">("running");

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((p) => Math.min(p + 2, 100));
      setLogs((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          timestamp: new Date(),
          level: Math.random() > 0.8 ? "debug" : "info",
          message: `Executing step ${prev.length + 1}: ${["Analyzing context", "Generating code", "Running tests", "Validating output"][Math.floor(Math.random() * 4)]}`,
          source: "executor",
        },
      ]);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Shell>
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="h-14 border-b border-border flex items-center justify-between px-6 bg-background/50 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <StatusIndicator
              status={{
                state: status === "running" ? "coding" : status === "failed" ? "error" : "idle",
                progress,
                lastActivity: new Date(),
              }}
              showLabel
            />
            <div className="w-px h-4 bg-border" />
            <span className="text-sm text-muted-foreground">Task #{params.id}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setStatus(status === "running" ? "paused" : "running")}
              className="p-2 rounded-lg hover:bg-white/5 transition-colors"
            >
              {status === "running" ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button className="p-2 rounded-lg hover:bg-white/5 transition-colors">
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Progress */}
        <div className="px-6 py-3 border-b border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
            <span>Execution Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-accent to-accent-secondary rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ type: "spring", stiffness: 50 }}
            />
          </div>
        </div>

        {/* Main Grid */}
        <div className="flex-1 overflow-auto p-6">
          <div className="grid grid-cols-3 gap-6 h-full">
            {/* Thoughts */}
            <div className="col-span-1 space-y-4">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Agent Thoughts
              </h3>
              <div className="space-y-3">
                {mockThoughts.map((thought, i) => (
                  <motion.div
                    key={thought.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.2 }}
                  >
                    <GlassCard className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${
                            thought.type === "plan"
                              ? "bg-accent/10 text-accent"
                              : thought.type === "reasoning"
                              ? "bg-terminal-purple/10 text-terminal-purple"
                              : thought.type === "action"
                              ? "bg-terminal-green/10 text-terminal-green"
                              : "bg-terminal-yellow/10 text-terminal-yellow"
                          }`}
                        >
                          {thought.type}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {thought.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-foreground/80 leading-relaxed">
                        {thought.content}
                      </p>
                    </GlassCard>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Logs */}
            <div className="col-span-1 flex flex-col">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
                Live Logs
              </h3>
              <div className="flex-1 min-h-0">
                <Terminal logs={logs} live title="execution.log" className="h-full" />
              </div>
            </div>

            {/* Sandbox & Metrics */}
            <div className="col-span-1 space-y-4">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Docker Sandbox
              </h3>
              
              <GlassCard className="p-4">
                <div className="flex items-center gap-3 mb-4">
                  <Container className="w-5 h-5 text-accent" />
                  <div>
                    <div className="text-sm font-medium">{mockSandbox.containerId}</div>
                    <div className="text-xs text-muted-foreground">Uptime: {mockSandbox.uptime}s</div>
                  </div>
                  <span className="ml-auto flex items-center gap-1.5 text-xs text-terminal-green">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-terminal-green opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-terminal-green" />
                    </span>
                    {mockSandbox.status}
                  </span>
                </div>

                <div className="space-y-3">
                  {[
                    { label: "CPU", value: mockSandbox.resources.cpu, icon: Cpu, color: "bg-accent" },
                    { label: "Memory", value: mockSandbox.resources.memory, icon: HardDrive, color: "bg-terminal-purple" },
                    { label: "Disk", value: mockSandbox.resources.disk, icon: Timer, color: "bg-terminal-green" },
                  ].map((metric) => (
                    <div key={metric.label}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="flex items-center gap-1.5 text-muted-foreground">
                          <metric.icon className="w-3 h-3" />
                          {metric.label}
                        </span>
                        <span>{metric.value}%</span>
                      </div>
                      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                          className={`h-full ${metric.color} rounded-full`}
                          initial={{ width: 0 }}
                          animate={{ width: `${metric.value}%` }}
                          transition={{ duration: 1 }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </GlassCard>

              {/* Retry Visualization */}
              <GlassCard className="p-4">
                <h4 className="text-sm font-medium mb-3">Execution Steps</h4>
                <div className="space-y-2">
                  {[
                    { status: "complete", label: "Initialize environment" },
                    { status: "complete", label: "Clone repository" },
                    { status: "complete", label: "Analyze codebase" },
                    { status: "running", label: "Generate OAuth2 implementation" },
                    { status: "pending", label: "Run test suite" },
                    { status: "pending", label: "Create pull request" },
                  ].map((step, i) => (
                    <div key={i} className="flex items-center gap-3">
                      {step.status === "complete" ? (
                        <CheckCircle2 className="w-4 h-4 text-terminal-green shrink-0" />
                      ) : step.status === "running" ? (
                        <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-white/20 shrink-0" />
                      )}
                      <span
                        className={`text-sm ${
                          step.status === "complete"
                            ? "text-muted-foreground line-through"
                            : step.status === "running"
                            ? "text-foreground"
                            : "text-muted-foreground/50"
                        }`}
                      >
                        {step.label}
                      </span>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
