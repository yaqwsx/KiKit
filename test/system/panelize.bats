#!/usr/bin/env bats

load common

@test "Extract board" {
    kikit separate --source 'rectangle; tlx: 89mm; tly: 89mm; brx: 111mm; bry: 111mm' \
        $RES/multiboard.kicad_pcb board_a.kicad_pcb

    kikit separate --source 'annotation; ref: B1' \
        $RES/multiboard.kicad_pcb board_a.kicad_pcb
}

@test "Simple grid, no space, vcuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2;' \
        --tabs full \
        --cuts vcuts \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Simple grid, spacing, vcuts" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts vcuts \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Simple grid, spacing, mousebites" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 5mm' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}


@test "Simple grid, spacing, mousebites prolonged" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Simple grid, change number of tabs" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Simple grid, rails" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb

    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railslr; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Simple grid, frame" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: true' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Simple grid, tightgrid" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 6mm' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts vcuts \
        --framing 'tightframe; width: 5mm; space: 3mm; ' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
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
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Grid with alternation" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 3mm; alternation: cols;' \
        --tabs 'fixed; width: 3mm; vcount: 2' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'frame; width: 5mm; space: 3mm; cuts: true' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Grid with backbone" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; hspace: 2mm; vspace: 9mm; hbackbone: 5mm; hbonecut: true' \
        --tabs 'fixed; width: 3mm; vcount: 2; hcount: 0' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Tabs from annotation" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 8mm; hbackbone: 3mm; vbackbone: 3mm' \
        --tabs annotation \
        --source 'tolerance: 15mm' \
        --cuts 'mousebites; drill: 0.5mm; spacing: 1mm; offset: 0.2mm; prolong: 0.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Copperfill" {
    kikit panelize \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts 'vcuts; clearance: 1.5mm' \
        --framing 'railstb; width: 5mm; space: 3mm;' \
        --post 'millradius: 1mm; copperfill: true' \
        $RES/conn.kicad_pcb panel.kicad_pcb
}

@test "Dumping preset" {
    kikit panelize --dump preset.json \
        --layout 'grid; rows: 2; cols: 2; space: 2mm' \
        --tabs 'fixed; hwidth: 10mm; vwidth: 15mm' \
        --cuts 'vcuts; clearance: 1.5mm' \
        $RES/conn.kicad_pcb panel-original.kicad_pcb
    kikit panelize -p preset.json $RES/conn.kicad_pcb panel-copy.kicad_pcb

    # Remove timestamps
    perl -pi -e 's/\((tedit|tstamp).*\)//g' panel-original.kicad_pcb
    perl -pi -e 's/\((tedit|tstamp).*\)//g' panel-copy.kicad_pcb

    cmp -s panel-original.kicad_pcb panel-copy.kicad_pcb
}