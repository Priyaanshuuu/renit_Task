// Vercel evaluates this file at build time. The browser keeps using /api.
const configuredOrigin = process.env.BACKEND_ORIGIN;
if (!configuredOrigin) {
  throw new Error(
    "Set BACKEND_ORIGIN to the backend's HTTPS origin in this Vercel project before deploying.",
  );
}

const backend = new URL(configuredOrigin);
if (
  backend.protocol !== "https:" ||
  backend.username ||
  backend.password ||
  backend.pathname !== "/" ||
  backend.search ||
  backend.hash
) {
  throw new Error(
    "BACKEND_ORIGIN must be an HTTPS origin without credentials, a path, query, or fragment.",
  );
}

export const config = {
  framework: "vite",
  installCommand: "npm ci",
  buildCommand: "npm run build",
  outputDirectory: "build/client",
  rewrites: [
    { source: "/api/:path*", destination: `${backend.origin}/api/:path*` },
  ],
};
