import os, glob
from mcp_servers.base_mcp import BaseMCP
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

class FileSystemMCP(BaseMCP):
    def __init__(self, contracts_dir: str):
        super().__init__()
        self.contracts_dir = contracts_dir
    async def list_pdfs(self) -> list:
        return sorted(glob.glob(os.path.join(self.contracts_dir, "*.pdf")))
    async def read_pdf_text(self, path: str) -> str:
        if PdfReader is None: raise ImportError("Install pypdf")
        reader = PdfReader(path)
        return "\n".join(p.extract_text() or "" for p in reader.pages)
