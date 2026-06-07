The spec has been written to `/Users/pk/Projects/ModelPrism/requirements/features/feature-f29-token-counting-usage.md`. Key aspects of the specification:

**8 acceptance criteria** covering:
1. Non-streaming upstream usage extraction and validation
2. Streaming token counts from final SSE chunk
3. Tiktoken fallback with configurable encoding lookup
4. Durable persistence with 3-tier retry (in-memory → Redis → errors table)
5. `model_pricing` table with glob-pattern rate resolution (seeded with 4 default tiers)
6. Three JSON:API endpoints: list, summary (with `group_by`), and export (CSV/NDJSON)
7. Full frontend usage dashboard with uPlot charts, filters, and export buttons
8. Error and edge-case handling (zero-length, client disconnect, upstream errors, embeddings)

**5 concrete examples** with full JSON payloads covering non-streaming, streaming, tiktoken fallback, dashboard aggregation, and error recording.

**Integration points** with F3 (schema), F27 (API keys), F28 (proxy lifecycle hook), F30 (TPM correction), F31 (routing), F34 (isolation), F37 (Stripe billing), and F38 (billing dashboard).
