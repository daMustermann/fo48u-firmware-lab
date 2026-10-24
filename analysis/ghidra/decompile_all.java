// Ghidra headless post-script (Java): decompile all functions
// @category Analysis

import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.*;

public class decompile_all extends GhidraScript {
    public void run() throws Exception {
        String outPath = getScriptArgs().length > 0 ? getScriptArgs()[0] : "decompiled.txt";
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        ConsoleTaskMonitor monitor = new ConsoleTaskMonitor();
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        PrintWriter pw = new PrintWriter(new FileWriter(outPath));
        int count = 0;
        while (it.hasNext()) {
            Function f = it.next();
            DecompileResults res = decomp.decompileFunction(f, 30, monitor);
            if (res != null && res.getDecompiledFunction() != null) {
                pw.println("=".repeat(80));
                pw.println("FUNCTION: " + f.getName() + " @ " + f.getEntryPoint());
                pw.println(res.getDecompiledFunction().getC());
                pw.println();
                count++;
            }
        }
        pw.close();
        println("Decompiled " + count + " functions -> " + outPath);
    }
}

