# Ghidra headless post-script: decompile all functions and dump to a file
# Run: analyzeHeadless ... -postScript decompile_all.py <outfile>
import ghidra.app.decompiler.DecompInterface as DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

prog = currentProgram
decomp = DecompInterface()
decomp.openProgram(prog)
monitor = ConsoleTaskMonitor()
fm = prog.getFunctionManager()
funcs = fm.getFunctions(True)
out_path = getScriptArgs()[0] if getScriptArgs() else "decompiled.txt"
f = open(out_path, "w")
count = 0
for func in funcs:
    res = decomp.decompileFunction(func, 30, monitor)
    if res and res.decompiledFunction:
        f.write("="*80 + "\n")
        f.write("FUNCTION: %s @ %s\n" % (func.getName(), func.getEntryPoint()))
        f.write(res.decompiledFunction.getC())
        f.write("\n")
        count += 1
f.close()
print("Decompiled %d functions -> %s" % (count, out_path))
