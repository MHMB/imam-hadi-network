/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone", // for slim Docker image (P8)
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: {
    // typedRoutes: true,  // re-enable after P5 routing stabilizes
  },
  async rewrites() {
    // In dev, proxy /api/* to FastAPI on :8000.  In prod, Traefik handles it.
    if (process.env.NODE_ENV !== "development") return [];
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_DEV_API_PROXY ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
