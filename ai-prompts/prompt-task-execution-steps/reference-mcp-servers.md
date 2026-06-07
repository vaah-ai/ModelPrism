---
title: MCP Servers Reference
purpose: Available MCP servers and when to use each
---

# MCP Servers

| Server | Purpose | When to Use |
| ------ | ------- | ----------- |
| `memory` | Persistent knowledge graph for project context | Step 0: load session context. Step 8: save implementation plan. Step 16: persist patterns, decisions, lessons. Step 17: save impact inventory. |
| `git` | Git operations (branch, commit, log, diff) | Step 3: create feature branch. Step 15: review diff. Step 19: check dependencies. Step 20: git commit. |
| `filesystem` / Read/Edit/Write | File system operations | All implementation steps. Step 4: list files in task scope. Step 6: read related code. Step 14: write documentation. |
| `fetch` / context7 | Web search and documentation lookup | Step 5: research technologies. Look up official docs for discovered versions, changelogs, breaking changes. |
| `sequential-thinking` | Complex problem decomposition | Step 8: decompose task into ordered implementation steps. Step 6: architectural decisions. |
