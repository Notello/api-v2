from typing import List

class QuizQuestionAnswer():
    label: str
    correct: bool
    explanation: str

class QuizQuestion():
    question: str
    answers: List[QuizQuestionAnswer]
    topics: List[str]
    userId: str
    courseId: str
    noteId: str