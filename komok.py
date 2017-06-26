import datetime
import re

import pymongo
from grab import Grab


# search500 = 'http://www.komok.com/?type_message=auction&forumpage_topics=500'
search500 = 'http://www.komok.com/?forumpage_topics=500&type_message=auction&forumpage_days=5536'
regexp4idFromUrl = re.compile('cgi\?id=(\d+:\d+)')
regex4bid = re.compile("(\d{2}.\d{2}.\d{4} \d{2}:\d{2}:\d{2}). (.+) сделал ставку (\d+)")  # ungreedy
reger4timeLeft = re.compile('rtimer=(\d+);')
regex4date = re.compile('(\d{2}-\d{2}-\d{4} \d{2}:\d{2})')
regex4bidLimits = re.compile('Минимальная ставка - (\d+) руб, максимальная - (\d+) рублей')

g = Grab()

mongoCreds = {'host': '10.48.68.73', 'port': 27017}

MONGO_CLI = pymongo.MongoClient(**mongoCreds).komok.aucs


def normal(values: list, zero=None, one=None): # todo уметь принимать кастомный "0" и "1" - начало и конец торга
    """
    возвращает список со значениями пропорционально от 0 до 1
    :param values: list
    :param one:
    :param zero:
    :return: list
    """
    if not values:
        return []

    zero = min(values)
    one = max(values)
    if not one - zero:
        return []

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

    def __repr__(self):
        return str(self.bid)


class Bids:
    def __init__(self, g):
        if isinstance(g, list):
            self.bids = [Bid(**i) for i in g if i]
        else:
            history = g.doc.select(".//div[@id='ahistory']")[0].text()
            a = [[{'name': name, 'date': date, 'bid': bid} for date, name, bid in regex4bid.findall(i)]
                    for i in history.split('руб.')]
            self.bids = [Bid(**i[0]) for i in a if i]
        # todo обрабатывать отмену ставки

    def json(self):
        return [bid.json() for bid in self.bids]

    def normal(self):
        bids = normal([bid.bid for bid in self.bids])
        dates = normal([bid.dateSeconds for bid in self.bids])
        if not all([bids, dates]):
            bids, dates = [], []

        return {'bids': bids,
                'dates': dates}

    def __repr__(self):
        bids = [bid.bid for bid in self.bids]
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

    def __repr__(self):
        return '%s - %s' % (self.price, self.strDate)


class Predicts:
    def __init__(self, g):
        self.ps = []
        if isinstance(g, list):
            self.ps = [Predict(**i) for i in g if i]
        else:
            self.ps = self.method1(g)
            if not [p for p in self.ps if p.price]:
                self.ps = self.method2(g)

    def method1(self, g):
        ps = []
        for i in g.doc.select(".//table[@cellpadding='3']//tr/td[@class='t2' or 't1'][@valign='top']/a/../.."):
            ps.append([i.select("td/a")[0].text(),
                       i.select("td/table//tr/td[@class='date1']")[0].text(),
                       i.select("td/table//tr/td[@class='n']")[0].text()])
        return [Predict(*i) for i in ps if i[2].isdigit()]

    def method2(self, g):
        ps = []
        for i in g.doc.select(".//table[@cellpadding='3']//tr/td[@class='t2' or 't1'][@width='82%']/.."):
            ps.append([i.select("td[@valign='top']").text(),
                       i.select("td/table//tr/td[@class='date1']")[0].text(),
                       i.select("td/table//tr/td[@class='n']")[0].text()])
        return [Predict(*i) for i in ps if i[2].isdigit()]

    def json(self):
        return [p.json() for p in self.ps]

    def normal(self):
        # zip([[p.price, p.dateSeconds] for p in self.ps])
        return {'prices': normal([p.price for p in self.ps]),
                'dates': normal([p.dateSeconds for p in self.ps])}

    def __repr__(self):
        ps = [ps.price for ps in self.ps]
        if not ps: ps = [0]
        return '%s - %s' % (min(ps), max(ps))


class Auc:
    def __init__(self, id=None, **kwargs):
        self.id = id
        self.url = 'http://www.komok.com/topic.cgi?id=%s&h=1#h' % id

        self.isLogedIn = False
        self.secondsLeft = None

        self.isActive = kwargs.get('isActive', True)

        if kwargs and not self.isActive:

            self.title = kwargs['title']
            self.description = kwargs['description']
            self.strStarted = kwargs['started']
            self.started = kwargs['started']
            self.looks = kwargs['looks']
            self.price = kwargs['price']
            self.predicts = Predicts(kwargs['predicts'])
            self.bids = Bids(kwargs['bids'])
            self.parsed = kwargs.get('parced')
            self.fromWeb = False
        else:
            g.go(self.url)
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
                self.bidStepLimits = [i.text() for i in g.doc.select(".//div[@style='background: #90ee90; padding: 15px; margin: 0px']")][0]
                self.bidStepLimits = [int(i) for i in  regex4bidLimits.findall(self.bidStepLimits)[0]]
                self.secondsLeft = reger4timeLeft.findall(secondsLeft[0].text())[0]
            self.predicts = Predicts(g)
            self.bids = Bids(g)
            self.parsed = ''  # todo дату
            self.fromWeb = True
            self.save()

    def makeBid(self):
        pass

    def save(self):
        j = self.json()
        MONGO_CLI.update({'id': j['id']}, j, upsert=True)

    def login(self):
        pass

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


class Aucs:
    def __init__(self):
        self.aucs = [Auc(**auc) for auc in MONGO_CLI.find()]

        g.go(search500)  # .//table[@cellpadding='3']
        webIds = [regexp4idFromUrl.findall(i.attr('href')) for i in g.doc.select(".//table[@cellpadding='3']/tr/td//a")]
        webIds = {i[0] for i in webIds if i}
        loadedIds = [j.id for j in self.aucs]
        [self.aucs.append(Auc(i)) for i in webIds if i not in loadedIds]

    def __repr__(self):
        return '%s / %s' % (len([a for a in self.aucs if self.isActive]), len(self.aucs))

if __name__ == '__main__':

    # a = Auc('34:50600')
    # a.predicts.normal()
    # a.save()
    aa = Aucs()
    print()
