import logging
from random import randint
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.models.Quiz import QuizQuestion, QuizQuestionAnswer
from flask_app.services.GraphCreationService import GraphCreationService

class QuizService():
    validSpecifiers = ['userId', 'courseId', 'noteId']

    @staticmethod
    def generate_quiz(topics=[],
                      courseId=None,
                      userId=None,
                      quizId=None,
                      noteId=None,
                      difficulty=None,
                      numQuestions=None,
                      specifierParam=None
                      ):

        topic_graph = GraphQueryService.get_topic_graph(
            courseId=courseId, 
            userId=userId, 
            noteId=noteId,
            specifierParam=specifierParam,
            topics=topics
            )
    
        if topic_graph is None:
            return None
        
        questionIds = []
        
        for _ in range(numQuestions):
            question = SupabaseService.add_quiz_question(quizId=quizId)

            if len(question) == 0:
                logging.error(f"Failed to add question for quiz {quizId}")
                return None
            
            questionIds.append(question[0]['id'])

        questions = QuizService.generate_quiz_questions(
            topic_graph=topic_graph,
            courseId=courseId, 
            userId=userId,
            quizId=quizId,
            noteId=noteId,
            questionIds=questionIds,
            difficulty=difficulty,
            numQuestions=numQuestions
            )
        
        GraphCreationService.insert_quiz_question(questions=questions)
    
    @staticmethod
    def generate_quiz_questions(
        topic_graph, 
        courseId, 
        userId,
        quizId=None,
        questionIds=[],
        difficulty=None,
        numQuestions=None,
        noteId=None):

        questions = []

        for i in range(numQuestions):
            question = QuizQuestion(
                question=f"Question {i}",
                answers=[],
                topics=[f"Topic {j}" for j in range(randint(1, 5))],
                difficulty=difficulty,
                userId=userId,
                courseId=courseId,
                noteId=noteId,
                quizId=quizId,
                questionId=f"{questionIds[i]}",
            )

            for j in range(4):
                question.answers.append(QuizQuestionAnswer(
                    label=f"Answer {j}",
                    correct=(j == 2),
                    explanation=f"Explanation for answer {j}"
                ))
            
            questions.append(question)

        return questions
