/** @type {import('next').NextConfig} */
const nextConfig = {
  // ─── Core Settings ─────────────────────────────────────────
  reactStrictMode: true,
  swcMinify: true,

  // ─── Output ────────────────────────────────────────────────
  // Use 'standalone' for Docker deployment (smaller image)
  // Use 'export' for static hosting (no server needed)
  output: 'standalone',

  // ─── Image Optimization ──────────────────────────────────
  images: {
    unoptimized: false,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'avatars.githubusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'github.com',
      },
    ],
  },

  // ─── API Rewrites (Proxy to Backend) ─────────────────────
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
      {
        source: '/ws/:path*',
        destination: 'http://localhost:8000/ws/:path*',
      },
    ];
  },

  // ─── Headers ───────────────────────────────────────────────
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ];
  },

  // ─── Webpack Customization ─────────────────────────────────
  webpack: (config, { isServer }) => {
    // Monaco Editor worker support
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
    }

    return config;
  },

  // ─── Experimental Features ─────────────────────────────────
  experimental: {
    // Enable if using server components with dynamic data
    // serverActions: true,
    
    // Optimize package imports for faster builds
    optimizePackageImports: [
      'lucide-react',
      '@monaco-editor/react',
    ],
  },

  // ─── Environment Variables (exposed to browser) ──────────
  env: {
    CUSTOM_KEY: process.env.CUSTOM_KEY,
  },

  // ─── Powered By Header ─────────────────────────────────────
  poweredByHeader: false,
};

module.exports = nextConfig;
