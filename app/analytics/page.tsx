"use client";

import { Shell } from "@/components/layout/shell";
import { Sidebar } from "@/components/layout/sidebar";
import { GlassCard } from "@/components/glass/glass-card";
import { motion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Zap,
  Clock,
  DollarSign,
  Activity,
  BarChart3,
  PieChart,
} from "lucide-react";

const metrics = [
  {
    title: "Total Tokens",
    value: "2.4M",
    change: "+12.5%",
    trend: "up",
    icon: Zap,
    color: "text-accent",
    bg: "bg-accent/10",
  },
  {
    title: "Avg Latency",
    value: "1.2s",
    change: "-8.3%",
    trend: "down",
    icon: Clock,
    color: "text-terminal-green",
    bg: "bg-terminal-green/10",
  },
  {
    title: "Success Rate",
    value: "94.2%",
    change: "+2.1%",
    trend: "up",
    icon: Activity,
    color: "text-terminal-purple",
    bg: "bg-terminal-purple/10",
  },
  {
    title: "Total Cost",
    value: "$1,247",
    change: "+5.4%",
    trend: "up",
    icon: DollarSign,
    color: "text-terminal-yellow",
    bg: "bg-terminal-yellow/10",
  },
];

const chartData = Array.from({ length: 24 }, (_, i) => ({
  hour: i,
  tokens: Math.floor(Math.random() * 50000) + 10000,
  latency: Math.random() * 2 + 0.5,
  success: Math.random() * 10 + 90,
}));

export default function AnalyticsPage() {
  const maxTokens = Math.max(...chartData.map((d) => d.tokens));

  return (
    <Shell>
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-auto">
        {/* Header */}
        <div className="h-14 border-b border-border flex items-center px-6 bg-background/50 backdrop-blur-sm">
          <BarChart3 className="w-4 h-4 text-accent mr-2" />
          <h1 className="font-semibold">Analytics</h1>
        </div>

        <div className="p-6 space-y-6">
          {/* Metrics Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics.map((metric, i) => (
              <motion.div
                key={metric.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                <GlassCard className="p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`p-2 rounded-lg ${metric.bg}`}>
                      <metric.icon className={`w-4 h-4 ${metric.color}`} />
                    </div>
                    <div
                      className={`flex items-center gap-1 text-xs ${
                        metric.trend === "up" ? "text-terminal-green" : "text-error"
                      }`}
                    >
                      {metric.trend === "up" ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {metric.change}
                    </div>
                  </div>
                  <div className="text-2xl font-bold mb-1">{metric.value}</div>
                  <div className="text-xs text-muted-foreground">{metric.title}</div>
                </GlassCard>
              </motion.div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Token Usage Chart */}
            <GlassCard className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold">Token Usage (24h)</h3>
                <span className="text-xs text-muted-foreground">Last 24 hours</span>
              </div>
              <div className="h-64 flex items-end gap-1">
                {chartData.map((d, i) => (
                  <motion.div
                    key={i}
                    initial={{ height: 0 }}
                    animate={{ height: `${(d.tokens / maxTokens) * 100}%` }}
                    transition={{ delay: i * 0.02, duration: 0.5 }}
                    className="flex-1 bg-accent/20 hover:bg-accent/40 transition-colors rounded-t-sm relative group"
                  >
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] bg-surface-elevated px-2 py-1 rounded border border-border whitespace-nowrap">
                      {d.tokens.toLocaleString()} tokens
                    </div>
                  </motion.div>
                ))}
              </div>
              <div className="flex justify-between mt-2 text-[10px] text-muted-foreground">
                <span>00:00</span>
                <span>06:00</span>
                <span>12:00</span>
                <span>18:00</span>
                <span>23:59</span>
              </div>
            </GlassCard>

            {/* Success Rate */}
            <GlassCard className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold">Success Rate Distribution</h3>
                <span className="text-xs text-muted-foreground">By task type</span>
              </div>
              <div className="space-y-4">
                {[
                  { label: "Code Generation", value: 96, color: "bg-accent" },
                  { label: "Refactoring", value: 92, color: "bg-terminal-purple" },
                  { label: "Bug Fixes", value: 88, color: "bg-terminal-green" },
                  { label: "Tests", value: 95, color: "bg-terminal-yellow" },
                  { label: "Documentation", value: 98, color: "bg-blue-400" },
                ].map((item) => (
                  <div key={item.label}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span>{item.label}</span>
                      <span className="text-muted-foreground">{item.value}%</span>
                    </div>
                    <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                      <motion.div
                        className={`h-full ${item.color} rounded-full`}
                        initial={{ width: 0 }}
                        animate={{ width: `${item.value}%` }}
                        transition={{ duration: 1, ease: "easeOut" }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>

          {/* Cost Breakdown */}
          <GlassCard className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold">Cost Breakdown</h3>
              <span className="text-xs text-muted-foreground">This month</span>
            </div>
            <div className="grid md:grid-cols-4 gap-4">
              {[
                { label: "GPT-4o", cost: "$845", pct: 68, color: "from-accent to-blue-500" },
                { label: "Claude 3.5", cost: "$312", pct: 25, color: "from-terminal-purple to-violet-500" },
                { label: "Embedding", cost: "$67", pct: 5, color: "from-terminal-green to-emerald-500" },
                { label: "Infrastructure", cost: "$23", pct: 2, color: "from-terminal-yellow to-amber-500" },
              ].map((item) => (
                <div key={item.label} className="text-center">
                  <div className="relative w-24 h-24 mx-auto mb-3">
                    <svg className="w-full h-full -rotate-90">
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        fill="none"
                        stroke="rgba(255,255,255,0.05)"
                        strokeWidth="8"
                      />
                      <motion.circle
                        cx="48"
                        cy="48"
                        r="40"
                        fill="none"
                        stroke="url(#gradient)"
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={`${2 * Math.PI * 40}`}
                        initial={{ strokeDashoffset: 2 * Math.PI * 40 }}
                        animate={{ strokeDashoffset: 2 * Math.PI * 40 * (1 - item.pct / 100) }}
                        transition={{ duration: 1.5, ease: "easeOut" }}
                      />
                      <defs>
                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                          <stop offset="0%" className={`text-${item.color.split(" ")[1].replace("to-", "")}`} stopColor="currentColor" />
                          <stop offset="100%" className={`text-${item.color.split(" ")[3]}`} stopColor="currentColor" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-lg font-bold">{item.pct}%</span>
                    </div>
                  </div>
                  <div className="text-sm font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">{item.cost}</div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>
    </Shell>
  );
}
