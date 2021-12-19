#!/usr/bin/env bats

load common

@test "Fab: JLCPCB without assembly" {
    kikit fab jlcpcb $RES/conn.kicad_pcb jlcpcb.noassembly
}

@test "Fab: JLCPCB with assembly" {
    if [ $(kikit-info kicadversion) = "5.0" ]; then
        skip "This test is not implemented for v5"
    fi

    kikit fab jlcpcb --assembly \
        --no-drc \
        --schematic $RES/assembly_project1/assembly_project1.kicad_sch \
        $RES/assembly_project1/assembly_project1.kicad_pcb jlcpcb.assembly

    sort jlcpcb.assembly/bom.csv > bom.test.csv
    sort jlcpcb.assembly/pos.csv > pos.test.csv
    sort $RES/assembly_project1/bom.csv > bom.truth.csv
    sort $RES/assembly_project1/pos.csv > pos.truth.csv

    cmp -s bom.test.csv bom.truth.csv
    cmp -s pos.test.csv pos.truth.csv
}

@test "Fab: PcbWay without assembly" {
    kikit fab pcbway $RES/conn.kicad_pcb pcbway.noassembly
}

@test "Fab: OSHPark" {
    kikit fab oshpark $RES/conn.kicad_pcb oshpark.noassembly
}