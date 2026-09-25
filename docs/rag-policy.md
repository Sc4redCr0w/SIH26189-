# Grounded assistant policy

The assistant follows this order:

1. Parse the question for stored entity names and investigation scope.
2. Retrieve active entities, relationships, and evidence from the database.
3. Build citations from relationship/evidence IDs.
4. Return a deterministic structured answer.
5. Optionally ask a local Ollama model to phrase the same retrieved facts.

The model is not allowed to introduce an entity, relationship, date, or legal status that is absent from the retrieval context. If retrieval is insufficient, the response says so and returns no citations.

The current local implementation supports direct connections, two-degree neighborhoods, evidence-focused questions, case scoping, and network summaries. Production RAG should add document chunking, access-filtered retrieval, citation span validation, and evaluation against labeled questions.
