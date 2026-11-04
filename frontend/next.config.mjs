/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_API_URL || "https://murasaki-leadradar-1.onrender.com";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
