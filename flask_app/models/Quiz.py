from typing import List

class QuizQuestionAnswer():
    def __init__(self, 
        label: str, 
        correct: bool, 
        explanation: str
        ):
        self.label = label
        self.correct = correct
        self.explanation = explanation

    label: str
    correct: bool
    explanation: str

    def __repr__(self):
        return f"QuizQuestionAnswer(label={self.label}, correct={self.correct}, explanation={self.explanation})"

class QuizQuestion():
    def __init__(self, 
        question: str, 
        answers: List[QuizQuestionAnswer], 
        topics: List[str], 
        difficulty: int, 
        userId: str, 
        courseId: str, 
        noteId: str, 
        quizId: str, 
        questionId: str
        ):
        self.question = question
        self.answers = answers
        self.topics = topics
        self.difficulty = difficulty
        self.userId = userId
        self.courseId = courseId
        self.noteId = noteId
        self.quizId = quizId
        self.questionId = questionId

    question: str
    answers: List[QuizQuestionAnswer]
    topics: List[str]
    difficulty: int
    userId: str
    courseId: str
    noteId: str
    quizId: str
    questionId: str

    def __repr__(self):
        return f"QuizQuestion(question={self.question}, answers={self.answers}, topics={self.topics}, difficulty={self.difficulty}, userId={self.userId}, courseId={self.courseId}, noteId={self.noteId}, quizId={self.quizId}, questionId={self.questionId})"