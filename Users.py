class Users(list):

    def append(self, name, bids, preds):
        super().append(User(name, bids, preds))

    # def __str__(self, aucs):
    #     pass


class User:
    def __init__(self, name, bids=0, preds=0, aucsBids=0, aucsPreds=0):
        self.name = name
        self.bids = bids if bids else 0
        self.preds = preds if preds else 0
        self.aucsBids = aucsBids if aucsBids else 0
        self.aucsPreds = aucsPreds if aucsPreds else 0

    def __str__(self):
        return '%s %s/%s' % (self.name, self.bids, self.preds)

    def update(self):
        pass

if __name__ == '__main__':

    u = Users()
    u.append('asd', 5, 4)
    print()
