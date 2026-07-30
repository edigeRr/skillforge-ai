from app.ai.base_provider import BaseAIProvider, Evaluation, GeneratedQuestion

# Deterministic question bank keyed by language. Difficulty isn't used to pick
# a different question in the fake provider (it doesn't need to be smart) -
# it's threaded through the interface so Sprint 4's real provider can use it
# to shape the prompt.
_QUESTION_BANK: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("data-structures", "How would you deduplicate a list while preserving order?"),
        ("concurrency", "Explain the GIL and how it affects multi-threaded CPU-bound code."),
        ("generators", "What's the difference between a generator and a list comprehension?"),
        ("decorators", "Write a decorator that retries a function on exception."),
        ("error-handling", "When would you reach for a custom exception hierarchy?"),
    ],
    "java": [
        (
            "collections",
            "Compare ArrayList and LinkedList - when would you pick one over the other?",
        ),
        ("concurrency", "Explain the difference between synchronized and a ReentrantLock."),
        ("generics", "What is type erasure and how does it affect generics at runtime?"),
        ("garbage-collection", "Describe how the JVM decides when to collect an object."),
        ("streams", "How would you use the Stream API to group a list of objects by a field?"),
    ],
    "cpp": [
        ("memory", "Explain the difference between a unique_ptr and a shared_ptr."),
        ("templates", "What is SFINAE and when would you use it?"),
        ("move-semantics", "What problem do move semantics solve compared to copy semantics?"),
        ("concurrency", "How does std::mutex differ from std::atomic for protecting shared state?"),
        ("raii", "Explain RAII and why it matters for exception safety."),
    ],
    "javascript": [
        ("async", "Explain the difference between a microtask and a macrotask in the event loop."),
        ("closures", "Write a function that returns a counter using a closure."),
        ("prototypes", "How does prototypal inheritance differ from classical inheritance?"),
        (
            "this-binding",
            "Explain how 'this' is determined in a regular function vs an arrow function.",
        ),
        (
            "promises",
            "How would you run three async operations in parallel and collect all results?",
        ),
    ],
}


class FakeAIProvider(BaseAIProvider):
    """Deterministic stand-in for a real LLM. Lets the full interview loop
    (start -> answer -> answer -> finish) be built and verified end to end
    before Sprint 4 wires up a real provider behind the same interface."""

    async def generate_question(
        self, language: str, difficulty: str, exclude_topics: list[str]
    ) -> GeneratedQuestion:
        bank = _QUESTION_BANK.get(language, _QUESTION_BANK["python"])
        available = [q for q in bank if q[0] not in exclude_topics]
        pool = available or bank  # wrap around once every topic has been asked
        topic, question_text = pool[0]
        return GeneratedQuestion(topic=topic, question=question_text)

    async def evaluate_answer(self, question: str, answer: str) -> Evaluation:
        trimmed = answer.strip()
        if not trimmed:
            return Evaluation(score=0.0, feedback="No answer was provided.")

        # Placeholder heuristic: longer, more developed answers score higher,
        # capped at 10. Sprint 4 replaces this with a real LLM judgment of
        # correctness - this only needs to be deterministic and testable.
        word_count = len(trimmed.split())
        score = min(10.0, round(word_count / 8, 1))
        if score >= 7:
            feedback = "Solid, well-developed answer."
        elif score >= 4:
            feedback = "Reasonable start, but could go into more depth."
        else:
            feedback = "Answer is quite brief - try to explain your reasoning more."
        return Evaluation(score=score, feedback=feedback)
