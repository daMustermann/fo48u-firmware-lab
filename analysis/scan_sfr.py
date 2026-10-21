import sys
sys.path.insert(0,'.')
from oplen import OPLEN
d=open('../firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin','rb').read()
from collections import Counter, defaultdict
# mov direct, #data : opcode 0x75, addr, data
sfr_imm = Counter()
sfr_targets = defaultdict(Counter)
end=0x140000
i=0
while i < end:
    op=d[i]
    L=OPLEN.get(op,1)
    if op==0x75 and i+2 < len(d):
        addr=d[i+1]; val=d[i+2]
        if addr >= 0x80:  # SFR
            sfr_imm[addr]+=1
            sfr_targets[addr][val]+=1
    i+=L

print('SFR mov #imm counts (top 40):')
for a,c in sfr_imm.most_common(40):
    print('SFR %s count=%d  vals=%s' % (hex(a), c, dict(sfr_targets[a].most_common(8))))

