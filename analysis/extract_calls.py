import sys
sys.path.insert(0,'.')
from oplen import OPLEN

d=open('../firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin','rb').read()

from collections import Counter
lcall_targets=Counter()
acall_targets=Counter()
ljmp_targets=Counter()
ajmp_targets=Counter()

end=0x140000
i=0
while i < end:
    op=d[i]
    L=OPLEN.get(op,1)
    if op==0x12:
        tgt=(d[i+1]<<8)|d[i+2]
        lcall_targets[tgt]+=1
    elif op in (0x11,0x31,0x51,0x71,0x91,0xb1,0xd1,0xf1):
        page = (i+2) & 0xF800
        addr11 = ((op & 0xE0) << 3) | d[i+1]
        tgt = page | addr11
        acall_targets[tgt]+=1
    elif op==0x02:
        tgt=(d[i+1]<<8)|d[i+2]
        ljmp_targets[tgt]+=1
    elif op in (0x01,0x21,0x41,0x61,0x81,0xa1,0xc1,0xe1):
        page=(i+2)&0xF800
        addr11=((op&0xE0)<<3)|d[i+1]
        tgt=page|addr11
        ajmp_targets[tgt]+=1
    i+=L

out=[]
out.append('distinct lcall targets: %d' % len(lcall_targets))
out.append('top lcall targets:')
for t,c in lcall_targets.most_common(80):
    out.append('%s %d' % (hex(t), c))
out.append('')
out.append('distinct acall targets: %d' % len(acall_targets))
out.append('top acall targets:')
for t,c in acall_targets.most_common(80):
    out.append('%s %d' % (hex(t), c))
out.append('')
out.append('distinct ljmp targets: %d' % len(ljmp_targets))
for t,c in ljmp_targets.most_common(40):
    out.append('ljmp %s %d' % (hex(t), c))
out.append('')
out.append('distinct ajmp targets: %d' % len(ajmp_targets))
out.append('top ajmp targets:')
for t,c in ajmp_targets.most_common(40):
    out.append('ajmp %s %d' % (hex(t), c))

open('calltargets.txt','w').write('\n'.join(out))
print('done')