class BaseMCP:
    def __init__(self, **kwargs): self._config = kwargs
    async def health_check(self) -> bool: return True
