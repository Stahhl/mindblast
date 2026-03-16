import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "../../..");

function resolveQuizzesDir(): string {
  const configured = process.env.MINDBLAST_CONTENT_DIR?.trim();
  if (configured) {
    return path.resolve(REPO_ROOT, configured);
  }
  return path.resolve(REPO_ROOT, "../mindblast-content/quizzes");
}

const QUIZZES_DIR = resolveQuizzesDir();

function getContentType(filePath: string): string {
  if (filePath.endsWith(".json")) {
    return "application/json; charset=utf-8";
  }
  return "text/plain; charset=utf-8";
}

function resolveQuizFile(urlPath: string): string | null {
  const relative = decodeURIComponent(urlPath.slice("/quizzes/".length));
  const targetPath = path.resolve(QUIZZES_DIR, relative);
  const safePrefix = `${QUIZZES_DIR}${path.sep}`;
  if (targetPath !== QUIZZES_DIR && !targetPath.startsWith(safePrefix)) {
    return null;
  }
  return targetPath;
}

function createQuizStaticMiddleware() {
  return (req, res, next) => {
    const urlPath = (req.url || "").split("?")[0];
    if (!urlPath.startsWith("/quizzes/")) {
      next();
      return;
    }

    const targetPath = resolveQuizFile(urlPath);
    if (!targetPath) {
      res.statusCode = 403;
      res.end("Forbidden");
      return;
    }

    fs.stat(targetPath, (statError, stats) => {
      if (statError || !stats.isFile()) {
        res.statusCode = 404;
        res.end("Not found");
        return;
      }

      res.setHeader("Content-Type", getContentType(targetPath));
      const stream = fs.createReadStream(targetPath);
      stream.on("error", () => {
        res.statusCode = 500;
        res.end("Failed to read file");
      });
      stream.pipe(res);
    });
  };
}

function quizzesPlugin() {
  const middleware = createQuizStaticMiddleware();
  return {
    name: "mindblast-quizzes-static",
    configureServer(server: { middlewares: { use: (mw: ReturnType<typeof createQuizStaticMiddleware>) => void } }) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server: { middlewares: { use: (mw: ReturnType<typeof createQuizStaticMiddleware>) => void } }) {
      server.middlewares.use(middleware);
    }
  };
}

export default defineConfig({
  plugins: [react(), quizzesPlugin()],
  server: {
    host: "127.0.0.1",
    port: 5173
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true
  }
});
