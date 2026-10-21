import sys
sys.path.insert(0,'.')
from oplen import OPLEN
d=open('../firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin','rb').read()
from collections import Counter
# find lcall 0x507e (12 50 7e) and check preceding instruction for mov a,#imm (74 xx)
banks=Counter()
i=0; end=0x140000; hits=[]
while i<end:
    if d[i]==0x12 and i+2<end and d[i+1]==0x50 and d[i+2]==0x7e:
        # preceding instruction: check if i-2..i is 74 xx
        if i>=2 and d[i-2]==0x74:
            banks[d[i-1]]+=1
            hits.append((i-2, d[i-1]))
    i+=OPLEN.get(d[i],1)
print('bank-switch calls with mov a,#imm preceding:', len(hits))
print('bank numbers used:', sorted(banks))
for b,n in sorted(banks.items()):
    print('bank', b, 'count', n)

