/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Proxies /api/* to the FastAPI backend so the browser never needs
    // to know the backend's port, and CORS is a non-issue in prod.
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8001/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
