# Offline firmware research outputs

The only firmware image published by this repository is the **unmodified F08 reference** under [`../F08-20221115/`](../F08-20221115/). Experimental images and generated manifests are local build products and are **excluded from Git**.

The tools in [`analysis/`](../../analysis/) provide byte-level audits and offline research experiments. Their checks establish offsets and byte sequences, **not hardware safety or functioning manual refresh**. No modified build is approved for flashing.

## Verify the source image

Run from the repository root:

```bash
python analysis/build_variant.py --verify
python analysis/build_custom.py --verify
python analysis/audit_menu_reachability.py
python analysis/audit_refresh_command_table.py
```

The expected source is `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` (2,031,616 bytes, MD5 `d4324c6c88abea48b1ee896f7e14ee9f`).

To research a code path, consult [the analysis map](../../analysis/README.md) and [the panel-care internals](../../analysis/panel_protection.md). Validate packet framing, selection reachability and recovery procedures before any physical test.
