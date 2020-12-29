#!/usr/bin/env bats

load common

@test "Fab: JLCPCB without assembly" {
    kikit fab jlcpcb $RES/conn.kicad_pcb jlcpcb.noassembly
}

@test "Fab: PcbWay without assembly" {
    kikit fab pcbway $RES/conn.kicad_pcb pcbway.noassembly
}

# TBA: Assembly tests
