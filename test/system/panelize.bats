#!/usr/bin/env bats

load common

@test "Extract board" {
    kikit separate --source 'rectangle; tlx: 89mm; tly: 89mm; brx: 111mm; bry: 111mm' \
        --debug 'trace: true' \
        $RES/multiboard.kicad_pcb board_a_by_area.kicad_pcb

    kikit separate --source 'annotation; ref: B1' \
        $RES/multiboard.kicad_pcb board_a_by_ref.kicad_pcb
}

@test "Simple grid, no space, vcuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2;' \
        --tabs full \
        --cuts vcuts \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t1.kicad_pcb
}

@test "Simple grid, spacing, vcuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts vcuts \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t2.kicad_pcb
}

@test "Simple grid, spacing, mousebites" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 5mm' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t3.kicad_pcb
}


@test "Simple grid, spacing, mousebites prolonged" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t4.kicad_pcb
}

@test "Simple grid, change number of tabs" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t5.kicad_pcb
}

@test "Simple grid, rails" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t6.kicad_pcb

    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railslr; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t7.kicad_pcb
}

@test "Simple grid, frame, both cuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: both' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t8.kicad_pcb
}

@test "Simple grid, frame, vertical cuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: v' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t9.kicad_pcb
}

@test "Simple grid, frame, horizontal cuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: h' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t10.kicad_pcb
}

@test "Simple grid, frame, no cuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: none' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t11.kicad_pcb
}

@test "Simple grid, tightgrid" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 6mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts vcuts \
        --framing 'tightframe; width: 5mm; space: 3mm; ' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t12.kicad_pcb
}

@test "Simple grid, framing features" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --tooling '3hole; hoffset: 2.5mm; voffset: 2.5mm; size: 1.5mm' \
        --fiducials '3fid; hoffset: 5mm; voffset: 2.5mm; coppersize: 2mm; opening: 1mm;' \
        --text 'simple; text: yaqwsx panel; anchor: mt; voffset: 2.5mm; hjustify: center; vjustify: center;' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t13.kicad_pcb
}

@test "Simple grid, framing features with variable" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --tooling '3hole; hoffset: 2.5mm; voffset: 2.5mm; size: 1.5mm' \
        --fiducials '3fid; hoffset: 5mm; voffset: 2.5mm; coppersize: 2mm; opening: 1mm;' \
        --text 'simple; text: yaqwsx panel {date}; anchor: mt; voffset: 2.5mm; hjustify: center; vjustify: center;' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t14.kicad_pcb
}


@test "Grid with alternation" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 3mm; alternation: cols;' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: both' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t15.kicad_pcb
}

@test "Grid with backbone" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; hspace: 2mm; vspace: 9mm; hbackbone: 5mm; hbonecut: true' \
        --tabs 'fixed; width: 3mm; vcount: 2; hcount: 0' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t16.kicad_pcb
}

@test "Tabs from annotation" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 8mm; hbackbone: 3mm; vbackbone: 3mm' \
        --tabs annotation \
        --source 'tolerance: 15mm' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t17.kicad_pcb
}

@test "Copperfill" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts 'vcuts; clearance: 1.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm; copperfill: true' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t18.kicad_pcb
}

@test "Set aux origin" {
    kikit panelize \
        --post 'origin: bl;' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t19.kicad_pcb
}

@test "Set page" {
    if [ $(kikit-info drcapi) -lt 1 ]; then
        skip "KiCAD $(kikit-info kicadversion) doesn't support page size."
    fi

    kikit panelize \
        --page 'A3;' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t20.kicad_pcb
}

@test "Render dimensions" {
    kikit panelize \
        --post 'dimensions: true;' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel_t20.kicad_pcb
}


@test "Use layout plugin" {
    kikit panelize --dump preset.json \
        --layout "plugin; code: $RES/testplugin.py.MyLayout" \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts 'vcuts; clearance: 1.5mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-plugin-layout.kicad_pcb
}

@test "Use framing plugin" {
    kikit panelize --dump preset.json \
        --layout "grid" \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --framing "plugin; code: $RES/testplugin.py.MyFraming" \
        --cuts 'vcuts; clearance: 1.5mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-plugin-framing.kicad_pcb
}

@test "Use tabs plugin" {
    kikit panelize --dump preset.json \
        --layout "grid" \
        --tabs "plugin; code: $RES/testplugin.py.MyTabs" \
        --cuts 'vcuts; clearance: 1.5mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-plugin-tabs.kicad_pcb
}

@test "Use cuts plugin" {
    kikit panelize --dump preset.json \
        --layout "grid" \
        --cuts "plugin; code: $RES/testplugin.py.MyCuts" \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-plugin-cuts.kicad_pcb
}

@test "Use fiducials and tooling plugin" {
    kikit panelize --dump preset.json \
        --layout "grid" \
        --fiducials "plugin; code: $RES/testplugin.py.MyFiducials" \
        --tooling "plugin; code: $RES/testplugin.py.MyTooling" \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-plugin-fiducials.kicad_pcb
}

@test "Dumping preset" {
    kikit panelize --dump preset.json \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts 'vcuts; clearance: 1.5mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-original.kicad_pcb
    kikit panelize -p preset.json $RES/conn.kicad_pcb panel-copy.kicad_pcb

    # Remove timestamps - with determinization it is no longer needed
    # perl -pi -e 's/\((tedit|tstamp).*\)//g' panel-original.kicad_pcb
    # perl -pi -e 's/\((tedit|tstamp).*\)//g' panel-copy.kicad_pcb

    # Instead, we sort the files
    cmp -s <(sort panel-original.kicad_pcb)  <(sort panel-copy.kicad_pcb)
}

@test "Dumping preset with plugin" {
    kikit panelize --dump preset-plugin.json \
        --layout "plugin; code: $RES/testplugin.py.MyLayout" \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts 'vcuts; clearance: 1.5mm' \
        --debug 'trace: true; deterministic: true' \
        $RES/conn.kicad_pcb panel-original-plugin.kicad_pcb
    kikit panelize -p preset-plugin.json $RES/conn.kicad_pcb panel-copy-plugin.kicad_pcb

    # Remove timestamps - with determinization it is no longer needed
    # perl -pi -e 's/\((tedit|tstamp).*\)//g' panel-original-plugin.kicad_pcb
    # perl -pi -e 's/\((tedit|tstamp).*\)//g' panel-copy-plugin.kicad_pcb

    # Instead, we sort the files
    cmp -s <(sort panel-original-plugin.kicad_pcb) <(sort panel-copy-plugin.kicad_pcb)
}
