// index.ts
import { execFile } from "child_process";
import { promisify } from "util";
import { existsSync, readFileSync } from "fs";
import { basename, dirname, join } from "path";
import { fileURLToPath } from "url";
var execFileAsync = promisify(execFile);
var HOME = process.env.HOME || "";
var THIS_DIR = dirname(fileURLToPath(import.meta.url));
var PKG_ROOT = basename(THIS_DIR) === "dist" ? dirname(THIS_DIR) : THIS_DIR;
function getDefaultScriptPath() {
  const candidate = join(PKG_ROOT, "tool_runner.py");
  if (existsSync(candidate)) return candidate;
  return HOME ? `${HOME}/openclaw-data-china-stock/tool_runner.py` : "";
}
function getManifestPath() {
  const candidates = [
    join(PKG_ROOT, "config", "tools_manifest.json"),
    join(process.cwd(), "config", "tools_manifest.json")
  ];
  for (const p of candidates) {
    if (existsSync(p)) return p;
  }
  return candidates[0];
}
function loadToolsManifest() {
  const manifestPath = process.env.OPENCLAW_DATA_CHINA_STOCK_MANIFEST_PATH || getManifestPath();
  try {
    const raw = readFileSync(manifestPath, "utf-8");
    const data = JSON.parse(raw);
    return { tools: data.tools || [] };
  } catch (e) {
    throw new Error(`\u52A0\u8F7D\u5DE5\u5177\u6E05\u5355\u5931\u8D25 (${manifestPath}): ${e}`);
  }
}
function resolvePythonBin() {
  const envPython = (process.env.OPENCLAW_DATA_CHINA_STOCK_PYTHON || "").trim();
  if (envPython) {
    return { bin: envPython, source: "env:OPENCLAW_DATA_CHINA_STOCK_PYTHON" };
  }
  const localCandidates = [
    join(PKG_ROOT, ".venv", "bin", "python"),
    join(PKG_ROOT, ".venv", "Scripts", "python.exe"),
    join(process.cwd(), ".venv", "bin", "python"),
    join(process.cwd(), ".venv", "Scripts", "python.exe")
  ];
  for (const c of localCandidates) {
    if (existsSync(c)) {
      return { bin: c, source: "local-venv" };
    }
  }
  if (HOME) {
    const legacyProjectVenv = `${HOME}/openclaw-data-china-stock/.venv/bin/python`;
    if (existsSync(legacyProjectVenv)) {
      return { bin: legacyProjectVenv, source: "legacy-home-project-venv" };
    }
    const pipxMootdxPython = `${HOME}/.local/share/pipx/venvs/mootdx/bin/python`;
    if (existsSync(pipxMootdxPython)) {
      return { bin: pipxMootdxPython, source: "pipx-mootdx-venv" };
    }
  }
  return { bin: "python3", source: "fallback:python3" };
}
var PYTHON_SELECTION = resolvePythonBin();
var PYTHON_BIN = PYTHON_SELECTION.bin;
var plugin = {
  id: "openclaw-data-china-stock",
  name: "OpenClaw Data China Stock",
  description: "A\u80A1/ETF/\u671F\u6743\u6570\u636E\u91C7\u96C6\u63D2\u4EF6\uFF08\u6293\u53D6\u4E0E\u7F13\u5B58\u8BFB\u53D6\uFF09",
  configSchema: {
    type: "object",
    properties: {
      apiBaseUrl: {
        type: "string",
        default: "http://localhost:5000",
        description: "\u53EF\u9009\u5916\u90E8\u670D\u52A1 API \u57FA\u7840\u5730\u5740\uFF08\u4EC5\u90E8\u5206\u517C\u5BB9\u63A5\u53E3\u53EF\u80FD\u9700\u8981\uFF09"
      },
      apiKey: { type: "string", description: "API Key\uFF08\u53EF\u9009\uFF09" },
      scriptPath: {
        type: "string",
        description: "tool_runner.py \u7EDD\u5BF9\u8DEF\u5F84\uFF0C\u4E0D\u586B\u5219\u7528\u9ED8\u8BA4\uFF08HOME/openclaw-data-china-stock/tool_runner.py\uFF09\u6216\u73AF\u5883\u53D8\u91CF OPENCLAW_DATA_CHINA_STOCK_SCRIPT_PATH"
      },
      manifestPath: {
        type: "string",
        description: "\u5DE5\u5177\u6E05\u5355 JSON \u8DEF\u5F84\uFF08\u53EF\u9009\uFF09\uFF0C\u4E0D\u586B\u5219\u7528 config/tools_manifest.json"
      }
    }
  },
  register(api) {
    registerAllTools(api);
    api.logger.info?.(`openclaw-data-china-stock: Python interpreter -> ${PYTHON_BIN} (${PYTHON_SELECTION.source})`);
    api.logger.info?.("openclaw-data-china-stock: Registered all tools from manifest");
  }
};
function registerAllTools(api) {
  const config = api.getConfig?.() ?? {};
  const scriptPath = process.env.OPENCLAW_DATA_CHINA_STOCK_SCRIPT_PATH || config.scriptPath || getDefaultScriptPath();
  if (config.manifestPath) {
    process.env.OPENCLAW_DATA_CHINA_STOCK_MANIFEST_PATH = config.manifestPath;
  }
  const { tools } = loadToolsManifest();
  for (const t of tools) {
    const id = t.id;
    const parameters = t.parameters && typeof t.parameters === "object" && "type" in t.parameters ? t.parameters : { type: "object", properties: {} };
    api.registerTool(
      {
        name: id,
        label: t.label || id,
        description: t.description || "",
        parameters: {
          type: parameters.type || "object",
          properties: parameters.properties || {},
          ...Array.isArray(parameters.required) && parameters.required.length > 0 ? { required: parameters.required } : {}
        },
        async execute(_toolCallId, params) {
          return await callPythonTool(scriptPath, id, params ?? {});
        }
      },
      { name: id }
    );
  }
}
async function callPythonTool(scriptPath, toolName, params) {
  try {
    const argsJson = JSON.stringify(params || {});
    const { stdout, stderr } = await execFileAsync(PYTHON_BIN, [scriptPath, toolName, argsJson], {
      timeout: 6e4,
      maxBuffer: 10 * 1024 * 1024
    });
    if (stderr && !stdout) {
      return { content: [{ type: "text", text: `\u9519\u8BEF: ${stderr}` }] };
    }
    try {
      const result = JSON.parse(stdout);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        details: result
      };
    } catch {
      return { content: [{ type: "text", text: stdout }] };
    }
  } catch (err) {
    const errorObj = err;
    const errorMsg = errorObj instanceof Error ? errorObj.message : typeof errorObj.message === "string" ? errorObj.message : String(errorObj);
    const exitCode = typeof errorObj.code !== "undefined" ? errorObj.code : void 0;
    return {
      content: [{ type: "text", text: `\u6267\u884C\u5931\u8D25: ${errorMsg}` }],
      details: { error: errorMsg, exitCode }
    };
  }
}
var index_default = plugin;
export {
  index_default as default
};
