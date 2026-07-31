QUESTION_GENERATION_SYSTEM_PROMPT = """You are an experienced technical interviewer conducting a \
mock interview. Generate exactly one interview question.

Respond with ONLY a JSON object (no markdown fences, no other text) in this exact shape:
{"topic": "short-kebab-case-topic", "question": "the full question text"}"""


def build_question_generation_prompt(
    language: str, difficulty: str, exclude_topics: list[str]
) -> str:
    exclude_note = (
        f" Do not ask about these topics again, they were already covered in this session: "
        f"{', '.join(exclude_topics)}."
        if exclude_topics
        else ""
    )
    return (
        f"Ask a {difficulty}-level technical interview question for a {language} developer."
        f"{exclude_note} The question should test real understanding, not trivia."
    )


ANSWER_EVALUATION_SYSTEM_PROMPT = """You are an experienced technical interviewer scoring a \
candidate's answer to a technical interview question.

Respond with ONLY a JSON object (no markdown fences, no other text) in this exact shape:
{"score": 7.5, "feedback": "one or two sentences of specific, constructive feedback"}

The score must be a number from 0 to 10. Judge correctness, completeness, and clarity."""


def build_answer_evaluation_prompt(question: str, answer: str) -> str:
    return f"Question: {question}\n\nCandidate's answer: {answer}"
