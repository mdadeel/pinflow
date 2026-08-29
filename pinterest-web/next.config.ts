import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Backend-hosted images are served by the API on :8000. The Next image
    // optimizer fetches them server-side, which fails when the backend is only
    // reachable via IPv4/IPv6 mismatch (localhost -> ::1). Load them directly.
    unoptimized: true,
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000" },
      { protocol: "http", hostname: "127.0.0.1", port: "8000" },
      { protocol: "https", hostname: "localhost", port: "8000" },
      { protocol: "https", hostname: "127.0.0.1", port: "8000" },
    ],
  },
};

export default nextConfig;
