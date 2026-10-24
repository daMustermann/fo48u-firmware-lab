import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
public class seedfuncs extends GhidraScript {
    public void run() throws Exception {
        String listPath = getScriptArgs().length > 0 ? getScriptArgs()[0] : "targets.txt";
        BufferedReader br = new BufferedReader(new FileReader(listPath));
        int n=0, ok=0;
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            // parse hex address (first token)
            String tok = line.split("\\s+")[0];
            if (tok.startsWith("0x") || tok.startsWith("0X")) tok = tok.substring(2);
            long v = Long.parseLong(tok, 16);
            Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(v);
            if (currentProgram.getFunctionManager().getFunctionAt(a) != null) { n++; continue; }
            try {
                currentProgram.getFunctionManager().createFunction("f_" + Long.toHexString(v), a, new ghidra.program.model.address.AddressSet(a, a), SourceType.ANALYSIS);
                ok++;
            } catch (Exception e) { println("err at " + tok + ": " + e); }
            n++;
        }
        br.close();
        println("Processed " + n + " targets, created " + ok + " functions");
    }
}

