#!/usr/bin/env bats

load common

@test "Fab: JLCPCB without assembly" {
    kikit fab jlcpcb $RES/conn.kicad_pcb jlcpcb.noassembly
}

@test "Fab: JLCPCB with assembly - v6" {
    if [ $(kikit-info kicadversion) = "5.0" ]; then
        skip "This test is not implemented for v5"
    fi

    kikit fab jlcpcb --assembly --debug \
        --no-drc \
        --schematic $RES/assembly_project_1_KiCAD6/assembly_project_1_KiCAD6.kicad_sch \
        $RES/assembly_project_1_KiCAD6/assembly_project_1_KiCAD6.kicad_pcb jlcpcb.assembly.v6

    sort jlcpcb.assembly.v6/bom.csv > bom.test.csv
    sort jlcpcb.assembly.v6/pos.csv > pos.test.csv
    sort $RES/assembly_project_1_KiCAD6/bom.csv > bom.truth.csv
    sort $RES/assembly_project_1_KiCAD6/pos.csv > pos.truth.csv

    cmp -s bom.test.csv bom.truth.csv
    cmp -s pos.test.csv pos.truth.csv
}

@test "Fab: JLCPCB with assembly - v7/v8" {
    if [ $(kikit-info kicadversion) != "7.0" && $(kikit-info kicadversion) != "8.0"  ]; then
        skip "This test is not supported on older versions"
    fi

    kikit fab jlcpcb --assembly --debug \
        --no-drc \
        --schematic $RES/assembly_project_1_KiCAD7/assembly_project_1_KiCAD7.kicad_sch \
        $RES/assembly_project_1_KiCAD7/assembly_project_1_KiCAD7.kicad_pcb jlcpcb.assembly.v7

    sort jlcpcb.assembly.v7/bom.csv > bom.test.csv
    sort jlcpcb.assembly.v7/pos.csv > pos.test.csv
    sort $RES/assembly_project_1_KiCAD7/bom.csv > bom.truth.csv
    sort $RES/assembly_project_1_KiCAD7/pos.csv > pos.truth.csv

    cmp -s bom.test.csv bom.truth.csv
    cmp -s pos.test.csv pos.truth.csv
}

@test "Fab: PcbWay without assembly" {
    kikit fab pcbway $RES/conn.kicad_pcb pcbway.noassembly
}

@test "Fab: PcbWay with assembly" {
    kikit fab pcbway --assembly --debug \
        --no-drc \
        --schematic $RES/assembly_project_1_KiCAD6/assembly_project_1_KiCAD6.kicad_sch \
        $RES/assembly_project_1_KiCAD6/assembly_project_1_KiCAD6.kicad_pcb \
        pcbway.assembly
}

@test "Fab: OSHPark" {
    kikit fab oshpark $RES/conn.kicad_pcb oshpark.noassembly
}

@test "Fab: OpenPNP - v8" {
    if [ $(kikit-info kicadversion) != "8.0"  ]; then
        skip "This test is not supported on older versions"
    fi

    kikit fab openpnp --debug \
    --no-drc \
    $RES/conn-fail-ignored-v8.kicad_pcb \
    openpnp
}
