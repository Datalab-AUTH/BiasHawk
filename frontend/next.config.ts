import path from "node:path";

import { config as loadEnv } from "dotenv";
import type { NextConfig } from "next";

// Local dev shares the repo-root .env with the backend, so there is one file to
// edit rather than two that drift. In Docker that file is absent (excluded by
// .dockerignore) and compose supplies the same variables from docker.env.
loadEnv({ path: path.resolve(process.cwd(), "..", ".env"), quiet: true });

const nextConfig: NextConfig = {
  // Ships a minimal server bundle instead of the full node_modules tree.
  output: "standalone",
  env: {
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api",
  },
};

export default nextConfig;
