import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { execFile } from "child_process";
import { promisify } from "util";
import { existsSync, readFileSync } from "fs";
import { basename, dirname, join } from "path";
import { fileURLToPath } from "url";

const execFileAsync = promisify(execFile);

const HOME = process.env.HOME || "";
const THIS_DIR = dirname(fileURLToPath(import.meta.url));
/** 发布包入口在 dist/ 时，资源文件仍在仓库根（tool_runner.py、config/） */
const PKG_ROOT = basename(THIS_DIR) === "dist" ? dirname(THIS_DIR) : THIS_DIR;

function getDefaultScriptPath(): string {
  // Prefer locating `tool_runner.py` inside the installed plugin package directory.
  const candidate = join(PKG_ROOT, "tool_runner.py");
  if (existsSync(candidate)) return candidate;
  // Fallback: keep backward compatibility with older installations.
  return HOME ? `${HOME}/openclaw-data-china-stock/tool_runner.py` : "";
}

function getManifestPath(): string {
  const candidates = [
    join(PKG_ROOT, "config", "tools_manifest.json"),
    join(process.cwd(), "config", "tools_manifest.json"),
  ];
  for (const p of candidates) {
    if (existsSync(p)) return p;
  }
  return candidates[0];
}

function loadToolsManifest(): { tools: Array<{ id: string; label: string; description: string; parameters: object }> } {
  const manifestPath =
    process.env.OPENCLAW_DATA_CHINA_STOCK_MANIFEST_PATH ||
    getManifestPath();
  try {
    const raw = readFileSync(manifestPath, "utf-8");
    const data = JSON.parse(raw) as { tools?: Array<{ id: string; label: string; description: string; parameters?: object }> };
    return { tools: data.tools || [] };
  } catch (e) {
    throw new Error(`加载工具清单失败 (${manifestPath}): ${e}`);
  }
}

type PythonBinSelection = {
  bin: string;
  source: string;
};

function resolvePythonBin(): PythonBinSelection {
  const envPython = (process.env.OPENCLAW_DATA_CHINA_STOCK_PYTHON || "").trim();
  if (envPython) {
    return { bin: envPython, source: "env:OPENCLAW_DATA_CHINA_STOCK_PYTHON" };
  }

  const localCandidates = [
    join(PKG_ROOT, ".venv", "bin", "python"),
    join(PKG_ROOT, ".venv", "Scripts", "python.exe"),
    join(process.cwd(), ".venv", "bin", "python"),
    join(process.cwd(), ".venv", "Scripts", "python.exe"),
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

const PYTHON_SELECTION = resolvePythonBin();
const PYTHON_BIN = PYTHON_SELECTION.bin;

const plugin = {
  id: "openclaw-data-china-stock",
  name: "OpenClaw Data China Stock",
  description: "A股/ETF/期权数据采集插件（抓取与缓存读取）",
  configSchema: {
    type: "object",
    properties: {
      apiBaseUrl: {
        type: "string",
        default: "http://localhost:5000",
        description: "可选外部服务 API 基础地址（仅部分兼容接口可能需要）",
      },
      apiKey: { type: "string", description: "API Key（可选）" },
      scriptPath: {
        type: "string",
        description: "tool_runner.py 绝对路径，不填则用默认（HOME/openclaw-data-china-stock/tool_runner.py）或环境变量 OPENCLAW_DATA_CHINA_STOCK_SCRIPT_PATH",
      },
      manifestPath: {
        type: "string",
        description: "工具清单 JSON 路径（可选），不填则用 config/tools_manifest.json",
      },
    },
  },
  register(api: OpenClawPluginApi) {
    registerAllTools(api);
    api.logger.info?.(`openclaw-data-china-stock: Python interpreter -> ${PYTHON_BIN} (${PYTHON_SELECTION.source})`);
    api.logger.info?.("openclaw-data-china-stock: Registered all tools from manifest");
  },
};

function registerAllTools(api: OpenClawPluginApi) {
  const config = (api as { getConfig?: () => Record<string, unknown> }).getConfig?.() ?? {};
  const scriptPath =
    (process.env.OPENCLAW_DATA_CHINA_STOCK_SCRIPT_PATH as string) ||
    (config.scriptPath as string) ||
    getDefaultScriptPath();

  if (config.manifestPath) {
    process.env.OPENCLAW_DATA_CHINA_STOCK_MANIFEST_PATH = config.manifestPath as string;
  }

  const { tools } = loadToolsManifest();

  for (const t of tools) {
    const id = t.id;
    const parameters = (t.parameters && typeof t.parameters === "object" && "type" in t.parameters)
      ? (t.parameters as { type: string; properties?: Record<string, unknown>; required?: string[] })
      : { type: "object" as const, properties: {} };
  
  api.registerTool(
    {
        name: id,
        label: t.label || id,
        description: t.description || "",
      parameters: {
          type: parameters.type || "object",
          properties: parameters.properties || {},
          ...(Array.isArray(parameters.required) && parameters.required.length > 0 ? { required: parameters.required } : {}),
      },
      async execute(_toolCallId, params) {
          return await callPythonTool(scriptPath, id, params ?? {});
        },
      },
      { name: id }
    );
  }
}

async function callPythonTool(scriptPath: string, toolName: string, params: Record<string, unknown>) {
  try {
    const argsJson = JSON.stringify(params || {});
    const { stdout, stderr } = await execFileAsync(PYTHON_BIN, [scriptPath, toolName, argsJson], {
        timeout: 60_000,
        maxBuffer: 10 * 1024 * 1024,
    });

    if (stderr && !stdout) {
      return { content: [{ type: "text" as const, text: `错误: ${stderr}` }] };
    }

    try {
      const result = JSON.parse(stdout);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        details: result,
      };
    } catch {
      return { content: [{ type: "text" as const, text: stdout }] };
    }
  } catch (err) {
    const errorObj = err as { message?: string; code?: number | string } | Error;
    const errorMsg =
      errorObj instanceof Error
        ? errorObj.message
        : typeof (errorObj as { message?: string }).message === "string"
          ? (errorObj as { message: string }).message
        : String(errorObj);
    const exitCode =
      typeof (errorObj as { code?: number | string }).code !== "undefined"
        ? (errorObj as { code: number | string }).code
        : undefined;
    return {
      content: [{ type: "text" as const, text: `执行失败: ${errorMsg}` }],
      details: { error: errorMsg, exitCode },
    };
  }
}

export default plugin;
