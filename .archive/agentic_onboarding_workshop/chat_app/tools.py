# --- Tool implementations ---


from mock_data import PRODUCTS


def search_catalog(query: str) -> str:
    """Search the product catalog for items matching the query."""
    query_lower = query.lower()
    matches = [
        p
        for p in PRODUCTS
        if query_lower in p["name"].lower() or query_lower in p["category"].lower()
    ]

    if not matches:
        return "No products found matching your query."

    results = []
    for p in matches[:3]:
        results.append(f"{p['id']}: {p['name']} ({p['category']}) - {p['specs']}")

    return "\n".join(results)


def retrieve_docs(query: str) -> str:
    """Retrieve relevant documentation from the knowledge base."""
    import app

    if app.chroma_collection is None:
        return "Knowledge base not initialized."

    results = app.chroma_collection.query(query_texts=[query], n_results=3)

    if not results["documents"] or not results["documents"][0]:
        return "No relevant documentation found."

    return "\n\n".join(results["documents"][0])


# Anthropic tool definitions
TOOLS = [
    {
        "name": "search_catalog",
        "description": "Search the product catalog for items matching the query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for the product catalog",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "retrieve_docs",
        "description": "Retrieve relevant documentation from the knowledge base.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for the knowledge base",
                }
            },
            "required": ["query"],
        },
    },
]

TOOL_FUNCTIONS = {
    "search_catalog": search_catalog,
    "retrieve_docs": retrieve_docs,
}
