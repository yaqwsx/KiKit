#!/usr/bin/env bats

load common

@test "DXF export" {
    kikit export dxf $RES/conn-fail.kicad_pcb dxfExport
}

@test "Gerber export" {
    kikit export gerber $RES/conn-fail.kicad_pcb gerberExport
}

