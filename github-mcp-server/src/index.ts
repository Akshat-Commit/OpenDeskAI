import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fetch from "node-fetch";

/**
 * OpenDesk GitHub MCP Server (Local Stdio Version)
 */
const server = new Server(
  {
    name: "opendesk-github-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const GITHUB_TOKEN = process.env.GITHUB_TOKEN || "";
const BASE_URL = "https://api.github.com";

const headers = {
  "Authorization": `Bearer ${GITHUB_TOKEN}`,
  "Accept": "application/vnd.github.v3+json",
  "User-Agent": "OpenDeskAI-GitHub-MCP/1.0",
  "Content-Type": "application/json",
};

/**
 * Helper to request GitHub API
 */
async function requestGitHubAPI(endpoint: string, options: any = {}) {
  if (!GITHUB_TOKEN) {
    throw new Error("GITHUB_TOKEN environment variable is not set.");
  }

  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`GitHub API Error (${response.status}): ${text}`);
  }

  if (response.status === 204) return { success: true };
  return response.json();
}

/**
 * Register Tool Definitions
 */
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "github_list_repos",
      description: "List repositories for the authenticated user",
      inputSchema: {
        type: "object",
        properties: {
          visibility: { type: "string", enum: ["all", "public", "private"] },
          sort: { type: "string", enum: ["created", "updated", "pushed", "full_name"] }
        }
      }
    },
    {
      name: "github_get_repo",
      description: "Get details of a specific repository",
      inputSchema: {
        type: "object",
        properties: {
          owner: { type: "string" },
          repo: { type: "string" }
        },
        required: ["owner", "repo"]
      }
    },
    {
      name: "github_search_repos",
      description: "Search for GitHub repositories",
      inputSchema: {
        type: "object",
        properties: { query: { type: "string" } },
        required: ["query"]
      }
    },
    {
      name: "github_list_issues",
      description: "List issues in a repository",
      inputSchema: {
        type: "object",
        properties: {
          owner: { type: "string" },
          repo: { type: "string" },
          state: { type: "string", enum: ["open", "closed", "all"] }
        },
        required: ["owner", "repo"]
      }
    },
    {
      name: "github_create_issue",
      description: "Create a new issue in a repository",
      inputSchema: {
        type: "object",
        properties: {
          owner: { type: "string" },
          repo: { type: "string" },
          title: { type: "string" },
          body: { type: "string" }
        },
        required: ["owner", "repo", "title", "body"]
      }
    },
    {
      name: "github_get_file_contents",
      description: "Get the contents of a file or directory",
      inputSchema: {
        type: "object",
        properties: {
          owner: { type: "string" },
          repo: { type: "string" },
          path: { type: "string" }
        },
        required: ["owner", "repo", "path"]
      }
    },
    {
      name: "github_search_code",
      description: "Search for code across GitHub repositories",
      inputSchema: {
        type: "object",
        properties: { query: { type: "string" } },
        required: ["query"]
      }
    }
  ],
}));

/**
 * Handle Tool Execution
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;
    switch (name) {
      case "github_list_repos":
        result = await requestGitHubAPI(`/user/repos?visibility=${args?.visibility || "all"}&sort=${args?.sort || "full_name"}`);
        break;
      case "github_get_repo":
        result = await requestGitHubAPI(`/repos/${args?.owner}/${args?.repo}`);
        break;
      case "github_search_repos":
        result = await requestGitHubAPI(`/search/repositories?q=${encodeURIComponent(args?.query as string)}`);
        break;
      case "github_list_issues":
        result = await requestGitHubAPI(`/repos/${args?.owner}/${args?.repo}/issues?state=${args?.state || "open"}`);
        break;
      case "github_create_issue":
        result = await requestGitHubAPI(`/repos/${args?.owner}/${args?.repo}/issues`, {
          method: "POST",
          body: JSON.stringify({ title: args?.title, body: args?.body })
        });
        break;
      case "github_get_file_contents":
        result = await requestGitHubAPI(`/repos/${args?.owner}/${args?.repo}/contents/${args?.path}`);
        break;
      case "github_search_code":
        result = await requestGitHubAPI(`/search/code?q=${encodeURIComponent(args?.query as string)}`);
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

/**
 * Start Server
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("OpenDesk GitHub MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
