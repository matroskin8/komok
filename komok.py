import datetime
import re

import logging
from collections import Counter

import pymongo
from grab import Grab

# исключить '44:10454'

# search500 = 'http://www.komok.com/?type_message=auction&forumpage_topics=500'
from Users import User, Users

search500 = 'http://www.komok.com/?forumpage_topics=500&type_message=auction&forumpage_days=5536'
regexp4idFromUrl = re.compile('cgi\?id=(\d+:\d+)')
regex4bid = re.compile("(\d{2}.\d{2}.\d{4} \d{2}:\d{2}:\d{2}). (.+) сделал ставку (\d+)")  # ungreedy
reger4timeLeft = re.compile('rtimer=(\d+);')
regex4date = re.compile('(\d{2}-\d{2}-\d{4} \d{2}:\d{2})')
regex4bidLimits = re.compile('Минимальная ставка - (\d+) руб, максимальная - (\d+) рублей')


g = Grab()
g.setup(connect_timeout=5)

mongoCreds = {'host': '10.48.68.73', 'port': 27017}

MONGO_CLI = pymongo.MongoClient(**mongoCreds).komok.aucs


def normal(values: list, zero=0, one=None): # todo уметь принимать кастомный "0" и "1" - начало и конец торга
    """
    возвращает список со значениями пропорционально от 0 до 1
    :param values: list
    :param one:
    :param zero:
    :return: list
    """
    if not values:
        return []

    # zero = zero or min(values)
    one = one or max(values)
    # if not one - zero:
    #     return []

    return [(value - zero) / (one - zero) for value in values]


class Bid:
    def __init__(self, name, date, bid):
        self.bid = int(bid)
        if isinstance(date, datetime.datetime):
            self.strDate = str(date)
            self.date = date
            self.dateSeconds = int(self.date.timestamp())
        else:
            self.strDate = date
            self.date = datetime.datetime.strptime(date, '%d.%m.%Y %H:%M:%S')
            self.dateSeconds = int(self.date.timestamp())
        self.name = name

    def json(self):
        return {'name': self.name, 'date': self.date, 'bid': self.bid}

    def __str__(self):
        return str(self.bid)


class Bids(list):
    # def __init__(self, g):
    #     if isinstance(g, list):
    #         self.bids = [Bid(**i) for i in g if i]
    #     else:
    #         history = g.doc.select(".//div[@id='ahistory']")[0].text()
    #         a = [[{'name': name, 'date': date, 'bid': bid} for date, name, bid in regex4bid.findall(i)]
    #                 for i in history.split('руб.')]
    #         self.bids = [Bid(**i[0]) for i in a if i]
    #     # todo обрабатывать отмену ставки

    def append(self, name, date, bid):
        super().append(Bid(name, date, bid))

    def json(self):
        return [bid.json() for bid in self]

    def normal(self):
        bids = normal([bid.bid for bid in self])
        dates = normal([bid.dateSeconds for bid in self], min([bid.dateSeconds for bid in self]))
        if not all([bids, dates]):
            bids, dates = [], []

        return {'bids': bids,
                'dates': dates}

    def __str__(self):
        bids = [bid.bid for bid in self]
        if not bids: bids = [0]
        return '%s - %s' % (min(bids), max(bids))


class Predict:
    def __init__(self, name, date, price):
        self.price = int(price)
        if isinstance(date, datetime.datetime):
            self.strDate = str(date)
            self.date = date
            self.dateSeconds = int(self.date.timestamp())
        else:
            self.strDate = ' '.join(date.split()[1:])
            self.date = datetime.datetime.strptime(self.strDate, "%d-%m-%Y %H:%M")
            self.dateSeconds = int(self.date.timestamp())
        self.name = name

    def json(self):
        return {'name': self.name, 'date': self.date, 'price': self.price}

    def __str__(self):
        return '%s - %s' % (self.price, self.strDate)


class Predicts(list): # todo не добавлять предсказания сделанные позже окончания аукциона

    def append(self, name, date, price):
        super().append(Predict(name, date, price))

    def json(self):
        return [p.json() for p in self]

    def normal(self, zero=0, onePrice=None, oneDate=None):
        if self.ps:
            return {'prices': normal([p.price for p in self], one=onePrice),
                    'dates': normal([p.dateSeconds for p in self], min([p.dateSeconds for p in self]), one=oneDate)}
        else:
            return {'prices': [],
                    'dates': []}

    def __str__(self):
        ps = [ps.price for ps in self]
        if not ps: ps = [0]
        return '%s - %s' % (min(ps), max(ps))


class Auc:
    def __init__(self, id=None, **kwargs):

        self.isLogedIn = False
        self.secondsLeft = None

        self.isActive = kwargs.get('isActive', True)
        self.predicts = Predicts()
        self.bids = Bids()

        if kwargs and not self.isActive:
            self.id = id
            self.title = kwargs['title']
            self.description = kwargs['description']
            self.strStarted = kwargs['started']
            self.started = kwargs['started']
            self.looks = kwargs['looks']
            self.price = kwargs['price']
            [self.predicts.append(**i) for i in kwargs['predicts']]
            [self.bids.append(**i) for i in kwargs['bids']]
            self.parsed = kwargs.get('parced')
            self.fromWeb = False
        else:
            self.loadFromWeb(id)

    def loadFromWeb(self, id): # todo собрать dict и вызвать __imit__
        def predMethod1(g):
            ps = []
            for i in g.doc.select(".//table[@cellpadding='3']//tr/td[@class='t2' or 't1'][@valign='top']/a/../.."):
                ps.append([i.select("td/a")[0].text(),
                           i.select("td/table//tr/td[@class='date1']")[0].text(),
                           i.select("td/table//tr/td[@class='n']")[0].text()])
            return [i for i in ps if i[2].isdigit()]

        def predMethod2(g):
            ps = []
            for i in g.doc.select(".//table[@cellpadding='3']//tr/td[@class='t2' or 't1'][@width='82%']/.."):
                ps.append([i.select("td[@valign='top']").text(),
                           i.select("td/table//tr/td[@class='date1']")[0].text(),
                           i.select("td/table//tr/td[@class='n']")[0].text()])
            return [i for i in ps if i[2].isdigit()]

        self.id = id
        self.url = 'http://www.komok.com/topic.cgi?id=%s&h=1#h' % id
        try:
            g.go(self.url)
        except Exception as e:
            logging.exception(self.url, e)
            return None
        print(self.url)
        getByXpath = lambda t, n=0: [i.text() for i in g.doc.select(t)][n]
        self.isActive = False

        self.title = getByXpath(".//div[@class='n3']/font[1]")
        # print(self.title)
        self.description = getByXpath(".//div[@class='n3']")
        self.strStarted = getByXpath(".//table[@cellpadding='2']//tr[@class='t1'][1]/td[@class='t3'][2]")
        self.started = datetime.datetime.strptime(self.strStarted, "%d-%m-%Y %H:%M")
        self.looks = getByXpath(".//table[@cellpadding='2']//tr[@class='t1'][2]/td[@class='t3'][2]")
        self.price = int(getByXpath(".//table[@cellpadding='2']//tr[@class='t1'][6]/td[@class='t3'][2]").split()[0])
        secondsLeft = g.doc.select(".//td[@style='padding-left: 10px']/script")
        if secondsLeft:
            self.isActive = True
            self.bidStepLimits = \
            [i.text() for i in g.doc.select(".//div[@style='background: #90ee90; padding: 15px; margin: 0px']")][0]
            self.bidStepLimits = [int(i) for i in regex4bidLimits.findall(self.bidStepLimits)[0]]
            self.secondsLeft = reger4timeLeft.findall(secondsLeft[0].text())[0]

        [self.predicts.append(*i) for i in predMethod1(g)]
        if not [p for p in self.predicts if p.price]:
            [self.predicts.append(*i) for i in predMethod2(g)]

        history = g.doc.select(".//div[@id='ahistory']")[0].text()
        a = [[{'name': name, 'date': date, 'bid': bid} for date, name, bid in regex4bid.findall(i)]
             for i in history.split('руб.')]
        [self.bids.append(**i[0]) for i in a if i]

        self.parsed = datetime.datetime.now()
        self.fromWeb = True
        self.save()

    def makeBid(self):
        pass

    def save(self):
        j = self.json()
        MONGO_CLI.update({'id': j['id']}, j, upsert=True)

    def json(self):
        return {'description': self.description,
                'url': self.url,
                'bids': self.bids.json(),
                'secondsLeft': self.secondsLeft,
                'started': self.started,
                'predicts': self.predicts.json(),
                'price': self.price,
                'looks': self.looks,
                'id': self.id,
                'title': self.title,
                'isActive': self.isActive}

    def __str__(self):
        return '%s %s' % (self.id, self.title)


class Aucs(list):
    def append(self, a):
        super().append(Auc(**a))

class Komok:
    def __init__(self, fromWeb=False):
        self.aucs = Aucs()
        [self.aucs.append(auc) for auc in MONGO_CLI.find()]
        print('Аукционов из базы - %s' % len(self.aucs))
        if fromWeb:
            self.getNew()
        self.sort()
        self.users = Users()
        self.buildUsers()

    def getNew(self):
        g.go(search500)  # .//table[@cellpadding='3']
        webIds = [regexp4idFromUrl.findall(i.attr('href')) for i in g.doc.select(".//table[@cellpadding='3']/tr/td//a")]
        webIds = {i[0] for i in webIds if i}
        loadedIds = [j.id for j in self.aucs]
        [self.aucs.append(Auc(i)) for i in webIds if i not in loadedIds]

    def sort(self):
        self.aucs.sort(key=lambda a: a.started, reverse=True)

    def buildUsers(self):
        bids = []
        [[bids.append(bid.name) for bid in auc.bids.bids] for auc in self.aucs]
        preds = []
        [[preds.append(p.name) for p in auc.predicts] for auc in self.aucs]
        users = set(bids + preds)
        countedBids = Counter(bids)
        countedPreds = Counter(preds)
        users = [user for user in users if 'отменил свою ставку' not in user]

        for user in users:
            self.users.append(user, countedBids.get(user), countedPreds.get(user))
        print()

    def __str__(self):
        return '%s / %s' % (len([a for a in self.aucs if self.isActive]), len(self.aucs))

if __name__ == '__main__':

    # a = Auc('34:50600')
    # a.predicts.normal()
    # a.save()
    aa = Komok(False)
    print()
