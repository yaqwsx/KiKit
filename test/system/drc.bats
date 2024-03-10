#!/usr/bin/env bats

load common

@test "Basic DRC" {
    if [ $(kikit-info drcapi) -lt 1 ]; then
        skip "KiCAD $(kikit-info kicadversion) does not support DRC API"
    fi

    run kikit drc run $RES/conn.kicad_pcb
    [ "$status" -eq 0 ]

    run kikit drc run $RES/conn-fail.kicad_pcb
    [ "$status" -eq 1 ]

    SUFFIX=""
    if [ $(kikit-info kicadversion) = "8.0"  ]; then
        SUFFIX="-v8"
    fi

    run kikit drc run $RES/conn-fail-ignored${SUFFIX}.kicad_pcb
    [ "$status" -eq 0 ]
}
