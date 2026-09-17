import os
import streamlit as st
import pandas as pd
from src.generator.question_generator import QuestionGenerator


def rerun():
    st.rerun()

class QuizManager:
    def __init__(self):
        self.questions=[]
        self.user_answers=[]
        self.results=[]

    def generate_questions(self, generator:QuestionGenerator , topic:str , question_type:str , difficulty:str , num_questions:int):
        self.questions=[]
        self.user_answers=[]
        self.results=[]

        try:
            for _ in range(num_questions):
                if question_type == "Multiple Choice":
                    question = generator.generate_mcq(topic,difficulty.lower())

                    self.questions.append({
                        'type' : 'MCQ',
                        'question' : question.question,
                        'options' : question.options,
                        'correct_answer': question.correct_answer,
                        'explanation': getattr(question, 'explanation', '') or ''
                    })

                else:
                    question = generator.generate_fill_blank(topic,difficulty.lower())

                    self.questions.append({
                        'type' : 'Fill in the blank',
                        'question' : question.question,
                        'correct_answer': question.answer,
                        'explanation': getattr(question, 'explanation', '') or ''
                    })
        except Exception as e:
            st.error(f"Error generating question {e}")
            return False
        
        return True
    
    def set_questions(self, question_list):
        self.questions = list(question_list) if question_list is not None else []
        self.user_answers = []
        self.results = []
        return True

    def attempt_quiz(self):
        self.user_answers = []
        for i,q in enumerate(self.questions):
            st.markdown(f"**Question {i+1} : {q['question']}**")

            if q['type']=='MCQ':
                user_answer = st.radio(
                    f"Select an answer for Question {i+1}",
                    q['options'],
                    index=None,
                    key=f"mcq_{i}"
                )

                self.user_answers.append(user_answer if user_answer is not None else "")

            else:
                user_answer=st.text_input(
                    f"Fill in the blank for Question {i+1}",
                    key = f"fill_blank_{i}"
                )

                self.user_answers.append(user_answer)

    def evaluate_quiz(self):
        self.results=[]

        for i, (q,user_ans) in enumerate(zip(self.questions,self.user_answers)):
            result_dict = {
                'question_number' : i+1,
                'question': q['question'],
                'question_type' :q["type"],
                'user_answer' : user_ans,
                'correct_answer' : q["correct_answer"],
                'explanation' : q.get('explanation', '') or '',
                "is_correct" : False
            }

            if q['type'] == 'MCQ':
                result_dict['options'] = q['options']
                result_dict["is_correct"] = user_ans == q["correct_answer"]

            else:
                result_dict['options'] = []
                user_ans_norm = (user_ans or "").strip().lower()
                correct_norm = (q.get('correct_answer') or "").strip().lower()
                result_dict["is_correct"] = bool(user_ans_norm) and user_ans_norm == correct_norm

            if q.get("target_skill"):
                result_dict["target_skill"] = q["target_skill"]

            self.results.append(result_dict)

    def generate_result_dataframe(self):
        if not self.results:
            return pd.DataFrame()
        
        return pd.DataFrame(self.results)
    
    def save_to_csv(self, filename_prefix="quiz_results"):
        if not self.results:
            st.warning("No results to save !!")
            return None
        
        df = self.generate_result_dataframe()


        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{filename_prefix}_{timestamp}.csv"

        os.makedirs('results' , exist_ok=True)
        full_path = os.path.join('results' , unique_filename)

        try:
            df.to_csv(full_path,index=False)
            st.success("Results saved successfully....")
            return full_path
        
        except Exception as e:
            st.error(f"Failed to save results {e}")
            return None


def save_match_report_to_json(match_result, filename_prefix="match_report"):
    """Serializes a ``MatchResult`` object to a JSON file under ``results/``.

    Mirrors ``QuizManager.save_to_csv`` so the Match & Skill report can be
    downloaded just like the quiz results. JSON is used (instead of CSV)
    because ``MatchResult`` contains nested structures such as ``radar_data``
    and several string lists that a flat CSV would destroy.

    Returns the saved file path, or ``None`` when there is nothing to save.
    """
    if match_result is None:
        st.warning("No match report to save !!")
        return None

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{filename_prefix}_{timestamp}.json"

    os.makedirs('results', exist_ok=True)
    full_path = os.path.join('results', unique_filename)

    try:
        # ``model_dump_json`` is available on Pydantic v2 models; fall back to
        # ``json()`` for older Pydantic versions to stay backward compatible.
        if hasattr(match_result, "model_dump_json"):
            payload = match_result.model_dump_json(indent=2)
        else:
            payload = match_result.json(indent=2)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(payload)

        st.success("Match report saved successfully....")
        return full_path

    except Exception as e:
        st.error(f"Failed to save match report {e}")
        return None
            