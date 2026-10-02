class FakeLLM:
    """Deterministic stand-in for Ollama. Records prompts so tests can assert on what the LLM saw."""

    def __init__(self, verifier_score: float = 0.9) -> None:
        self.verifier_score = verifier_score
        self.calls: list[list[dict]] = []

    def chat(self, messages, json_mode=False, temperature=0.1):
        self.calls.append(messages)
        if json_mode:
            return f'{{"score": {self.verifier_score}, "unsupported_claims": []}}'
        return "Réponse de test [1]"
