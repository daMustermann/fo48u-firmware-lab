import ghidra.app.script.GhidraScript;
public class listfuncs extends GhidraScript {
    public void run() throws Exception {
        String outPath = getScriptArgs().length > 0 ? getScriptArgs()[0] : "funcs.txt";
        java.io.PrintWriter pw = new java.io.PrintWriter(new java.io.FileWriter(outPath));
        int n = 0;
        for (ghidra.program.model.listing.Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            pw.println(f.getEntryPoint() + " " + f.getName());
            n++;
        }
        pw.close();
        println("Total functions: " + n);
    }
}
