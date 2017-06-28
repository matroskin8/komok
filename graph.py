import matplotlib.pyplot as plt
from numpy import linspace

from komok import Aucs

a = Aucs()

b = [([b.bid for b in auc.bids.bids], [b.date for b in auc.bids.bids]) for auc in a.aucs]
p = [([p.price for p in auc.predicts.ps], [p.date for p in auc.predicts.ps]) for auc in a.aucs]

# plt.figure(dpi=800)
for i, j in b:
    plt.figure()
    plt.plot(j, i)

for i, j in p:
    plt.plot(j, i)
plt.savefig('1.png')
pass

