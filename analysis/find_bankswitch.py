import sys
sys.path.insert(0,'.')
from oplen import OPLEN
d=open('../firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin','rb').read()
from collections import Counter
# Find mov direct,#imm (0x75 a v) where direct in 0x60-0x7f, followed within up to 4 bytes by ljmp (0x02) to >=0x8000
hits=[]
i=0; end=0x140000
while i<end:
    op=d[i]; L=OPLEN.get(op,1)
    if op==0x75 and i+2<end and 0x60<=d[i+1]<=0x7f:
        # look ahead up to 4 bytes for 0x02
        for j in range(i+3, min(i+8, end-2)):
            if d[j]==0x02:
                tgt=(d[j+1]<<8)|d[j+2]
                if tgt>=0x8000:
                    hits.append((i, d[i+1], d[i+2], j, tgt))
                    break
    i+=L
print('num hits:', len(hits))
from collections import Counter
c=Counter((h[1],h[2]) for h in hits)
for (sfr,val),n in c.most_common(30):
    print('SFR %s = %s  count=%d' % (hex(sfr), hex(val), n))
print()
print('first 30 hits:')
for h in hits[:30]:
    print(hex(h[0]), 'mov',hex(h[1]),hex(h[2]), 'ljmp@',hex(h[3]), hex(h[4]))

