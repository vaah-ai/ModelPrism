The file has been written to `/Users/pk/Projects/ModelPrism/requirements/features/feature-f31-request-routing.md`. It contains:

- **7 acceptance criteria** (ACF31-1 through ACF31-7), each with testable Given/When/Then style specifications
- **5 concrete examples** with full JSON payloads covering: direct match, model alias resolution, load balancing across multiple agents, no-available-upstream error, and API key scope denial
- **Integration points** referencing F3, F7, F16, F19, F22, F27, F28, F29, F30, and F34
- **Actual file paths** from the ModelPrism directory structure (`backend/app/services/router.py`, `backend/app/schemas/routing.py`, `backend/app/services/router_subscriber.py`, `backend/app/api/proxy.py`, etc.)
- **JSON:API and OpenAI-format** references where appropriate
- **Real-world model names** (qwen2.5-72b-instruct, llama-3.1-8b-instruct, gpt-4-turbo)
- **UUIDs, ISO 8601 timestamps, and agent IDs** throughout
- **Technical implementation details** including core dataclasses, routing algorithm pseudocode, WebSocket message format, error classes, database schema, migration steps, edge cases, and a performance budget table