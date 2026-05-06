from mcp_servers.base_mcp import BaseMCP

class SearchMCP(BaseMCP):
    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key
    async def search(self, query: str) -> str:
        if not self.api_key:
            return f"[Mock] Market benchmark for '{query}' — avg $50-$120/unit (2026 estimate)."
        try:
            from serpapi import GoogleSearch
            results = GoogleSearch({"q": query, "api_key": self.api_key, "num": 3}).get_dict()
            return " | ".join(r.get("snippet","") for r in results.get("organic_results",[])[:3])
        except Exception as e:
            return f"Search error: {e}"
