import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import fs from "fs";

const MAX_SOURCE_FILE_BYTES = 1024 * 1024;

interface ProjectEntry {
  id: string;
  sourceRoot?: string;
}

function loadProjectIndex(): ProjectEntry[] {
  const indexPath = path.resolve(__dirname, "public/graphs/index.json");
  try {
    return JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  } catch {
    return [];
  }
}

function detectLanguage(filePath: string): string {
  const ext = path.extname(filePath).slice(1).toLowerCase();
  const map: Record<string, string> = {
    py: "python", js: "javascript", ts: "typescript", tsx: "tsx", jsx: "jsx",
    json: "json", md: "markdown", html: "markup", css: "css", yaml: "yaml",
    yml: "yaml", sh: "bash", bash: "bash", go: "go", rs: "rust", rb: "ruby",
    java: "java", c: "c", cpp: "cpp", h: "c", hpp: "cpp", txt: "text",
  };
  return map[ext] ?? "text";
}

function graphFilePathSet(graphFile: string, projectRoot: string): Set<string> {
  const allowed = new Set<string>();
  try {
    const raw = JSON.parse(fs.readFileSync(graphFile, "utf-8")) as {
      nodes?: Array<Record<string, unknown>>;
    };
    for (const node of raw.nodes ?? []) {
      if (typeof node.filePath !== "string") continue;
      const fp = node.filePath;
      const rel = path.isAbsolute(fp)
        ? (fp.startsWith(projectRoot) ? path.relative(projectRoot, fp) : null)
        : fp;
      if (rel) allowed.add(rel.split(path.sep).join("/"));
    }
  } catch { /* empty */ }
  return allowed;
}

export default defineConfig({
  base: "/",

  resolve: {
    alias: {
      "@understand-anything/core/schema": path.resolve(__dirname, "../core/dist/schema.js"),
      "@understand-anything/core/search": path.resolve(__dirname, "../core/dist/search.js"),
      "@understand-anything/core/types": path.resolve(__dirname, "../core/dist/types.js"),
    },
  },

  define: {
    "import.meta.env.VITE_DEMO_MODE": JSON.stringify("true"),
  },

  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) {
            return "react-vendor";
          }
          if (id.includes("node_modules/@xyflow/")) return "xyflow";
          if (id.includes("node_modules/elkjs/")) return "elk";
          if (id.includes("node_modules/graphology")) return "graphology";
          if (
            id.includes("node_modules/@dagrejs/") ||
            id.includes("node_modules/d3-force/")
          ) {
            return "graph-layout";
          }
          if (
            id.includes("node_modules/react-markdown/") ||
            id.includes("node_modules/hast-util-to-jsx-runtime/") ||
            /[\\/]node_modules[\\/](remark|rehype|mdast|hast|unist|micromark|decode-named-character-reference|property-information|space-separated-tokens|comma-separated-tokens|html-url-attributes|devlop|bail|ccount|character-entities|is-plain-obj|trim-lines|trough|unified|vfile|zwitch)/.test(id)
          ) {
            return "markdown";
          }
        },
      },
    },
  },

  plugins: [
    react(),
    tailwindcss(),
    {
      name: "serve-source-files",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const url = new URL(req.url ?? "/", "http://localhost");

          if (url.pathname !== "/file-content.json") {
            next();
            return;
          }

          const projectId = url.searchParams.get("project");
          const requestedPath = url.searchParams.get("path") ?? "";

          if (!projectId || !requestedPath) {
            res.statusCode = 400;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Missing project or path" }));
            return;
          }

          const projects = loadProjectIndex();
          const project = projects.find((p) => p.id === projectId);
          if (!project?.sourceRoot) {
            res.statusCode = 404;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: `No sourceRoot for project: ${projectId}` }));
            return;
          }

          if (requestedPath.includes("\0") || path.isAbsolute(requestedPath)) {
            res.statusCode = 400;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Invalid path" }));
            return;
          }

          const normalized = path.normalize(requestedPath);
          if (normalized === ".." || normalized.startsWith(`..${path.sep}`)) {
            res.statusCode = 400;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Path traversal not allowed" }));
            return;
          }

          const graphFile = path.resolve(__dirname, `public/graphs/${projectId}/knowledge-graph.json`);
          const allowed = graphFilePathSet(graphFile, project.sourceRoot);
          const safeRelative = normalized.split(path.sep).join("/");
          if (!allowed.has(safeRelative)) {
            res.statusCode = 404;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "File not in knowledge graph" }));
            return;
          }

          const absoluteFile = path.resolve(project.sourceRoot, normalized);
          if (!absoluteFile.startsWith(project.sourceRoot)) {
            res.statusCode = 400;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Path escapes project root" }));
            return;
          }

          let stat: fs.Stats;
          try {
            stat = fs.statSync(absoluteFile);
          } catch {
            res.statusCode = 404;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "File not found" }));
            return;
          }

          if (!stat.isFile() || stat.size > MAX_SOURCE_FILE_BYTES) {
            res.statusCode = 400;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Not a file or too large" }));
            return;
          }

          const buffer = fs.readFileSync(absoluteFile);
          if (buffer.includes(0)) {
            res.statusCode = 415;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Binary file" }));
            return;
          }

          const content = buffer.toString("utf8");
          res.statusCode = 200;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({
            path: safeRelative,
            language: detectLanguage(safeRelative),
            content,
            sizeBytes: buffer.byteLength,
            lineCount: content.length === 0 ? 0 : content.split(/\r\n|\n|\r/).length,
          }));
        });
      },
    },
  ],
});
