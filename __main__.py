#!/usr/bin/python3
# -*- coding: UTF-8 -*-

from email import header
import datetime
import random
import subprocess
from dingtalkchatbot.chatbot import DingtalkChatbot
import logging
import json
import schedule
import requests

class DingTalkBot:

    def __init__(self, webhook, keywords, phone_numbers=[]) -> None:
        self.phone_numbers = phone_numbers
        self.keywords = keywords
        self.dingtalk = DingtalkChatbot(webhook=webhook)

    def send_daily_push_msg(self, message):
        logging.warning(message)

        self.dingtalk.send_markdown(title=f'[{self.keywords}] [{datetime.datetime.now()}]:\n', text='> 失业机器人提醒您: 再不刷题厂都没得进了!\n ### 今日推送:\n\n '+
                    message, is_at_all=True, at_mobiles=self.phone_numbers)


LEETCODE_API_ENDPOINT = 'https://leetcode-cn.com/graphql/'
LEETCODE_QUESTION_BASE_URL = 'https://leetcode-cn.com/problems/'

class Question:

    def __init__(self, id, title, title_cn, title_slug, tags, difficult=None, paid_only=False) -> None:
        self.id = id
        self.difficult = difficult
        self.paid_only = paid_only
        self.title = title
        self.title_cn = title_cn
        self.title_slug = title_slug
        self.tags = tags

class LeetcodeHelper:

    def __init__(self, webhook, keywords, easys, mediums, hards, phone_numbers=[]) -> None:
        self.easys = easys
        self.mediums = mediums
        self.hards = hards

        self.questions = []
        self.questions_id_set = set()
        self.questions_id_finished_set = set()
        
        self.level_questions = {
            'easy': {
                'questions': [],
                'set': set(),
            },
            'medium': {
                'questions': [],
                'set': set(),
            },
            'hard': {
                'questions': [],
                'set': set()
            },
            'unknown': {
                'questions': [],
                'set': set()
            }
        }

        self.__daily_pushs = ""

        self.update_all_questions()
        self.ding = DingTalkBot(webhook, keywords, phone_numbers)

    def __dsl_query_probelm_set(self, limit, skip):
        return json.dumps({
            'query': '''
                query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
                    problemsetQuestionList(    
                        categorySlug: $categorySlug    
                        limit: $limit    
                        skip: $skip    
                        filters: $filters
                    ) {
                        hasMore    
                        total    
                        questions {
                            acRate      
                            difficulty     
                            freqBar      
                            frontendQuestionId      
                            isFavor      
                            paidOnly      
                            solutionNum      
                            status      
                            title      
                            titleCn      
                            titleSlug      
                            topicTags {        
                                name        
                                nameTranslated        
                                id        
                                slug      
                            }      
                                extra {        
                                    hasVideoSolution        
                                    topCompanyTags {          
                                        imgUrl          
                                        slug          
                                        numSubscribed        
                                    }      
                                }    
                        }  
                    }
                }
            ''',
            'variables': {
                'categorySlug': "",
                'filters': {},
                'limit': limit,
                'skip': skip,
            },
        })

    def update_all_questions(self):
        self.__daily_pushs = ""

        res = requests.post(LEETCODE_API_ENDPOINT, headers={
            'Content-type': 'application/json',
        }, data=self.__dsl_query_probelm_set(50, 0))

        i = 0
        PAGE_LIMIT = 100
        while True:
            res = requests.post(LEETCODE_API_ENDPOINT, headers={
                'Content-type': 'application/json',
            }, data=self.__dsl_query_probelm_set(PAGE_LIMIT, i))            
            data = json.loads(res.text)['data']
                
            for q in data['problemsetQuestionList']['questions']:
                tags = [t['slug'] for t in q['topicTags']]
                q_id = q['frontendQuestionId']
                if q_id not in self.questions_id_set:
                    new_question = Question(q_id, q['title'], q['titleCn'], q['titleSlug'], tags, q['difficulty'], q['paidOnly'])
                    self.questions.append(new_question)
                    self.questions_id_set.add(q_id)
                    level = 'unknown'
                    if q['difficulty'] == 'EASY':
                       level = 'easy'
                    elif q['difficulty'] == 'MEDIUM':
                        level = 'medium'
                    elif q['difficulty'] == 'HARD':
                        level = 'hard'
                    self.level_questions[level]['questions'].append(new_question)
                    self.level_questions[level]['set'].add(q_id)

            if not data['problemsetQuestionList']['hasMore']:
                break
            else:
                logging.warning(f'get page {i}..')
                i += PAGE_LIMIT

    def __peek_unfinished_questions(self, level):
        rid = random.randint(0, len(self.level_questions[level]['questions'])-1)
        if rid not in self.questions_id_finished_set:
            self.questions_id_finished_set.add(rid)
            return self.level_questions[level]['questions'][rid]
        else:
            self.__peek_unfinished_questions(level)

    def __find_daily_push_questions(self):
        easys = []
        for i in range(self.easys):
            easys.append(self.__peek_unfinished_questions('easy'))
        mediums = []
        for i in range(self.mediums):
            mediums.append(self.__peek_unfinished_questions('medium'))
        hards = []
        for i in range(self.hards):
            hards.append(self.__peek_unfinished_questions('medium'))
        return (easys, mediums, hards)

    def push_daily_questions(self):
        self.ding.send_daily_push_msg(self.daily_push)
    
    @property
    def daily_push(self):
        if self.__daily_pushs != "":
            return self.__daily_pushs
        else:
            msg = ''
            i = 0
            for qs in self.__find_daily_push_questions():
                if len(qs) > 0:
                    for q in qs:
                        msg += f'- [{q.difficult}] Id-{q.id}: [{q.title_cn}({q.title})]({LEETCODE_QUESTION_BASE_URL}{q.title_slug}) \n'
                        msg += f'> tags: {" ".join(q.tags)}\n\n'
                        i += 1
            return msg

if __name__ == "__main__":
    # res = requests.post(LEETCODE_API_ENDPOINT, headers={
    #     'Content-type': 'application/json',
    # }, data=json.dumps({'query': QUERY_DATA}))
    with open('config.json', 'r') as f:
        cfg = json.load(f)
    easys = cfg['easy'] if 'easy' in cfg else 0
    mediums = cfg['medium'] if 'medium' in cfg else 0
    hards = cfg['hards'] if 'hards' in cfg else 0

    l = LeetcodeHelper(cfg['webhook'], cfg['keywords'], easys, mediums, hards)
    schedule.every().day.at(cfg['update']).do(l.update_all_questions)
    for t in cfg['schedule']:
        schedule.every().day.at(t).do(l.push_daily_questions)

    while True:
        schedule.run_pending()