#!/usr/bin/env bats

load common

@test "Steel stencils" {
    kikit stencil create  --jigsize 60 60 $RES/conn.kicad_pcb steelStencil
}

@test "Steel stencils with cutout" {
    kikit stencil create  --jigsize 60 60 --cutout J4 $RES/conn.kicad_pcb steelStencil
}

@test "Printed stencils" {
    kikit stencil createprinted \
        --pcbthickness 1.5 --thickness 0.15 --framewidth 2 \
        $RES/conn.kicad_pcb steelStencil
}
