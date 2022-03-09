#!/root/.virtualenvs/DingLeetcode-ao4TfSK3/bin/python3
# -*- coding: UTF-8 -*-

from email import header
import datetime
import random
import subprocess
from dingtalkchatbot.chatbot import DingtalkChatbot
import logging
import json

import schedule
import time
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

    def send_daily_summary(self, message, phone_number):
        logging.warning(message)

        self.dingtalk.send_markdown(title=f'[{self.keywords}] [{datetime.datetime.now()}]:\n', text=f'> 失业机器人提醒您: 再不刷题厂都没得进了!\n ###  @{phone_number} 今日总结:\n\n '+
                    message, is_at_all=False, at_mobiles=[phone_number])

    def send_question_status(self, phone_number, question_slug, message):
        logging.warning(message)

        self.dingtalk.send_markdown(title=f'[{self.keywords}] [{datetime.datetime.now()}]:\n', text=f'###  @{phone_number} 已完成 {question_slug}\n\n '+
                    message, is_at_all=True)


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

    def __init__(self, webhook, keywords, easys, mediums, hards, finished_id, cookies, phone_numbers=[]) -> None:
        self.easys = easys
        self.mediums = mediums
        self.hards = hards
        
        # {phone_number: cookie}
        self.user_cookies = cookies

        self.questions = []
        self.questions_id_set = set()

        self.questions_id_finished_set = set(finished_id)
        self.__daily_questions_id_set = set()
        self.__daily_first_finished = set()
        
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

        self.__daily_pushs_msg = ""
        self.__daily_summary = []

        self.update_all_questions()
        self.ding = DingTalkBot(webhook, keywords, phone_numbers)

    def find_question_by_id(self, index):
        aimed = [q for q in self.questions if q.id == index]
        
        if aimed:
            return aimed[0]


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
        self.__daily_pushs_msg = ""
        self.__daily_questions_id_set = set()
        self.__daily_first_finished = set()
        
        with open('data/finished_id.json', 'w') as f:
            json.dump(list(self.questions_id_finished_set), f)

        res = requests.post(LEETCODE_API_ENDPOINT, headers={
            'Content-type': 'application/json',
        }, data=self.__dsl_query_probelm_set(100, 0))

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
        try:
            self.ding.send_daily_push_msg(self.daily_push)
        except Exception as e:
            logging.warning(e)
            time.sleep(30)
            self.push_daily_questions()

    @property
    def daily_push(self):
        if self.__daily_pushs_msg != "":
            return self.__daily_pushs_msg
        else:
            msg = ''
            i = 0
            for qs in self.__find_daily_push_questions():
                if len(qs) > 0:
                    for q in qs:
                        self.__daily_questions_id_set.add(q.id)
                        msg += f'- [{q.difficult}] Id-{q.id}: [{q.title_cn}({q.title})]({LEETCODE_QUESTION_BASE_URL}{q.title_slug}) \n'
                        msg += f'> tags: {" ".join(q.tags)}\n\n'
                        i += 1

            self.__daily_pushs_msg = msg
            return msg

    def push_daily_summary(self):
        for data in self.daily_summary:
            (phone_number, msg) = data

            try:
                self.ding.send_daily_summary(msg, phone_number)
            except Exception as e:
                logging.warning('error')
                time.sleep(30)
                continue

    def __dsl_query_user_profile_questions(self, limit, skip):
        return json.dumps({
            'operationName': 'userProfileQuestions',
            'query': '''
                query userProfileQuestions(
                $status: StatusFilterEnum!
                $skip: Int!
                $first: Int!
                $sortField: SortFieldEnum!
                $sortOrder: SortingOrderEnum!
                $keyword: String
                $difficulty: [DifficultyEnum!]
                ) {
                userProfileQuestions(
                    status: $status
                    skip: $skip
                    first: $first
                    sortField: $sortField
                    sortOrder: $sortOrder
                    keyword: $keyword
                    difficulty: $difficulty
                ) {
                    totalNum
                    questions {
                        translatedTitle
                        frontendId
                        titleSlug
                        title
                        difficulty
                        lastSubmittedAt
                        numSubmitted
                        lastSubmissionSrc {
                            sourceType
                            ... on SubmissionSrcLeetbookNode {
                            slug
                            title
                            pageId
                            __typename
                            }
                            __typename
                        }
                        __typename
                        }
                        __typename
                    }
                }
            ''',
            'variables': {
                'difficulty': [],
                'first': limit,
                'skip': skip,
                'sortField': "LAST_SUBMITTED_AT",
                'sortOrder': "DESCENDING",
                'status': "ACCEPTED"
            }
        })

    def __get_user_status(self):
        users = []
        for phone_num, cookie in self.user_cookies.items():
            try:
                res = requests.post(LEETCODE_API_ENDPOINT, headers={
                    'Content-type': 'application/json',
                    'cookie': cookie,
                }, data=self.__dsl_query_user_profile_questions(50, 0))
                data = json.loads(res.text)['data']['userProfileQuestions']
                total = int(data['totalNum'])
                finished = []
                for q in data['questions']:
                    q_id = q['frontendId']
                    if q_id not in self.__daily_questions_id_set:
                        continue

                    last_submmit = q['lastSubmittedAt']
                    submit_times = q['numSubmitted']
                    finished.append((q_id, last_submmit, submit_times))
                users.append((phone_num, total, finished))
            except Exception as e:
                logging.warning('get user status failed: ', phone_num)
        return users

    @property
    def daily_summary(self):
        if self.__daily_summary:
            return self.__daily_summary

        for user in self.__get_user_status():
            phone_number = user[0]
            total = user[1]
            finished = user[2]
            msg = f'- 总完成题目数: {total}\n\n'
            tmp = ''
            count = 0
            # for debug
            for p in self.__daily_questions_id_set:
                p_finished = None
                for fid in finished:
                    if fid[0] == p:
                        p_finished = fid
                if finished and p_finished:
                    tmp += f'[√] Id:{p} 上次提交: {datetime.datetime.fromtimestamp(int(p_finished[1])).strftime("%H:%M:%S")} 提交次数: {p_finished[2]} \n\n'
                    count += 1
                else:
                    q = self.find_question_by_id(p)
                    tmp += f'[X] Id:{p} [{q.title_cn}({q.title})]({LEETCODE_QUESTION_BASE_URL}{q.title_slug}) \n\n'
            msg += f"- 今日题目完成数: {count}/{len(self.__daily_questions_id_set)}\n\n"
            msg += tmp + "\n\n"

            self.__daily_summary.append((phone_number, msg))
        
        return self.__daily_summary

    def __dsl_get_submissions(self, offset, limit, question_slug):
        return json.dumps({
            'operationName': "submissions",
            'query': '''
                query submissions(
                    $offset: Int!
                    $limit: Int!
                    $lastKey: String
                    $questionSlug: String!
                    $markedOnly: Boolean
                    $lang: String
                ) {
                submissionList(
                    offset: $offset
                    limit: $limit
                    lastKey: $lastKey
                    questionSlug: $questionSlug
                    markedOnly: $markedOnly
                    lang: $lang
                ) {
                    lastKey
                    hasNext
                    submissions {
                        id
                        statusDisplay
                        lang
                        runtime
                        timestamp
                        url
                        isPending
                        memory
                        submissionComment {
                            comment
                            flagType
                            __typename
                        }
                        __typename
                        }
                        __typename
                    }
                }
            ''',
            'variables': {
                'offset': offset, 
                'limit': limit, 
                'lastKey': None, 
                'questionSlug': question_slug
            }
        })

    def __get_question_submissions(self, question_slug):
        user_submissions = dict()
        for phone_num, cookie in self.user_cookies.items():
            user_submissions[phone_num] = {}
            while True:
                res = requests.post(LEETCODE_API_ENDPOINT, headers={
                    'Content-type': 'application/json',
                    'cookie': cookie,
                }, data=self.__dsl_get_submissions(0, 40, question_slug))
                data = json.loads(res.text)['data']['submissionList']

                submissions = [s for s in data['submissions'] if s['statusDisplay'] == 'Accepted']

                info = {}
                for s in submissions:
                    lang = s['lang']
                    if lang not in info:
                        info[lang] = {}
                    if 'stmp' not in info[lang]:
                        info[lang]['stmp'] = 0
                    if int(s['timestamp']) > info[lang]['stmp']:
                        info[lang]['stmp'] = int(s['timestamp'])
                        info[lang]['time'] = s['runtime']
                        info[lang]['mem'] = s['memory']
                        info[lang]['url'] = LEETCODE_QUESTION_BASE_URL+question_slug+s['url']

                user_submissions[phone_num] = info
                
                if not data['hasNext']:
                    break
        
        return user_submissions

    def get_question_finished_user(self, question_slug):
        if question_slug in self.__daily_first_finished:
            return

        for pnum, data in self.__get_question_submissions(question_slug).items():
            if len(data.keys()) > 0:
                msg = ""
                for lang, info in data.items():
                    time = info['time']
                    mem = info['mem']
                    submit_time = info['stmp']
                    url = info['url']
                    msg += f'**Lang:** [{lang}]({url})\t**Time:** {time}\t**Mem:** {mem} --submit at {datetime.datetime.strftime(datetime.datetime.fromtimestamp(submit_time), "%H:%M:%S")}\n\n'
                # print(msg)
                self.__daily_first_finished.add(question_slug)
                self.ding.send_question_status(pnum, question_slug, msg)

    def question_finished(self):
        for i in self.__daily_questions_id_set:
            self.get_question_finished_user(self.find_question_by_id(i).title_slug)

if __name__ == "__main__":

    with open('config.json', 'r') as f:
        cfg = json.load(f)
    easys = cfg['easy'] if 'easy' in cfg else 0
    mediums = cfg['medium'] if 'medium' in cfg else 0
    hards = cfg['hards'] if 'hards' in cfg else 0
    with open('./data/finished_id.json', 'r') as f:
        finished_id = json.load(f)
    l = LeetcodeHelper(cfg['webhook'], cfg['keywords'], easys, mediums, hards, finished_id, cookies=cfg['cookies'])

    # # l.get_user_status()
    # l.daily_push
    # l.push_daily_summary()
    # # l.push_daily_questions()
    # # l.push_daily_summary()

    schedule.every().day.at(cfg['update']).do(l.update_all_questions)
    for t in cfg['schedule']:
        schedule.every().day.at(t).do(l.push_daily_questions)
    schedule.every().day.at("15:00").do(l.question_finished)
    schedule.every().day.at("16:00").do(l.question_finished)
    schedule.every().day.at("17:00").do(l.question_finished)
    schedule.every().day.at("19:00").do(l.question_finished)
    schedule.every().day.at("20:00").do(l.question_finished)
    schedule.every().day.at(cfg['summary']).do(l.push_daily_summary)

    while True:
        schedule.run_pending()

    # l.get_question_finished_user('binary-tree-preorder-traversal')
    # l.get_question_finished_user('masking-personal-information')
    # l.get_question_finished_user('sfvd7V')
    
    